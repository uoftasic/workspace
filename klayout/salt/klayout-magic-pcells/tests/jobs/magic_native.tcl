# What a Magic user gets from Magic's DRC on a GDS file (design-0.6.md 1, 6.3):
# the course checker's steps, which are also what Magic's GUI does after
# File > Read GDS and a check of the loaded cell. No plugin code is involved.
#
#   KMP_GDS=case.gds KMP_TOP=case KMP_OUT=native.tsv \
#     magic -dnull -noconsole -rcfile <pdk>.magicrc magic_native.tcl
#
# The file is read with DRC left on, as Magic starts; the top cell is loaded
# and checked from the top only (no check of each cell as its own top, no
# margin around the cell), first in drc(fast), then in drc(full), each time
# followed by "drc list count total" and "drc listall why". "drc euclidean on"
# is the course checker's setting. "drc catchup" makes batch Magic finish the
# check before the listing.
#
# KMP_GDS and KMP_TOP may each hold several names, one per line: every file
# is read, then each top cell is loaded and checked in turn in this one
# process. The jobs step does this for the gaps cases, at most 15 one-cell
# files with distinct cell names at a time, because a process that reads
# the whole gaps sheet with DRC on checks all of it at its first catchup.
#
# Lines of KMP_OUT, tab-separated, coordinates in um in the cell's frame:
#   count <cell> <style> <drc list count total>
#   box   <cell> <style> <why-text> <l b r t>
catch {crashbackups stop}
foreach f [split $::env(KMP_GDS) "\n"] {
    if {$f ne ""} { gds read $f }
}
set fh [open $::env(KMP_OUT) w]
set n 0
foreach cell [split $::env(KMP_TOP) "\n"] {
    if {$cell eq ""} { continue }
    load $cell
    select top cell
    drc euclidean on
    foreach style {drc(fast) drc(full)} {
        drc style $style
        drc check
        drc catchup
        set total [drc list count total]
        if {$total eq ""} { set total 0 }
        puts $fh "count\t$cell\t$style\t$total"
        set scale [cif scale out]
        foreach {why boxes} [drc listall why] {
            set w [string map {\t { } \n { } \r { }} $why]
            foreach b $boxes {
                set um {}
                foreach v $b { lappend um [expr {$v * $scale}] }
                puts $fh "box\t$cell\t$style\t$w\t$um"
            }
        }
    }
    incr n
}
close $fh
puts stdout "NATIVE_DONE $n"
flush stdout
quit -noprompt
