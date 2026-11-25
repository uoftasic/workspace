# Request server for the klayout-magic-pcells backend.
#
# The backend starts "magic -dnull -noconsole -rcfile <pdk>.magicrc" with its
# stdin, stdout and stderr on pipes and sends "source kmp_server.tcl".  After
# that, every line it sends is one complete Tcl command:
#
#     kmp::req <id> <hex>
#
# where <hex> is the hex encoding of a UTF-8 JSON object such as
#     {"op":"generate","device":"sky130_fd_pr__nfet_01v8",
#      "params":{"w":"1.5","l":"0.5"},"form":"cell","out":"/path/x.gds"}
# The form is "cell" (a drawn device: its cell alone), "wrapper" (a fixed
# device: the cell holding the arrayed vendor cell) or "box" (a box-paint
# generator: the box set to w x h um with its lower-left corner at the
# origin, the generator called with no arguments, as Magic's menu calls it).
# No parameter value is ever part of the Tcl source of a request, so a value
# with an unbalanced brace cannot leave the session waiting for more input.
#
# Each reply is a block of lines on stdout:
#     KMP_BEGIN <id>
#     KMP_KV <id> <key> <hex of value>        (rc first, then the other keys)
#     KMP_PARAM <id> <hex of name> <hex of value>   (checked dict, in order)
#     KMP_END <id>
# Any other line on stdout is Magic talking and is ignored by the client.

source [file join [file dirname [info script]] kmp_common.tcl]

namespace eval ::kmp {
    variable protocol 1
    variable base_cells {}
    variable vendor_cells {}
    variable top kmp_top
    variable box_seq 0
}

fconfigure stdout -buffering line
catch {crashbackups stop}
package require json

load $::kmp::top -silent
set ::kmp::base_cells [cellname list allcells]
::kmp::record_state

proc ::kmp::emit {id kv params} {
    ::kmp::real_puts "KMP_BEGIN $id"
    if {[dict exists $kv rc]} {
        ::kmp::real_puts "KMP_KV $id rc [::kmp::hex [dict get $kv rc]]"
    }
    dict for {k v} $kv {
        if {$k eq "rc"} continue
        ::kmp::real_puts "KMP_KV $id $k [::kmp::hex $v]"
    }
    dict for {k v} $params {
        ::kmp::real_puts "KMP_PARAM $id [::kmp::hex $k] [::kmp::hex $v]"
    }
    ::kmp::real_puts "KMP_END $id"
    flush stdout
}

proc ::kmp::require_device {dev} {
    set ns $::kmp::ns
    if {$ns eq ""} { error "unknown device \"$dev\": the rcfile loaded no PDK (PDKNAMESPACE is not set)" }
    if {[info commands ::${ns}::${dev}_draw] eq "" ||
        [info commands ::${ns}::${dev}_defaults] eq ""} {
        error "unknown device \"$dev\""
    }
}

proc ::kmp::require_boxpaint {name} {
    if {![::kmp::is_boxpaint $name]} {
        error "unknown box-paint generator \"$name\""
    }
}

# The PDKs' generator code evaluates some parameter values with an unbraced
# expr (for example "expr abs($viagb)" in sky130A.tcl), which substitutes
# [commands] and $variables inside the value.  The Python side only sends
# numbers and names from the dialog's choices; this refuses any value that
# could substitute, whoever sent it.
proc ::kmp::require_safe_params {params} {
    dict for {k v} $params {
        if {[regexp {[][$\\]} $v]} {
            error "parameter $k: the value contains \[, \], \$ or a backslash, which the PDK's generator code would substitute; refused"
        }
    }
}

# A box size, interpolated into "box values ...um": a decimal number with an
# optional minus sign, or inf or nan, as the Python side writes a float.
# Magic's own box command takes all of them: it puts a negative size left
# of or below the origin and paints there, and it reads inf, nan and sizes
# beyond its integer range as -2147483648 internal units, below every
# generator's minimum.
proc ::kmp::require_size {k v} {
    if {![regexp {^-?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$} $v] &&
        ![regexp {^-?(inf|nan)$} $v]} {
        error "box size $k=\"$v\" is not a decimal number, inf or nan; refused"
    }
}

