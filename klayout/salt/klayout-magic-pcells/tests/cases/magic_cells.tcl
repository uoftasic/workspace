# Magic's DRC on case cells, with tests/parity/mdrc.tcl's steps (drc off
# before gds read, load, the box grown 10 um, drc euclidean on, drc check,
# drc catchup, drc listall why) for each cell and style, then optionally the
# harness's netlist-only extraction. One line per cell and style:
#   CELLDRC <cell> <style> <rule id> <boxes> ...
#
#   KMP_GDS=f.gds KMP_CELLS="a b" KMP_STYLES="drc(fast) drc(full)" KMP_EXTRACT=0|1 KMP_OUT=dir \
#     magic -dnull -noconsole -rcfile <pdk>.magicrc magic_cells.tcl
#
# Give it at most 15 cells per process (design-0.6.md 2.1).
catch {crashbackups stop}
drc off
gds read $::env(KMP_GDS)
set out $::env(KMP_OUT); file mkdir $out
drc euclidean on
foreach c $::env(KMP_CELLS) {
    foreach st $::env(KMP_STYLES) {
        load $c
        select top cell
        box grow c 10um
        drc style $st
        drc check; drc catchup
        set cnt [dict create]
        foreach {why boxes} [drc listall why] {
            if {![regexp {\(([^()]*)\)\s*$} $why -> id]} { set id $why }
            dict incr cnt $id [llength $boxes]
        }
        puts "CELLDRC $c $st [lsort -stride 2 -index 0 $cnt]"
    }
    if {$::env(KMP_EXTRACT) eq "1"} {
        load $c
        select top cell
        extract path $out
        extract no capacitance; extract no coupling; extract no resistance; extract no length
        extract all
        ext2spice lvs
        ext2spice -p $out -o [file join $out $c.spice]
    }
}
puts "CELLS_DONE"
quit -noprompt
