# Magic extraction of many flat device cells in one session.
#
#   KMP_GDS=sheet.gds KMP_CELLS="D0001 D0002 ..." KMP_OUT=<dir> \
#     magic -dnull -noconsole -rcfile <pdk>.magicrc extract.tcl
#
# For each cell: extract all, ext2spice lvs, and write <dir>/<cell>.spice.
catch {crashbackups stop}
drc off
gds read $::env(KMP_GDS)
set out $::env(KMP_OUT)
file mkdir $out
set n 0
foreach c $::env(KMP_CELLS) {
    if {[catch {
        load $c
        select top cell
        extract path $out
        extract no capacitance
        extract no coupling
        extract no resistance
        extract no length
        extract all
        ext2spice lvs
        ext2spice -p $out -o [file join $out $c.spice]
    } err]} {
        puts stdout "EXTRACT_ERROR $c $err"
    }
    incr n
}
puts stdout "EXTRACT_DONE $n"
flush stdout
quit -noprompt
