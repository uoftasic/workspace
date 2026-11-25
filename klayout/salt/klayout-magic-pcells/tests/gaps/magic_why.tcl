# Magic's DRC on gap-table case cells, with tests/parity/mdrc.tcl's steps
# (drc off before gds read, load, the box grown 10 um, drc euclidean on,
# drc style, drc check, drc catchup, drc listall why), once per cell and
# style. It keeps Magic's whole why-text, so that a rule without an ID in
# parentheses can be looked up by its message.
#
#   KMP_FILES="a.gds b.gds" KMP_CELLS="a b" KMP_STYLES="drc(fast) drc(full)" KMP_OUT=out.tsv \
#     magic -dnull -noconsole -rcfile <pdk>.magicrc magic_why.tcl
#
# Writes one line per cell, style and why-text to KMP_OUT:
#   <cell> TAB <style> TAB <boxes> TAB <why-text>
# and a line with 0 boxes and an empty why-text for every cell and style
# checked. Give it at most 15 cells per process (design-0.6.md 2.1). Cell names
# arrive only through the environment.
catch {crashbackups stop}
drc off
foreach f $::env(KMP_FILES) {
    gds read $f
}
drc euclidean on
set fh [open $::env(KMP_OUT) w]
foreach c $::env(KMP_CELLS) {
    foreach st $::env(KMP_STYLES) {
        load $c
        select top cell
        box grow c 10um
        drc style $st
        drc check
        drc catchup
        foreach {why boxes} [drc listall why] {
            puts $fh "$c\t$st\t[llength $boxes]\t$why"
        }
        puts $fh "$c\t$st\t0\t"
    }
}
close $fh
puts "GAPS_CELLS_DONE"
quit -noprompt