# Every cell below a cell, at any depth.
proc ::kmp::descendants {c} {
    set out {}
    set todo [list $c]
    while {[llength $todo]} {
        set todo [lassign $todo x]
        set kids {}
        catch {set kids [cellname list children $x]}
        foreach k $kids {
            if {[lsearch -exact $out $k] < 0} {
                lappend out $k
                lappend todo $k
            }
        }
    }
    return $out
}

# Cells that a request left behind, other than the cells that existed at start
# and the cells kept on purpose: the vendor cells that fixed devices load from
# libs.ref, and cells that a generator places inside its device and reuses
# (sg13g2::npn13g2_draw creates npn13g2_base once).  Kept cells stay loaded
# and are reused, as in one session of Magic.
proc ::kmp::leftover_cells {} {
    set out {}
    foreach c [cellname list allcells] {
        if {[lsearch -exact $::kmp::base_cells $c] >= 0} continue
        if {[dict exists $::kmp::vendor_cells $c]} continue
        lappend out $c
    }
    return $out
}

proc ::kmp::op_ping {r} {
    return [dict create kv [dict create protocol $::kmp::protocol] params {}]
}

# Where Magic finds a cell's .mag (the first match on its search path, as
# "getcell" resolves it) and the vendor GDS file that .mag names.  Fixed
# devices copy their geometry from that file, so the backend hashes both.
proc ::kmp::resolve_cell {c} {
    set mag ""
    foreach dir [path search] {
        set d $dir
        catch {set d [subst -nocommands -nobackslashes $dir]}
        set f [file join $d $c.mag]
        if {[file isfile $f]} { set mag [file normalize $f]; break }
    }
    set gds ""
    if {$mag ne ""} {
        set fh [open $mag r]
        set text [read $fh]
        close $fh
        if {[regexp {string GDS_FILE (\S+)} $text -> gds]} {
            set map {}
            if {[info exists ::PDKPATH]} { lappend map {$PDKPATH} $::PDKPATH {${PDKPATH}} $::PDKPATH }
            if {[info exists ::env(PDK_ROOT)]} { lappend map {$PDK_ROOT} $::env(PDK_ROOT) {${PDK_ROOT}} $::env(PDK_ROOT) }
            set gds [string map $map $gds]
            if {[file pathtype $gds] eq "relative"} { set gds [file join [file dirname $mag] $gds] }
        }
    }
    return [list $mag $gds]
}

proc ::kmp::op_versions {r} {
    set kv [::kmp::version_info]
    dict set kv protocol $::kmp::protocol
    if {[dict exists $r vendor_cells]} {
        set lines {}
        foreach c [dict get $r vendor_cells] {
            lassign [::kmp::resolve_cell $c] mag gds
            lappend lines "$c\t$mag\t$gds"
        }
        dict set kv vendor [join $lines "\n"]
    }
    if {[dict exists $r procs_out]} {
        dict set kv procs_lines [::kmp::dump_procs [dict get $r procs_out]]
    }
    if {[dict exists $r defaults_out]} {
        dict set kv devices [::kmp::dump_defaults [dict get $r defaults_out]]
    }
    return [dict create kv $kv params {}]
}

# _check once on the merged defaults; nothing is drawn.  A device without a
# _check proc (sg13g2 rm6, rm7), or whose _check raises (gf180mcu npolyf_s at
# w 0), gets what gencell_create would draw with: the merged values,
# unchecked, with the reason in the log.
proc ::kmp::op_check {r} {
    set dev [dict get $r device]
    set params [dict get $r params]
    ::kmp::require_safe_params $params
    if {[dict exists $r form] && [dict get $r form] eq "box"} {
        return [::kmp::gen_box $dev $params ""]
    }
    ::kmp::require_device $dev
    set ns $::kmp::ns
    set merged [magic::gencell_defaults $dev $ns $params]
    if {[info commands ::${ns}::${dev}_check] eq ""} {
        append ::kmp::log "$dev has no _check proc; Magic draws the values unchecked\n"
        return [dict create kv [dict create check none] params $merged]
    }
    if {[catch {set checked [::${ns}::${dev}_check $merged]} err]} {
        if {$::kmp::abort ne ""} { error $::kmp::abort }
        append ::kmp::log "_check failed: $err; Magic draws the values unchecked\n"
        return [dict create kv [dict create check failed check_error $err] params $merged]
    }
    return [dict create kv {} params $checked]
}

