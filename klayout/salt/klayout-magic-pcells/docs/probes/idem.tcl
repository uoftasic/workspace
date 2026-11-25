rename ::puts ::kmp_real_puts
proc ::puts {args} {
   set a $args; set nonl 0
   if {[lindex $a 0] eq "-nonewline"} {set nonl 1; set a [lrange $a 1 end]}
   if {[llength $a] == 2 && [lindex $a 0] eq "stderr"} { append ::kmp_log [lindex $a 1] "\n"; return }
   uplevel 1 [list ::kmp_real_puts {*}$args]
}
proc diff {a b} {
   set out {}
   dict for {k v} $b { if {![dict exists $a $k] || [dict get $a $k] ne $v} { lappend out $k "[expr {[dict exists $a $k] ? [dict get $a $k] : {-}}] -> $v" } }
   return $out
}
foreach {dev user} {
  sky130_fd_pr__res_high_po_0p69 {w 1.0}
  sky130_fd_pr__res_high_po_0p69 {l 0.1}
  sky130_fd_pr__res_high_po_0p69 {l 0}
  sky130_fd_pr__res_high_po_0p69 {l 5 nx 2}
  sky130_fd_pr__cap_mim_m3_1 {l 0 val 50}
  sky130_fd_pr__cap_mim_m3_1 {square 1 val 100}
  sky130_fd_pr__cap_mim_m3_1 {w 50}
  sky130_fd_pr__diode_pd2nw_05v5 {}
  sky130_fd_pr__diode_pd2nw_05v5 {w 2 l 3}
  sky130_fd_pr__nfet_01v8 {l 0.1 w 0.1 nf 0}
  sky130_fd_pr__res_xhigh_po_0p35 {l 3}
  sky130_fd_pr__res_generic_m1 {}
} {
  set ::kmp_log {}
  set d0 [magic::gencell_defaults $dev sky130 $user]
  set c1 [sky130::${dev}_check $d0]
  set log1 $::kmp_log; set ::kmp_log {}
  set c2 [sky130::${dev}_check $c1]
  set log2 $::kmp_log
  set h1 [magic::get_gencell_hash $c1]; set h2 [magic::get_gencell_hash $c2]
  kmp_real_puts "== $dev {$user}"
  kmp_real_puts "   check1 changes: [diff $d0 $c1]  msgs: [string map {\n { | }} [string trim $log1]]"
  kmp_real_puts "   check2 changes: [diff $c1 $c2]  msgs: [string map {\n { | }} [string trim $log2]]"
  kmp_real_puts "   hash1 $h1 hash2 $h2 [expr {$h1 eq $h2 ? {IDEMPOTENT} : {DIFFERENT}}]"
}
quit -noprompt
