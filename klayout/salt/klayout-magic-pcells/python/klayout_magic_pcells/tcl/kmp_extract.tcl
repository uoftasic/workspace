# Magic extraction of one cell, for "Extract with Magic" and "LVS with
# netgen" (lvsjob.py).
#
#   KMP_GDS     the exported file (the hierarchy kept)
#   KMP_TOP     the cell to extract
#   KMP_DIR     the job directory: the .ext files and the netlist go here
#   KMP_OUT     the netlist's file name in KMP_DIR (default netlist.spice)
#   KMP_CAPS       1: with parasitic capacitance (extract do capacitance,
#                  extract do coupling, ext2spice cthresh 0)
#   KMP_FLATGLOB   1: gds flatglob *__kmp_* before the read, so the
#                  plugin's PCell variants are flattened into their parents
#   KMP_MAKEALL    1: port makeall after the load (every label is a port)
#
# Without KMP_CAPS the settings are the harness's (tests/parity/extract.tcl):
# no capacitance, coupling, resistance or length, then ext2spice lvs.
# The .ext files stay in KMP_DIR; extfile.py reads them, with the unit from
# the KMP_JOB_SCALE line that kmp_job_read prints from this same process.

source $::env(KMP_TCL_DIR)/kmp_job_common.tcl

proc kmp_extract_flag {name} {
    return [expr {[info exists ::env($name)] && $::env($name) eq "1"}]
}

set dir $::env(KMP_DIR)
set out [expr {[info exists ::env(KMP_OUT)] && $::env(KMP_OUT) ne "" ? $::env(KMP_OUT) : "netlist.spice"}]
set caps [kmp_extract_flag KMP_CAPS]

kmp_job_stage reading 0
if {[kmp_extract_flag KMP_FLATGLOB]} {
    gds flatglob *__kmp_*
}
kmp_job_read $::env(KMP_GDS)
kmp_job_load $::env(KMP_TOP)
if {[kmp_extract_flag KMP_MAKEALL]} {
    port makeall
    select top cell
}
catch {kmp_job_say "KMP_EXTRACT_PORTS [port last]"}

extract path $dir
if {$caps} {
    extract do capacitance
    extract do coupling
} else {
    extract no capacitance
    extract no coupling
}
extract no resistance
extract no length

kmp_job_stage extracting 0
set us [kmp_job_us {
    if {[catch {extract all} err]} {
        kmp_job_fail "extract all failed: $err"
    }
}]
kmp_job_say "KMP_EXTRACT_US $us"

kmp_job_stage writing 0
ext2spice lvs
if {$caps} {
    ext2spice cthresh 0
}
if {[catch {ext2spice -p $dir -o [file join $dir $out]} err]} {
    kmp_job_fail "ext2spice failed: $err"
}
if {![file exists [file join $dir $out]]} {
    kmp_job_fail "ext2spice wrote no netlist"
}
kmp_job_done 1
