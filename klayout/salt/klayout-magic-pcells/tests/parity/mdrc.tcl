# Magic DRC on a GDS file, for the parity harness.
#
#   KMP_GDS=sheet.gds KMP_TOP=SHEET KMP_OUT=result.tsv [KMP_STYLE=drc(fast)] \
#     magic -dnull -noconsole -rcfile <pdk>.magicrc mdrc.tcl
#
# Writes one line per error box: "<message>\t<l> <b> <r> <t>" in um, in the
# top cell's coordinates. "drc catchup" is needed in batch: without it Magic
# reports no errors at all. Works for every PDK: the rcfile picks the rules.
# KMP_STYLE is the DRC style, drc(full) when it is not set.
#
# With KMP_CELLS (cell names, one per line) instead of KMP_TOP, each cell is
# loaded and checked in turn, as its own top cell, in one Magic process, and
# each line starts with the cell: "<cell>\t<message>\t<l> <b> <r> <t>". The
# jobs step of tests/parity/run_sweep.py uses this, at most 15 cells per
# process (design-0.6.md 2.1). No plugin code is involved.
catch {crashbackups stop}
drc off
gds read $::env(KMP_GDS)
if {[info exists ::env(KMP_STYLE)] && $::env(KMP_STYLE) ne ""} {
    set style $::env(KMP_STYLE)
} else {
    set style drc(full)
}
if {[info exists ::env(KMP_CELLS)]} {
    set cells {}
    foreach c [split $::env(KMP_CELLS) "\n"] {
        if {$c ne ""} { lappend cells $c }
    }
    set tagged 1
} else {
    set cells [list $::env(KMP_TOP)]
    set tagged 0
}
set fh [open $::env(KMP_OUT) w]
set n 0
foreach cell $cells {
    load $cell
    select top cell
    # Check a margin around the cell too: an error area that lies outside the
    # cell's bounding box (the far side of a metal5 square narrower than the
    # width rule) is clipped to the checked box, so a lone device would lose it.
    box grow c 10um
    drc euclidean on
    drc style $style
    drc check
    drc catchup
    set scale [cif scale out]
    foreach {why boxes} [drc listall why] {
        set w [string map {\t { } \n { }} $why]
        foreach b $boxes {
            set um {}
            foreach v $b { lappend um [expr {$v * $scale}] }
            if {$tagged} {
                puts $fh "$cell\t$w\t$um"
            } else {
                puts $fh "$w\t$um"
            }
            incr n
        }
    }
}
close $fh
puts stdout "MDRC_DONE $n"
flush stdout
quit -noprompt
