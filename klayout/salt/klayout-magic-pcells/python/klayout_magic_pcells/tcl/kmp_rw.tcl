# The generated-layer job (layercheck.py, portcheck.py --magic): Magic reads
# the hierarchical export, writes it back, and extracts it, in one process.
#
#   KMP_GDS   the export (kmp_job_read)
#   KMP_TOP   the top cell, as it is named in the export
#   KMP_RW_MODE
#     rw     (default) gds write rw.gds from the top cell; then a flattened
#            copy made by Magic's own flatten, extracted with extract all and
#            ext2spice lvs, so that every device line of kmp__flat.ext is in
#            the top cell's coordinates. Magic decided each device's type
#            when it read its cell (design-0.6.md 3.1); flatten copies those
#            types, so the flat .ext keeps Magic's per-cell decisions
#            (design-0.6.md 3.3).
#     ports  only the extraction of the top cell as Magic reads it, for its
#            .subckt port list (P8): no write, no flatten.
#
# Output files in $KMP_DIR: rw.gds, kmp__flat.ext and kmp__flat.spice (rw);
# <top>.spice and the .ext files (ports). Timings (microseconds, from Tcl's
# time) go to rw_times.txt.

source $::env(KMP_TCL_DIR)/kmp_job_common.tcl

set kmp_dir $::env(KMP_DIR)
set kmp_top $::env(KMP_TOP)
set kmp_mode rw
if {[info exists ::env(KMP_RW_MODE)] && $::env(KMP_RW_MODE) ne ""} {
    set kmp_mode $::env(KMP_RW_MODE)
}
if {$kmp_mode ni {rw ports}} {
    kmp_job_fail "unknown KMP_RW_MODE $kmp_mode"
}
cd $kmp_dir
set times {}

kmp_job_stage read 0
lappend times read [kmp_job_us {kmp_job_read $::env(KMP_GDS)}]
kmp_job_load $kmp_top

proc kmp_rw_extract {} {
    extract no all
    extract do local
    extract all
    ext2spice lvs
    ext2spice -o [lindex [cellname list self] 0].spice
}

if {$kmp_mode eq "ports"} {
    kmp_job_stage extract 1
    if {[catch {lappend times extract [kmp_job_us {kmp_rw_extract}]} err]} {
        kmp_job_fail "extraction of $kmp_top failed: $err"
    }
} else {
    kmp_job_stage write 1
    if {[catch {lappend times write [kmp_job_us {gds write [file join $kmp_dir rw.gds]}]} err]} {
        kmp_job_fail "gds write failed: $err"
    }
    set flat kmp__flat
    if {[lsearch -exact [cellname list allcells] $flat] >= 0} {
        kmp_job_fail "the layout already has a cell named $flat"
    }
    kmp_job_stage flatten 2
    if {[catch {lappend times flatten [kmp_job_us {flatten $flat}]} err]} {
        kmp_job_fail "flatten failed: $err"
    }
    kmp_job_load $flat
    kmp_job_stage extract 3
    if {[catch {lappend times extract [kmp_job_us {kmp_rw_extract}]} err]} {
        kmp_job_fail "extraction of the flattened copy failed: $err"
    }
}

set f [open [file join $kmp_dir rw_times.txt] w]
puts $f "scale [cif scale out]"
foreach {k v} $times {
    puts $f "$k $v"
}
close $f
kmp_job_done 1