# --- Magic's parameter dialog, without Tk ------------------------------------
#
# Magic's dialog (magic::gencell_dialog in toolkit.tcl) keeps one value per
# widget, in the variable ::magic::<name>_val.  When the user presses Return
# in an entry (or leaves it), clicks a checkbox or picks an entry of a
# selectlist, Tk runs that widget's binding: one magic::update_dialog call
# for each callback that the device's _dialog registered on the widget with
# magic::add_dependency (sky130::res_recalc on val, l, w, nx; diode_recalc;
# cap_recalc), in the order they were registered, then two calls with no
# callback, which magic::add_check_callbacks adds, one for the widget's
# label and one for the widget itself.  add_dependency binds only widgets
# that exist when it runs.  update_dialog merges the device's defaults with
# the form, runs _check on that (an error is printed and the values stay),
# runs the callback on the result, and gencell_setparams writes every
# widget's value back into the form.  An error after that ends the binding:
# Tk stops a binding script at its first error.
#
# These procs do the same with the form in a dict, because the server has no
# Tk; magic::update_dialog itself reads the form through Tk's "grid slaves".
# The parity harness drives the real dialog under Xvfb and compares.

# The update_dialog callbacks of one widget's binding, in order ("" is the
# call with no callback).  order: the widget names in the order _dialog
# creates them; deps: {callback params after} per add_dependency call, after
# being how many widgets existed when it ran.
proc ::kmp::dialog_chain {pname order deps} {
    set pos [lsearch -exact $order $pname]
    set chain {}
    foreach d $deps {
        set cb [dict get $d callback]
        if {$pos >= 0 && $pos < [dict get $d after] && [lsearch -exact [dict get $d params] $pname] >= 0} {
            lappend chain $cb
        }
    }
    lappend chain "" ""
    return $chain
}

# One magic::update_dialog call on the form (a dict of every widget value).
proc ::kmp::dialog_pass {dev ns callback pname form} {
    set parameters [dict merge [${ns}::${dev}_defaults] $form]
    if {[catch {set parameters [${ns}::${dev}_check $parameters]} checkerr]} {
        puts stderr $checkerr
    }
    if {$callback ne ""} {
        set parameters [$callback $pname $parameters]
    }
    set out {}
    dict for {k v} $form {
        dict set out $k [dict get $parameters $k]
    }
    return $out
}

# A form value that is not a plain number (Magic's SPICE notation, such as
# 1.028k, 202.5m or 1.218u) as magic::spice2float reads it, or "".
proc ::kmp::form_number {v} {
    if {[string is double -strict $v]} { return $v }
    set saved $::kmp::log
    set n ""
    if {[catch {set n [magic::spice2float $v ""]}] || ![string is double -strict $n]} {
        set n ""
    }
    set ::kmp::log $saved
    return $n
}

# op dialog: start from the form r.form ({name text} for every widget the
# client keeps; Magic's own defaults fill in the rest), then for each
# {name text} in r.edits set that widget and run its binding.  The reply's
# params are the form afterwards, in r.form's order.  The kv values are
# JSON: numbers, {name: magic::spice2float of the value} for each value that
# is not a plain number; steps, [[name, {form}], ...] after each edit; and,
# with r.want_chains, chains, {name: [callback, ...]} for every widget in
# r.order.
proc ::kmp::op_dialog {r} {
    set dev [dict get $r device]
    ::kmp::require_device $dev
    set ns $::kmp::ns
    set form [dict get $r form]
    set order [dict get $r order]
    set deps [dict get $r deps]
    ::kmp::require_safe_params $form
    set steps {}
    foreach e [dict get $r edits] {
        lassign $e pname text
        ::kmp::require_safe_params [dict create $pname $text]
        if {![dict exists $form $pname]} { error "the dialog of $dev has no widget $pname" }
        dict set form $pname $text
        foreach cb [::kmp::dialog_chain $pname $order $deps] {
            if {[catch {set form [::kmp::dialog_pass $dev $ns $cb $pname $form]} err]} {
                if {$::kmp::abort ne ""} { error $::kmp::abort }
                append ::kmp::log "binding error: $err\n"
                break
            }
        }
        lappend steps "\[[::kmp::jstr $pname],[::kmp::jobj $form]\]"
    }
    set numbers {}
    dict for {k v} $form {
        set n [::kmp::form_number $v]
        if {$n ne $v && $n ne ""} { dict set numbers $k $n }
    }
    set kv [dict create numbers [::kmp::jobj $numbers] steps "\[[join $steps ,]\]"]
    if {[dict exists $r want_apply_name] && [dict get $r want_apply_name]} {
        # What the dialog's Apply button (magic::gencell_change) compares
        # with the instance's cell name: the device name and Magic's hash
        # of the form after one more _check. When they are equal, Apply
        # leaves the instance as it is.
        dict set kv apply_name [::kmp::apply_name $dev $ns $form]
    }
    if {[dict exists $r want_chains] && [dict get $r want_chains]} {
        set items {}
        foreach p $order {
            lappend items "[::kmp::jstr $p]:[::kmp::jlist [::kmp::dialog_chain $p $order $deps]]"
        }
        dict set kv chains "\{[join $items ,]\}"
    }
    return [dict create kv $kv params $form]
}

