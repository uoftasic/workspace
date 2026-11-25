# The box-paint generators through Magic's own menu, under Xvfb.
#
#   KMP_JOBS=jobs.json KMP_OUT=<dir> xvfb-run -a magic -d XR -rcfile <pdk>.magicrc menu_ref.tcl
#
# Path A calls a box-paint generator the way its menu entry does: the box
# set, then <ns>::<proc>_draw with no arguments. This checks that claim
# against the menu itself. For each job ({id, label, w, h}), it opens a new
# cell in the layout window, sets the box to w x h um with its lower-left
# corner at the origin, invokes the menu entry whose label is "label" (the
# PDK's "Devices" menus are Tk menus named *.toolmenu), and writes the cell
# to <dir>/<id>.gds. One JSON line per job goes to <dir>/index.jsonl. Uses
# none of the plugin's code.
package require json
catch {crashbackups stop}

proc ::menu_js {s} {
    set s [string map [list \\ \\\\ \" \\\" \n \\n \r \\r \t \\t] $s]
    regsub -all {[\x00-\x1f]} $s {} s
    return "\"$s\""
}

proc ::menu_find {w pat} {
    set r {}
    foreach c [winfo children $w] {
        if {[string match $pat $c]} { lappend r $c }
        lappend r {*}[::menu_find $c $pat]
    }
    return $r
}

# label -> {menu index}
set entries {}
foreach m [::menu_find . *.toolmenu] {
    set last [$m index end]
    if {$last eq "none"} continue
    for {set i 0} {$i <= $last} {incr i} {
        if {[$m type $i] eq "command"} {
            set lab [string trim [$m entrycget $i -label]]
            if {![dict exists $entries $lab]} { dict set entries $lab [list $m $i] }
        }
    }
}

set fh [open $::env(KMP_JOBS) r]
set jobs [json::json2dict [read $fh]]
close $fh
set out $::env(KMP_OUT)
file mkdir $out
set ix [open [file join $out index.jsonl] w]
set locks0 [lsort [tech lock]]
set units0 [lindex [units] 0]
foreach j $jobs {
    set id [dict get $j id]
    set label [dict get $j label]
    set cmd ""
    set rc [catch {
        if {![dict exists $entries $label]} { error "no menu entry \"$label\"" }
        lassign [dict get $entries $label] m i
        set cmd [$m entrycget $i -command]
        load menu_$id
        box values 0um 0um [dict get $j w]um [dict get $j h]um
        $m invoke $i
        gds write [file join $out $id.gds]
    } err]
    catch {load menu_base}
    catch {cellname delete menu_$id -noprompt}
    if {[info exists ::boxstack]} { set ::boxstack {} }
    if {[lindex [units] 0] ne $units0} { catch {units $units0} }
    if {[lsort [tech lock]] ne $locks0} {
        catch {tech revert}
        foreach t $locks0 { if {[lsearch -exact [tech lock] $t] < 0} { catch {tech lock $t} } }
    }
    puts $ix "\{\"id\":[::menu_js $id],\"rc\":$rc,\"command\":[::menu_js $cmd],\"error\":[::menu_js [expr {$rc ? $err : {}}]],\"top\":[::menu_js menu_$id]\}"
    flush $ix
}
close $ix
puts stdout "MENU_DONE [llength $jobs]"
flush stdout
quit -noprompt
