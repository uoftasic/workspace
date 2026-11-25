# Dump what tools/build_manifest.py needs to build the device manifest.
#
# Run as:  KMP_MANIFEST_OUT=<dir> magic -dnull -noconsole -rcfile <rc> kmp_manifest.tcl
#
# Writes into <dir>: versions.json, procs.txt, defaults.json, raw.json and one
# GDS per device under gds/ (generated with the defaults, through the same
# generate op the backend uses), and one per box-paint generator (drawn at its
# minimum box, through the same box op).

source [file join [file dirname [info script]] kmp_server.tcl]

set ::kmp::mout $::env(KMP_MANIFEST_OUT)
file mkdir [file join $::kmp::mout gds]

proc ::kmp::diffpairs {before after} {
    set out {}
    dict for {k v} $after {
        if {![dict exists $before $k]} {
            lappend out "\[[::kmp::jstr $k],null,[::kmp::jstr $v]\]"
        } elseif {[dict get $before $k] ne $v} {
            lappend out "\[[::kmp::jstr $k],[::kmp::jstr [dict get $before $k]],[::kmp::jstr $v]\]"
        }
    }
    dict for {k v} $before {
        if {![dict exists $after $k]} {
            lappend out "\[[::kmp::jstr $k],[::kmp::jstr $v],null\]"
        }
    }
    return "\[[join $out ,]\]"
}

proc ::kmp::run_check {dev params} {
    ::kmp::begin_request
    set ns $::kmp::ns
    set merged [magic::gencell_defaults $dev $ns $params]
    set err ""
    if {[info commands ::${ns}::${dev}_check] eq ""} {
        set checked $merged
        set err "no _check proc"
    } elseif {[catch {set checked [::${ns}::${dev}_check $merged]} err]} {
        set checked $merged
    } else {
        set err ""
    }
    ::kmp::restore_state
    return [list $merged $checked $::kmp::log $err]
}

# Does a box-paint generator paint anything into an s x s um box?  Returns
# {painted messages}.
proc ::kmp::box_paints {name s} {
    ::kmp::begin_request
    set c kmp_bp_probe_[incr ::kmp::probe_seq]
    set layers {}
    catch {
        load $c -silent
        box values 0um 0um ${s}um ${s}um
        ::${::kmp::ns}::${name}_draw
        box values -10000000 -10000000 10000000 10000000
        select area
        set layers [lindex [what -list] 0]
        select clear
    }
    set msg $::kmp::log
    catch {load $::kmp::top}
    catch {cellname delete $c -noprompt}
    ::kmp::restore_state
    return [list [expr {[llength $layers] > 0}] $msg]
}
set ::kmp::probe_seq 0

# 1. Versions, proc text and defaults, before anything below stubs a proc.
set vi [::kmp::version_info]
::kmp::write_file [file join $::kmp::mout versions.json] "[::kmp::jobj $vi]\n"
::kmp::dump_procs [file join $::kmp::mout procs.txt]
::kmp::dump_defaults [file join $::kmp::mout defaults.json]

# 2. Dialog widgets, by running each _dialog against recording stubs.
set ::kmp::widgets {}
set ::kmp::stubbed {add_entry add_checkbox add_message add_selectlist add_selectindex add_dependency}
foreach p $::kmp::stubbed {
    if {[info commands ::magic::$p] ne ""} {
        rename ::magic::$p ::kmp::orig_$p
    }
}
proc ::magic::add_entry {pname ptext parameters} {
    lappend ::kmp::widgets [list entry $pname $ptext {}]
}
proc ::magic::add_checkbox {pname ptext parameters} {
    lappend ::kmp::widgets [list checkbox $pname $ptext {}]
}
proc ::magic::add_message {pname ptext parameters {color blue}} {
    lappend ::kmp::widgets [list message $pname $ptext {}]
}
proc ::magic::add_selectlist {pname ptext all_values parameters {itext ""}} {
    lappend ::kmp::widgets [list selectlist $pname $ptext [::kmp::jlist $all_values]]
}
proc ::magic::add_selectindex {pname ptext all_values parameters {ival 0}} {
    lappend ::kmp::widgets [list selectindex $pname $ptext [::kmp::jlist $all_values]]
}
proc ::magic::add_dependency {callback gencell_type library args} {
    lappend ::kmp::widgets [list dependency $callback $gencell_type $args]
}

set ::kmp::dialogs [dict create]
set ns $::kmp::ns
foreach dev [::kmp::devices] {
    set ::kmp::widgets {}
    set derr ""
    if {[info commands ::${ns}::${dev}_dialog] ne ""} {
        if {[catch {::${ns}::${dev}_dialog [::${ns}::${dev}_defaults]} derr]} {
        } else {
            set derr ""
        }
    }
    dict set ::kmp::dialogs $dev [list $::kmp::widgets $derr]
}
foreach p $::kmp::stubbed {
    if {[info commands ::kmp::orig_$p] ne ""} {
        rename ::magic::$p ""
        rename ::kmp::orig_$p ::magic::$p
    }
}