# --- Magic's Apply and the "Edit device" dialog -------------------------------
#
# After Create, Magic's dialog reopens as "Edit device" on the new instance
# (the Create button runs magic::gencell_dialog $inst ...), and later edits
# start from what that dialog shows; its Apply button runs
# magic::gencell_change. These procs compute both without Tk.

# The parameters gencell_change hands gencell_create: the form merged with
# the defaults and checked once ("" for a fixed device, which it draws with
# them directly; gencell_create's own _check then gives the same).
proc ::kmp::apply_params {dev ns form} {
    set parameters [magic::gencell_defaults $dev $ns $form]
    if {[catch {set parameters [${ns}::${dev}_check $parameters]} checkerr]} {
        if {$::kmp::abort ne ""} { error $::kmp::abort }
        puts stderr $checkerr
    }
    return $parameters
}

proc ::kmp::apply_name {dev ns form} {
    set p [::kmp::apply_params $dev $ns $form]
    if {[dict exists $p gencell]} { set p [dict remove $p gencell] }
    return ${dev}_[magic::get_gencell_hash $p]
}

# What magic::gencell_dialog shows when it opens on instance $inst: the
# parameters it takes from the instance's cell (the "parameters" property,
# else the device's defaults, and for a fixed device the array's counts and
# pitch), put through the device's _dialog proc with the widget procs
# stubbed, as tools/build_manifest.py reads the dialogs. Returns
# {type <gencell> form {name text ...} note <why it fell back, or "">}; with
# a note, the dialog doesn't reopen in Magic either and keeps what Create's
# gencell_setparams wrote into it.
set ::kmp::dialog_stubs {add_entry add_checkbox add_message add_selectlist add_selectindex add_dependency}
proc ::kmp::stub_widget {pname parameters missing} {
    if {[dict exists $parameters $pname]} {
        lappend ::kmp::stub_widgets [list $pname [dict get $parameters $pname]]
    } else {
        lappend ::kmp::stub_widgets [list $pname $missing]
    }
}
proc ::kmp::reopened {inst ns} {
    set gname [instance list celldef $inst]
    set gtype ""
    catch {set gtype [cellname list property $gname gencell]}
    set parameters ""
    catch {set parameters [cellname list property $gname parameters]}
    if {$gtype eq ""} { return [dict create type "" form {} note "the cell has no gencell property"] }
    if {$parameters eq ""} {
        if {[catch {set parameters [${ns}::${gtype}_defaults]} err]} {
            return [dict create type $gtype form {} note $err]
        }
    }
    if {[dict exists $parameters nocell]} {
        select cell $inst
        set arcount [array -list count]
        set arpitch [array -list pitch]
        dict set parameters nx [expr {[lindex $arcount 1] - [lindex $arcount 0] + 1}]
        dict set parameters ny [expr {[lindex $arcount 3] - [lindex $arcount 2] + 1}]
        dict set parameters pitchx [lindex $arpitch 0]
        dict set parameters pitchy [lindex $arpitch 1]
        select clear
    }
    if {[info commands ::${ns}::${gtype}_dialog] eq ""} {
        return [dict create type $gtype form {} note "no ${gtype}_dialog proc"]
    }
    set ::kmp::stub_widgets {}
    foreach p $::kmp::dialog_stubs {
        if {[info commands ::magic::$p] ne ""} { rename ::magic::$p ::kmp::saved_$p }
    }
    # The value each widget opens with, as text (not through expr, which
    # would turn "0.690" into 0.69).
    proc ::magic::add_entry {pname ptext parameters} {
        ::kmp::stub_widget $pname $parameters ""
    }
    proc ::magic::add_checkbox {pname ptext parameters} {
        ::kmp::stub_widget $pname $parameters ""
    }
    proc ::magic::add_selectlist {pname ptext all_values parameters {itext ""}} {
        ::kmp::stub_widget $pname $parameters $itext
    }
    proc ::magic::add_selectindex {pname ptext all_values parameters {ival 0}} {
        ::kmp::stub_widget $pname $parameters $ival
    }
    proc ::magic::add_message {pname ptext parameters {color blue}} {}
    proc ::magic::add_dependency {callback gencell_type library args} {}
    try {
        set rc [catch {${ns}::${gtype}_dialog $parameters} err]
    } finally {
        foreach p $::kmp::dialog_stubs {
            catch {rename ::magic::$p ""}
            if {[info commands ::kmp::saved_$p] ne ""} { rename ::kmp::saved_$p ::magic::$p }
        }
    }
    if {$rc} {
        if {$::kmp::abort ne ""} { error $::kmp::abort }
        return [dict create type $gtype form {} note $err]
    }
    set form {}
    foreach w $::kmp::stub_widgets {
        lassign $w pname value
        if {$pname ne "gencell"} { dict set form $pname $value }
    }
    return [dict create type $gtype form $form note ""]
}

