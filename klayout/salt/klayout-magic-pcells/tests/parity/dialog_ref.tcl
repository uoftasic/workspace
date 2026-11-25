# Path D of the parity sweep: Magic's own parameter dialog, under Xvfb.
#
#   KMP_SWEEP=sweep.json KMP_OUT=<dir> [KMP_START=<n>] \
#     xvfb-run -a magic -d XR -noconsole -rcfile <pdk>.magicrc dialog_ref.tcl
#
# KMP_START skips the first n device points and appends to index.jsonl
# (run_sweep.py restarts Magic after a point that crashed it or hung).
# KMP_LIMIT ends the run after that many points; run_sweep.py then starts a
# fresh Magic at the next one. Under the GUI one Magic gets slower point by
# point (on sky130A's first device points, 50 took 7.7 s and 150 took 57 s,
# Magic's start included), so one Magic doesn't run the whole sweep.
#
# Uses none of the plugin's Tcl or Python. For every device point (box-paint
# points have no dialog and are skipped) it does what a user of Magic's
# "Devices" menu does:
#   1. opens the device's "New device" dialog: magic::gencell <ns>::<dev>,
#      the command behind the menu entry (Tk widgets, real bindings);
#   2. types each value of the point's request into its widget, in the
#      dialog's own row order: an entry gets the text and its <Return>
#      binding runs, a checkbox that shows the other state is clicked
#      (invoke), a selectlist gets the menu entry with that label invoked.
#      The request holds only the values that differ from the defaults the
#      dialog opens with, so these are the edits a user makes;
#   3. reads the form back (magic::gencell_getparams): the corrected values
#      the dialog shows;
#   4. presses Create (.params.buttons.apply), reads the dialog that Create
#      reopens on the new instance ("Edit device"), and writes what it made:
#      the device cell for a drawn device, the dref_<id> cell holding the
#      arrayed vendor cell for a fixed (nocell) device.
# An edit point (gen_sweep.py) types its "first" values in step 2, and
# after step 4 types its own values into the Edit device dialog, each only
# when the field shows another value (a number field compared as the
# number magic::spice2float reads, any other field as text), presses Apply
# (magic::gencell_change), reads the dialog as it reopens on the instance
# Apply left, and writes that instance's cell instead. Where the dialog
# didn't reopen on the instance after Create, it is still "New device":
# the old instance is deleted and Create pressed again.
# A Tcl error in a binding ends that binding script, as Tk does (the rest of
# the "; "-separated commands don't run); it is recorded and the next edit
# goes on. For the first point of each device it also records the bindings
# themselves: for every entry, checkbox and selectlist, the update_dialog
# calls its <Return> binding, -command or menu entries run.
# After every point the session state is put back (layer locks, units,
# Magic's box stack), as path A does. One JSON line per point goes to
# <dir>/index.jsonl.

package require json
catch {crashbackups stop}
# Magic's interactive DRC would check every cell Create makes, in the
# background; it changes nothing that is written.
catch {drc off}

set ::dref_log ""
set ::dref_checked {}
set ::dref_counts {}
set ::dref_abort ""
rename ::puts ::dref_real_puts
proc ::puts {args} {
    set a $args
    set nonl 0
    if {[lindex $a 0] eq "-nonewline"} { set nonl 1; set a [lrange $a 1 end] }
    if {[llength $a] == 2 && [lindex $a 0] eq "stderr"} {
        if {$::dref_abort ne ""} { error $::dref_abort }
        set msg [lindex $a 1]
        dict incr ::dref_counts $msg
        if {[dict get $::dref_counts $msg] > 10000} {
            set ::dref_abort "endless loop: Magic printed \"[string trim $msg]\" 10000 times"
            error $::dref_abort
        }
        if {[dict get $::dref_counts $msg] <= 20} {
            append ::dref_log $msg
            if {!$nonl} { append ::dref_log "\n" }
        }
        return
    }
    uplevel 1 [list ::dref_real_puts {*}$args]
}
# Tk reports an error in a binding through bgerror; record it instead of
# opening a message box.
proc ::bgerror {msg} { append ::dref_log "binding error: $msg\n" }
# The checked dict, as gencell_create hands it to gencell_setparams.
proc ::dref_on_setparams {cmd op} { set ::dref_checked [lindex $cmd 1] }
trace add execution ::magic::gencell_setparams enter ::dref_on_setparams

