# Procs shared by the job scripts (jobs.py runs one Magic process per job).
#
# Every job script starts with
#
#   source $::env(KMP_TCL_DIR)/kmp_job_common.tcl
#
# and talks to jobs.py only through these lines on stdout:
#
#   KMP_JOB_SCALE <um per Magic unit>   after gds read ([cif scale out])
#   KMP_JOB <stage> <n>                 progress
#   KMP_JOB_FAIL <message>              the job failed; Magic quits
#   KMP_JOB_DONE <n>                    the job finished; Magic quits
#
# A job without its done line has failed, whatever Magic's exit status:
# Magic exits 0 after a Tcl error in its startup script. Results go into
# files in $::env(KMP_DIR). A cell name from the user's layout reaches Tcl
# only as the value of a variable, never as script text. Magic's batch Tcl
# has no clock command, so times come from Tcl's time (kmp_job_us).

# stdout is a pipe: without line buffering the progress lines would reach
# jobs.py only when Magic exits.
fconfigure stdout -buffering line

proc kmp_job_say {text} {
    puts stdout $text
    flush stdout
}

proc kmp_job_stage {name {n 0}} {
    kmp_job_say "KMP_JOB $name $n"
}

proc kmp_job_fail {msg} {
    kmp_job_say "KMP_JOB_FAIL [string map {\n { } \r { }} $msg]"
    quit -noprompt
}

proc kmp_job_done {{n 0}} {
    kmp_job_say "KMP_JOB_DONE $n"
    quit -noprompt
}

# Microseconds the script takes, run in the caller's frame.
proc kmp_job_us {script} {
    set t [uplevel 1 [list time $script 1]]
    return [lindex $t 0]
}

# Read the GDS file and say Magic's output scale. The scale must come from
# this process: Magic rescales its units when a file has coordinates off
# its grid ("units rescaled by factor of 5 / 1"). DRC stays off during the
# read; the job checks when it wants to.
proc kmp_job_read {path} {
    catch {crashbackups stop}
    drc off
    if {[catch {gds read $path} err]} {
        kmp_job_fail "gds read $path failed: $err"
    }
    kmp_job_say "KMP_JOB_SCALE [cif scale out]"
}

# Load one cell as the edit cell, or fail the job. Magic does not always say
# when a load went wrong: for a name it doesn't know it creates a new empty
# cell; for "x/y" it loads an empty "y"; for "br[0]" it keeps the cell it
# had. So the name must be one Magic read, the cell Magic has loaded after
# the load must be that one, and it must not be empty.
proc kmp_job_load {cell} {
    if {[lsearch -exact [cellname list allcells] $cell] < 0} {
        kmp_job_fail "cell $cell is not among the cells Magic read from the file"
    }
    select clear
    if {[catch {load $cell} err]} {
        kmp_job_fail "load $cell failed: $err"
    }
    # cellname list self names the selected cell: select the new top cell
    # first, or it still names the cell loaded before.
    select top cell
    set self [lindex [cellname list self] 0]
    if {$self ne $cell} {
        kmp_job_fail "load $cell left the cell $self loaded"
    }
    set bb [box values]
    if {[llength $bb] != 4} {
        kmp_job_fail "cell $cell has no bounding box"
    }
    lassign $bb l b r t
    set w [expr {$r - $l}]
    set h [expr {$t - $b}]
    if {$w <= 0 || $h <= 0} {
        kmp_job_fail "cell $cell has an empty bounding box"
    }
    # A cell with nothing in it has the box 0 0 1 1; look inside a box that
    # small before calling it empty.
    if {$w <= 1 && $h <= 1} {
        select area
        set what [what -list]
        select clear
        set n 0
        foreach part $what { incr n [llength $part] }
        if {$n == 0} {
            kmp_job_fail "cell $cell is empty"
        }
        select top cell
    }
}

proc kmp_job__visit {cell seenVar orderVar} {
    upvar 1 $seenVar seen $orderVar order
    if {[dict exists $seen $cell]} {
        return
    }
    dict set seen $cell 1
    foreach child [cellname list children $cell] {
        kmp_job__visit $child seen order
    }
    lappend order $cell
}

# Every cell definition under top, children before their parents, then top.
proc kmp_job_cells {top} {
    set seen [dict create]
    set order {}
    kmp_job__visit $top seen order
    return $order
}