# Internal units as um, written without float noise: 1.005, not
# 1.0050000000000001.
proc ::kmp::um {n} {
    set v [string trimright [format %.6f [magic::i2u $n]] 0]
    if {[string index $v end] eq "."} { append v 0 }
    return $v
}

# A box-paint generator: a fresh cell, "box values 0um 0um <w>um <h>um" (the
# box's lower-left corner at the origin, or, for a negative size, the box
# left of or below it, as Magic puts it), the generator called with no
# arguments (as Magic's menu calls it), and, when out is not empty, the cell
# written to out.  The reply's params hold the size of the box Magic used,
# in um, after it rounded the size to its internal grid; kv box holds the
# box in internal units.
proc ::kmp::gen_box {name params out} {
    ::kmp::require_boxpaint $name
    foreach k {w h} {
        if {![dict exists $params $k]} { error "box-paint generator $name needs $k" }
        ::kmp::require_size $k [dict get $params $k]
    }
    set w [dict get $params w]
    set h [dict get $params h]
    set cell kmp_box_[incr ::kmp::box_seq]
    set bv {}
    set rc [catch {
        load $cell -silent
        box values 0um 0um ${w}um ${h}um
        set bv [box values]
        ::${::kmp::ns}::${name}_draw
        if {$out ne ""} {
            file delete -force $out
            gds write $out
            if {![file exists $out]} { error "gds write produced no file" }
        }
    } err opts]
    catch {load $::kmp::top}
    catch {cellname delete $cell -noprompt}
    catch {select clear}
    if {$rc} { return -options $opts $err }
    lassign $bv x1 y1 x2 y2
    set drawn [dict create w [::kmp::um [expr {$x2 - $x1}]] h [::kmp::um [expr {$y2 - $y1}]]]
    return [dict create kv [dict create cell "" box $bv] params $drawn]
}

