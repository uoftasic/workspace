# Magic's DRC on an exported layout, for drcjob.py (one Magic process per
# batch of at most 15 cells; drcjob.py starts the next batch).
#
#   KMP_GDS     the exported file (set by jobs.py)
#   KMP_TOP     the top cell's name in that file
#   KMP_MODE    hierarchical: every cell definition under the top, children
#               before parents, then the top (kmp_job_cells); flat: the top
#               cell alone (the export flattened it)
#   KMP_STYLE   Magic's DRC style, for example drc(full)
#   KMP_FIRST   the first cell of that order this process checks (0 based)
#   KMP_COUNT   how many cells it checks
#
# Each cell is checked as the edit cell, the way tests/parity/mdrc.tcl checks
# its top cell: load, select top cell, box grow c 10um, drc euclidean on,
# drc style, drc check, drc catchup, drc listall why, drc list count total.
#
# Files written into $KMP_DIR:
#   cells.txt     the whole order, one cell per line
#   drc_<i>.tsv   for the cell at position i: cell, why-text, l, b, r, t, in
#                 Magic's internal units (drcjob.py scales them with the
#                 KMP_JOB_SCALE line)
#   summary.tsv   per cell of this batch: i, cell, checked or empty,
#                 drc list count total, error boxes, microseconds of the check
#   meta.tsv      tech name and tech version
#
# A child cell that is empty to Magic (all its shapes on layers Magic's
# reader ignores) is skipped and listed as empty; an empty top cell fails
# the job (kmp_job_load).

source $::env(KMP_TCL_DIR)/kmp_job_common.tcl

# 1 when the cell has nothing Magic can check. It loads the cell.
proc kmp_drc_empty {cell} {
    if {[lsearch -exact [cellname list allcells] $cell] < 0} {
        return 0
    }
    select clear
    if {[catch {load $cell}]} {
        return 0
    }
    select top cell
    set bb [box values]
    if {[llength $bb] != 4} {
        return 1
    }
    lassign $bb l b r t
    if {$r - $l <= 0 || $t - $b <= 0} {
        return 1
    }
    if {$r - $l <= 1 && $t - $b <= 1} {
        select area
        set what [what -list]
        select clear
        set n 0
        foreach part $what { incr n [llength $part] }
        if {$n == 0} {
            return 1
        }
    }
    return 0
}

proc kmp_drc_write {path text} {
    set fh [open $path w]
    puts -nonewline $fh $text
    close $fh
}

kmp_job_stage reading 0
kmp_job_read $::env(KMP_GDS)

set top $::env(KMP_TOP)
set style $::env(KMP_STYLE)
set dir $::env(KMP_DIR)
set first $::env(KMP_FIRST)
set count $::env(KMP_COUNT)

if {[lsearch -exact [cellname list allcells] $top] < 0} {
    kmp_job_fail "cell $top is not among the cells Magic read from the file"
}
if {$::env(KMP_MODE) eq "flat"} {
    set order [list $top]
} else {
    set order [kmp_job_cells $top]
}
kmp_drc_write [file join $dir cells.txt] "[join $order \n]\n"

set tv [tech version]
kmp_drc_write [file join $dir meta.tsv] "tech\t[tech name]\ntech_version\t[lindex $tv 0]\n"

set fs [open [file join $dir summary.tsv] w]
set n 0
set last [expr {min([llength $order], $first + $count)}]
for {set i $first} {$i < $last} {incr i} {
    set cell [lindex $order $i]
    kmp_job_stage "checking $cell" $i
    if {$cell ne $top && [kmp_drc_empty $cell]} {
        puts $fs "$i\t$cell\tempty\t0\t0\t0"
        flush $fs
        continue
    }
    kmp_job_load $cell
    select top cell
    box grow c 10um
    drc euclidean on
    if {[catch {drc style $style} err]} {
        kmp_job_fail "drc style $style failed: $err"
    }
    set us [kmp_job_us {drc check; drc catchup}]
    set fh [open [file join $dir drc_$i.tsv] w]
    set nb 0
    foreach {why boxes} [drc listall why] {
        set w [string map {\t { } \n { } \r { }} $why]
        foreach b $boxes {
            puts $fh "$cell\t$w\t[join $b \t]"
            incr nb
        }
    }
    close $fh
    set total [drc list count total]
    if {$total eq ""} {
        set total 0
    }
    puts $fs "$i\t$cell\tchecked\t$total\t$nb\t$us"
    flush $fs
    incr n
}
close $fs
kmp_job_done $n