proc ::dref_js {s} {
    set s [string map [list \\ \\\\ \" \\\" \n \\n \r \\r \t \\t] $s]
    regsub -all {[\x00-\x1f]} $s {} s
    return "\"$s\""
}
proc ::dref_jobj {d} {
    set items {}
    dict for {k v} $d { lappend items "[::dref_js $k]:[::dref_js $v]" }
    return "\{[join $items ,]\}"
}
proc ::dref_jlist {l} {
    set items {}
    foreach v $l { lappend items [::dref_js $v] }
    return "\[[join $items ,]\]"
}

# The dialog's widgets in row order: {pname kind path}.
proc ::dref_widgets {} {
    set ws {}
    foreach w [grid slaves .params.body.area.edits] {
        if {[regexp {^\.params\.body\.area\.edits\.(.*)_(ent|chk|sel)$} $w -> p k]} {
            lappend ws [list [dict get [grid info $w] -row] $p $k $w]
        }
    }
    set out {}
    foreach x [lsort -integer -index 0 $ws] { lappend out [lrange $x 1 end] }
    return $out
}

# The callbacks of the update_dialog calls in a binding script, in order
# ("" for the check-only call).
proc ::dref_chain {script} {
    set out {}
    foreach cmd [split $script ";"] {
        set cmd [string trim $cmd]
        if {[llength $cmd] >= 5 && [lindex $cmd 0] eq "magic::update_dialog"} {
            lappend out [lindex $cmd 1]
        }
    }
    return $out
}

proc ::dref_bindings {} {
    set items {}
    foreach x [::dref_widgets] {
        lassign $x p k w
        switch $k {
            ent { set s [bind $w <Return>]
                  if {[bind $w <FocusOut>] ne $s} { set s "RETURN AND FOCUSOUT DIFFER: $s" } }
            chk { set s [$w cget -command] }
            sel { set s [$w.menu entrycget 0 -command] }
        }
        lappend items "[::dref_js $p]:\{\"kind\":[::dref_js $k],\"chain\":[::dref_jlist [::dref_chain $s]]\}"
    }
    return "\{[join $items ,]\}"
}

# Type one value into the dialog the way a user does.
proc ::dref_type {p k w text} {
    switch $k {
        ent {
            set ::magic::${p}_val $text
            set script [bind $w <Return>]
            if {[catch {uplevel #0 $script} err]} {
                append ::dref_log "binding error: $err\n"
            }
        }
        chk {
            if {[set ::magic::${p}_val] != $text} {
                if {[catch {$w invoke} err]} { append ::dref_log "binding error: $err\n" }
            }
        }
        sel {
            set m $w.menu
            set idx ""
            for {set i 0} {$i <= [$m index end]} {incr i} {
                if {[$m entrycget $i -label] eq $text} { set idx $i; break }
            }
            if {$idx eq ""} { error "selectlist $p has no entry \"$text\"" }
            if {[catch {$m invoke $idx} err]} { append ::dref_log "binding error: $err\n" }
        }
    }
}

# Does a field that shows $shown already hold $text?
proc ::dref_same {type shown text} {
    if {$shown eq $text} { return 1 }
    if {$type ni {float int bool01}} { return 0 }
    set a [magic::spice2float $shown ""]
    set b [magic::spice2float $text ""]
    if {![string is double -strict $a] || ![string is double -strict $b]} { return 0 }
    return [expr {$a == $b}]
}

# Magic's number for each value of the form $d that is not a plain number
# (SPICE notation such as 1.028k), as magic::spice2float reads it, "" for
# none. The PDKs' spice2float maps the suffix n to "* 1.0 e-9", which isn't
# a number, so it reads none from 170.0n.
proc ::dref_numbers {d} {
    set saved $::dref_log
    set out {}
    dict for {k v} $d {
        if {[string is double -strict $v]} continue
        set n ""
        catch {set n [magic::spice2float $v ""]}
        dict set out $k $n
    }
    set ::dref_log $saved
    return $out
}

# The values of the dialog's request $req typed in row order; returns the
# names typed.
proc ::dref_type_all {req types only_changed} {
    set typed {}
    set left [dict keys $req]
    foreach x [::dref_widgets] {
        lassign $x p k w
        if {![dict exists $req $p]} continue
        set left [lsearch -all -inline -not -exact $left $p]
        set text [dict get $req $p]
        if {$only_changed} {
            set type [expr {[dict exists $types $p] ? [dict get $types $p] : "string"}]
            if {[::dref_same $type [set ::magic::${p}_val] $text]} continue
        }
        ::dref_type $p $k $w $text
        lappend typed $p
        if {$::dref_abort ne ""} { error $::dref_abort }
    }
    if {[llength $left]} { error "the dialog has no widget for [join $left {, }]" }
    return $typed
}

set fh [open $::env(KMP_SWEEP) r]
fconfigure $fh -encoding utf-8
set sweep [json::json2dict [read $fh]]
close $fh
set out $::env(KMP_OUT)
file mkdir $out
set start 0
if {[info exists ::env(KMP_START)]} { set start $::env(KMP_START) }
set limit 1000000
if {[info exists ::env(KMP_LIMIT)]} { set limit $::env(KMP_LIMIT) }
set ix [open [file join $out index.jsonl] [expr {$start > 0 ? "a" : "w"}]]
fconfigure $ix -encoding utf-8 -translation lf

set ns sky130
if {[info exists ::env(KMP_NS)] && $::env(KMP_NS) ne ""} {
    set ns $::env(KMP_NS)
} elseif {[info exists ::PDKNAMESPACE] && $::PDKNAMESPACE ne ""} {
    set ns $::PDKNAMESPACE
}
set ::dref_units0 [lindex [units] 0]
# Under the GUI every Create unlocks fence, magnet and rotate (none of them
# is a GDS layer), as it does for a user, and each "tech lock", "tech
# unlock" or "tech revert" there takes longer than the one before (tech
# revert 1.5 s after the first point and 3.8 s after the fourth; locking
# 15 ms more per point). So those three are left as Create leaves them,
# and only other locks are put back, without tech revert. If a generator
# painted one of them, the geometry check against the plugin (which always
# runs with them locked) would show it.
set ::dref_gui_unlocked {fence magnet rotate}
proc ::dref_locks {} {
    set out {}
    foreach t [lsort [tech lock]] {
        if {[lsearch -exact $::dref_gui_unlocked $t] < 0} { lappend out $t }
    }
    return $out
}
set ::dref_locks0 [::dref_locks]
proc ::dref_restore {} {
    if {[info exists ::boxstack]} { set ::boxstack {} }
    if {[lindex [units] 0] ne $::dref_units0} { catch {units $::dref_units0} }
    set now [::dref_locks]
    if {$now ne $::dref_locks0} {
        set add {}
        foreach t $::dref_locks0 { if {[lsearch -exact $now $t] < 0} { lappend add $t } }
        if {[llength $add]} { catch {tech lock [join $add ,]} }
        set del {}
        foreach t [::dref_locks] { if {[lsearch -exact $::dref_locks0 $t] < 0} { lappend del $t } }
        if {[llength $del]} { catch {tech unlock [join $del ,]} }
    }
}

set pts {}
foreach pt [dict get $sweep points] {
    if {[dict exists $pt form] && [dict get $pt form] eq "box"} continue
    lappend pts $pt
}
set seen_dev {}
set n 0
foreach pt [lrange $pts $start [expr {$start + $limit - 1}]] {
    set id [dict get $pt id]
    set dev [dict get $pt device]
    set edit [expr {[dict exists $pt edit] && [dict get $pt edit]}]
    if {$edit} {
        set req [dict get $pt first request]
        set req2 [dict get $pt request]
        set types2 [dict get $pt types]
    } else {
        set req [dict get $pt request]
    }
    set nocell [dict exists [${ns}::${dev}_defaults] nocell]
    set ::dref_log ""
    set ::dref_counts {}
    set ::dref_abort ""
    set g ""
    set top ""
    set opened {}
    set form {}
    set typed {}
    set bindings ""
    set reopened {}
    set title ""
    set e {}
    set g1 ""
    set iname ""
    set ::inst ""
    set gds [file join $out $id.gds]
    set t0 [lindex [time {set rc [catch {
        load dref_$id -silent
        box values 0 0 0 0
        catch {destroy .params}
        magic::gencell ${ns}::$dev
        if {[catch {wm state .params}]} { error "magic::gencell opened no dialog" }
        set opened [magic::gencell_getparams]
        set ws [::dref_widgets]
        if {[lsearch -exact $seen_dev $dev] < 0} {
            lappend seen_dev $dev
            set bindings [::dref_bindings]
        }
        set typed [::dref_type_all $req {} 0]
        set form [magic::gencell_getparams]
        set ::dref_checked {}
        # Create: gencell_create with the form's values (one more _check),
        # then the dialog reopens on the new instance (sets ::inst). The
        # reopening can fail after the cell exists: on gf180mcuD's eFuse
        # and two npn devices, whose vendor cell is a stub, it looks for
        # <stub>_defaults. A user then gets Tk's error box and the cell
        # Create made; the error goes into the log.
        set crc [catch {.params.buttons.apply invoke} cerr]
        if {$crc && $::inst eq ""} {
            error $cerr
        } elseif {$crc} {
            append ::dref_log "Create's dialog, reopening on the new instance: $cerr\n"
        }
        if {$::dref_abort ne ""} { error $::dref_abort }
        if {$::inst eq ""} { error "Create placed no instance" }
        set g [instance list celldef $::inst]
        if {$g eq ""} { error "Create placed no instance" }
        # What the dialog shows now: "Edit device" on the new instance, or,
        # where it failed to reopen, what Create's gencell_setparams wrote.
        set reopened [magic::gencell_getparams]
        set title [.params.title.lab1 cget -text]
        if {$edit} {
            set g1 $g
            set checked1 $::dref_checked
            set iname $::inst
            dict set e first_form $form
            dict set e first_checked $checked1
            dict set e first_cell $g1
            dict set e first_reopened $reopened
            dict set e first_numbers [::dref_numbers $reopened]
            dict set e first_title $title
            dict set e typed [::dref_type_all $req2 $types2 1]
            set form [magic::gencell_getparams]
            set ::dref_checked {}
            set ::inst ""
            if {$title eq "Edit device:"} {
                dict set e button Apply
                if {[catch {.params.buttons.apply invoke} aerr]} {
                    append ::dref_log "Apply: $aerr\n"
                }
                set iname [.params.title.ient get]
            } else {
                # The dialog didn't reopen on the instance (gf180mcuD's stub
                # devices): its button is still Create, which makes another
                # instance, and makes none over an identical one. A user
                # deletes the old instance and presses Create again.
                dict set e button Create
                # select runs Magic's gencell_update, which tries to reopen
                # the dialog on the instance and fails the same way.
                catch {select cell $iname}
                catch {delete}
                catch {select clear}
                set crc [catch {.params.buttons.apply invoke} cerr]
                if {$crc && $::inst eq ""} { error $cerr }
                if {$crc} { append ::dref_log "Create's dialog, reopening on the new instance: $cerr\n" }
                set iname $::inst
            }
            if {$::dref_abort ne ""} { error $::dref_abort }
            set g [instance list celldef $iname]
            if {$g eq ""} { error "no instance $iname after [dict get $e button]" }
            # The instance's values: its cell's parameters property (a fixed
            # device has none: the values its cell was drawn with).
            set prop ""
            if {!$nocell} { catch {set prop [cellname list property $g parameters]} }
            if {$prop ne ""} { set ::dref_checked $prop } elseif {$::dref_checked eq ""} { set ::dref_checked $checked1 }
            if {[catch {magic::gencell_dialog $iname {} {} {}} rerr]} {
                append ::dref_log "reopening the dialog on $iname: $rerr\n"
            }
            set reopened [magic::gencell_getparams]
            set title [.params.title.lab1 cget -text]
        }
        if {$nocell} {
            set top dref_$id
            load dref_$id
        } else {
            set top $g
            load $g
        }
        gds write $gds
    } err]}] 0]
    if {$::dref_abort ne ""} { set rc 1; set err $::dref_abort }
    set ::dref_abort ""
    catch {destroy .params}
    catch {load dref_$id}
    foreach i [list $::inst $iname] {
        if {$i ne ""} { catch {select cell $i}; catch {delete} }
    }
    if {!$nocell} {
        foreach c [lsort -unique [list $g $g1]] {
            if {$c ne ""} { catch {cellname delete $c -noprompt} }
        }
    }
    catch {load dref_base -silent; cellname delete dref_$id -noprompt}
    catch {select clear}
    ::dref_restore
    set line "\{\"id\":[::dref_js $id],\"device\":[::dref_js $dev],\"rc\":$rc,\"top\":[::dref_js $top],\"magic_cell\":[::dref_js $g],\"log\":[::dref_js $::dref_log],\"error\":[::dref_js [expr {$rc ? $err : {}}]],\"typed\":[::dref_jlist $typed],\"opened\":[::dref_jobj $opened],\"form\":[::dref_jobj $form],\"checked\":[::dref_jobj $::dref_checked],\"reopened\":[::dref_jobj $reopened],\"numbers\":[::dref_jobj [::dref_numbers $reopened]],\"title\":[::dref_js $title],\"nocell\":[expr {$nocell ? 1 : 0}],\"us\":$t0"
    if {$bindings ne ""} { append line ",\"bindings\":$bindings" }
    if {$edit} {
        set items {}
        foreach k {first_form first_checked first_reopened first_numbers} {
            if {[dict exists $e $k]} { lappend items "[::dref_js $k]:[::dref_jobj [dict get $e $k]]" }
        }
        foreach k {first_cell first_title button} {
            if {[dict exists $e $k]} { lappend items "[::dref_js $k]:[::dref_js [dict get $e $k]]" }
        }
        if {[dict exists $e typed]} { lappend items "\"typed\":[::dref_jlist [dict get $e typed]]" }
        append line ",\"edit\":\{[join $items ,]\}"
    }
    append line "\}"
    ::dref_real_puts $ix $line
    flush $ix
    incr n
}
close $ix
::dref_real_puts "DREF_DONE $n"
flush stdout
quit -noprompt
