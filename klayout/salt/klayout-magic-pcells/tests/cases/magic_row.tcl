# Have Magic place a row of standard cells and write it as GDS, so that the
# row is Magic-written (a negative control, design-0.6.md 3.3). build.py's
# run_magic_row() sets:
#
#   KMP_ROW_TOP    the new cell's name
#   KMP_ROW_CELLS  the cells, left to right
#   KMP_ROW_X      each cell's origin x in um
#   KMP_ROW_MAG    the library's mag/ folder, or empty
#   KMP_ROW_GDS    when KMP_ROW_MAG is empty: GDS files that hold the cells
#   KMP_OUT        the GDS file to write
#
#   magic -dnull -noconsole -rcfile <pdk>.magicrc magic_row.tcl
#
# Cell names reach Tcl only as environment values.
catch {crashbackups stop}
drc off
if {$::env(KMP_ROW_MAG) ne ""} {
    addpath $::env(KMP_ROW_MAG)
} else {
    foreach f $::env(KMP_ROW_GDS) { gds read $f }
}
load $::env(KMP_ROW_TOP)
set n 0
foreach c $::env(KMP_ROW_CELLS) x $::env(KMP_ROW_X) {
    box values ${x}um 0um ${x}um 0um
    getcell $c child 0 0
    incr n
}
select top cell
gds write $::env(KMP_OUT)
puts stdout "ROW_DONE $n [cellname list self]"
flush stdout
quit -noprompt