# 3. Per device: _check on the defaults, probes, and one generation.
set devjs {}
foreach dev [::kmp::devices] {
    set defs [::${ns}::${dev}_defaults]
    lassign [dict get $::kmp::dialogs $dev] widgets derr
    set wjs {}
    foreach w $widgets {
        lassign $w kind pname ptext extra
        lappend wjs "\{\"kind\":[::kmp::jstr $kind],\"name\":[::kmp::jstr $pname],\"label\":[::kmp::jstr $ptext],\"extra\":[::kmp::jstr $extra]\}"
    }

    lassign [::kmp::run_check $dev {}] merged checked clog cerr
    set checkjs "\{\"changes\":[::kmp::diffpairs $merged $checked],\"messages\":[::kmp::jstr $clog],\"error\":[::kmp::jstr $cerr]\}"

    # Probes: each entry parameter set to 0, to 10000 and to 2.5.
    set probes {}
    foreach w $widgets {
        lassign $w kind pname ptext extra
        if {$kind ne "entry" || ![dict exists $defs $pname]} continue
        foreach val {0 10000 2.5} {
            lassign [::kmp::run_check $dev [list $pname $val]] m c plog perr
            set got [expr {[dict exists $c $pname] ? [dict get $c $pname] : ""}]
            lappend probes "\{\"param\":[::kmp::jstr $pname],\"value\":[::kmp::jstr $val],\"result\":[::kmp::jstr $got],\"messages\":[::kmp::jstr $plog],\"error\":[::kmp::jstr $perr]\}"
        }
    }

    set nocell [dict exists $defs nocell]
    set form [expr {$nocell ? "wrapper" : "cell"}]
    set gds [file join $::kmp::mout gds ${dev}.gds]
    ::kmp::begin_request
    set grc [catch {::kmp::op_generate [dict create device $dev params {} form $form out $gds]} gres]
    set glog $::kmp::log
    ::kmp::restore_state
    if {$grc} {
        set genjs "\{\"ok\":false,\"error\":[::kmp::jstr $gres],\"messages\":[::kmp::jstr $glog]\}"
    } else {
        set cell [dict get $gres kv cell]
        set genjs "\{\"ok\":true,\"cell\":[::kmp::jstr $cell],\"checked\":[::kmp::jpairs [dict get $gres params]],\"messages\":[::kmp::jstr $glog],\"gds\":[::kmp::jstr $gds]\}"
    }

    lappend devjs "\{\"name\":[::kmp::jstr $dev],\"has_check\":[llength [info commands ::${ns}::${dev}_check]],\"has_convert\":[llength [info commands ::${ns}::${dev}_convert]],\"has_dialog\":[llength [info commands ::${ns}::${dev}_dialog]],\"draw_args\":[::kmp::jstr [info args ::${ns}::${dev}_draw]],\"defaults\":[::kmp::jpairs $defs],\"widgets\":\[[join $wjs ,]\],\"dialog_error\":[::kmp::jstr $derr],\"check_on_defaults\":$checkjs,\"probes\":\[[join $probes ,]\],\"nocell\":[expr {$nocell ? "true" : "false"}],\"form\":[::kmp::jstr $form],\"defaults_run\":$genjs\}"
}

# 4. Box-paint generators: the smallest square box (on the 5 nm grid, up to
# 20 um) they paint into, found by bisection, the message one step below it,
# and one generation at the minimum through the server's box op.
set bpjs {}
foreach h [::kmp::boxpaint] {
    set lo 0
    set hi 4000
    if {![lindex [::kmp::box_paints $h [expr {$hi * 0.005}]] 0]} {
        set minjs null
        set belowjs null
        set genjs "\{\"ok\":false,\"error\":\"paints nothing up to 20 um\"\}"
        set min ""
    } else {
        while {$hi - $lo > 1} {
            set mid [expr {($lo + $hi) / 2}]
            if {[lindex [::kmp::box_paints $h [expr {$mid * 0.005}]] 0]} { set hi $mid } else { set lo $mid }
        }
        set min [format %.3f [expr {$hi * 0.005}]]
        set min [string trimright [string trimright $min 0] .]
        if {[string first . $min] < 0} { append min .0 }
        set below [format %.3f [expr {($hi - 1) * 0.005}]]
        lassign [::kmp::box_paints $h $below] bpaint bmsg
        set minjs [::kmp::jstr $min]
        set belowjs "\{\"box_um\":[::kmp::jstr $below],\"painted\":[expr {$bpaint ? "true" : "false"}],\"messages\":[::kmp::jstr $bmsg]\}"
        set gds [file join $::kmp::mout gds box_${h}.gds]
        ::kmp::begin_request
        set grc [catch {::kmp::gen_box $h [dict create w $min h $min] $gds} gres]
        set glog $::kmp::log
        ::kmp::restore_state
        if {$grc} {
            set genjs "\{\"ok\":false,\"error\":[::kmp::jstr $gres],\"messages\":[::kmp::jstr $glog]\}"
        } else {
            set genjs "\{\"ok\":true,\"cell\":\"\",\"checked\":[::kmp::jpairs [dict get $gres params]],\"box\":[::kmp::jstr [dict get $gres kv box]],\"messages\":[::kmp::jstr $glog],\"gds\":[::kmp::jstr $gds]\}"
        }
    }
    lappend bpjs "\{\"name\":[::kmp::jstr $h],\"draw_args\":[::kmp::jstr [info args ::${ns}::${h}_draw]],\"min_box_um\":$minjs,\"below_min\":$belowjs,\"defaults_run\":$genjs\}"
}

::kmp::write_file [file join $::kmp::mout raw.json] "\{\"devices\":\[\n[join $devjs ",\n"]\n\],\"helpers\":[::kmp::jlist [::kmp::helpers]],\"boxpaint\":\[\n[join $bpjs ",\n"]\n\]\}\n"
::kmp::real_puts "KMP_MANIFEST_DONE [llength $devjs]"
flush stdout
quit -noprompt