proc ::kmp::op_generate {r} {
    set dev [dict get $r device]
    set params [dict get $r params]
    ::kmp::require_safe_params $params
    set form [dict get $r form]
    set out [dict get $r out]
    if {$form eq "box"} {
        return [::kmp::gen_box $dev $params $out]
    }
    ::kmp::require_device $dev
    if {$form ni {cell wrapper}} { error "unknown form \"$form\"" }
    set ns $::kmp::ns

    # apply: the cell that the dialog's Apply button makes on an existing
    # instance (magic::gencell_change): the form checked once, then
    # gencell_create with the result, which checks it again. A fixed device
    # gets the form checked once either way.
    set apply [expr {[dict exists $r apply] && [dict get $r apply] eq "1"}]
    set ::kmp::checked {}
    set inst ""
    set g ""
    set reo {}
    set rc [catch {
        load $::kmp::top
        box 0 0 0 0
        # Always the merged defaults: an empty dict sends gencell_create down
        # its dialog branch.
        set merged [magic::gencell_defaults $dev $ns $params]
        if {$apply && ![dict exists $merged nocell]} {
            set merged [::kmp::apply_params $dev $ns $params]
        }
        set inst [magic::gencell_create $dev $ns $merged]
        if {$inst eq ""} {
            error "gencell_create returned no instance (no box, or an exact copy of an existing cell)"
        }
        # What reopening the dialog prints (a fixed device's vendor cell has
        # no parameters property) is not Create's: keep it out of the log.
        set saved_log $::kmp::log
        if {[catch {set reo [::kmp::reopened $inst $ns]} rerr]} {
            if {$::kmp::abort ne ""} { error $::kmp::abort }
            set reo [dict create type "" form {} note $rerr]
        }
        set ::kmp::log $saved_log
        set g [instance list celldef $inst]
        if {$form eq "cell"} {
            load $g
        } else {
            load $::kmp::top
        }
        file delete -force $out
        gds write $out
        if {![file exists $out]} { error "gds write produced no file" }
    } err opts]

    # Clean up whatever exists, even after an error, so that the next request
    # for the same parameters starts from an empty name.  Cells below the
    # device are kept: a fixed device's vendor cell and its children, and
    # cells a generator places in its device and reuses (npn13g2_base).
    set kept {}
    if {$g ne ""} {
        foreach k [::kmp::descendants $g] {
            if {![dict exists $::kmp::vendor_cells $k]} { lappend kept $k }
            dict set ::kmp::vendor_cells $k 1
        }
    }
    catch {load $::kmp::top}
    if {$inst ne ""} {
        catch {select cell $inst; delete}
    }
    if {$g ne ""} {
        if {$form eq "cell"} {
            catch {cellname delete $g -noprompt}
        } else {
            dict set ::kmp::vendor_cells $g 1
        }
    }
    catch {select clear}
    if {$rc} {
        # A request that failed part way may have made cells (an IHP fixed
        # device whose layout script is missing leaves its empty cell):
        # delete them, so that the same request fails the same way again
        # instead of placing what the failure left.
        foreach c [::kmp::leftover_cells] {
            catch {cellname delete $c -noprompt}
        }
        return -options $opts $err
    }
    set left [::kmp::leftover_cells]
    set kv [dict create cell $g]
    if {[dict size $reo]} {
        # magic::spice2float of each value that is not a plain number, for
        # the reopened form and (for a dialog that doesn't reopen) for the
        # checked dict.
        foreach {key d} [list opened_numbers [dict get $reo form] checked_numbers $::kmp::checked] {
            set numbers {}
            dict for {k v} $d {
                set n [::kmp::form_number $v]
                if {$n ne $v && $n ne ""} { dict set numbers $k $n }
            }
            dict set kv $key [::kmp::jobj $numbers]
        }
        dict set kv opened [::kmp::jobj [dict get $reo form]]
        dict set kv opened_type [dict get $reo type]
        dict set kv opened_note [dict get $reo note]
    }
    if {[llength $kept]} {
        dict set kv kept [join $kept " "]
    }
    if {[llength $left]} {
        dict set kv restart 1
        dict set kv leftover [join $left " "]
    }
    return [dict create kv $kv params $::kmp::checked]
}

proc ::kmp::req {id hex} {
    ::kmp::begin_request
    set res {}
    set t [time {
        set rc [catch {
            set r [json::json2dict [::kmp::unhex $hex]]
            set op [dict get $r op]
            if {[info commands ::kmp::op_$op] eq ""} { error "unknown op \"$op\"" }
            set res [::kmp::op_$op $r]
        } err]
    }]
    # A stopped request is an error even if something on the way swallowed it.
    if {$::kmp::abort ne ""} {
        set rc 1
        set err $::kmp::abort
    }
    set ::kmp::abort ""
    set restored [::kmp::restore_state]
    if {$rc} {
        set kv [dict create rc 1 error $err]
        set params {}
    } else {
        set kv [dict merge [dict create rc 0] [dict get $res kv]]
        set params [dict get $res params]
    }
    dict set kv log $::kmp::log
    dict set kv us [lindex $t 0]
    if {$restored ne ""} { dict set kv restored $restored }
    ::kmp::emit $id $kv $params
    ::kmp::begin_request
}

::kmp::real_puts "KMP_READY $::kmp::protocol"
flush stdout
