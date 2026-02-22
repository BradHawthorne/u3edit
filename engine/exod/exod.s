; ===========================================================================
; EXOD.s — Ultima III: Exodus Boot Loader & Title Sequence
; ===========================================================================
;
; 26,208 bytes at $2000. 87% data (HGR animation frames, tile graphics),
; 13% code (title screen, intro animation, sound, Mockingboard init).
; Reassembled byte-identical from CIDAR disassembly via asmiigs.
;
; Memory Layout:
;   $2000-$2003  Entry — JMP to init code at $8220+
;   $2003-$81FF  Data — HGR animation frames, tile graphics, glyph data (~25 KB)
;   $8220-$86FF  Code — Title sequence, animation engine, HGR ops, audio
;
; Code Functions ($8220+):
;   $823D  intro_print_string     — Print high-ASCII string from $FE/$FF
;   $825E  intro_sequence         — Main intro sequence orchestrator
;   $82E6  intro_wipe_title       — Title screen wipe animation
;   $832A  intro_wipe_serpent     — Serpent wipe with mask transition
;   $836E  intro_load_castle      — Load castle scene graphic
;   $8384  intro_text_crawl       — Vertical text scroll animation
;   $83AD  intro_load_exodus      — Load Exodus graphic
;   $83BF  intro_load_frame_3     — Load animation frame 3
;   $83D1  intro_load_frame_4     — Load animation frame 4
;   $83E3  intro_hgr_blit         — HGR block blit with transparency
;   $844C  intro_plot_pair        — Plot character pair at position
;   $8453  intro_plot_pixel       — Plot single HGR pixel
;   $84A4  intro_memcpy           — Block memory copy (X pages)
;   $84BF  intro_memswap          — Swap memory blocks (page flip)
;   $84E6  intro_check_key        — Poll keyboard with timeout
;   $850C  intro_sound_effect     — Speaker tone generation
;   $8548  intro_prng_mod         — PRNG with modulo
;   $856A  intro_reveal_anim      — Progressive column reveal animation
;   $85B8  intro_draw_column      — Draw single glyph column
;
; Note: EXOD contains no patchable data tables — the $2003-$81FF region
; is entirely HGR animation frame data (anim_data_* labels).
;
; Architecture:
;   - HGR 140x192 with page 1/2 double-buffering ($C054/$C055)
;   - Data-driven animation via EQU pointer tables
;   - Self-modifying code for address patching (glyph/source pointers)
;   - Speaker audio at $C030, keyboard at $C000/$C010
;
; === Optimization Hints Report ===
; Total hints: 10
; Estimated savings: 54 cycles/bytes

; Address   Type              Priority  Savings  Description
; ---------------------------------------------------------------
; $0083C7   REDUNDANT_LOAD    MEDIUM    3        Redundant LDA: same value loaded at $0083C3
; $008629   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $008614
; $0082E2   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $0082E2 followed by RTS
; $008326   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $008326 followed by RTS
; $00836A   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $00836A followed by RTS
; $008380   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $008380 followed by RTS
; $0083BB   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $0083BB followed by RTS
; $0083CD   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $0083CD followed by RTS
; $0083DF   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $0083DF followed by RTS
; $0085A5   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $0085A5 followed by RTS

; Loop Analysis Report
; ====================
; Total loops: 23
;   for:       0
;   while:     18
;   do-while:  0
;   infinite:  0
;   counted:   5
; Max nesting: 2
;
; Detected Loops:
;   Header    Tail      Type      Nest  Counter
;   ------    ----      ----      ----  -------
;   $0084B0   $0084B5   while        1  Y: 0 step 1
;   $0084B0   $0084BC   counted      1  X: 0 step -1
;   $0084D1   $0084DC   while        1  Y: 0 step 1
;   $0084D1   $0084E3   counted      1  X: 4 step -1
;                       ~4 iterations
;   $00828D   $008296   counted      1  Y: 5 step -1
;                       ~5 iterations
;   $00828B   $00829B   while        0  -
;   $008414   $00843E   while        2  Y: 0 step 1
;   $0083F2   $008446   while        1  Y: 0 step 1
;   $0082F6   $00830B   while        1  -
;   $0082E2   $0084F9   while        0  Y: 0 step 1
;   $0084E6   $0084F1   counted      1  Y: 0 step -1
;   $00833A   $00834F   while        1  -
;   $00838C   $0083A9   while        1  -
;   $00862B   $00863D   while        1  Y: 0 step 1
;   $008606   $008643   while        0  Y: 0 step 1
;   $00857C   $008591   while        2  -
;   $008577   $00859E   while        0  -
;   $008577   $0085A1   while        0  -
;   $00855C   $008565   while        0  -
;   $00851A   $00851B   counted      2  X: 0 step -1
;   $008514   $008522   while        0  -
;   $008514   $008526   while        0  -
;   $008245   $008254   while        0  -

; Call Site Analysis Report
; =========================
; Total call sites: 43
;   JSR calls:      41
;   JSL calls:      2
;   Toolbox calls:  0
;
; Parameter Statistics:
;   Register params: 18
;   Stack params:    2
;
; Calling Convention Analysis:
;   Predominantly short calls (JSR/RTS)
;   Register-based parameter passing
;
; Call Sites (first 20):
;   $0020DC: JSR $00E420
;   $0020FB: JSR $00E41E
;   $0021B8: JSR $003032
;   $0022D4: JSR $00E420
;   $0022D7: JSR $003038
;   $0022F3: JSR $00E41E
;   $0022F6: JSR $003030
;   $002C9F: JSR $00531F
;   $002CB9: JSR $001304
;   $0035C7: JSR $003E30 params: stack
;   $0036C0: JSR $005003
;   $006268: JSR $000000
;   $006368: JSR $000000
;   $006A68: JSR $000000
;   $006D68: JSL $011844
;   $007557: JSR $001048
;   $007568: JSL $014846
;   $007957: JSR $003908
;   $00796D: JSR $002078
;   $007DE8: JSR $000000
;   ... and 23 more call sites

; === I/O Pattern Sequences: 1 detected ===
;   $8270: video_mode_read - Hi-res graphics mode

; === Stack Frame Analysis (Sprint 5.3) ===
; Functions with frames: 22

; Function $002000: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00823D: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00825E: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0082E6: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;      +32: param_32 (2 bytes, 3 accesses)

; Function $00832A: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +131: param_131 (2 bytes, 3 accesses)

; Function $00836E: none
;   Frame: 0 bytes, Locals: 0, Params: 4
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +160: param_160 (2 bytes, 1 accesses)
;      +96: param_96 (2 bytes, 1 accesses)

; Function $008384: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0083AD: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0083BF: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0083D1: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0083E3: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00844C: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $008453: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $008476: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0084A4: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0084BF: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0084E6: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0084FC: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00850C: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $008548: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00856A: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0085B8: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no


; === Liveness Analysis Summary (Sprint 5.4) ===
; Functions analyzed: 22
; Functions with register params: 11
; Functions with register returns: 22
; Total dead stores detected: 72 (in 11 functions)
;
; Function Details:
;   $002000: params(XY) returns(AXY) [20 dead]
;   $00823D: params(X) returns(AXY) [2 dead]
;   $00825E: returns(AXY) [14 dead]
;   $0082E6: returns(AXY) [7 dead]
;   $00832A: returns(AXY) [7 dead]
;   $00836E: returns(AXY) 
;   $008384: params(Y) returns(AXY) 
;   $0083AD: returns(AXY) 
;   $0083BF: returns(AXY) 
;   $0083D1: returns(AXY) 
;   $0083E3: params(AXY) returns(AXY) [6 dead]
;   $00844C: returns(AXY) 
;   $008453: returns(AXY) 
;   $008476: params(AXY) returns(AXY) 
;   $0084A4: params(AXY) returns(AXY) 
;   $0084BF: returns(AXY) 
;   $0084E6: params(XY) returns(AXY) [1 dead]
;   $0084FC: params(XY) returns(AXY) [1 dead]
;   $00850C: params(Y) returns(AXY) 
;   $008548: params(AXY) returns(AXY) [1 dead]
;   $00856A: returns(AXY) [4 dead]
;   $0085B8: params(AXY) returns(AXY) [9 dead]

; Function Signature Report
; =========================
; Functions analyzed:    22
;   Leaf functions:      7
;   Interrupt handlers:  3
;   Stack params:        0
;   Register params:     21
;
; Function Signatures:
;   Entry     End       Conv       Return   Frame  Flags
;   -------   -------   --------   ------   -----  -----
;   $002000   $00823D   register   A:X         0   JI
;     Proto: uint32_t func_002000(uint16_t param_X, uint16_t param_Y);
;   $00823D   $00825E   register   A:X         0   
;     Proto: uint32_t func_00823D(uint16_t param_X);
;   $00825E   $0082E6   register   A:X         0   
;   $0082E6   $00832A   register   A:X         0   
;   $00832A   $00836E   register   A:X         0   
;   $00836E   $008384   register   A:X         0   
;     Proto: uint32_t func_00836E(void);
;   $008384   $0083AD   register   A:X         0   I
;     Proto: uint32_t func_008384(uint16_t param_Y);
;   $0083AD   $0083BF   register   A:X         0   
;     Proto: uint32_t func_0083AD(void);
;   $0083BF   $0083D1   register   A:X         0   
;     Proto: uint32_t func_0083BF(void);
;   $0083D1   $0083E3   register   A:X         0   
;     Proto: uint32_t func_0083D1(void);
;   $0083E3   $00844C   register   A:X         0   LI
;     Proto: uint32_t func_0083E3(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $00844C   $008453   unknown    A:X         0   
;   $008453   $008476   register   A:X         0   L
;     Proto: uint32_t func_008453(void);
;   $008476   $0084A4   register   A:X         0   
;     Proto: uint32_t func_008476(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $0084A4   $0084BF   register   A:X         0   L
;     Proto: uint32_t func_0084A4(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $0084BF   $0084E6   register   A:X         0   L
;     Proto: uint32_t func_0084BF(void);
;   $0084E6   $0084FC   register   A:X         0   
;     Proto: uint32_t func_0084E6(uint16_t param_X, uint16_t param_Y);
;   $0084FC   $00850C   register   A:X         0   L
;     Proto: uint32_t func_0084FC(uint16_t param_X, uint16_t param_Y);
;   $00850C   $008548   register   A:X         0   
;     Proto: uint32_t func_00850C(uint16_t param_Y);
;   $008548   $00856A   register   A:X         0   L
;     Proto: uint32_t func_008548(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $00856A   $0085B8   register   A:X         0   
;   $0085B8   $008660   register   A:X         0   L
;     Proto: uint32_t func_0085B8(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;
; Flags: L=Leaf, J=JSL/RTL, I=Interrupt, F=FrameSetup

; Constant Propagation Analysis
; =============================
; Constants found: 38
; Loads with known value: 35
; Branches resolved: 0
; Compares resolved: 0
; Memory constants tracked: 5
;
; Final register state:
;   A: unknown
;   X: unknown
;   Y: unknown
;   S: [$0100-$01FF]
;   DP: undefined
;   DBR: undefined
;   PBR: undefined
;   P: undefined
;
; Memory constants (first 20):
;   $00000D = $0098 (dp)
;   $000004 = $0000 (dp)
;   $0000AA = $00FF (dp)
;   $000014 = $00FF (dp)
;   $000010 = $0080 (abs)

; ============================================================================
; TYPE INFERENCE REPORT
; ============================================================================
;
; Entries analyzed: 495
; Bytes typed:      93
; Words typed:      94
; Pointers typed:   4
; Arrays typed:     194
; Structs typed:    358
;
; Inferred Types:
;   Address   Type       Conf   R    W   Flags  Name
;   -------   --------   ----   ---  --- -----  ----
;   $000030   ARRAY      95%    76    0 IP     arr_0030 [elem=1]
;   $000034   BYTE       80%     7    0 IP     byte_0034
;   $001E30   WORD       90%    19    0        word_1E30
;   $000000   STRUCT     80%   498    4 IP     struct_0000 {size=29}
;   $000020   FLAG       90%    40    0 P      flag_0020
;   $00000D   ARRAY      85%    13    2 IP     arr_000D [elem=1]
;   $000031   BYTE       80%    15    0 IP     byte_0031
;   $000038   BYTE       90%    16    0 IP     byte_0038
;   $000037   BYTE       90%    17    0 P      byte_0037
;   $003330   ARRAY      75%     1    0 I      arr_3330 [elem=1]
;   $000043   BYTE       90%    22    0 IP     byte_0043
;   $00004E   BYTE       50%     2    0 P      byte_004E
;   $001E38   WORD       50%     2    0        word_1E38
;   $00001E   BYTE       70%     5    0 P      byte_001E
;   $000033   BYTE       70%     6    1 IP     byte_0033
;   $001E43   WORD       50%     2    0        word_1E43
;   $000035   ARRAY      75%     4    2 IP     arr_0035 [elem=1]
;   $000036   BYTE       90%     9    2 IP     byte_0036
;   $000042   BYTE       50%     2    0 P      byte_0042
;   $000046   BYTE       60%     5    0 IP     byte_0046
;   $000045   ARRAY      80%     3    0 IP     arr_0045 [elem=1]
;   $000009   BYTE       90%     6    1 P      byte_0009
;   $000004   BYTE       90%     6    4 P      byte_0004
;   $000056   BYTE       50%     2    0        byte_0056
;   $000008   PTR        80%     9    1 IP     ptr_0008
;   $000040   BYTE       90%    41    0 IP     byte_0040
;   $00017C   LONG       50%     3    0        long_017C
;   $00007E   ARRAY      90%    10    0 IP     arr_007E [elem=1]
;   $00005F   BYTE       90%     9    0 IP     byte_005F
;   $005C00   ARRAY      75%     1    0 I      arr_5C00 [elem=1]
;   $000078   ARRAY      75%    24    0 IP     arr_0078 [elem=1]
;   $710000   LONG       70%     4    0        long_710000
;   $000058   BYTE       90%    30    0 P      byte_0058
;   $000068   BYTE       90%     9    0 IP     byte_0068
;   $000001   BYTE       90%    64    3 IP     byte_0001
;   $000006   BYTE       90%   102    0 IP     byte_0006
;   $000E00   STRUCT     70%     4    0 I      struct_0E00 {size=15}
;   $003F00   WORD       50%     2    0        word_3F00
;   $000070   BYTE       90%    29    0 P      byte_0070
;   $000378   ARRAY      80%     3    0 I      arr_0378 [elem=1]
;   $006167   ARRAY      75%     1    0 I      arr_6167 [elem=1]
;   $003E03   ARRAY      90%     4    0 I      arr_3E03 [elem=1]
;   $000060   BYTE       90%    98    0 IP     byte_0060
;   $003E00   STRUCT     70%     0    0        struct_3E00 {size=4}
;   $00003E   BYTE       90%     9    2 IP     byte_003E
;   $007000   ARRAY      95%    20    0 I      arr_7000 [elem=1]
;   $003E01   ARRAY      80%     2    0 I      arr_3E01 [elem=1]
;   $00005C   BYTE       70%     4    0 P      byte_005C
;   $000018   BYTE       90%    11    5 P      byte_0018
;   $00000C   BYTE       90%    20    1 IP     byte_000C
;   $001800   ARRAY      80%     2    0 I      arr_1800 [elem=1]
;   $000003   BYTE       90%    40    0 IP     byte_0003
;   $004000   ARRAY      80%     3    0 I      arr_4000 [elem=1]
;   $000161   ARRAY      75%     1    0 I      arr_0161 [elem=1]
;   $000061   BYTE       90%    12    0 P      byte_0061
;   $00004F   BYTE       60%     3    0 P      byte_004F
;   $007C06   ARRAY      90%     4    0 I      arr_7C06 [elem=1]
;   $000057   BYTE       50%     2    0 P      byte_0057
;   $006000   ARRAY      75%     5    0 I      arr_6000 [elem=1]
;   $000063   BYTE       90%     8    0 IP     byte_0063
;   $007C02   ARRAY      85%     3    0 I      arr_7C02 [elem=1]
;   $00007D   BYTE       60%     3    0 P      byte_007D
;   $003801   ARRAY      85%     3    0 I      arr_3801 [elem=1]
;   $000021   BYTE       70%     4    0 P      byte_0021
;   $001806   ARRAY      85%     3    0 I      arr_1806 [elem=1]
;   $005000   WORD       60%     3    0        word_5000
;   $780D7B   LONG       50%     2    0        long_780D7B
;   $004001   ARRAY      80%     2    0 I      arr_4001 [elem=1]
;   $0D4006   LONG       60%     3    0        long_D4006
;   $000643   WORD       50%     2    0        word_0643
;   $000079   BYTE       60%     4    0 IP     byte_0079
;   $000071   BYTE       90%    12    2 IP     byte_0071
;   $000E26   WORD       50%     2    0        word_0E26
;   $000007   BYTE       90%    19    0 IP     byte_0007
;   $007E01   ARRAY      80%     2    0 I      arr_7E01 [elem=1]
;   $000047   BYTE       70%     4    0 P      byte_0047
;   $00003F   BYTE       80%     5    0        byte_003F
;   $00001B   ARRAY      90%     8    4 I      arr_001B [elem=1]
;   $000B77   WORD       50%     2    0        word_0B77
;   $00000B   ARRAY      80%     6    9 I      arr_000B [elem=1]
;   $000E06   ARRAY      75%     4    0 I      arr_0E06 [elem=1]
;   $000005   BYTE       90%    10    1        byte_0005
;   $0E0006   LONG       50%     2    0        long_E0006
;   $00000E   BYTE       90%    15    1 I      byte_000E
;   $000C1F   ARRAY      95%     5    0 I      arr_0C1F [elem=1]
;   $00400C   ARRAY      80%     2    0 I      arr_400C [elem=1]
;   $000066   BYTE       70%     4    0 P      byte_0066
;   $000E0D   WORD       50%     2    0        word_0E0D
;   $7F0000   LONG       60%     3    0        long_7F0000
;   $003E0D   ARRAY      80%     2    0 I      arr_3E0D [elem=1]
;   $006037   WORD       50%     2    0        word_6037
;   $00000F   ARRAY      85%     8    0 IP     arr_000F [elem=1]
;   $001C0C   ARRAY      75%     1    0 I      arr_1C0C [elem=1]
;   $000D00   STRUCT     70%     6    0        struct_0D00 {size=14}
;   $00007B   BYTE       80%     6    0 I      byte_007B
;   $001C00   STRUCT     70%     2    0 I      struct_1C00 {size=1}
;   $00001C   ARRAY      75%     3    1 I      arr_001C [elem=1]
;   $001839   ARRAY      75%     1    0 I      arr_1839 [elem=1]
;   $00001F   BYTE       90%    13    2 IP     byte_001F
;   $007E19   ARRAY      75%     1    0 I      arr_7E19 [elem=1]
;   $00406F   ARRAY      75%     1    0 I      arr_406F [elem=1]
;   $007C00   ARRAY      75%     3    0 I      arr_7C00 [elem=1]
;   $110000   LONG       60%     3    0        long_110000
;   $000019   BYTE       90%     5    3        byte_0019
;   $004063   ARRAY      75%     1    0 I      arr_4063 [elem=1]
;   $000F0E   WORD       50%     2    0        word_0F0E
;   $316000   LONG       50%     2    0        long_316000
;   $000C00   ARRAY      75%     1    0 I      arr_0C00 [elem=1]
;   $000E0E   ARRAY      75%     7    0 I      arr_0E0E [elem=1]
;   $007E00   ARRAY      75%     2    0 I      arr_7E00 [elem=1]
;   $000770   ARRAY      75%     1    0 I      arr_0770 [elem=1]
;   $000044   BYTE       60%     3    0 P      byte_0044
;   $00070E   WORD       50%     2    0        word_070E
;   $000041   BYTE       70%     4    0 P      byte_0041
;   $00070F   WORD       50%     2    0        word_070F
;   $000703   WORD       60%     3    0        word_0703
;   $004007   ARRAY      75%     1    0 I      arr_4007 [elem=1]
;   $007C01   ARRAY      75%     1    0 I      arr_7C01 [elem=1]
;   $005F26   ARRAY      75%     1    0 I      arr_5F26 [elem=1]
;   $000C0F   ARRAY      75%     1    0 I      arr_0C0F [elem=1]
;   $000E40   ARRAY      75%     1    0 I      arr_0E40 [elem=1]
;   $00181F   ARRAY      75%     1    0 I      arr_181F [elem=1]
;   $000646   WORD       50%     2    0        word_0646
;   $406300   LONG       50%     2    0        long_406300
;   $007F0D   ARRAY      80%     2    0 I      arr_7F0D [elem=1]
;   $003E4C   ARRAY      75%     1    0 I      arr_3E4C [elem=1]
;   $000B4C   ARRAY      75%     1    0 I      arr_0B4C [elem=1]
;   $006F59   ARRAY      80%     2    0 I      arr_6F59 [elem=1]
;   $005A7D   ARRAY      75%     1    0 I      arr_5A7D [elem=1]
;   $007800   WORD       50%     2    0        word_7800
;   $00006C   BYTE       60%     4    0 IP     byte_006C
;   $000002   BYTE       90%    79    0 P      byte_0002
;   $003073   ARRAY      75%     1    0 I      arr_3073 [elem=1]
;   $007F40   ARRAY      75%     1    0 I      arr_7F40 [elem=1]
;   $00015F   ARRAY      75%     1    0 I      arr_015F [elem=1]
;   $000072   BYTE       60%     4    0 IP     byte_0072
;   $00007C   ARRAY      85%    19    0 IP     arr_007C [elem=1]
;   $003E67   ARRAY      75%     1    0 I      arr_3E67 [elem=1]
;   $001403   ARRAY      75%     1    0 I      arr_1403 [elem=1]
;   $003E37   ARRAY      75%     1    0 I      arr_3E37 [elem=1]
;   $003E79   ARRAY      75%     1    0 I      arr_3E79 [elem=1]
;   $006003   ARRAY      80%     2    0 I      arr_6003 [elem=1]
;   $003E31   ARRAY      75%     1    0 I      arr_3E31 [elem=1]
;   $000028   BYTE       50%     2    0        byte_0028
;   $007C6E   ARRAY      75%     1    0 I      arr_7C6E [elem=1]
;   $004008   WORD       50%     2    0        word_4008
;   $007D72   ARRAY      75%     1    0 I      arr_7D72 [elem=1]
;   $000706   WORD       60%     3    0        word_0706
;   $004707   WORD       50%     2    0        word_4707
;   $00007F   BYTE       80%     8    0 IP     byte_007F
;   $000022   BYTE       60%     3    0 P      byte_0022
;   $000011   ARRAY      80%     7    3 IP     arr_0011 [elem=1]
;   $00408C   ARRAY      75%     1    0 I      arr_408C [elem=1]
;   $000707   WORD       50%     2    0        word_0707
;   $000700   STRUCT     75%     0    0        struct_0700 {size=8}
;   $000E2C   ARRAY      75%     1    0 I      arr_0E2C [elem=1]
;   $000C1C   ARRAY      75%     1    0 I      arr_0C1C [elem=1]
;   $007F19   ARRAY      75%     1    0 I      arr_7F19 [elem=1]
;   $003E58   ARRAY      75%     1    0 I      arr_3E58 [elem=1]
;   $000077   BYTE       50%     2    0 P      byte_0077
;   $000017   BYTE       90%     4    5        byte_0017
;   $0000B1   ARRAY      85%     3    0 I      arr_00B1 [elem=1]
;   $001C18   ARRAY      75%     1    0 I      arr_1C18 [elem=1]
;   $0000C0   ARRAY      75%     1    0 I      arr_00C0 [elem=1]
;   $001A30   ARRAY      75%     1    0 I      arr_1A30 [elem=1]
;   $003873   ARRAY      75%     1    0 I      arr_3873 [elem=1]
;   $005F03   ARRAY      75%     1    0 I      arr_5F03 [elem=1]
;   $00380A   ARRAY      75%     1    0 I      arr_380A [elem=1]
;   $003070   ARRAY      75%     1    0 I      arr_3070 [elem=1]
;   $005F01   ARRAY      75%     1    0 I      arr_5F01 [elem=1]
;   $000050   BYTE       60%     3    0 P      byte_0050
;   $000437   ARRAY      75%     1    0 I      arr_0437 [elem=1]
;   $007C0D   ARRAY      75%     1    0 I      arr_7C0D [elem=1]
;   $007C05   ARRAY      85%     3    0 I      arr_7C05 [elem=1]
;   $000713   WORD       50%     2    0        word_0713
;   $00061F   ARRAY      75%     1    0 I      arr_061F [elem=1]
;   $001F06   ARRAY      75%     1    0 I      arr_1F06 [elem=1]
;   $006300   ARRAY      75%     1    0 I      arr_6300 [elem=1]
;   $003818   ARRAY      80%     2    0 I      arr_3818 [elem=1]
;   $003800   STRUCT     70%     0    0        struct_3800 {size=25}
;   $00381C   ARRAY      75%     1    0 I      arr_381C [elem=1]
;   $005F19   ARRAY      75%     1    0 I      arr_5F19 [elem=1]
;   $001838   ARRAY      75%     1    0 I      arr_1838 [elem=1]
;   $003430   WORD       90%     6    0        word_3430
;   $000025   BYTE       90%     7    0 P      byte_0025
;   $003400   STRUCT     70%     0    0        struct_3400 {size=49}
;   $00213D   ARRAY      85%     3    0 I      arr_213D [elem=1]
;   $000029   BYTE       60%     3    0        byte_0029
;   $003531   WORD       60%     3    0        word_3531
;   $00223D   ARRAY      85%     3    0 I      arr_223D [elem=1]
;   $00002A   BYTE       60%   124    0 I      byte_002A
;   $003632   WORD       90%     6    0        word_3632
;   $002622   ARRAY      85%     3    0 I      arr_2622 [elem=1]
;   $002723   ARRAY      85%     3    0 I      arr_2723 [elem=1]
;   $3B3733   LONG       90%     6    0        long_3B3733
;   $000D0D   WORD       50%     2    0        word_0D0D
;   $000015   ARRAY      85%     4    2 I      arr_0015 [elem=1]
;   $000016   ARRAY      90%     4    0 I      arr_0016 [elem=1]
;   $001919   ARRAY      80%     2    0 I      arr_1919 [elem=1]
;   $001A1A   ARRAY      75%     1    0 I      arr_1A1A [elem=1]
;   $001900   STRUCT     70%     0    0        struct_1900 {size=26}
;   $001D1D   ARRAY      80%     2    0 I      arr_1D1D [elem=1]
;   $001E1E   ARRAY      80%     2    0 I      arr_1E1E [elem=1]
;   $001D00   STRUCT     70%     0    0        struct_1D00 {size=30}
;   $001F1E   ARRAY      75%     1    0 I      arr_1F1E [elem=1]
;   $001E00   STRUCT     70%     0    0        struct_1E00 {size=153}
;   $000024   BYTE       60%     3    0        byte_0024
;   $000026   BYTE       60%     3    0        byte_0026
;   $0000AA   ARRAY      95%   995   18 IP     arr_00AA [elem=1]
;   $00E015   ARRAY      80%     2    0 I      arr_E015 [elem=1]
;   $00D500   LONG       50%     2    0        long_D500
;   $0000A2   ARRAY      95%    14    0 I      arr_00A2 [elem=1]
;   $00008A   ARRAY      95%    14    0 IP     arr_008A [elem=1]
;   $000080   ARRAY      95%    45   20 IP     arr_0080 [elem=1]
;   $000082   ARRAY      95%     7    2 IP     arr_0082 [elem=1]
;   $0000A8   BYTE       60%     1    3 I      byte_00A8
;   $0000A0   ARRAY      80%     2    3 IP     arr_00A0 [elem=1]
;   $000088   ARRAY      80%     0    4 I      arr_0088 [elem=1]
;   $008080   ARRAY      80%     2    3 I      arr_8080 [elem=1]
;   $0000E8   PTR        80%     1    0 P      ptr_00E8
;   $000081   BYTE       60%     3    0        byte_0081
;   $0000DF   BYTE       50%     1    2 IP     byte_00DF
;   $00DC80   ARRAY      75%     0    1 I      arr_DC80 [elem=1]
;   $0000F8   ARRAY      75%     1    0 I      arr_00F8 [elem=1]
;   $005530   WORD       90%    73    0        word_5530
;   $005500   STRUCT     70%     0    0        struct_5500 {size=49}
;   $00006A   ARRAY      95%    11    0 I      arr_006A [elem=1]
;   $401F60   LONG       80%     5    0        long_401F60
;   $00001A   ARRAY      95%    12    2 I      arr_001A [elem=1]
;   $005540   ARRAY      85%     6    0 I      arr_5540 [elem=1]
;   $007801   ARRAY      80%     2    0 I      arr_7801 [elem=1]
;   $00003A   ARRAY      95%     7    0 I      arr_003A [elem=1]
;   $700000   LONG       70%     4    0        long_700000
;   $002A55   WORD       90%    10    0        word_2A55
;   $00007A   ARRAY      75%     1    0 I      arr_007A [elem=1]
;   $001C38   ARRAY      75%     1    0 I      arr_1C38 [elem=1]
;   $007109   ARRAY      75%     1    0 I      arr_7109 [elem=1]
;   $00F881   ARRAY      75%     1    0 I      arr_F881 [elem=1]
;   $007C03   ARRAY      75%     1    0 I      arr_7C03 [elem=1]
;   $003001   ARRAY      75%     1    0 I      arr_3001 [elem=1]
;   $007F7F   ARRAY      80%     2    0 I      arr_7F7F [elem=1]
;   $005700   ARRAY      75%     1    0 I      arr_5700 [elem=1]
;   $00600F   ARRAY      75%     1    0 I      arr_600F [elem=1]
;   $00A080   ARRAY      75%     1    0 I      arr_A080 [elem=1]
;   $007E07   ARRAY      75%     1    0 I      arr_7E07 [elem=1]
;   $002A70   WORD       50%     2    0        word_2A70
;   $00002B   ARRAY      85%     3    0 I      arr_002B [elem=1]
;   $007820   ARRAY      75%     1    0 I      arr_7820 [elem=1]
;   $00080E   ARRAY      75%     1    0 I      arr_080E [elem=1]
;   $007F18   ARRAY      75%     1    0 I      arr_7F18 [elem=1]
;   $00077F   ARRAY      75%     1    0 I      arr_077F [elem=1]
;   $005F3D   ARRAY      75%     1    0 I      arr_5F3D [elem=1]
;   $00003C   BYTE       50%     2    0 P      byte_003C
;   $00003D   BYTE       50%     1    2 I      byte_003D
;   $003D62   ARRAY      75%     1    0 I      arr_3D62 [elem=1]
;   $00385F   ARRAY      75%     1    0 I      arr_385F [elem=1]
;   $005E36   ARRAY      75%     1    0 I      arr_5E36 [elem=1]
;   $00005D   ARRAY      75%     1    0 I      arr_005D [elem=1]
;   $005C33   ARRAY      75%     1    0 I      arr_5C33 [elem=1]
;   $005E32   ARRAY      75%     1    0 I      arr_5E32 [elem=1]
;   $00396C   ARRAY      75%     1    0 I      arr_396C [elem=1]
;   $00006B   ARRAY      75%     1    0 I      arr_006B [elem=1]
;   $000067   ARRAY      75%     1    0 I      arr_0067 [elem=1]
;   $003874   ARRAY      75%     1    0 I      arr_3874 [elem=1]
;   $000073   ARRAY      75%     1    0 I      arr_0073 [elem=1]
;   $000032   BYTE       50%     1    1 P      byte_0032
;   $000039   ARRAY      75%     2    0 I      arr_0039 [elem=1]
;   $003981   ARRAY      75%     1    0 I      arr_3981 [elem=1]
;   $00397E   ARRAY      75%     1    0 I      arr_397E [elem=1]
;   $007D38   ARRAY      75%     1    0 I      arr_7D38 [elem=1]
;   $003900   STRUCT     70%     0    0        struct_3900 {size=130}
;   $007F32   ARRAY      75%     1    0 I      arr_7F32 [elem=1]
;   $003A83   ARRAY      75%     1    0 I      arr_3A83 [elem=1]
;   $003892   ARRAY      75%     1    0 I      arr_3892 [elem=1]
;   $009A3F   ARRAY      75%     0    1 I      arr_9A3F [elem=1]
;   $003D9A   ARRAY      75%     1    0 I      arr_3D9A [elem=1]
;   $00993C   ARRAY      75%     0    1 I      arr_993C [elem=1]
;   $003996   ARRAY      75%     1    0 I      arr_3996 [elem=1]
;   $009938   ARRAY      75%     0    1 I      arr_9938 [elem=1]
;   $000098   ARRAY      75%     1    0 I      arr_0098 [elem=1]
;   $000097   ARRAY      75%     1    0 I      arr_0097 [elem=1]
;   $0039A5   ARRAY      75%     1    0 I      arr_39A5 [elem=1]
;   $0038AA   ARRAY      75%     1    0 I      arr_38AA [elem=1]
;   $0038B1   ARRAY      75%     1    0 I      arr_38B1 [elem=1]
;   $0039BC   ARRAY      75%     1    0 I      arr_39BC [elem=1]
;   $0000BA   ARRAY      75%     1    0 I      arr_00BA [elem=1]
;   $0000B9   ARRAY      75%     1    0 I      arr_00B9 [elem=1]
;   $00B833   ARRAY      75%     1    0 I      arr_B833 [elem=1]
;   $00BD3C   ARRAY      75%     1    0 I      arr_BD3C [elem=1]
;   $0039C1   ARRAY      75%     1    0 I      arr_39C1 [elem=1]
;   $0000C3   ARRAY      75%     1    0 I      arr_00C3 [elem=1]
;   $0038CC   ARRAY      75%     1    0 I      arr_38CC [elem=1]
;   $0000CB   ARRAY      75%     1    0 I      arr_00CB [elem=1]
;   $0000CA   ARRAY      75%     1    0 I      arr_00CA [elem=1]
;   $004C59   ARRAY      75%     1    0 I      arr_4C59 [elem=1]
;   $002082   ARRAY      75%     1    0 I      arr_2082 [elem=1]
;   $000482   ARRAY      75%     1    0 I      arr_0482 [elem=1]
;   $0000CE   ARRAY      75%     1    0 I      arr_00CE [elem=1]
;   $0000FE   PTR        80%     3    1 P      ptr_00FE
;   $0000FF   BYTE       80%     4    1 P      byte_00FF
;   $00C054   WORD       70%     4    0        word_C054
;   $00C000   STRUCT     70%     2    0        struct_C000 {size=86}
;   $00C010   WORD       50%     2    0        word_C010
;   $00000A   BYTE       90%     5   10        byte_000A
;   $001B00   ARRAY      90%     4    0 I      arr_1B00 [elem=1]
;   $000010   BYTE       90%     1    8 P      byte_0010
;   $001BC0   ARRAY      90%     4    0 I      arr_1BC0 [elem=1]
;   $000012   PTR        80%     2    3 P      ptr_0012
;   $000013   BYTE       50%     0    2        byte_0013
;   $000014   BYTE       90%     3    3        byte_0014
;   $00C030   WORD       60%     3    0        word_C030
;   $001C80   ARRAY      75%     1    0 I      arr_1C80 [elem=1]
;   $0000A9   BYTE       50%     1    1        byte_00A9
;   $008569   WORD       50%     1    1        word_8569
;   $008500   STRUCT     70%     0    0        struct_8500 {size=255}
;   $0085B5   ARRAY      75%     1    0 I      arr_85B5 [elem=1]
;   $0085A9   ARRAY      75%     1    0 I      arr_85A9 [elem=1]
;   $0085AC   ARRAY      75%     1    0 I      arr_85AC [elem=1]
;   $0085AF   ARRAY      75%     1    0 I      arr_85AF [elem=1]
;   $0085B2   ARRAY      75%     1    0 I      arr_85B2 [elem=1]
;   $001D84   ARRAY      75%     1    0 I      arr_1D84 [elem=1]
;   $000400   ARRAY      75%     1    0 I      arr_0400 [elem=1]
;   $000401   ARRAY      75%     1    0 I      arr_0401 [elem=1]
;   $001D80   ARRAY      75%     1    0 I      arr_1D80 [elem=1]
;   $001E98   ARRAY      75%     1    0 I      arr_1E98 [elem=1]
;   $001E80   ARRAY      75%     1    0 I      arr_1E80 [elem=1]
;   $001E9C   ARRAY      75%     1    0 I      arr_1E9C [elem=1]
;   $00FFFF   ARRAY      80%     3    0 I      arr_FFFF [elem=1]
;   $00862C   WORD       50%     1    1        word_862C
;   $00862D   WORD       50%     1    1        word_862D
;   $008600   STRUCT     70%     0    0        struct_8600 {size=46}
;   $001DA4   ARRAY      75%     1    0 I      arr_1DA4 [elem=1]

; ============================================================================
; SWITCH/CASE DETECTION REPORT
; ============================================================================
;
; Switches found:   118
;   Jump tables:    118
;   CMP chains:     0
;   Computed:       0
; Total cases:      1080
; Max cases/switch: 64
;
; Detected Switches:
;
; Switch #1 at $002447:
;   Type:       jump_table
;   Table:      $000001
;   Index Reg:  X
;   Cases:      0
;
; Switch #2 at $00244B:
;   Type:       jump_table
;   Table:      $003073
;   Index Reg:  X
;   Cases:      0
;
; Switch #3 at $002464:
;   Type:       jump_table
;   Table:      $007C33
;   Index Reg:  X
;   Cases:      0
;
; Switch #4 at $002524:
;   Type:       jump_table
;   Table:      $000001
;   Index Reg:  X
;   Cases:      0
;
; Switch #5 at $002601:
;   Type:       jump_table
;   Table:      $000001
;   Index Reg:  X
;   Cases:      0
;
; Switch #6 at $00260A:
;   Type:       jump_table
;   Table:      $000066
;   Index Reg:  X
;   Cases:      0
;
; Switch #7 at $002617:
;   Type:       jump_table
;   Table:      $00006E
;   Index Reg:  X
;   Cases:      0
;
; Switch #8 at $002624:
;   Type:       jump_table
;   Table:      $000172
;   Index Reg:  X
;   Cases:      0
;
; Switch #9 at $002631:
;   Type:       jump_table
;   Table:      $000062
;   Index Reg:  X
;   Cases:      0
;
; Switch #10 at $00266A:
;   Type:       jump_table
;   Table:      $003001
;   Index Reg:  X
;   Cases:      0
;
; Switch #11 at $00269E:
;   Type:       jump_table
;   Table:      $000001
;   Index Reg:  X
;   Cases:      0
;
; Switch #12 at $002849:
;   Type:       jump_table
;   Table:      $007C03
;   Index Reg:  X
;   Cases:      24
;     (too many cases to list - 24 total)
;
; Switch #13 at $0028BF:
;   Type:       jump_table
;   Table:      $00183F
;   Index Reg:  X
;   Cases:      0
;
; Switch #14 at $002954:
;   Type:       jump_table
;   Table:      $006F5A
;   Index Reg:  X
;   Cases:      9
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;         0   $008080     sw_2954_case_0
;         1   $008080     sw_2954_case_1
;         2   $00D5A8     sw_2954_case_2
;         3   $00D5AA     sw_2954_case_3
;         4   $00D5AA     sw_2954_case_4
;         5   $00D5AA     sw_2954_case_5
;         6   $00808A     sw_2954_case_6
;         7   $00FFF8     sw_2954_case_7
;         8   $0080E0     sw_2954_case_8
;
; Switch #15 at $00295B:
;   Type:       jump_table
;   Table:      $000007
;   Index Reg:  X
;   Cases:      0
;
; Switch #16 at $002968:
;   Type:       jump_table
;   Table:      $00000F
;   Index Reg:  X
;   Cases:      0
;
; Switch #17 at $002975:
;   Type:       jump_table
;   Table:      $00001F
;   Index Reg:  X
;   Cases:      0
;
; Switch #18 at $002982:
;   Type:       jump_table
;   Table:      $00183F
;   Index Reg:  X
;   Cases:      0
;
; Switch #19 at $002A12:
;   Type:       jump_table
;   Table:      $000001
;   Index Reg:  X
;   Cases:      0
;
; Switch #20 at $002A24:
;   Type:       jump_table
;   Table:      $005F33
;   Index Reg:  X
;   Cases:      0
;
; ... and 98 more switches

; Cross-Reference Report
; ======================
; Total references: 1247
;   Calls: 102  Jumps: 29  Branches: 1051  Data: 27
;
; Target Address  Type     From Address
; -------------- -------- --------------
; $000000         INDIRECT  $00786D
; $000000         CALL     $00279C
; $000000         CALL     $007239
;
; $000001         INDIRECT  $002447
; $000001         INDIRECT  $00269E
; $000001         INDIRECT  $00366B
; $000001         INDIRECT  $002601
; $000001         INDIRECT  $002524
; $000001         INDIRECT  $0075B2
; $000001         INDIRECT  $002AEF
; $000001         CALL     $0032CF
; $000001         INDIRECT  $00358E
;
; $000003         CALL     $003297
; $000003         CALL     $003855
; $000003         CALL     $002CD9
; $000003         CALL     $0033B8
;
; $000007         INDIRECT  $00760E
; $000007         INDIRECT  $003407
; $000007         INDIRECT  $0030AD
; $000007         INDIRECT  $003234
; $000007         INDIRECT  $0074B6
;
; $000008         INDIRECT  $0084A1
;
; $00000F         INDIRECT  $003414
;
; $00001C         JUMP     $002842
;
; $00001F         JUMP     $00633F
; $00001F         JUMP     $0029AA
;
; $000030         CALL     $002A17
;
; $000034         CALL     $002FD5
;
; $00003F         INDIRECT  $002F5B
; $00003F         INDIRECT  $0039EC
;
; $000051         CALL     $0031FE
;
; $000063         INDIRECT  $0024BC
; $000063         INDIRECT  $003AD7
;
; $000070         INDIRECT  $002505
;
; $000080         WRITE    $0066EA
;
; $0000E3         INDIRECT  $003519
;
; $000304         CALL     $003835
;
; $000341         CALL     $00388D
;
; $000378         INDIRECT  $00373A
;
; $000619         JUMP     $00266F
;
; $00065F         CALL     $0027B1
;
; $00075C         CALL     $0038F8
;
; $000C08         JUMP     $002869
;
; $000C1C         JUMP     $003989
;
; $000E1C         CALL     $00288E
;
; $000E1F         JUMP     $002D2F
;
; $000F78         INDIRECT  $00317C
;
; $00101C         CALL     $002EF6
;
; $001048         CALL     $007557
;
; $001118         CALL     $003A72
;
; $001304         CALL     $002CB9
;
; $001604         CALL     $003277
;
; $00161C         CALL     $002D7C
;
; $001800         INDIRECT  $002B58
;
; $00183F         INDIRECT  $00342E
; $00183F         INDIRECT  $0028BF
;
; $002020         CALL     $003E64
; $002020         CALL     $003E61
;
; $002038         BRANCH   $002003
;
; $002039         BRANCH   $002005
;
; $002040         BRANCH   $002009
;
; $002042         BRANCH   $00200F
;
; $002049         BRANCH   $002017
;
; $00204A         BRANCH   $002015
;
; $002057         BRANCH   $002022
;
; $002059         BRANCH   $002020
;
; $00205C         BRANCH   $002028
;
; $00205D         BRANCH   $002024
;
; $002060         BRANCH   $00202E
; $002060         BRANCH   $00202C
;
; $00206B         BRANCH   $002036
;
; $00206D         BRANCH   $002034
;
; $00206F         BRANCH   $00203D
;
; $002070         CALL     $00716D
;
; $002076         BRANCH   $002041
;
; $002078         CALL     $00796D
; $002078         BRANCH   $00203F
;
; $00207C         BRANCH   $002047
; $00207C         BRANCH   $002043
;
; $00207F         BRANCH   $00204D
;
; $002080         BRANCH   $00204B
;
; $002081         BRANCH   $00204F
;
; $00208D         BRANCH   $002055
;
; $00209B         BRANCH   $002053
;
; $00209E         BRANCH   $002066
; $00209E         BRANCH   $00206C
;
; $0020A2         BRANCH   $00206A
;
; $0020A4         BRANCH   $00205E
;
; $0020A8         BRANCH   $002062
;
; $0020AC         BRANCH   $002074
;
; $0020BD         BRANCH   $00208B
;
; $0020C8         BRANCH   $002093
;
; $0020CA         BRANCH   $002085
;
; $0020CE         BRANCH   $002089
;
; $0020DC         BRANCH   $0020AA
;
; $0020E5         BRANCH   $0020B2
;
; $0020E9         BRANCH   $0020A4
;
; $0020ED         BRANCH   $0020A8
;
; $0020FB         BRANCH   $0020C9
;
; $002102         BRANCH   $0020CF
;
; ... and 1147 more references

; Stack Depth Analysis Report
; ===========================
; Entry depth: 0
; Current depth: -16180
; Min depth: -16180 (locals space: 16180 bytes)
; Max depth: 0
;
; Stack Operations:
;   Push: 85  Pull: 110
;   JSR/JSL: 108  RTS/RTL: 314
;
; WARNING: Stack imbalance detected at $002428
;   Entry depth: 0, Return depth: -16180
;
; Inferred Local Variables:
;   Stack frame size: 16180 bytes
;   Offsets: S+$01 through S+$3F34

; === Resolved Jump Tables ===
;
; Jump Table at $006F5A (2 entries, 2-byte each)
; Dispatch code at $002954 (indirect)
;   [ 0] $008080
;   [ 1] $008080
;
; Jump Table at $007E1B (1 entries, 2-byte each)
; Dispatch code at $002F03 (indirect)
;   [ 0] $00300D
;
; Jump Table at $007E33 (1 entries, 2-byte each)
; Dispatch code at $0034C1 (indirect)
;   [ 0] $007801
;
; Jump Table at $007E1B (1 entries, 2-byte each)
; Dispatch code at $003A7F (indirect)
;   [ 0] $00300D
;
; Jump Table at $007E01 (1 entries, 2-byte each)
; Dispatch code at $006A32 (indirect)
;   [ 0] $002A60
;
; Jump Table at $007F41 (1 entries, 2-byte each)
; Dispatch code at $006E32 (indirect)
;   [ 0] $007800
;
; Jump Table at $007F41 (1 entries, 2-byte each)
; Dispatch code at $007232 (indirect)
;   [ 0] $007800
;
; Jump Table at $007F1F (2 entries, 2-byte each)
; Dispatch code at $007F3E (indirect)
;   [ 0] $006A58
;   [ 1] $002B00
;
; Jump Table at $007C36 (1 entries, 2-byte each)
; Dispatch code at $008102 (indirect)
;   [ 0] $00352A

; === Hardware Context Analysis ===
; Total I/O reads:  15
; Total I/O writes: 0
;
; Subsystem Access Counts:
;   Keyboard        : 5
;   Speaker         : 2
;   Video           : 8
;
; Final Video Mode: HIRES
; Memory State: 80STORE=0 RAMRD=0 RAMWRT=0 ALTZP=0 LC_BANK=2 LC_RD=0 LC_WR=0
; Speed Mode: Normal (1 MHz)
;
; Detected Hardware Patterns:
;   - Video mode change sequence detected
;   - Speaker toggle detected (2 accesses)

; Disassembly generated by DeAsmIIgs v2.0.0
; Source: D:\Projects\rosetta_v2\archaeology\games\rpg\u3p_dsk1\extracted\GAME\EXOD#062000
; Base address: $002000
; Size: 26208 bytes
; Analysis: 0 functions, 43 call sites, 22 liveness, stack: +0 max

        ; Emulation mode

; === Analysis Summary ===
; Basic blocks: 153
; CFG edges: 271
; Loops detected: 23
; Patterns matched: 664
; Branch targets: 373
; Functions: 22
; Call edges: 51
;
; Loops:
;   $0084B0: while loop
;   $0084B0: loop
;   $0084D1: while loop
;   $0084D1: loop
;   $00828D: loop
;   $00828B: while loop
;   $008414: while loop
;   $0083F2: while loop
;   $0082F6: while loop
;   $0082E2: while loop
;   $0084E6: loop
;   $00833A: while loop
;   $00838C: while loop
;   $00862B: while loop
;   $008606: while loop
;   $00857C: while loop
;   $008577: while loop
;   $008577: while loop
;   $00855C: while loop
;   $00851A: loop
;   $008514: while loop
;   $008514: while loop
;   $008245: while loop
;
; Pattern summary:
;   GS/OS calls: 2
;
; Call graph:
;   $002000: 0 caller(s)
;   $00823D: 1 caller(s)
;   $00825E: 1 caller(s)
;   $0082E6: 1 caller(s)
;   $00832A: 1 caller(s)
;   $00836E: 1 caller(s)
;   $008384: 1 caller(s)
;   $0083AD: 1 caller(s)
;   $0083BF: 1 caller(s)
;   $0083D1: 1 caller(s)
;   $0083E3: 10 caller(s)
;   $00844C: 1 caller(s)
;   $008453: 1 caller(s)
;   $008476: 2 caller(s)
;   $0084A4: 2 caller(s)
;   $0084BF: 2 caller(s)
;   $0084E6: 7 caller(s)
;   $0084FC: 6 caller(s)
;   $00850C: 1 caller(s)
;   $008548: 1 caller(s)
;   $00856A: 1 caller(s)
;   $0085B8: 2 caller(s)
;

; ===========================================================================
; Forward references — labels at mid-instruction addresses
; ===========================================================================

; NOTE: anim_data_2552 enters mid-instruction — alternate decode: ROL $3E01,X / ADC $7000,Y / AND ...
anim_data_2552   EQU $2552

; NOTE: anim_data_256B enters mid-instruction — alternate decode: ADC ($5C,X) / BRK #$5C / BRK #$00
anim_data_256B   EQU $256B

; NOTE: anim_data_25E5 enters mid-instruction — alternate decode: BRK #$3C / BVS $25F0 / BRK #$40
anim_data_25E5   EQU $25E5

; NOTE: anim_data_2B42 enters mid-instruction — alternate decode: BMI $2BA7 / BVC $2B47 / BVC $2B49
anim_data_2B42   EQU $2B42

; NOTE: anim_data_2C20 enters mid-instruction — alternate decode: JMP $0619
anim_data_2C20   EQU $2C20

; NOTE: anim_data_31EB enters mid-instruction — alternate decode: TSB $0C18 / CLC / ASL $00
anim_data_31EB   EQU $31EB

; NOTE: anim_data_32BD enters mid-instruction — alternate decode: CLC / BMI $32CC / BRK #$40
anim_data_32BD   EQU $32BD

; NOTE: anim_data_32BF enters mid-instruction — alternate decode: TSB $4000 / ADC $61,S / ORA $60,S
anim_data_32BF   EQU $32BF

; NOTE: anim_data_35EC enters mid-instruction — alternate decode: BMI $35F1 / CLI / ORA ($50,X)
anim_data_35EC   EQU $35EC

; NOTE: anim_data_364C enters mid-instruction — alternate decode: ADC ($70,X) / BRK #$00 / BIT $0770,X
anim_data_364C   EQU $364C

; ... and 8 more mid-instruction entries

anim_data_2529  EQU $2529
anim_data_258B   EQU $258B
anim_data_28E3   EQU $28E3
anim_data_2A09   EQU $2A09
anim_data_2B47   EQU $2B47
anim_data_2B49   EQU $2B49
anim_data_2C23   EQU $2C23
anim_data_2EAE   EQU $2EAE
anim_data_2FAD   EQU $2FAD
anim_data_3017   EQU $3017
anim_data_3103   EQU $3103
anim_data_3171  EQU $3171
anim_data_3185   EQU $3185
anim_data_35E0   EQU $35E0
anim_data_74ED   EQU $74ED
anim_data_7DC6  EQU $7DC6
anim_data_36D7  EQU $36D7
anim_data_37A9   EQU $37A9
intro_draw_src_lo EQU $85F6
intro_draw_src_hi EQU $85F7
intro_draw_src2_lo EQU $85FD
intro_draw_src2_hi EQU $85FE
intro_draw_glyph_lo EQU $862C
intro_draw_glyph_hi EQU $862D

; (34 forward-reference equates, 18 with alternate decode notes)

            ORG  $2000


; FUNC $002000: register -> A:X [IJ]
; Proto: uint32_t func_002000(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [20 dead stores]
            jmp  intro_entry     

; --- Data region (1104 bytes, text data) ---
            DB      $30,$33,$30,$32,$37,$42,$30,$35,$37,$38,$34,$35,$30,$31,$34,$30
            DB      $37,$46,$30,$33,$30,$30,$0D,$30,$1E,$E4,$20,$32,$30,$30,$37,$30
            DB      $33,$30,$37,$37,$33,$30,$32,$37,$30,$30,$32,$30,$30,$34,$30,$37
            DB      $46,$30,$37,$30,$33,$0D,$30,$1E,$E4,$20,$30,$30,$30,$37,$30,$33
            DB      $30,$37,$32,$33,$30,$33,$32,$30,$30,$33,$30,$30,$30,$30,$37,$46
            DB      $30,$46,$30,$36,$0D,$30,$1E,$E4,$20,$34,$30,$30,$44,$34,$30,$30
            DB      $44,$34,$33,$30,$36,$34,$30,$30,$36,$30,$30,$34,$30,$36,$31,$31
            DB      $45,$30,$36,$0D,$30,$1E,$E4,$20,$36,$30,$31,$38,$36,$30,$31,$38
            DB      $33,$33,$30,$43,$33,$30,$30,$43,$30,$30,$34,$30,$34,$31,$37,$39
            DB      $30,$33,$0D,$30,$1E,$E4,$20,$36,$30,$33,$30,$33,$30,$31,$38,$33
            DB      $33,$30,$43,$31,$38,$30,$43,$30,$30,$36,$30,$36,$31,$37,$31,$30
            DB      $31,$0D,$30,$1E,$E4,$20,$37,$30,$37,$30,$33,$38,$33,$38,$33,$42
            DB      $31,$43,$31,$43,$31,$43,$30,$30,$32,$30,$32,$31,$30,$31,$30,$30
            DB      $0D ; string length
            DB      $30,$26,$41,$4E,$49,$4D,$30,$34,$20,$20,$E4,$20,$38
            DB      $30,$30,$30,$30,$30,$30,$30,$30,$30,$30,$30,$31,$38,$30,$30,$30
            DB      $30,$33,$30,$30,$30,$30,$30,$30,$30,$0D,$20,$1E,$E4,$20,$30,$30
            DB      $30,$30,$30,$30,$30,$30,$30,$30,$30,$30,$30,$43,$30,$30,$30,$30
            DB      $36,$38,$30,$30,$37,$38,$30,$33,$0D,$38,$1E,$E4,$20,$30,$30,$30
            DB      $45,$32,$36,$30,$45,$30,$30,$36,$37,$30,$36,$30,$37,$30,$30,$37
            DB      $45,$30,$31,$37,$45,$30,$30,$0D,$45,$1E,$E4,$20,$30,$30,$30,$45
            DB      $32,$36,$30,$45,$30,$30,$34,$37,$30,$33,$30,$37,$30,$30,$37,$30
            DB      $34,$31,$31,$46,$30,$30,$0D,$30,$1E,$E4,$20,$30,$30,$34,$45,$33
            DB      $46,$30,$45,$30,$36,$34,$37,$30,$36,$30,$37,$30,$33,$35,$43,$36
            DB      $31,$30,$46,$30,$30,$0D,$43,$1E,$E4,$20,$30,$30,$30,$34,$32,$36
            DB      $30,$34,$30,$36,$32,$30,$30,$30,$30,$30,$30,$33,$34,$30,$37,$31
            DB      $30,$37,$30,$30,$0D,$30,$1E,$E4,$20,$34,$30,$33,$46,$34,$36,$33
            DB      $46,$37,$36,$31,$42,$37,$30,$31,$42,$30,$33,$34,$30,$37,$42,$30
            DB      $33,$30,$30,$0D,$30,$1E,$E4,$20,$32,$30,$35,$46,$30,$36,$35,$46
            DB      $37,$36,$31,$42,$37,$30,$33,$42,$30,$33,$30,$30,$37,$46,$30,$31
            DB      $30,$30,$0D,$30,$1E,$E4,$20,$31,$30,$30,$45,$30,$37,$30,$45,$37
            DB      $37,$30,$42,$37,$30,$34,$42,$30,$37,$30,$30,$37,$46,$30,$33,$30
            DB      $30,$0D,$30,$1E,$E4,$20,$32,$30,$30,$34,$30,$36,$30,$34,$37,$36
            DB      $30,$42,$37,$30,$30,$42,$30,$33,$30,$30,$37,$46,$30,$37,$30,$30
            DB      $0D,$30,$1E,$E4,$20,$34,$30,$30,$45,$30,$36,$30,$45,$36,$36,$30
            DB      $35,$36,$30,$30,$35,$30,$30,$30,$30,$37,$46,$30,$46,$30,$36,$0D
            DB      $30,$1E,$E4,$20,$30,$30,$30,$45,$30,$36,$30,$45,$34,$36,$30,$36
            DB      $34,$30,$30,$36,$30,$30,$30,$30,$37,$45,$31,$46,$30,$43,$0D,$30
            DB      $1E,$E4,$20,$30,$30,$31,$42,$30,$30,$31,$42,$30,$36,$30,$44,$30
            DB      $30,$30,$44,$30,$30,$30,$30,$34,$33,$33,$44,$30,$43,$0D,$30,$1E
            DB      $E4,$20,$34,$30,$33,$31,$34,$30,$33,$31,$36,$36,$31,$38,$36,$30
            DB      $31,$38,$30,$30,$30,$30,$30,$33,$37,$33,$30,$37,$0D,$30,$1E,$E4
            DB      $20,$34,$30,$36,$31,$36,$30,$33,$30,$36,$36,$31,$38,$33,$30,$31
            DB      $38,$30,$30,$34,$30,$34,$33,$36,$33,$30,$33,$0D,$30,$1E,$E4,$20
            DB      $36,$30,$36,$31,$37,$31,$37,$30,$37,$36,$33,$38,$33,$38,$33,$38
            DB      $30,$30,$34,$30,$34,$32,$30,$32,$30,$30,$0D,$30,$26,$41,$4E,$49
            DB      $4D,$30,$35,$20,$20,$E4,$20,$38,$30,$30,$30,$30,$30,$30,$30,$30
            DB      $30,$30,$30,$33,$30,$30,$30,$30,$30,$36,$30,$30,$30,$30,$30,$30
            DB      $30,$0D,$20,$1E,$E4,$20,$30,$30,$30,$30,$30,$30,$30,$30,$30,$30
            DB      $30,$30,$31,$38,$30,$30,$30,$30,$35,$30,$30,$31,$37,$30,$30,$37
            DB      $0D,$30,$1E,$E4,$20,$30,$30,$31,$43,$34,$43,$31,$43,$30,$30,$34
            DB      $45,$30,$44,$30,$45,$30,$30,$37,$43,$30,$33,$37,$43,$30,$31,$0D
            DB      $43,$1E,$E4,$20,$30,$30,$31,$43,$34,$43,$31,$43,$30,$30,$30,$45
            DB      $30,$37,$30,$45,$30,$30,$36,$30,$30,$33,$33,$46,$30,$30,$0D,$30
            DB      $1E,$E4,$20,$30,$30,$31,$43,$37,$46,$31,$43,$30,$43,$30,$45,$30
            DB      $44,$30,$45,$30,$36,$33,$38,$34,$33,$31,$46,$30,$30,$0D,$38,$1E
            DB      $E4,$20,$30,$30,$30,$38,$34,$43,$30,$38,$30,$43,$34,$30,$30,$30
            DB      $30,$30,$30,$36,$30,$30,$36,$33,$30,$46,$30,$30,$0D,$30,$1E,$E4
            DB      $20,$30,$30,$37,$46,$30,$43,$37,$46,$36,$43,$33,$37,$36,$30,$33
            DB      $37,$30,$36,$30,$30,$37,$37,$30,$37,$30,$30,$0D,$30,$1E,$E4,$20
            DB      $34,$30,$33,$45,$30,$44,$33,$45,$36,$44,$33,$37,$36,$30,$37,$37
            DB      $30,$36,$30,$30,$37,$45,$30,$33,$30,$30,$0D,$30,$1E,$E4,$20,$32
            DB      $30,$31,$43,$30,$45,$31,$43,$36,$45,$31,$37,$36,$30,$31,$37,$30
            DB      $46,$30,$30,$37,$45,$30,$37,$30,$30,$0D,$30,$1E,$E4,$20,$34,$30
            DB      $30,$38,$30,$43,$30,$38,$36,$43,$31,$37,$36,$30,$31,$37,$30,$08
            DB      $04,$C6,$09,$84,$0F,$42,$15,$16,$04,$E6,$04,$B6,$05,$86,$06,$56
            DB      $07,$26,$08,$F6,$08,$80,$00,$00,$00,$00,$40,$01,$00,$00,$03,$00
            DS      7
            DB      $60,$00,$00,$40,$06,$40,$1F,$00,$70,$30,$72,$00,$38,$36,$38,$00
            DB      $70,$0F,$70,$07,$00,$70,$30,$72,$00,$38,$1C,$38,$00,$00,$0F,$7C
            DB      $01,$00,$70,$7C,$73,$30,$38,$34,$38,$18,$60
; --- End data region (1104 bytes) ---

anim_data_2453  ora  !$007E          ; [SP-32]
            brk  #$20            ; [SP-35]

; --- Data region (169 bytes) ---
            DB      $30,$22,$30,$00,$02,$00,$18,$00,$0C,$3F,$00,$00,$7C,$33,$7C,$33
            DB      $5F,$01,$5F,$19,$00,$5C,$1F,$00,$00,$7A,$35,$78,$35,$5F,$01,$5F
            DB      $1B,$00,$78,$0F,$00,$00,$71,$38,$70,$38,$5F,$00,$5F,$3C,$00,$78
            DB      $1F,$00,$00,$22,$30,$20,$30,$5F,$00,$5F,$18,$00,$78,$3F,$00,$00
            DB      "t0p0."
            DB      $00 ; null terminator
            DB      $2E,$00,$00,$78,$7F,$30,$00,$70,$30,$70,$30,$34,$00,$34,$00,$00
            DB      $70,$7F,$61,$00,$58,$01,$58,$31,$68,$00,$68,$00,$00,$18,$6C,$63
            DB      $00,$0C,$03,$0C,$33,$46,$01,$46,$01,$00,$18,$18,$3F,$00,$0C,$06
            DB      $06,$33,$46,$01,$43,$01,$00,$1C,$1C,$1E,$00,$0E,$0E,$07,$37,$47
            DB      $43,$43,$03,$00,$14,$14,$00,$00,$80,$00,$00,$00,$00,$00,$03,$00
            DB      $00,$06,$00,$00,$00,$00,$00,$00,$00,$00,$40,$01,$00,$00,$0D,$00
            DB      $3F,$00,$60
; --- End data region (169 bytes) ---

anim_data_2501  adc  ($64,X)         ; [SP-104]
            ora  ($70,X)         ; [SP-104]
            jmp  ($0070)         ; [SP-104]
            DB      $60
anim_data_2509
            DB      $1F
; LUMA: epilogue_rts
            rts                  ; [SP-102]
            DB      $0F
; LUMA: int_brk
            brk  #$60            ; [SP-102]
anim_data_250E  adc  ($64,X)         ; [SP-100]
            ora  ($70,X)         ; [SP-100]
            sec                  ; [SP-100]
            bvs  anim_data_2515      ; [SP-100]
; XREF: 1 ref (1 branch) from anim_data_250E
anim_data_2515  brk  #$1E            ; [SP-103]
            DB      $78,$03,$00,$60
anim_data_251B  adc  $6167,Y         ; [SP-101]
            bvs  anim_data_2588      ; [SP-101]
            bvs  anim_data_2552      ; [SP-101]
; Interrupt return (RTI)
            rti                  ; [SP-98]

; ---
            DB      $1B,$7C,$01,$00,$40,$60
anim_data_2529
            DB      $44
; ---

            rts                  ; [SP-93]
            brk  #$04            ; [SP-93]

; ---
            DB      $00,$30,$00,$18,$7E,$00,$00,$78,$67,$78,$67,$3E,$03,$3E,$33,$00
            DB      $38,$3F,$00,$00,$74,$6B
; ---

anim_data_2543  bvs  anim_data_25B0     ; [SP-90]
            rol  $3E03,X         ; [SP-90]
            DB      $37
; LUMA: int_brk
            brk  #$70            ; [SP-90]

; ---
            DB      $1F,$00,$00,$62,$71,$60
; ---

anim_data_2551  adc  ($3E),Y         ; [SP-95]
            ora  ($3E,X)         ; [SP-95]
            adc  $7000,Y         ; [SP-95]
            DB      $3F
; LUMA: int_brk
            brk  #$00            ; [SP-95]
            DB      $44
            DB      $60

; ---------------------------------------------------------------------------
; anim_data_255D
; ---------------------------------------------------------------------------
; Interrupt return (RTI)
anim_data_255D  rti                  ; [SP-90]

; ---
            DB      $60,$3E,$01,$3E,$31,$00,$70,$7F,$00,$00,$68,$61,$60
; ---

; XREF: 1 ref (1 branch) from anim_data_2543
anim_data_256B  adc  ($5C,X)         ; [SP-90]
; LUMA: int_brk
            brk  #$5C            ; [SP-93]

; ---
            DB      $00,$00,$70,$7F,$61,$00,$60,$61,$60,$61,$68,$00,$68,$00,$00,$60
anim_data_257F
            DB      $7F
            DB      $43
; ---

            ora  ($30,X)         ; [SP-98]

; ---
            DB      $03,$30,$63,$50,$01
; ---

; XREF: 1 ref (1 branch) from anim_data_251B
anim_data_2588  bvc  anim_data_258B      ; [SP-98]
; LUMA: int_brk
            brk  #$30            ; [SP-98]
; LUMA: int_enable
            cli                  ; [SP-98]
            DB      $47
            ora  ($18,X)         ; [SP-98]

; --- Data region (33 bytes) ---
            DB      $06,$18,$66,$0C,$03,$0C,$03,$00,$30,$30,$7E,$00,$18,$0C,$0C,$66
            DB      $0C,$03,$06,$03,$00,$38,$38,$3C,$00,$1C,$1C,$0E,$6E,$0E,$07,$07
anim_data_25B0
            DB      $07
; --- End data region (33 bytes) ---

; LUMA: int_brk
            brk  #$28            ; [SP-98]

; --- Data region (47 bytes) ---
            DB      $28,$00,$00,$80,$00,$00,$00,$00,$00,$06,$00,$00,$0C,$00,$00,$00
            DS      6
            DB      $03,$00,$00,$1A,$00,$7E,$00,$40,$43,$49,$03,$60,$59,$61,$01,$40
            DB      $3F,$40,$1F,$00,$40,$43,$49,$03,$60
; --- End data region (47 bytes) ---

anim_data_25E2  adc  ($60),Y         ; [SP-126]
            ora  ($00,X)         ; [SP-126]

; --- Data region (54 bytes) ---
            DB      $3C
            DB      $70,$07,$00,$40,$73,$4F,$43,$61,$51,$61,$61,$00,$37,$78,$03,$00
            DB      $00,$41,$09,$41,$01,$08,$00,$60,$00,$30,$7C,$01,$00,$70,$4F,$71
            DB      $4F,$7D,$06,$7C,$66,$00,$70,$7E,$00,$00,$68,$57,$61,$57,$7D,$06
            DB      $7C,$6E,$00,$60
anim_data_261B
            DB      $3F
; --- End data region (54 bytes) ---

; LUMA: int_brk
            brk  #$00            ; [SP-140]

; ---
            DB      $44
            DB      $63,$41,$63,$7D,$02,$7C,$72,$01,$60
anim_data_2628
            DB      $7F
; ---

; LUMA: int_brk
            brk  #$00            ; [SP-141]
            php                  ; [SP-141]

; ---
            DB      $41,$01,$41,$7D,$02,$7C,$62,$00,$60
anim_data_2635
            DB      $7F
; ---

            ora  ($00,X)         ; [SP-146]
            bvc  $267D           ; [SP-146]

; ---
            DB      $41,$43,$39,$01,$38,$01,$00,$60
anim_data_2642
            DB      $7F
            DB      $43
; ---

            ora  ($40,X)         ; [SP-144]

; ---
            DB      $43,$41,$43,$51,$01,$50,$01,$00,$40,$7F,$07,$03,$60
; ---

anim_data_2653  asl  $60             ; [SP-141]
            lsr  $21             ; [SP-141]
            DB      $03
            jsr  !$0003          ; [SP-141]
            DB      $60
anim_data_265C  bmi  anim_data_266D      ; [SP-139]
            DB      $03
            bmi  anim_data_266D      ; [SP-139]

; ---
            DB      $30,$4C,$19,$06,$18,$06,$00,$60
; ---

; LUMA: epilogue_rts
anim_data_2669  rts                  ; [SP-135]
            DB      $7C,$01,$30
; XREF: 1 ref (1 branch) from anim_data_265C
anim_data_266D  clc                  ; [SP-135]
            clc                  ; [SP-135]
            jmp  $0619           ; [SP-135]

; --- Data region (71 bytes) ---
            DB      $0C,$06,$00,$70,$70,$78,$00,$38,$38,$1C,$5C,$1D,$0E,$0E,$0E,$00
            DB      $50,$50,$00,$00,$80,$00,$00,$00,$00,$00,$0C,$00,$00,$18,$00,$00
            DS      7
            DB      $06,$00,$00,$34,$00,$7C,$01,$00,$07,$13,$07,$40,$33,$43,$03,$00
            DB      $7F,$00,$3F,$00,$00,$07,$13,$07,$40,$63,$41,$03,$00,$78,$60
anim_data_26B8
            DB      $0F
; --- End data region (71 bytes) ---

; LUMA: int_brk
            brk  #$00            ; [SP-172]

; ---
            DB      $67
            DB      $1F,$07,$43,$23,$43,$43,$01,$6E,$70,$07,$00,$00,$02,$13,$02,$03
            DB      $10,$00,$40,$01,$60
; ---


; ---------------------------------------------------------------------------
; anim_data_26D1
; ---------------------------------------------------------------------------
; LUMA: int_disable
anim_data_26D1  sei                  ; [SP-178]
            DB      $03
; LUMA: int_brk
            brk  #$60            ; [SP-178]

; ---
anim_data_26D5
            DB      $1F
            DB      $63
            DB      $1F
            DB      $7B
            DB      $0D,$78,$4D,$01,$60
; ---

anim_data_26DE  adc  !$0001,X        ; [SP-176]
            bvc  anim_data_2712     ; [SP-176]

; --- Data region (50 bytes) ---
            DB      $43
            DB      $2F
            DB      $7B,$0D,$78,$5D,$01,$40,$7F,$00,$00,$08,$47,$03,$47,$7B,$05,$78
            DB      $65,$03,$40,$7F,$01,$00,$10,$02,$03,$02,$7B,$05,$78,$45,$01,$40
            DB      $7F,$03,$00,$20,$07,$03,$07,$73,$02,$70,$02,$00,$40
anim_data_2712
            DB      $7F
            DB      $07
            DB      $03
; --- End data region (50 bytes) ---

; LUMA: int_brk
            brk  #$07            ; [SP-179]

; ---
            DB      $03,$07,$23,$03,$20,$03,$00,$00,$7F,$0F,$06,$40,$0D,$40,$0D,$43
            DB      $06,$40,$06,$00,$40,$61,$1E,$06,$60
; ---

anim_data_2730  clc                  ; [SP-173]
; LUMA: epilogue_rts
            rts                  ; [SP-171]

; ---
            DB      $18,$33,$0C,$30,$0C,$00,$40,$41,$79,$03,$60,$30,$30,$18,$33,$0C
            DB      $18,$0C,$00,$60
; ---

anim_data_2746  adc  ($71,X)         ; [SP-174]
            ora  ($70,X)         ; [SP-174]
            bvs  anim_data_2784     ; [SP-174]
            sec                  ; [SP-174]

; --- Data region (56 bytes) ---
            DB      $3B,$1C,$1C,$1C,$00,$20,$21,$01,$00,$80,$00,$00,$00,$00,$00,$18
            DB      $00,$00,$30,$00,$00,$00,$00,$00,$00,$00,$00,$00,$0C,$00,$00,$68
            DB      $00,$78,$03,$00,$0E,$26,$0E,$00,$67,$06,$07,$00,$7E,$01,$7E,$00
            DB      $00,$0E,$26,$0E,$00,$47,$03
anim_data_2784
            DB      $07
; --- End data region (56 bytes) ---

; LUMA: int_brk
            brk  #$70            ; [SP-221]

; --- Data region (88 bytes) ---
            DB      $41,$1F,$00,$00,$4E,$3F,$0E,$06,$47,$06,$07,$03,$5C,$61,$0F,$00
            DB      $00,$04,$26,$04,$06,$20,$00,$00,$03,$40,$71,$07,$00,$40,$3F,$46
            DB      $3F,$76,$1B,$70,$1B,$03,$40,$7B,$03,$00,$20,$5F,$06,$5F,$76,$1B
            DB      $70,$3B,$03,$00,$7F,$01,$00,$10,$0E,$07,$0E,$77,$0B,$70,$4B,$07
            DB      $00,$7F,$03,$00,$20,$04,$06,$04,$76,$0B,$70,$0B,$03,$00,$7F,$07
            DB      $00,$40,$0E,$06,$0E,$66,$05,$60
; --- End data region (88 bytes) ---

anim_data_27DF  ora  $00             ; [SP-233]
            brk  #$7F            ; [SP-236]

; --- Data region (35 bytes) ---
            DB      $0F,$06,$00,$0E,$06,$0E,$46,$06,$40,$06,$00,$00,$7E,$1F,$0C,$00
            DB      $1B,$00,$1B,$06,$0D,$00,$0D,$00,$00,$43,$3D,$0C,$40,$31,$40,$31
            DB      $66,$18,$60
; --- End data region (35 bytes) ---

anim_data_2806  clc                  ; [SP-240]
            brk  #$00            ; [SP-243]

; --- Data region (115 bytes) ---
            DB      $03,$73,$07,$40,$61,$60,$30,$66,$18,$30,$18,$00,$40,$43,$63,$03
            DB      $60,$61,$71,$70,$76,$38,$38,$38,$00,$40,$42,$02,$00,$80,$00,$00
            DS      3
            DB      $30,$00,$00,$60,$00,$00,$00,$00,$00,$00,$00,$00,$00,$18,$00,$00
            DB      $50,$01,$70,$07,$00,$1C,$4C,$1C,$00,$4E,$0D,$0E,$00,$7C,$03,$7C
            DB      $01,$00,$1C,$4C,$1C,$00,$0E,$07,$0E,$00,$60
anim_data_2857
            DB      $03
            DB      $3F
            DB      $00,$00,$1C,$7F,$1C,$0C,$0E,$0D,$0E,$06,$38,$43,$1F,$00,$00,$08
            DB      $4C,$08,$0C,$40,$00,$00,$06,$00,$63,$0F,$00,$00,$7F,$0C,$7F,$6C
            DB      $37,$60
anim_data_287B
            DB      $37
; --- End data region (115 bytes) ---

            asl  $00             ; [SP-302]

; --- Data region (37 bytes) ---
            DB      $77,$07,$00,$40,$3E,$0D,$3E,$6D,$37,$60,$77,$06,$00,$7E,$03,$00
            DB      $20,$1C,$0E,$1C,$6E,$17,$60
anim_data_2895
            DB      $17
            DB      $0F
            DB      $00,$7E,$07,$00,$40,$08,$0C,$08,$6C,$17,$60
anim_data_28A2
            DB      $17
; --- End data region (37 bytes) ---

            asl  $00             ; [SP-306]

; --- Data region (62 bytes) ---
            DB      $7E,$0F,$00,$00,$1D,$0C,$1C,$4C,$0B,$40,$0B,$00,$00,$7E,$1F,$0C
            DB      $00,$1C,$0C,$1C,$0C,$0D,$00,$0D,$00,$00,$7C,$3F,$18,$00,$36,$00
            DB      $36,$0C,$1A,$00,$1A,$00,$00,$06,$7B,$18,$00,$63,$00,$63,$4C,$31
            DB      $40,$31,$00,$00,$06,$66,$0F,$00,$43,$41,$61,$4C,$31,$60
; --- End data region (62 bytes) ---

anim_data_28E3  bmi  anim_data_28E5      ; [SP-338]
; XREF: 1 ref (1 branch) from anim_data_28E3
anim_data_28E5  brk  #$07            ; [SP-341]

; --- Data region (41 bytes) ---
            DB      $47,$07,$40,$43,$63,$61,$6D,$71,$70,$70,$00,$00,$05,$05,$00,$80
            DS      5
            DB      $60,$00,$00,$40,$01,$00,$00,$00,$00,$00,$00,$00,$00,$30,$00,$00
            DB      $20,$03,$60
anim_data_290F
            DB      $0F
; --- End data region (41 bytes) ---

            brk  #$38            ; [SP-362]
            clc                  ; [SP-362]

; --- Data region (220 bytes) ---
            DB      $39,$00,$1C,$1B,$1C,$00,$78,$07,$78,$03,$00,$38,$18,$39,$00,$1C
            DB      $0E,$1C,$00,$40,$07,$7E,$00,$00,$38,$7E,$39,$18,$1C,$1A,$1C,$0C
            DB      $70,$06,$3F,$00,$00,$10,$18,$11,$18,$00,$01,$00,$0C,$00,$46,$1F
            DB      $00,$00,$7E,$19,$7E,$59,$6F,$40,$6F,$0C,$00,$6E,$0F,$00,$00,$7D
            DB      $1A,$7C,$5A,$6F,$40,$6F,$0D,$00,$7C,$07,$00,$40,$38,$1C,$38,$5C
            DB      $2F,$40,$2F,$1E,$00,$7C,$0F,$00,$00,$11,$18,$10,$58,$2F,$40,$2F
            DB      $0C,$00,$7C,$1F,$00,$00,$3A,$18,$38,$18,$17,$00,$17,$00,$00,$7C
            DB      $3F,$18,$00,$38,$18,$38,$18,$1A,$00,$1A,$00,$00,$78,$7F,$30,$00
            DB      $6C,$00,$6C,$18,$34,$00,$34,$00,$00,$0C,$76,$31,$00,$46,$01,$46
            DB      $19,$63,$00,$63,$00,$00,$0C,$4C,$1F,$00,$06,$03,$43,$19,$63,$40
            DB      $61,$00,$00,$0E,$0E,$0F,$00,$07,$47,$43,$5B,$63,$61,$61,$01,$00
            DB      $0A,$0A,$00,$D4,$09,$A4,$0A,$74,$0B,$44,$0C,$14,$0D,$E4,$0D,$B4
            DB      $0E,$00,$30,$00,$00,$00,$18,$00,$00,$00,$03,$00,$00,$00,$00,$30
            DS      3
            DB      $18,$00,$00,$40,$06,$00,$3F,$00,$60
; --- End data region (220 bytes) ---

anim_data_29EF  adc  !$0071,X        ; [SP-428]
            sec                  ; [SP-428]
            clc                  ; [SP-428]
            sec                  ; [SP-428]
            brk  #$70            ; [SP-431]
            DB      $0F,$60
anim_data_29F9
            DB      $0F
            brk  #$60            ; [SP-431]
            and  ($70),Y         ; [SP-429]

; ---
            DB      $00,$38,$18,$38,$00,$00,$0F,$78,$03,$00,$60
; ---

anim_data_2A09  and  ($70),Y         ; [SP-433]
            bmi  anim_data_2A45      ; [SP-433]
            DB      $3C
            sec                  ; [SP-433]
            brk  #$60            ; [SP-433]
anim_data_2A11  ora  $017C           ; [SP-431]
            brk  #$40            ; [SP-434]

; --- Data region (47 bytes) ---
            DB      $38,$20,$30,$00,$1A,$00,$40,$01,$18,$7E,$00,$00,$78,$37,$7C,$33
            DB      $5F,$01,$5F,$61,$00,$38,$3F,$00,$00,$74,$33,$7A,$35,$5F,$01,$5F
            DB      $37,$00,$70,$1F,$00,$00,$62,$31,$71,$38,$5F,$00,$5F,$1C,$00
; --- End data region (47 bytes) ---

; XREF: 1 ref (1 branch) from anim_data_2A09
anim_data_2A45  bvs  anim_data_2A86      ; [SP-447]
            brk  #$00            ; [SP-447]

; ---
            DB      "D0"
            DB      $22
            DB      "0_"
            DB      $00 ; null terminator
            DB      $5F,$34,$00,$70,$7F,$60,$00,$68,$01,$74,$30,$2E,$00,$2E,$00,$00
            DB      $70
anim_data_2A60
            DB      $7F
; ---

            eor  ($01,X)         ; [SP-457]
            rts                  ; [SP-455]

; ---
            DB      $01,$70,$30,$34,$00,$34,$00,$00,$60
anim_data_2A6D
            DB      $7F
            DB      $43
; ---

            ora  ($30,X)         ; [SP-459]

; ---
            DB      $03,$58,$31,$68,$00,$68,$00,$00,$30,$58,$7F,$00,$18,$06,$0C,$33
            DB      $46,$01,$46,$01,$00
; ---

anim_data_2A86  clc                  ; [SP-465]
            clc                  ; [SP-465]
            rol  $0C00,X         ; [SP-465]
            asl  $0C             ; [SP-465]
            DB      $33
            lsr  $01             ; [SP-465]

; --- Data region (56 bytes) ---
            DB      $46,$01,$00,$1C,$1C,$00,$00,$0E,$0E,$0E,$37,$47,$03,$47,$03,$00
            DB      $14,$14,$00,$00,$00,$60,$00,$00,$00,$30,$00,$00,$00,$06,$00,$00
            DB      $00,$00,$60,$00,$00,$00,$30,$00,$00,$00,$0D,$00,$7E,$00,$40,$7B
            DB      $63,$01,$70,$30,$70,$00,$60
anim_data_2AC7
            DB      $1F
; --- End data region (56 bytes) ---

; Interrupt return (RTI)
            rti                  ; [SP-504]
            DB      $1F
            brk  #$40            ; [SP-504]
            DB      $63,$60
anim_data_2ACE  ora  ($70,X)         ; [SP-501]
            bmi  anim_data_2B42      ; [SP-501]
            brk  #$00            ; [SP-504]

; --- Data region (54 bytes) ---
            DB      $1E,$70,$07,$00,$40,$63,$60,$61,$70,$78,$70,$00,$40,$1B,$78,$03
            DB      $00,$00,$71,$40,$60,$00,$34,$00,$00,$03,$30,$7C,$01,$00,$70,$6F
            DB      $78,$67,$3E,$03,$3E,$43,$01,$70,$7E,$00,$00,$68
anim_data_2B00
            DB      $67
            DB      $74
            DB      $6B,$3E,$03,$3E,$6F,$00,$60
anim_data_2B09
            DB      $3F
; --- End data region (54 bytes) ---

            brk  #$00            ; [SP-510]

; ---
            DB      $44
            DB      $63,$62,$71,$3E,$01,$3E,$39,$00,$60
anim_data_2B16
            DB      $7F
; ---

            brk  #$00            ; [SP-510]
            php                  ; [SP-510]

; ---------------------------------------------------------------------------
; anim_data_2B1A
; ---------------------------------------------------------------------------
anim_data_2B1A  adc  ($44,X)         ; [SP-510]
            rts                  ; [SP-508]
anim_data_2B1D  rol  $3E01,X         ; [SP-508]
            adc  #$00            ; A=A ; [SP-508]
            rts                  ; A=A ; [SP-506]

; ---
            DB      $7F,$41,$01,$50,$03,$68,$61,$5C,$00,$5C,$00,$00,$60
anim_data_2B30
            DB      $7F
            DB      $03
            DB      $03
; ---

; Interrupt return (RTI)
            rti                  ; A=A ; [SP-510]
            DB      $03,$60
anim_data_2B36  adc  ($68,X)         ; A=A ; [SP-510]
            brk  #$68            ; A=A ; [SP-513]

; ---
            DB      $00,$00,$40,$7F,$07,$03,$60
; ---

anim_data_2B41  asl  $30             ; A=A ; [SP-513]
            DB      $63
            bvc  anim_data_2B47      ; [SP-513]
            bvc  anim_data_2B49      ; [SP-513]
            brk  #$60            ; [SP-513]

; --- Data region (73 bytes) ---
            DB      $30,$7F,$01,$30,$0C,$18,$66,$0C,$03,$0C,$03,$00,$30,$30,$7C,$00
            DB      $18,$0C,$18,$66,$0C,$03,$0C,$03,$00,$38,$38,$00,$00,$1C,$1C,$1C
            DB      $6E,$0E,$07,$0E,$07,$00,$28,$28,$00,$00,$00,$40,$01,$00,$00,$60
            DS      3
            DB      $0C,$00,$00,$00,$00,$40,$01,$00,$00,$60,$00,$00,$00,$1A,$00,$7C
            DB      $01,$00,$77,$47,$03,$60
; --- End data region (73 bytes) ---

anim_data_2B93  adc  ($60,X)         ; A=A ; [SP-542]
            ora  ($40,X)         ; A=A ; [SP-542]
            DB      $3F
            brk  #$3F            ; A=A ; [SP-542]
            brk  #$00            ; A=A ; [SP-542]
            DB      $47,$41,$03,$60
anim_data_2BA0  adc  ($60,X)         ; A=A ; [SP-543]
            ora  ($00,X)         ; A=A ; [SP-543]
            DB      $3C
            rts                  ; A=A ; [SP-543]
            DB      $0F
anim_data_2BA7  brk  #$00            ; [SP-546]

; ---
            DB      $47,$41,$43,$61,$71,$61,$01,$00,$37,$70,$07,$00,$00,$62,$01,$41
            DB      $01,$68,$00,$00,$06,$60
; ---

anim_data_2BBF  sei                  ; A=A ; [SP-552]
            DB      $03
            brk  #$60            ; A=A ; [SP-552]

; ---
            DB      $5F,$71,$4F,$7D,$06,$7C,$06,$03,$60
; ---

anim_data_2BCC  adc  !$0001,X        ; A=A ; [SP-548]
            bvc  anim_data_2C20      ; A=A ; [SP-548]
            adc  #$57            ; A=A+$57 ; [SP-548]
            adc  $7C06,X         ; A=A+$57 ; [SP-548]
            lsr  $4001,X         ; A=A+$57 ; [SP-548]
            DB      $7F
            brk  #$00            ; A=A+$57 ; [SP-548]
            php                  ; A=A+$57 ; [SP-548]

; --- Data region (54 bytes) ---
            DB      $47,$45,$63,$7D,$02,$7C,$72,$00,$40,$7F,$01,$00,$10,$42,$09,$41
            DB      $7D,$02,$7C,$52,$01,$40,$7F,$03,$03,$20,$07,$50,$43,$39,$01,$38
            DB      $01,$00,$40,$7F,$07,$06,$00,$07,$40,$43,$51,$01,$50,$01,$00,$00
            DB      $7F,$0F,$06,$40,$0D,$60
; --- End data region (54 bytes) ---

anim_data_2C13  lsr  $21             ; A=A+$57 ; [SP-546]
            DB      $03
            jsr  !$0003          ; A=A+$57 ; [SP-546]

; ---
            DB      $40,$61,$7E,$03,$60
; ---

anim_data_2C1E  clc                  ; A=A+$57 ; [SP-543]
            bmi  anim_data_2C6D     ; A=A+$57 ; [SP-543]
            ora  $1806,Y         ; A=A+$57 ; [SP-543]
            asl  $00             ; A=A+$57 ; [SP-543]
            rts                  ; A=A+$57 ; [SP-541]
anim_data_2C27  rts                  ; A=A+$57 ; [SP-539]

; --- Data region (92 bytes) ---
            DB      $78,$01,$30,$18,$30,$4C,$19,$06,$18,$06,$00,$70,$70,$00,$00,$38
            DB      $38,$38,$5C,$1D,$0E,$1C,$0E,$00,$50,$50,$00,$00,$00,$00,$03,$00
            DB      $00,$40,$01,$00,$00,$18,$00,$00,$00,$00,$00,$03,$00,$00,$40,$01
            DB      $00,$00,$34,$00,$78,$03,$00,$6E,$0F,$07,$40,$43,$41,$03,$00,$7F
            DB      $00,$7E,$00,$00,$0E
anim_data_2C6D
            DB      $03
            DB      $07
            DB      $40,$43,$41,$03,$00,$78,$40,$1F,$00,$00,$0E,$03,$07,$43,$63,$43
            DB      $03,$00,$6E,$60
anim_data_2C83
            DB      $0F
; --- End data region (92 bytes) ---

            brk  #$00            ; A=A+$57 ; [SP-561]

; --- Data region (106 bytes) ---
            DB      $44
            DB      $03,$02,$03,$50,$01,$00,$0C,$40,$71,$07,$00,$40,$3F,$63,$1F,$7B
            DB      $0D,$78,$0D,$06,$40,$7B,$03,$00,$20,$1F,$53,$2F,$7B,$0D,$78,$3D
            DB      $03,$00,$7F,$01,$00,$10,$0E,$0B,$47,$7B,$05,$78,$65,$01,$00,$7F
            DB      $03,$00,$20,$04,$13,$02,$7B,$05,$78,$25,$03,$00,$7F,$07,$06,$40
            DB      $0E,$20,$07,$73,$02,$70,$02,$00,$00,$7F,$0F,$0C,$00,$0E,$00,$07
            DB      $23,$03,$20,$03,$00,$00,$7E,$1F,$0C,$00,$1B,$40,$0D,$43,$06,$40
            DB      $06,$00,$00,$43,$7D,$07,$40,$31,$60
; --- End data region (106 bytes) ---

anim_data_2CF0  clc                  ; A=A+$57 ; [SP-573]

; ---
            DB      $33
            DB      $0C
            DB      $30,$0C,$00,$40,$41,$71,$03,$60,$30,$60
; ---

anim_data_2CFD  clc                  ; A=A+$57 ; [SP-576]

; ---
            DB      $33
            DB      $0C
            DB      $30,$0C,$00,$60
; ---

anim_data_2D04  adc  ($01,X)         ; A=A+$57 ; [SP-579]
            brk  #$70            ; A=A+$57 ; [SP-582]

; --- Data region (149 bytes) ---
            DB      $70,$70,$38,$3B,$1C,$38,$1C,$00,$20,$21,$01,$00,$00,$00,$06,$00
            DB      $00,$00,$03,$00,$00,$30,$00,$00,$00,$00,$00,$06,$00,$00,$00,$03
            DB      $00,$00,$68,$00,$70,$07,$00,$5C,$1F,$0E,$00,$07,$03,$07,$00,$7E
            DB      $01,$7C,$01,$00,$1C,$06,$0E,$00,$07,$03,$07,$00,$70,$01,$3F,$00
            DB      $00,$1C,$06,$0E,$06,$47,$07,$07,$00,$5C,$41,$1F,$00,$00,$08,$07
            DB      $04,$06,$20,$03,$00,$18,$00,$63,$0F,$00,$00,$7F,$46,$3F,$76,$1B
            DB      $70,$1B,$0C,$00,$77,$07,$00,$40,$3E,$26,$5F,$76,$1B,$70,$7B,$06
            DB      $00,$7E,$03,$00,$20,$1C,$16,$0E,$77,$0B,$70,$4B,$03,$00,$7E,$07
            DB      $00,$40,$08,$26,$04,$76,$0B,$70,$4B,$06,$00,$7E,$0F,$0C,$00,$1D
            DB      $40,$0E,$66,$05,$60
; --- End data region (149 bytes) ---

anim_data_2D9D  ora  $00             ; A=A+$57 ; [SP-629]
            brk  #$7E            ; A=A+$57 ; [SP-632]

; --- Data region (35 bytes) ---
            DB      $1F,$18,$00,$1C,$00,$0E,$46,$06,$40,$06,$00,$00,$7C,$3F,$18,$00
            DB      $36,$00,$1B,$06,$0D,$00,$0D,$00,$00,$06,$7B,$0F,$00,$63,$40,$31
            DB      $66,$18,$60
; --- End data region (35 bytes) ---

anim_data_2DC4  clc                  ; A=A+$57 ; [SP-642]
            brk  #$00            ; A=A+$57 ; [SP-645]

; ---
            DB      $03,$63,$07,$40,$61,$40,$31,$66,$18,$60
; ---

anim_data_2DD1  clc                  ; A=A+$57 ; [SP-643]
            brk  #$40            ; A=A+$57 ; [SP-646]

; --- Data region (42 bytes) ---
            DB      $43,$03,$00,$60,$61,$61,$71,$76,$38,$70,$38,$00,$40,$42,$02,$00
            DB      $00,$00,$0C,$00,$00,$00,$06,$00,$00,$60,$00,$00,$00,$00,$00,$0C
            DS      3
            DB      $06,$00,$00,$50,$01,$60
anim_data_2DFD
            DB      $0F
; --- End data region (42 bytes) ---

            brk  #$38            ; A=A+$57 ; [SP-681]

; ---
            DB      $3F
            DB      $1C,$00,$0E,$06,$0E,$00,$7C,$03,$78,$03,$00,$38,$0C,$1C,$00,$0E
            DB      $06,$0E,$00,$60
anim_data_2E15
            DB      $03
; ---

            ror  !$0000,X        ; A=A+$57 ; [SP-687]

; --- Data region (33 bytes) ---
            DB      $38,$0C,$1C,$0C,$0E,$0F,$0E,$00,$38,$03,$3F,$00,$00,$10,$0E,$08
            DB      $0C,$40,$06,$00,$30,$00,$46,$1F,$00,$00,$7E,$0D,$7F,$6C,$37,$60
anim_data_2E39
            DB      $37
; --- End data region (33 bytes) ---

            clc                  ; A=A+$57 ; [SP-703]

; --- Data region (38 bytes) ---
            DB      $00,$6E,$0F,$00,$00,$7D,$4C,$3E,$6D,$37,$60,$77,$0D,$00,$7C,$07
            DB      $00,$40,$38,$2C,$1C,$6E,$17,$60
anim_data_2E53
            DB      $17
            DB      $07
            DB      $00,$7C,$0F,$00,$00,$11,$4C,$08,$6C,$17,$60
anim_data_2E60
            DB      $17
; --- End data region (38 bytes) ---

            ora  $7C00           ; A=A+$57 ; [SP-709]

; --- Data region (74 bytes) ---
            DB      $1F,$18,$00,$3A,$00,$1D,$4C,$0B,$40,$0B,$00,$00,$7C,$3F,$30,$00
            DB      $38,$00,$1C,$0C,$0D,$00,$0D,$00,$00,$78,$7F,$30,$00,$6C,$00,$36
            DB      $0C,$1A,$00,$1A,$00,$00,$0C,$76,$1F,$00,$46,$01,$63,$4C,$31,$40
            DB      $31,$00,$00,$06,$46,$0F,$00,$43,$01,$63,$4C,$31,$40,$31,$00,$00
            DB      $07,$07,$00,$40,$43,$43,$63,$6D,$71,$60
; --- End data region (74 bytes) ---

anim_data_2EAE  adc  ($00),Y         ; A=A+$57 ; [SP-740]
            brk  #$05            ; A=A+$57 ; [SP-743]

; --- Data region (251 bytes) ---
            DB      $05,$00,$00,$00,$18,$00,$00,$00,$0C,$00,$00,$40,$01,$00,$00,$00
            DB      $00,$18,$00,$00,$00,$0C,$00,$00,$20,$03,$40,$1F,$00,$70,$7E,$38
            DB      $00,$1C,$0C,$1C,$00,$78,$07,$70,$07,$00,$70,$18,$38,$00,$1C,$0C
            DB      $1C,$00,$40,$07,$7C,$01,$00,$70,$18,$38,$18,$1C,$1E,$1C,$00,$70
            DB      $06,$7E,$00,$00,$20,$1C,$10,$18,$00,$0D,$00,$60,$00,$0C,$3F,$00
            DB      $00,$7C,$1B,$7E,$59,$6F,$40,$6F,$30,$00,$5C,$1F,$00,$00,$7A,$19
            DB      $7D,$5A,$6F,$40,$6F,$1B,$00,$78,$0F,$00,$00,$71,$58,$38,$5C,$2F
            DB      $40,$2F,$0E,$00,$78,$1F,$00,$00,$22,$18,$11,$58,$2F,$40,$2F,$1A
            DB      $00,$78,$3F,$30,$00,$74,$00,$3A,$18,$17,$00,$17,$00,$00,$78,$7F
            DB      $60,$00,$70,$00,$38,$18,$1A,$00,$1A,$00,$00,$70,$7F,$61,$00,$58
            DB      $01,$6C,$18,$34,$00,$34,$00,$00,$18,$6C,$3F,$00,$0C,$03,$46,$19
            DB      $63,$00,$63,$00,$00,$0C,$0C,$1F,$00,$06,$03,$46,$19,$63,$00,$63
            DB      $00,$00,$0E,$0E,$00,$00,$07,$07,$47,$5B,$63,$41,$63,$01,$00,$0A
            DB      $0A,$00,$92,$0F,$62,$10,$32,$11,$02,$12,$D2,$12,$A2,$13,$72,$14
            DB      $00,$60,$00,$30,$00,$00,$00,$00,$00,$06,$00,$00,$00,$00,$60,$00
            DB      $30,$00,$00,$00,$00,$00,$0D,$00,$00,$00,$60
; --- End data region (251 bytes) ---

anim_data_2FAD  adc  $3073,Y         ; A=A+$57 ; [SP-854]
            sec                  ; A=A+$57 ; [SP-854]
            brk  #$38            ; A=A+$57 ; [SP-857]
            DB      $00,$60
anim_data_2FB5
            DB      $1F
            brk  #$00            ; A=A+$57 ; [SP-860]
            brk  #$60            ; A=A+$57 ; [SP-860]
anim_data_2FBA  adc  ($70,X)         ; A=A+$57 ; [SP-858]
            bmi  anim_data_2FF6      ; A=A+$57 ; [SP-858]
            brk  #$38            ; A=A+$57 ; [SP-861]

; ---
            DB      $00,$00,$1E,$40,$7F,$00,$60
; ---

anim_data_2FC7  adc  ($70),Y         ; A=A+$57 ; [SP-867]
            sec                  ; A=A+$57 ; [SP-867]
            sec                  ; A=A+$57 ; [SP-867]
            clc                  ; A=A+$57 ; [SP-867]
            sec                  ; A=A+$57 ; [SP-867]
            brk  #$28            ; A=A+$57 ; [SP-870]

; --- Data region (39 bytes) ---
            DB      $1A,$78,$0F,$00,$40,$68,$20,$34,$00,$18,$00,$00,$0A,$1B,$7E,$03
            DB      $00,$78,$67,$7C,$33,$5F,$19,$5F,$01,$0A,$38,$7F,$00,$00,$74,$63
            DB      $7A,$31,$5F,$1B,$5F,$1B,$02
; --- End data region (39 bytes) ---

; XREF: 1 ref (1 branch) from anim_data_2FBA
anim_data_2FF6  bvs  anim_data_3017      ; A=A+$57 ; [SP-875]
            brk  #$00            ; A=A+$57 ; [SP-875]

; ---
            DB      $62,$61,$72,$30,$5F,$3C,$5F,$7C,$01,$70,$3F,$00,$00,$44,$60
anim_data_3009
            DB      $22
; ---

            bmi  $306B           ; A=A+$57 ; [SP-876]
            clc                  ; A=A+$57 ; [SP-876]
anim_data_300D
            DB      $5F
            clc                  ; A=A+$57 ; [SP-876]
            brk  #$70            ; A=A+$57 ; [SP-876]

; ---
            DB      $7F,$00,$00,$68,$61,$72
; ---

anim_data_3017  bmi  anim_data_3047      ; A=A+$57 ; [SP-876]
            brk  #$2E            ; A=A+$57 ; [SP-879]

; ---
            DB      $00,$00,$70,$7F,$61,$00,$60,$61,$70,$30,$34,$00,$34,$00,$00,$60
anim_data_302B
            DB      $7F
            DB      $43
; ---

            ora  ($30,X)         ; [SP-884]

; ---
            DB      $03,$58,$01,$68,$00,$68,$00,$00,$30,$58,$47,$81,$18,$06,$0C,$03
            DB      $46,$01,$46,$01,$00,$30,$18,$7E
; ---

; XREF: 1 ref (1 branch) from anim_data_3017
anim_data_3047  brk  #$18            ; A=A+$57 ; [SP-890]

; --- Data region (127 bytes) ---
            DB      $06,$0C,$03,$06,$03,$46,$01,$00,$38,$1C,$3C,$00,$1C,$0E,$0E,$07
            DB      $07,$07,$47,$03,$00,$28,$14,$00,$00,$00,$40,$01,$60,$00,$00,$00
            DB      $00,$00,$0C,$00,$00,$00,$00,$40,$01,$60,$00,$00,$00,$00,$00,$1A
            DS      3
            DB      "@sgap"
            DB      $00 ; null terminator
            DB      $70,$00,$40,$3F,$00,$00,$00,$40,$43,$61,$61,$70,$00,$70,$00,$00
            DB      $3C,$00,$7F,$01,$40,$63,$61,$71,$70,$30,$70,$00,$50,$34,$70,$1F
            DB      $00,$00,$51,$41,$68,$00,$30,$00,$00,$14,$36,$7C,$07,$00,$70,$4F
            DB      $79,$67,$3E,$33,$3E,$03,$14,$70,$7E,$01,$00,$68,$47,$75,$63,$3E
            DB      $37,$3E,$37,$04,$60
anim_data_30C7
            DB      $3F
; --- End data region (127 bytes) ---

            brk  #$00            ; A=A+$57 ; [SP-931]

; ---
            DB      $44
            DB      $43,$65,$61,$3E,$79,$3E,$79,$03,$60
anim_data_30D4
            DB      $7F
; ---

            brk  #$00            ; A=A+$57 ; [SP-931]
            php                  ; A=A+$57 ; [SP-931]

; ---
            DB      "AE`>1>1"
            DB      $00 ; null terminator
            DB      $60
anim_data_30E1
            DB      $7F
; ---

            ora  ($00,X)         ; A=A+$57 ; [SP-927]
            bvc  $3129           ; A=A+$57 ; [SP-927]

; ---
            DB      $65,$61,$5C,$00,$5C,$00,$00,$60
anim_data_30EE
            DB      $7F
            DB      $43
; ---

            ora  ($40,X)         ; [SP-931]

; ---
            DB      $43,$61,$61,$68,$00,$68,$00,$00,$40,$7F,$07,$03,$60
; ---

anim_data_30FF  asl  $30             ; A=A+$57 ; [SP-934]
            DB      $03
            bvc  $3105           ; A=A+$57 ; [SP-934]
            bvc  $3107           ; A=A+$57 ; [SP-934]
            brk  #$60            ; A=A+$57 ; [SP-934]
anim_data_3108  bmi  anim_data_3119     ; A=A+$57 ; [SP-932]
            DB      $83
            bmi  anim_data_3119     ; A=A+$57 ; [SP-932]

; ---
            DB      $18,$06,$0C,$03,$0C,$03,$00,$60
; ---

anim_data_3115  bmi  anim_data_3193     ; A=A+$57 ; [SP-930]
            ora  ($30,X)         ; A=A+$57 ; [SP-930]
anim_data_3119
            DB      $0C
            clc                  ; A=A+$57 ; [SP-930]
            asl  $0C             ; A=A+$57 ; [SP-930]

; --- Data region (54 bytes) ---
            DB      $06,$0C,$03,$00,$70,$38,$78,$00,$38,$1C,$1C,$0E,$0E,$0E,$0E,$07
            DB      $00,$50,$28,$00,$00,$00,$00,$03,$40,$01,$00,$00,$00,$00,$18,$00
            DS      4
            DB      $03,$40,$01,$00,$00,$00,$00,$34,$00,$00,$00,$00,$67,$4F,$43,$61
            DB      $01,$60
; --- End data region (54 bytes) ---

anim_data_3153  ora  ($00,X)         ; A=A+$57 ; [SP-963]
            DB      $7F
            brk  #$00            ; A=A+$57 ; [SP-963]
            brk  #$00            ; A=A+$57 ; [SP-963]

; ---
            DB      $07,$43,$43,$61,$01,$60
; ---

anim_data_3160  ora  ($00,X)         ; A=A+$57 ; [SP-964]
            sei                  ; A=A+$57 ; [SP-964]
            brk  #$7E            ; A=A+$57 ; [SP-967]

; ---
            DB      $03,$00,$47,$43,$63,$61,$61,$60,$01,$20,$69,$60
anim_data_3171
            DB      $3F
; ---

            brk  #$00            ; A=A+$57 ; [SP-967]

; ---
            DB      $22
            DB      $03,$51,$01,$60,$00,$00,$28,$6C,$78,$0F,$00,$60
anim_data_3181
            DB      $1F
            DB      $73
            DB      $4F
; ---

            adc  $7C66,X         ; A=A+$57 ; [SP-972]
            asl  $28             ; A=A+$57 ; [SP-972]
            rts                  ; A=A+$57 ; [SP-970]
anim_data_318A  adc  !$0003,X        ; A=A+$57 ; [SP-970]
            bvc  anim_data_319E      ; A=A+$57 ; [SP-970]

; ---
            DB      $6B,$47,$7D,$6E
anim_data_3193
            DB      $7C
; ---

            ror  $4008           ; A=A+$57 ; [SP-967]

; ---
            DB      $7F,$00,$00,$08,$07,$4B,$43
; ---

; XREF: 1 ref (1 branch) from anim_data_318A
anim_data_319E  adc  $7D72,X         ; A=A+$57 ; [SP-965]

; --- Data region (48 bytes) ---
            DB      $72
            DB      $07
            DB      $40,$7F,$01,$00,$10,$02,$0B,$41,$7D,$62,$7C,$62,$00,$40,$7F,$03
            DB      $00,$20,$07,$4B,$43,$39,$01,$38,$01,$00,$40,$7F,$07,$03,$00,$07
            DB      $43,$43,$51,$01,$50,$01,$00,$00,$7F,$0F,$06,$40,$0D,$60
; --- End data region (48 bytes) ---

anim_data_31D1  asl  $20             ; A=A+$57 ; [SP-968]
            DB      $03
            jsr  !$0003          ; A=A+$57 ; [SP-968]

; ---
            DB      $40,$61,$1E,$86,$60
; ---

anim_data_31DC  clc                  ; A=A+$57 ; [SP-965]
            bmi  anim_data_31EB      ; A=A+$57 ; [SP-965]
            clc                  ; A=A+$57 ; [SP-965]
            asl  $18             ; A=A+$57 ; [SP-965]
            asl  $00             ; A=A+$57 ; [SP-965]
; Interrupt return (RTI)
            rti                  ; A=A+$57 ; [SP-962]
            DB      $61,$78,$03,$60
anim_data_31E9  clc                  ; A=A+$57 ; [SP-962]
            bmi  anim_data_31F8     ; A=A+$57 ; [SP-962]
            clc                  ; A=A+$57 ; [SP-962]
            DB      $0C

; ---------------------------------------------------------------------------
; anim_data_31EE
; ---------------------------------------------------------------------------
anim_data_31EE  clc                  ; [SP-962]
            asl  $00             ; [SP-962]
            rts                  ; [SP-965]
anim_data_31F2  adc  ($70),Y         ; A=A+$57 ; [SP-965]
            ora  ($70,X)         ; A=A+$57 ; [SP-965]
            sec                  ; A=A+$57 ; [SP-965]
            sec                  ; A=A+$57 ; [SP-965]

; --- Data region (182 bytes) ---
anim_data_31F8
            DB      $1C
            DB      $1C
            DB      $1C
            DB      $1C,$0E,$00,$20,$51,$00,$00,$00,$00,$06,$00,$03,$00,$00,$00,$00
            DB      $30,$00,$00,$00,$00,$00,$06,$00,$03,$00,$00,$00,$00,$68,$00,$00
            DB      $00,$00,$4E,$1F,$07,$43,$03,$40,$03,$00,$7E,$01,$00,$00,$00,$0E
            DB      $06,$07,$43,$03,$40,$03,$00,$70,$01,$7C,$07,$00,$0E,$07,$47,$43
            DB      $43,$41,$03,$40,$52,$41,$7F,$00,$00,$44,$06,$22,$03,$40,$01,$00
            DB      $50,$58,$71,$1F,$00,$40,$3F,$66,$1F,$7B,$4D,$79,$0D,$50,$40,$7B
            DB      $07,$00,$20,$1F,$56,$0F,$7B,$5D,$79,$5D,$11,$00,$7F,$01,$00,$10
            DB      $0E,$16,$07,$7B,$65,$7B,$65,$0F,$00,$7F,$03,$00,$20,$04,$16,$02
            DB      $7B,$45,$79,$45,$01,$00,$7F,$07,$00,$40,$0E,$16,$07,$73,$02,$70
            DB      $02,$00,$00,$7F,$0F,$06,$00,$0E,$06,$07,$23,$03,$20,$03,$00,$00
            DB      $7E,$1F,$0C,$00,$1B,$40,$0D,$40,$06,$40,$06,$00,$00,$43,$3D,$8C
            DB      $40,$31,$60
; --- End data region (182 bytes) ---

anim_data_32AE  clc                  ; A=A+$57 ; [SP-1012]
            bmi  anim_data_32BD      ; A=A+$57 ; [SP-1012]
            bmi  anim_data_32BF      ; A=A+$57 ; [SP-1012]
            brk  #$00            ; A=A+$57 ; [SP-1015]

; ---
            DB      $43,$71,$07,$40,$31,$60
; ---

anim_data_32BB  clc                  ; A=A+$57 ; [SP-1015]
            bmi  anim_data_32D6      ; A=A+$57 ; [SP-1015]
            bmi  anim_data_32CC     ; A=A+$57 ; [SP-1015]
            brk  #$40            ; A=A+$57 ; [SP-1018]

; ---
            DB      $63,$61,$03,$60,$71,$70,$38,$38,$38,$38
anim_data_32CC
            DB      $1C
; ---

            brk  #$40            ; A=A+$57 ; [SP-1018]

; ---
            DB      $22,$01,$00,$00,$00,$0C,$00
; ---

; XREF: 1 ref (1 branch) from anim_data_32BB
anim_data_32D6  asl  $00             ; A=A+$57 ; [SP-1027]
            brk  #$00            ; A=A+$57 ; [SP-1030]

; --- Data region (42 bytes) ---
            DB      $00,$60,$00,$00,$00,$00,$00,$0C,$00,$06,$00,$00,$00,$00,$50,$01
            DS      3
            DB      $1C,$3F,$0E,$06,$07,$00,$07,$00,$7C,$03,$00,$00,$00,$1C,$0C,$0E
            DB      $06,$07,$00,$07,$00,$60
anim_data_3303
            DB      $03
; --- End data region (42 bytes) ---

            sei                  ; A=A+$57 ; [SP-1070]

; --- Data region (86 bytes) ---
            DB      $0F,$00,$1C,$0E,$0E,$07,$07,$03,$07,$00,$25,$03,$7F,$01,$00,$08
            DB      $0D,$44,$06,$00,$03,$00,$20,$31,$63,$3F,$00,$00,$7F,$4C,$3F,$76
            DB      $1B,$73,$1B,$20,$01,$77,$0F,$00,$40,$3E,$2C,$1F,$76,$3B,$73,$3B
            DB      $23,$00,$7E,$03,$00,$20,$1C,$2C,$0E,$76,$4B,$77,$4B,$1F,$00,$7E
            DB      $07,$00,$40,$08,$2C,$04,$76,$0B,$73,$0B,$03,$00,$7E,$0F,$00,$00
            DB      $1D,$2C,$0E,$66,$05,$60
; --- End data region (86 bytes) ---

anim_data_335B  ora  $00             ; A=A+$57 ; [SP-1092]
            brk  #$7E            ; A=A+$57 ; [SP-1095]

; --- Data region (33 bytes) ---
            DB      $1F,$0C,$00,$1C,$0C,$0E,$46,$06,$40,$06,$00,$00,$7C,$3F,$18,$00
            DB      $36,$00,$1B,$00,$0D,$00,$0D,$00,$00,$06,$7B,$98,$00,$63,$40,$31
            DB      $60
; --- End data region (33 bytes) ---

anim_data_3380  clc                  ; A=A+$57 ; [SP-1110]
            rts                  ; A=A+$57 ; [SP-1108]

; ---
            DB      $18,$00,$00,$06,$63,$0F,$00,$63,$40,$31,$60
; ---

anim_data_338D  bmi  anim_data_33EF      ; A=A+$57 ; [SP-1111]
            clc                  ; A=A+$57 ; [SP-1111]
            brk  #$00            ; A=A+$57 ; [SP-1114]

; --- Data region (93 bytes) ---
            DB      $47,$43,$07,$40,$63,$61,$71,$70,$70,$70,$38,$00,$00,$45,$02,$00
            DB      $00,$00,$18,$00,$0C,$00,$00,$00,$00,$40,$01,$00,$00,$00,$00,$18
            DB      $00,$0C,$00,$00,$00,$00,$20,$03,$00,$00,$00,$38,$7E,$1C,$0C,$0E
            DB      $00,$0E,$00,$78,$07,$00,$00,$00,$38,$18,$1C,$0C,$0E,$00,$0E,$00
            DB      $40,$07,$70,$1F,$00,$38,$1C,$1C,$0E,$0E,$06,$0E,$00,$4A,$06,$7E
            DB      $03,$00,$10,$1A,$08,$0D,$00,$06,$00,$40,$62,$46,$7F
; --- End data region (93 bytes) ---

; XREF: 1 ref (1 branch) from anim_data_338D
anim_data_33EF  brk  #$00            ; A=A+$57 ; [SP-1173]

; --- Data region (181 bytes) ---
            DB      $7E,$19,$7F,$6C,$37,$66,$37,$40,$02,$6E,$1F,$00,$00,$7D,$58,$3E
            DB      $6C,$77,$66,$77,$46,$00,$7C,$07,$00,$40,$38,$58,$1C,$6C,$17,$6F
            DB      $17,$3F,$00,$7C,$0F,$00,$00,$11,$58,$08,$6C,$17,$66,$17,$06,$00
            DB      $7C,$1F,$00,$00,$3A,$58,$1C,$4C,$0B,$40,$0B,$00,$00,$7C,$3F,$18
            DB      $00,$38,$18,$1C,$0C,$0D,$00,$0D,$00,$00,$78,$7F,$30,$00,$6C,$00
            DB      $36,$00,$1A,$00,$1A,$00,$00,$0C,$76,$B1,$00,$46,$01,$63,$40,$31
            DB      $40,$31,$00,$00,$0C,$46,$1F,$00,$46,$01,$63,$40,$61,$40,$31,$00
            DB      $00,$0E,$07,$0F,$00,$47,$43,$63,$61,$61,$61,$71,$00,$00,$0A,$05
            DS      3
            DB      $30,$00,$18,$00,$00,$00,$00,$00,$03,$00,$00,$00,$00,$30,$00,$18
            DS      4
            DB      $40,$06,$00,$00,$00,$70,$7C,$39,$18,$1C,$00,$1C,$00,$70,$0F,$00
            DB      $00,$00,$70,$30,$38,$18,$1C,$00,$1C,$00,$00,$0F,$60
anim_data_34A5
            DB      $3F
; --- End data region (181 bytes) ---

            brk  #$70            ; A=A+$57 ; [SP-1247]
            sec                  ; A=A+$57 ; [SP-1247]

; --- Data region (130 bytes) ---
            DB      $38,$1C,$1C,$0C,$1C,$00,$14,$0D,$7C,$07,$00,$20,$34,$10,$1A,$00
            DB      $0C,$00,$00,$45,$0D,$7F,$01,$00,$7C,$33,$7E,$59,$6F,$4C,$6F,$00
            DB      $05,$5C,$3F,$00,$00,$7A,$31,$7D,$58,$6F,$4D,$6F,$0D,$01,$78,$0F
            DB      $00,$00,$71,$30,$39,$58,$2F,$5E,$2F,$7E,$00,$78,$1F,$00,$00,$22
            DB      $30,$11,$58,$2F,$4C,$2F,$0C,$00,$78,$3F,$00,$00,$74,$30,$39,$18
            DB      $17,$00,$17,$00,$00,$78,$7F,$30,$00,$70,$30,$38,$18,$1A,$00,$1A
            DB      $00,$00,$70,$7F,$61,$00,$58,$01,$6C,$00,$34,$00,$34,$00,$00,$18
            DB      $6C,$E3,$00,$0C,$03,$46,$01,$63,$00,$63,$00,$00,$18,$0C,$3F,$00
            DB      $0C
anim_data_352A
            DB      $03
; --- End data region (130 bytes) ---

            lsr  $01             ; A=A+$57 ; [SP-1286]

; ---
            DB      $43,$01,$63,$00,$00,$1C,$0E,$1E,$00,$0E,$07,$47,$43,$43,$43,$63
            DB      $01,$00,$14,$0A,$00,$50,$15,$20,$16,$F0,$16,$C0,$17,$90,$18,$60
; ---

anim_data_354D  ora  $1A30,Y         ; A=A+$57 ; [SP-1293]
            brk  #$00            ; A=A+$57 ; [SP-1296]

; --- Data region (34 bytes) ---
            DB      $00,$30,$00,$30,$00,$00,$00,$06,$00,$00,$00,$00,$00,$00,$30,$00
            DB      $30,$00,$00,$00,$0D,$00,$3F,$00,$60,$31,$72,$30,$70,$30,$38,$00
            DB      $60
anim_data_3573
            DB      $1F
; --- End data region (34 bytes) ---

            rts                  ; A=A+$57 ; [SP-1326]
            DB      $0F
            brk  #$60            ; [SP-1326]
anim_data_3578  and  ($72),Y         ; [SP-1324]
            bmi  anim_data_35EC      ; [SP-1324]
            bmi  anim_data_35B6      ; [SP-1324]
            brk  #$00            ; A=A+$57 ; [SP-1327]

; ---
            DB      $1E,$78,$03,$00,$60
; ---

anim_data_3585  adc  $3873,X         ; A=A+$57 ; [SP-1330]
            bvs  anim_data_3602      ; A=A+$57 ; [SP-1330]
            sec                  ; A=A+$57 ; [SP-1330]
            clc                  ; A=A+$57 ; [SP-1330]
            plp                  ; A=A+$57 ; [SP-1329]

; --- Data region (41 bytes) ---
            DB      $1A,$7C,$01,$00,$40,$30,$22,$34,$00,$34,$00,$18,$0A,$1B,$7E,$00
            DB      $00,$78,$37,$7C,$33,$3E,$03,$5F,$19,$0A,$38,$3F,$00,$00,$74,$37
            DB      $78,$31,$3E,$01,$5F,$1B,$02,$70,$1F
; --- End data region (41 bytes) ---

; XREF: 2 refs (2 branches) from anim_data_3578, anim_data_3585
anim_data_35B6  brk  #$00            ; A=A+$57 ; [SP-1329]

; --- Data region (40 bytes) ---
            DB      $62,$3D,$70,$30,$3E,$01,$5F,$3C,$00,$70,$3F,$00,$00,$44,$30,$20
            DB      $30,$3E,$01,$5F,$18,$00,$70,$7F,$00,$00,$68,$31,$70,$30,$5C,$01
            DB      $2E,$00,$00,$70,$7F,$01,$00,$60
; --- End data region (40 bytes) ---

anim_data_35E0  and  ($70),Y         ; A=A+$57 ; [SP-1333]
            bmi  anim_data_364C      ; A=A+$57 ; [SP-1333]
            brk  #$34            ; A=A+$57 ; [SP-1336]

; ---
            DB      $00,$00,$60
anim_data_35E9
            DB      $7F
            DB      $63
; ---

            brk  #$30            ; [SP-1337]
            DB      $03
            cli                  ; A=A+$57 ; [SP-1337]
            ora  ($50,X)         ; A=A+$57 ; [SP-1337]
anim_data_35F1  ora  ($68,X)         ; A=A+$57 ; [SP-1337]
            brk  #$00            ; A=A+$57 ; [SP-1340]

; ---
            DB      $30,$58,$47,$01,$18,$06,$0C,$03,$0C,$03,$46,$01,$00
; ---

; XREF: 1 ref (1 branch) from anim_data_3585
anim_data_3602  bmi  anim_data_361C      ; A=A+$57 ; [SP-1340]
            lsr  $1801           ; A=A+$57 ; [SP-1340]
            asl  $0C             ; A=A+$57 ; [SP-1340]
            asl  $06             ; A=A+$57 ; [SP-1340]
            DB      $03
            asl  $03             ; A=A+$57 ; [SP-1340]

; ---
            DB      $00,$38,$1C,$7C,$00,$1C,$0E,$0E,$0E,$07,$07,$07,$07,$00
; ---

; XREF: 1 ref (1 branch) from anim_data_3602
anim_data_361C  plp                  ; A=A+$57 ; [SP-1343]
            DB      $14
            sec                  ; A=A+$57 ; [SP-1343]

; --- Data region (45 bytes) ---
            DS      4
            DB      $60,$00,$60,$00,$00,$00,$0C,$00,$00,$00,$00,$00,$00,$60,$00,$60
            DS      3
            DB      $1A,$00,$7E,$00,$40,$63,$64,$61,$60,$61,$70,$00,$40,$3F,$40,$1F
            DB      $00,$40,$63,$64,$61,$60
; --- End data region (45 bytes) ---

; XREF: 1 ref (1 branch) from anim_data_35E0
anim_data_364C  adc  ($70,X)         ; A=A+$57 ; [SP-1378]
            brk  #$00            ; A=A+$57 ; [SP-1381]

; --- Data region (54 bytes) ---
            DB      $3C,$70,$07,$00,$40,$7B,$67,$71,$60,$71,$71,$30,$50,$34,$78,$03
            DB      $00,$00,$61,$44,$68,$00,$68,$00,$30,$14,$36,$7C,$01,$00,$70,$6F
            DB      $78,$67,$7C,$06,$3E,$33,$14,$70,$7E,$00,$00,$68,$6F,$70,$63,$7C
            DB      $02,$3E,$37,$04,$60
anim_data_3685
            DB      $3F
; --- End data region (54 bytes) ---

            brk  #$00            ; A=A+$57 ; [SP-1390]
            DB      $44
            DB      $7B,$60
anim_data_368B  adc  ($7C,X)         ; A=A+$57 ; [SP-1388]
            DB      $02
            rol  !$0079,X        ; A=A+$57 ; [SP-1391]
            DB      $60
anim_data_3692
            DB      $7F
            brk  #$00            ; A=A+$57 ; [SP-1391]
            php                  ; A=A+$57 ; [SP-1391]

; ---
            DB      $61,$40,$60
anim_data_3699
            DB      $7C
            DB      $02
; ---

            rol  !$0031,X        ; [SP-1389]
            DB      $60
anim_data_369F
            DB      $7F
            ora  ($00,X)         ; A=A+$57 ; [SP-1387]
            bvc  $3707           ; A=A+$57 ; [SP-1387]
            DB      $60
anim_data_36A5  adc  ($38,X)         ; A=A+$57 ; [SP-1387]

; ---
            DB      $03
            DB      $5C
            DB      $00,$00,$60
anim_data_36AC
            DB      $7F
            DB      $03
; ---

            brk  #$40            ; [SP-1388]
            DB      $63,$60
anim_data_36B2  adc  ($50,X)         ; A=A+$57 ; [SP-1388]
            ora  ($68,X)         ; A=A+$57 ; [SP-1388]
            brk  #$00            ; A=A+$57 ; [SP-1391]

; ---
            DB      $40,$7F,$47,$01,$60
; ---

anim_data_36BD  asl  $30             ; A=A+$57 ; [SP-1388]
            DB      $03
            jsr  $5003           ; A=A+$57 ; [SP-1388]
            DB      $01,$00,$60
anim_data_36C6  bmi  anim_data_36D7     ; A=A+$57 ; [SP-1386]
            DB      $03
            bmi  anim_data_36D7     ; A=A+$57 ; [SP-1386]

; ---
            DB      $18,$06,$18,$06,$0C,$03,$00,$60
; ---

anim_data_36D3  bmi  anim_data_36F1      ; A=A+$57 ; [SP-1384]
            DB      $03
            bmi  $36E4           ; A=A+$57 ; [SP-1384]
            clc                  ; A=A+$57 ; [SP-1384]

; ---
            DB      $0C
            DB      $0C,$06,$0C,$06,$00,$70,$38,$78,$01,$38,$1C,$1C,$1C,$0E,$0E,$0E
            DB      $0E,$00,$50,$28,$70,$00,$00
; ---

; XREF: 1 ref (1 branch) from anim_data_36D3
anim_data_36F1  brk  #$00            ; A=A+$57 ; [SP-1386]

; --- Data region (48 bytes) ---
            DB      $40,$01,$40,$01,$00,$00,$18,$00,$00,$00,$00,$00,$00,$40,$01,$40
            DB      $01,$00,$00,$34,$00,$7C,$01,$00,$47,$49,$43,$41,$43,$61,$01,$00
            DB      $7F,$00,$3F,$00,$00,$47,$49,$43,$41,$43,$61,$01,$00,$78,$60
anim_data_3722
            DB      $0F
; --- End data region (48 bytes) ---

            brk  #$00            ; A=A+$57 ; [SP-1408]

; ---
            DB      $77
            DB      $4F,$63,$41,$63,$63,$61,$20,$69,$70,$07,$00,$00,$42,$09,$51,$01
            DB      $50,$01,$60
; ---

anim_data_3739  plp                  ; A=A+$57 ; [SP-1412]
            jmp  ($0378)         ; A=A+$57 ; [SP-1412]

; --- Data region (82 bytes) ---
            DB      $00,$60,$5F,$71,$4F,$79,$0D,$7C,$66,$28,$60,$7D,$01,$00,$50,$5F
            DB      $61,$47,$79,$05,$7C,$6E,$08,$40,$7F,$00,$00,$08,$77,$41,$43,$79
            DB      $05,$7C,$72,$01,$40,$7F,$01,$00,$10,$42,$01,$41,$79,$05,$7C,$62
            DB      $00,$40,$7F,$03,$00,$20,$47,$41,$43,$71,$06,$38,$01,$00,$40,$7F
            DB      $07,$00,$00,$47,$41,$43,$21,$03,$50,$01,$00,$00,$7F,$0F,$03,$40
            DB      $0D,$60
; --- End data region (82 bytes) ---

anim_data_378F  asl  $40             ; A=A+$57 ; [SP-1409]
            asl  $20             ; A=A+$57 ; [SP-1409]
            DB      $03
            brk  #$40            ; A=A+$57 ; [SP-1409]
            DB      $61,$1E,$06,$60
anim_data_379A  clc                  ; A=A+$57 ; [SP-1406]
            bmi  anim_data_37A9      ; A=A+$57 ; [SP-1406]
            bmi  anim_data_37AB     ; A=A+$57 ; [SP-1406]
            clc                  ; A=A+$57 ; [SP-1406]
            asl  $00             ; A=A+$57 ; [SP-1406]
; Interrupt return (RTI)
            rti                  ; A=A+$57 ; [SP-1403]
            DB      $61,$38,$06,$60
anim_data_37A7  clc                  ; A=A+$57 ; [SP-1403]
            bmi  anim_data_37C2     ; A=A+$57 ; [SP-1403]
            clc                  ; A=A+$57 ; [SP-1403]
anim_data_37AB
            DB      $0C
            clc                  ; A=A+$57 ; [SP-1403]
            DB      $0C
            DB      $00,$60
anim_data_37B0  adc  ($70),Y         ; A=A+$57 ; [SP-1406]
            DB      $03
            bvs  $37ED           ; A=A+$57 ; [SP-1406]

; ---
            DB      $38,$38,$1C,$1C,$1C,$1C,$00,$20,$51,$60
; ---

anim_data_37BF  ora  ($00,X)         ; A=A+$57 ; [SP-1406]

; --- Data region (171 bytes) ---
            DB      $00
anim_data_37C2
            DB      $00,$00,$03,$00,$03,$00,$00,$30,$00,$00,$00,$00,$00,$00,$00,$03
            DB      $00,$03,$00,$00,$68,$00,$78,$03,$00,$0E,$13,$07,$03,$07,$43,$03
            DB      $00,$7E,$01,$7E,$00,$00,$0E,$13,$07,$03,$07,$43,$03,$00,$70,$41
            DB      $1F,$00,$00,$6E,$1F,$47,$03,$47,$47,$43,$41,$52,$61,$0F,$00,$00
            DB      $04,$13,$22,$03,$20,$03,$40,$51,$58,$71,$07,$00,$40,$3F,$63,$1F
            DB      $73,$1B,$78,$4D,$51,$40,$7B,$03,$00,$20,$3F,$43,$0F,$73,$0B,$78
            DB      $5D,$11,$00,$7F,$01,$00,$10,$6E,$03,$07,$73,$0B,$78,$65,$03,$00
            DB      $7F,$03,$00,$20,$04,$03,$02,$73,$0B,$78,$45,$01,$00,$7F,$07,$00
            DB      $40,$0E,$03,$07,$63,$0D,$70,$02,$00,$00,$7F,$0F,$00,$00,$0E,$03
            DB      $07,$43,$06,$20,$03,$00,$00,$7E,$1F,$06,$00,$1B,$40,$0D,$00,$0D
            DB      $40,$06,$00,$00,$43,$3D,$0C,$40,$31,$60
; --- End data region (171 bytes) ---

anim_data_386C  clc                  ; A=A+$57 ; [SP-1467]
            rts                  ; A=A+$57 ; [SP-1465]

; --- Data region (171 bytes) ---
            DB      $18,$30,$0C,$00,$00,$43,$71,$0C,$40,$31,$60,$30,$30,$18,$30,$18
            DB      $00,$40,$63,$61,$07,$60,$71,$70,$70,$38,$38,$38,$38,$00,$40,$22
            DB      $41,$03,$00,$00,$00,$00,$06,$00,$06,$00,$00,$60,$00,$00,$00,$00
            DS      3
            DB      $06,$00,$06,$00,$00,$50,$01,$70,$07,$00,$1C,$26,$0E,$06,$0E,$06
            DB      $07,$00,$7C,$03,$7C,$01,$00,$1C,$26,$0E,$06,$0E,$06,$07,$00,$60
anim_data_38C1
            DB      $03
            DB      $3F
            DB      $00,$00,$5C,$3F,$0E,$07,$0E,$0F,$07,$03,$25,$43,$1F,$00,$00,$08
            DB      $26,$44,$06,$40,$06,$00,$23,$31,$63,$0F,$00,$00,$7F,$46,$3F,$66
            DB      $37,$70,$1B,$23,$01,$77,$07,$00,$40,$7E,$06,$1F,$66,$17,$70,$3B
            DB      $23,$00,$7E,$03,$00,$20,$5C,$07,$0E,$66,$17,$70,$4B,$07,$00,$7E
            DB      $07,$00,$40,$08,$06,$04,$66,$17,$70,$0B,$03,$00,$7E,$0F,$00,$00
            DB      $1D,$06,$0E,$46,$1B,$60
; --- End data region (171 bytes) ---

anim_data_3919  ora  $00             ; A=A+$57 ; [SP-1526]
            brk  #$7E            ; A=A+$57 ; [SP-1529]

; --- Data region (35 bytes) ---
            DB      $1F,$00,$00,$1C,$06,$0E,$06,$0D,$40,$06,$00,$00,$7C,$3F,$0C,$00
            DB      $36,$00,$1B,$00,$1A,$00,$0D,$00,$00,$06,$7B,$18,$00,$63,$40,$31
            DB      $40,$31,$60
; --- End data region (35 bytes) ---

anim_data_3940  clc                  ; A=A+$57 ; [SP-1541]
            brk  #$00            ; A=A+$57 ; [SP-1544]

; --- Data region (55 bytes) ---
            DB      $06,$63,$19,$00,$63,$40,$61,$60,$30,$60,$30,$00,$00,$47,$43,$0F
            DB      "@caaqppp"
            DB      $00 ; null terminator
            DB      $00,$45,$02,$07,$00,$00,$00,$00,$0C,$00,$0C,$00,$00,$40,$01,$00
            DS      5
            DB      $0C,$00,$0C,$00,$00,$20,$03,$60
anim_data_3979
            DB      $0F
; --- End data region (55 bytes) ---

            brk  #$38            ; A=A+$57 ; [SP-1570]
            jmp  $0C1C           ; A=A+$57 ; [SP-1570]

; --- Data region (94 bytes) ---
            DB      $1C,$0C,$0E,$00,$78,$07,$78,$03,$00,$38,$4C,$1C,$0C,$1C,$0C,$0E
            DB      $00,$40,$07,$7E,$00,$00,$38,$7F,$1C,$0E,$1C,$1E,$0E,$06,$4A,$06
            DB      $3F,$00,$00,$10,$4C,$08,$0D,$00,$0D,$00,$46,$62,$46,$1F,$00,$00
            DB      $7E,$0D,$7F,$4C,$6F,$60,$37,$46,$02,$6E,$0F,$00,$00,$7D,$0D,$3E
            DB      $4C,$2F,$60,$77,$46,$00,$7C,$07,$00,$40,$38,$0F,$1C,$4C,$2F,$60
anim_data_39CF
            DB      $17
            DB      $0F
            DB      $00,$7C,$0F,$00,$00,$11,$0C,$08,$4C,$2F,$60
anim_data_39DC
            DB      $17
; --- End data region (94 bytes) ---

            asl  $00             ; A=A+$57 ; [SP-1592]

; --- Data region (9803 bytes) ---
            DB      $7C,$1F,$00,$00,$3A,$0C,$1C,$0C,$37,$40,$0B,$00,$00,$7C,$3F,$00
            DB      $00,$38,$0C,$1C,$0C,$1A,$00,$0D,$00,$00,$78,$7F,$18,$00,$6C,$00
            DB      $36,$00,$34,$00,$1A,$00,$00,$0C,$76,$31,$00,$46,$01,$63,$00,$63
            DB      $40,$31,$00,$00,$0C,$46,$33,$00,$46,$01,$43,$41,$61,$40,$61,$00
            DB      $00,$0E,$07,$1F,$00,$47,$43,$43,$63,$61,$61,$61,$01,$00,$0A,$05
            DB      $0E,$00,$00,$00,$00,$18,$00,$18,$00,$00,$00,$03,$00,$00,$00,$00
            DB      $00,$00,$18,$00,$18,$00,$00,$40,$06,$40,$1F,$00,$70,$18,$39,$18
            DB      $38,$18,$1C,$00,$70,$0F,$70,$07,$00,$70,$18,$39,$18,$38,$18,$1C
            DB      $00,$00,$0F,$7C,$01,$00,$70,$7E,$39,$1C,$38,$3C,$1C,$0C,$14,$0D
            DB      $7E,$00,$00,$20,$18,$11,$1A,$00,$1A,$00,$0C,$45,$0D,$3F,$00,$00
            DB      $7C,$1B,$7E,$19,$5F,$41,$6F,$0C,$05,$5C,$1F,$00,$00,$7A,$1B,$7C
            DB      $18,$5F,$40,$6F,$0D,$01,$78,$0F,$00,$00,$71,$1E,$38,$18,$5F,$40
            DB      $2F,$1E,$00,$78,$1F,$00,$00,$22,$18,$10,$18,$5F,$40,$2F,$0C,$00
            DB      $78,$3F,$00,$00,$74,$18,$38,$18,$6E,$00,$17,$00,$00,$78,$7F,$00
            DB      $00,$70,$18,$38,$18,$34,$00,$1A,$00,$00,$70,$7F,$31,$00,$58,$01
            DB      $6C,$00,$68,$00,$34,$00,$00,$18,$6C,$63,$00,$0C,$03,$46,$01,$46
            DB      $01,$63,$00,$00,$18,$0C,$67,$00,$0C,$03,$06,$03,$43,$01,$43,$01
            DB      $00,$1C,$0E,$3E,$00,$0E,$07,$07,$47,$43,$43,$43,$03,$00,$14,$0A
            DB      $1C,$00,$00,$00,$00,$00,$00,$00,$00,$80,$80,$80,$80,$80,$80,$80
            DB      $80,$00,$00,$00,$00,$00,$00,$00,$00,$80,$80,$80,$80,$80,$80,$80
            DB      $80,$00,$00,$00,$00,$00,$00,$00,$00,$80,$80,$80,$80,$80,$80,$80
            DB      $80,$00,$00,$00,$00,$00,$00,$00,$00,$80,$80,$80,$80,$80,$80,$80
            DB      $80,$28,$28,$28,$28,$28,$28,$28,$28,$A8,$A8,$A8,$A8,$A8,$A8,$A8
            DB      $A8,$28,$28,$28,$28,$28,$28,$28,$28,$A8,$A8,$A8,$A8,$A8,$A8,$A8
            DB      $A8,$28,$28,$28,$28,$28,$28,$28,$28,$A8,$A8,$A8,$A8,$A8,$A8,$A8
            DB      $A8,$28,$28,$28,$28,$28,$28,$28,$28,$A8,$A8,$A8,$A8,$A8,$A8,$A8
            DB      $A8,$50,$50,$50,$50,$50,$50,$50,$50,$D0,$D0,$D0,$D0,$D0,$D0,$D0
            DB      $D0,$50,$50,$50,$50,$50,$50,$50,$50,$D0,$D0,$D0,$D0,$D0,$D0,$D0
            DB      $D0,$50,$50,$50,$50,$50,$50,$50,$50,$D0,$D0,$D0,$D0,$D0,$D0,$D0
            DB      $D0,$50,$50,$50,$50,$50,$50,$50,$50,$D0,$D0,$D0,$D0,$D0,$D0,$D0
            DB      $D0,$20,$24,$28,$2C,$30,$34,$38,$3C,$20,$24,$28,$2C,$30,$34,$38
            DB      $3C,$21,$25,$29,$2D,$31,$35,$39,$3D,$21,$25,$29,$2D,$31,$35,$39
            DB      $3D,$22,$26,$2A,$2E,$32,$36,$3A,$3E,$22,$26,$2A,$2E,$32,$36,$3A
            DB      $3E,$23,$27,$2B,$2F,$33,$37,$3B,$3F,$23,$27,$2B,$2F,$33,$37,$3B
            DB      $3F,$20,$24,$28,$2C,$30,$34,$38,$3C,$20,$24,$28,$2C,$30,$34,$38
            DB      $3C,$21,$25,$29,$2D,$31,$35,$39,$3D,$21,$25,$29,$2D,$31,$35,$39
            DB      $3D,$22,$26,$2A,$2E,$32,$36,$3A,$3E,$22,$26,$2A,$2E,$32,$36,$3A
            DB      $3E,$23,$27,$2B,$2F,$33,$37,$3B,$3F,$23,$27,$2B,$2F,$33,$37,$3B
            DB      $3F,$20,$24,$28,$2C,$30,$34,$38,$3C,$20,$24,$28,$2C,$30,$34,$38
            DB      $3C,$21,$25,$29,$2D,$31,$35,$39,$3D,$21,$25,$29,$2D,$31,$35,$39
            DB      $3D,$22,$26,$2A,$2E,$32,$36,$3A,$3E,$22,$26,$2A,$2E,$32,$36,$3A
            DB      $3E,$23,$27,$2B,$2F,$33,$37,$3B,$3F,$23,$27,$2B,$2F,$33,$37,$3B
            DB      $3F,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01
            DB      $02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04
            DB      $08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10
            DB      $20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40
            DB      $01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02
            DB      $04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08
            DB      $10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20
            DB      $40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01
            DB      $02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04
            DB      $08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10
            DB      $20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40
            DB      $01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02
            DB      $04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08
            DB      $10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20
            DB      $40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01
            DB      $02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04
            DB      $08,$00,$00,$00,$00,$00,$00,$00,$01,$01,$01,$01,$01,$01,$01,$02
            DB      $02,$02,$02,$02,$02,$02,$03,$03,$03,$03,$03,$03,$03,$04,$04,$04
            DB      $04,$04,$04,$04,$05,$05,$05,$05,$05,$05,$05,$06,$06,$06,$06,$06
            DB      $06,$06,$07,$07,$07,$07,$07,$07,$07,$08,$08,$08,$08,$08,$08,$08
            DB      $09,$09,$09,$09,$09,$09,$09,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0B,$0B
            DB      $0B,$0B,$0B,$0B,$0B,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0D,$0D,$0D,$0D
            DB      $0D,$0D,$0D,$0E,$0E,$0E,$0E,$0E,$0E,$0E,$0F,$0F,$0F,$0F,$0F,$0F
            DB      $0F,$10,$10,$10,$10,$10,$10,$10,$11,$11,$11,$11,$11,$11,$11,$12
            DB      $12,$12,$12,$12,$12,$12,$13,$13,$13,$13,$13,$13,$13,$14,$14,$14
            DB      $14,$14,$14,$14,$15,$15,$15,$15,$15,$15,$15,$16,$16,$16,$16,$16
            DB      $16,$16,$17,$17,$17,$17,$17,$17,$17,$18,$18,$18,$18,$18,$18,$18
            DB      $19,$19,$19,$19,$19,$19,$19,$1A,$1A,$1A,$1A,$1A,$1A,$1A,$1B,$1B
            DB      $1B,$1B,$1B,$1B,$1B,$1C,$1C,$1C,$1C,$1C,$1C,$1C,$1D,$1D,$1D,$1D
            DB      $1D,$1D,$1D,$1E,$1E,$1E,$1E,$1E,$1E,$1E,$1F,$1F,$1F,$1F,$1F,$1F
            DB      $1F ; string length
            DB      "       !!!!!!!"
            DB      $22,$22,$22,$22,$22,$22,$22
            DB      "#######$$$"
            DB      "$$$$%%%%%%%&&&&&&&'''''''"
            DB      $00 ; null terminator
            DB      $01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02
            DB      $03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04
            DB      $05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06
            DB      $00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01
            DB      $02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03
            DB      $04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05
            DB      $06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00
            DB      $01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02
            DB      $03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04
            DB      $05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06
            DB      $00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01
            DB      $02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03
            DB      $04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05
            DB      $06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00
            DB      $01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02
            DB      $03,$04,$05,$06,$00,$01,$02,$03,$04,$05,$06,$00,$01,$02,$03,$30
            DB      $37,$46,$30,$43,$37,$46,$36,$43,$33,$37,$36,$30,$33,$37,$30,$36
            DB      $30,$30,$37,$37,$30,$37,$30,$30,$0D,$30,$1E,$E4,$20,$34,$30,$33
            DB      $45,$30,$44,$33,$45,$36,$44,$33,$37,$36,$30,$37,$37,$30,$36,$30
            DB      $30,$37,$45,$30,$33,$30,$30,$0D,$30,$1E,$E4,$20,$32,$30,$31,$43
            DB      $30,$45,$31,$43,$36,$45,$31,$37,$36,$30,$31,$37,$30,$46,$30,$30
            DB      $37,$45,$30,$37,$30,$30,$0D,$30,$1E,$E4,$20,$34,$30,$30,$38,$30
            DB      $43,$30,$38,$36,$43,$31,$37,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DS      38
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$02,$3E,$15,$E0,$04,$12,$0F,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$14,$14,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$A2,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D1
            DB      $AA,$D5,$AA,$D5,$A2,$C5,$AA,$D5,$8A,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$8A,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80
            DB      $80,$80,$C0,$81,$80,$80,$83,$80,$80,$80,$00,$80,$80,$80,$80,$80
            DB      $00,$80,$00,$80,$00,$80,$00,$80,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$F1,$B8,$F0
            DB      $B8,$DF,$80,$DF,$BC,$80,$F8,$9F,$80,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$C5,$AA,$D5,$A2,$95,$AA,$D4,$A2,$D5,$AA,$95,$AA,$D1
            DB      $AA,$95,$AA,$D5,$A2,$C1,$AA,$95,$82,$D5,$AA,$D5,$AA,$C5,$A2,$C5
            DB      $AA,$D5,$82
            ASC     "E*E*T*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      23
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80
            DB      $80,$80,$E0,$80,$80,$C0,$86,$C0,$9F,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A2,$B0,$A0
            DB      $B0,$DF,$80,$DF,$98,$80,$F8,$BF,$80,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$8A,$85,$AA,$D5,$A2,$95,$AA,$D4,$A2,$C5,$AA,$95,$AA,$D0
            DB      $AA,$85,$A8,$D5,$80,$C1,$8A,$95,$82,$D5,$A2,$95,$AA,$C5,$A2,$C1
            DB      $AA,$D5,$80
            ASC     "A*D*T*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      23
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$F0,$B0,$F2
            DB      $80,$B8,$B6,$B8,$80,$F0,$8F,$F0,$87,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$F4,$B0,$F0
            DB      $B0,$AE,$80,$AE,$80,$80,$F8,$FF,$B0,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$8A,$81,$AA,$D5,$A0,$95,$88,$D4,$82,$C5,$A2,$85,$AA,$D0
            DB      $A2,$85,$A8,$D1,$80,$C1,$82,$95,$80,$D5,$80,$95,$AA,$C1,$80,$C1
            DB      $AA,$D4,$80,$C0,$AA,$C0,$8A,$D4,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$F0,$B0,$F2
            DB      $80,$B8,$9C,$B8,$80,$80,$8F,$FC,$81,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$F0,$B0,$F0
            DB      $B0,$B4,$80,$B4,$80,$80,$F0,$FF,$E1,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$82,$80,$A8,$D4,$A0,$85,$88,$D4,$80,$C1,$A2,$85,$88,$D0
            DB      $A0,$81,$A0,$D1,$80,$80,$82,$95,$80,$D4,$80,$94,$A8,$81,$80,$81
            DB      $AA,$94,$80,$80,$8A,$C0,$8A,$D0,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$F0,$FC,$F3
            DB      $B0,$B8,$B4,$B8,$98,$E0,$8D,$FE,$80,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$D8,$81,$D8
            DB      $B1,$E8,$80,$E8,$80,$80,$98,$EC,$E3,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$82,$80,$A8,$D0,$80,$85,$88,$D4,$80,$C0,$A2,$85,$88,$D0
            DB      $80,$81,$A0,$C0,$80,$80,$82,$94,$80,$D4,$80,$94,$A8,$81,$80,$80
            DB      $AA,$94,$80,$80,$8A,$80,$8A,$C0,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A0,$B0,$A2
            DB      $B0,$80,$82,$80,$98,$80,$8C,$BF,$80,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$8C,$83,$8C
            DB      $B3,$C6,$81,$C6,$81,$80,$98,$98,$BF,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$A0,$90,$80,$85,$80,$90,$80,$C0,$80,$81,$80,$C0
            DB      $80,$81,$A0,$C0,$80,$80,$80,$84,$80,$90,$80,$84,$A0,$81,$80,$80
            DB      $88,$90,$80,$80,$8A,$80,$8A,$C0,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$FC,$B3,$FC
            DB      $B3,$DF,$81,$DF,$99,$80,$DC,$9F,$80,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$8C,$86,$86
            DB      $B3,$C6,$81,$C3,$81,$80,$9C,$9C,$9E,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$81,$80,$90,$80,$80,$80,$81,$80,$C0
; Address table (3 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$84,$80,$90,$80,$80,$A0,$80,$80,$80,$88,$80,$80,$80,$88,$80
            DB      $82,$C0,$AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00
            DS      34
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$FA,$B5,$F8
            DB      $B5,$DF,$81,$DF,$9B,$80,$F8,$8F,$80,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$8E,$8E,$87
            DB      $B7,$C7,$C3,$C3,$83,$80,$94,$94,$80,$80,$00,$00,$00,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$60
; --- End data region (9803 bytes) ---

frame_data_602A  rol  a               ; A=A+$57 ; [SP-11054]
            adc  $00,X           ; A=A+$57 ; [SP-11054]
            brk  #$00            ; A=A+$57 ; [SP-11057]

; --- Data region (123 bytes) ---
            DS      3
            DB      $2B,$55,$2A,$55,$2A,$03,$40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00
            DB      $2B,$0D,$30,$55,$01,$58,$6A,$00,$00,$00,$40,$55,$06,$AA,$D5,$00
            DS      12
            DB      $1E,$00,$00,$00,$00,$00,$00,$78,$01,$00,$00,$00,$00,$00,$00,$00
            DS      9
            DB      $AA,$02,$3E,$15,$E0,$04,$12,$0F,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$60
; --- End data region (123 bytes) ---

frame_data_60AA  rol  a               ; A=A+$57 ; [SP-11179]
            eor  $2A,X           ; A=A+$57 ; [SP-11179]
            eor  $2A,X           ; A=A+$57 ; [SP-11179]
            eor  $06,X           ; A=A+$57 ; [SP-11179]
            cli                  ; A=A+$57 ; [SP-11179]
            rol  a               ; A=A+$57 ; [SP-11179]
            ora  $7000,X         ; A=A+$57 ; [SP-11179]
            rol  a               ; A=A+$57 ; [SP-11179]
            and  $40,X           ; A=A+$57 ; [SP-11179]
            eor  $2A,X           ; A=A+$57 ; [SP-11179]
            eor  $2A,X           ; A=A+$57 ; [SP-11179]
            ora  $5530           ; A=A+$57 ; [SP-11179]
            rol  a               ; A=A+$57 ; [SP-11179]
            eor  $2A,X           ; A=A+$57 ; [SP-11179]
            ora  $5530           ; A=A+$57 ; [SP-11179]
            rol  a               ; A=A+$57 ; [SP-11179]
            eor  $6A,X           ; A=A+$57 ; [SP-11179]
            brk  #$2B            ; A=A+$57 ; [SP-11182]

; ---
            DB      $55,$2A,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$00,$00,$30,$06,$0F
            DB      $00,$00,$30,$40,$31,$30,$40,$31,$00,$40,$41,$01,$03,$0C,$0C,$60
; ---

frame_data_60EB  clc                  ; A=A+$57 ; [SP-11182]
            brk  #$46            ; A=A+$57 ; [SP-11185]

; ---
            DB      $01,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$00,$14,$14,$00,$00,$00
            DB      $00,$00,$D5,$60
; ---

frame_data_6102  rol  a               ; A=A+$57 ; [SP-11206]
            eor  $2A,X           ; A=A+$57 ; [SP-11206]
            eor  $2A,X           ; A=A+$57 ; [SP-11206]
            eor  $06,X           ; A=A+$57 ; [SP-11206]
            brk  #$00            ; A=A+$57 ; [SP-11209]

; --- Data region (119 bytes, mostly zeros) ---
            DS      15
            DB      $7C,$03,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      37
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (119 bytes) ---

frame_data_6182  rol  a               ; A=A+$57 ; [SP-11374]
            and  $00,X           ; A=A+$57 ; [SP-11374]
            brk  #$00            ; A=A+$57 ; [SP-11377]

; --- Data region (123 bytes) ---
            DS      19
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      26
            DB      $7F,$1F,$00,$00,$00,$70,$01,$00,$00,$00,$00,$AA,$D5,$AA,$D5,$AA
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$80,$80,$80,$80,$80
            DB      $80,$80,$80,$C0,$81,$80,$80
            ASC     " U*U*U*U*U*U*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (123 bytes) ---

frame_data_6202  rol  a               ; A=A+$57 ; [SP-11482]
            ora  !$0000          ; A=A+$57 ; [SP-11482]

; --- Data region (48 bytes, mostly zeros) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      4
            DB      $7E,$00,$70,$01,$7C,$01,$60
frame_data_6235
            DB      $03
; --- End data region (48 bytes) ---

            brk  #$1E            ; A=A+$57 ; [SP-11532]

; ---
            DS      10
            DB      $06,$70,$0F,$60
frame_data_6246
            DB      $1F
; ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 ; [SP-11544]
            DB      $3F
            brk  #$00            ; [SP-11544]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$A2,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80
; Address table (4 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$FC,$8F,$80,$A0,$D5,$AA,$D5,$AA,$D5,$8A,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_6282  rol  a               ; A=A+$57 ; [SP-11564]
            eor  $2A,X           ; A=A+$57 ; [SP-11564]
            eor  $1A,X           ; A=A+$57 ; [SP-11564]
            brk  #$00            ; A=A+$57 ; [SP-11567]

; --- Data region (62 bytes) ---
            DB      $58,$2A,$07,$00,$40,$2B,$35,$40,$55,$2A,$55,$2A,$0D,$30,$55,$2A
            DB      $55,$2A,$0D,$30,$55,$01,$58,$6A,$00,$2B,$55,$2A,$55,$06,$AA,$D5
            DS      5
            DB      $7E,$00,$70,$01,$7C,$01,$78,$03,$40,$1F,$00,$7F,$7F,$7F,$7F,$03
            DB      $3C,$70,$0F,$00,$00,$70,$0F,$60
frame_data_62C6
            DB      $1F
; --- End data region (62 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 ; [SP-11573]
            DB      $3F
            brk  #$00            ; [SP-11573]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80
            DB      $94,$A8,$85,$80,$D5,$AA,$95,$80,$B0,$80,$80,$80,$80,$80,$80,$80
            DB      $00,$80,$00,$80,$00,$80,$00,$80,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_6302  rol  a               ; A=A+$57 ; [SP-11606]
            and  $00,X           ; A=A+$57 ; [SP-11606]
            brk  #$00            ; A=A+$57 ; [SP-11609]

; --- Data region (56 bytes) ---
            DB      $00,$00,$70,$2A,$55,$6E,$55,$2A,$1D,$40,$55,$06,$00,$2B,$0D,$30
            DB      $55,$01,$00,$2B,$0D,$30,$55,$01,$58,$6A,$00,$2B,$0D,$00,$00,$00
            DB      $AA,$D5,$00,$00,$00,$00,$00,$7E,$01,$78,$07,$7C,$01,$78,$03,$00
            DB      $1F,$00,$3F,$40,$1F,$60
frame_data_633D
            DB      $0F
            DB      $3C
; --- End data region (56 bytes) ---

            jmp  !$001F          ; [SP-11622]

; ---
            DB      $00,$70,$0F,$60
frame_data_6346
            DB      $1F
; ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 ; [SP-11625]
            DB      $3F
            brk  #$02            ; [SP-11625]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$AA
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$FC,$8F,$80,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_6382  rol  a               ; A=A+$57 ; [SP-11658]
            ora  !$0000          ; A=A+$57 ; [SP-11658]

; ---
            DS      4
            DB      $60
; ---

frame_data_638B  eor  $2A,X           ; A=A+$57 ; [SP-11662]
            eor  $0E,X           ; A=A+$57 ; [SP-11662]
            brk  #$40            ; A=A+$57 ; [SP-11665]

; --- Data region (39 bytes) ---
            DB      $55,$06,$00,$2B,$0D,$30,$55,$01,$00,$2B,$0D,$30,$55,$01,$58,$6A
            DB      $00,$2B,$55,$2A,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$00,$7E,$07
            DB      $00,$7F,$07,$40,$1F,$60
frame_data_63B7
            DB      $7F
; --- End data region (39 bytes) ---

            rts                  ; A=A+$57 ; [SP-11677]
            DB      $7F
            adc  ($7F),Y         ; [SP-11677]

; ---
            DB      $70,$03,$78,$0F,$7E,$01,$7C,$0F,$00,$60
frame_data_63C6
            DB      $7F
            DB      $7F
            DB      $7F
; ---

            brk  #$00            ; [SP-11677]

; --- Data region (95 bytes, text data) ---
            DS      4
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$60
; --- End data region (95 bytes) ---

frame_data_642A  rol  a               ; A=A+$57 ; [SP-11695]
            eor  $03,X           ; A=A+$57 ; [SP-11695]
            brk  #$00            ; A=A+$57 ; [SP-11698]

; --- Data region (123 bytes) ---
            DB      $00,$00,$40,$2B,$55,$3A,$55,$2A,$07,$40,$55,$06,$00,$2B,$0D,$30
            DB      $55,$01,$00,$2B,$0D,$30,$55,$01,$58,$6A,$00,$00,$00,$40,$55,$06
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$33
            DS      4
            DB      $03,$00,$0C,$03,$00,$00,$00,$00,$00,$00,$30,$00,$00,$00,$00,$00
            DS      4
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$00,$00,$00,$00,$00
            DS      32
            DB      $AA,$D5,$60
; --- End data region (123 bytes) ---

frame_data_64AA  rol  a               ; A=A+$57 ; [SP-11825]
            eor  $2A,X           ; A=A+$57 ; [SP-11825]
            eor  $2A,X           ; A=A+$57 ; [SP-11825]
            eor  $06,X           ; A=A+$57 ; [SP-11825]
            cli                  ; A=A+$57 ; [SP-11825]
            rol  a               ; A=A+$57 ; [SP-11825]
            ora  $6000           ; A=A+$57 ; [SP-11825]
            rol  a               ; A=A+$57 ; [SP-11825]
            and  $40,X           ; A=A+$57 ; [SP-11825]
            eor  $2A,X           ; A=A+$57 ; [SP-11825]
            eor  $2A,X           ; A=A+$57 ; [SP-11825]
            ora  $5530           ; A=A+$57 ; [SP-11825]
            rol  a               ; A=A+$57 ; [SP-11825]
            eor  $2A,X           ; A=A+$57 ; [SP-11825]
            ora  $5530           ; A=A+$57 ; [SP-11825]
            rol  a               ; A=A+$57 ; [SP-11825]
            eor  $6A,X           ; A=A+$57 ; [SP-11825]
            brk  #$2B            ; A=A+$57 ; [SP-11828]
anim_data_xor eor  $2A,X           ; A=A+$57 ; [SP-11828]
            eor  $06,X           ; A=A+$57 ; [SP-11828]
            tax                  ; A=A+$57 X=A ; [SP-11828]
            cmp  $00,X           ; A=A+$57 X=A ; [SP-11828]

; ---
            DS      6
; ---

            bvs  $64DD           ; A=A+$57 X=A ; [SP-11837]
            asl  $00             ; A=A+$57 X=A ; [SP-11837]
            brk  #$18            ; A=A+$57 X=A ; [SP-11840]
            rts                  ; A=A+$57 X=A ; [SP-11838]
frame_data_64DF  clc                  ; A=A+$57 X=A ; [SP-11838]
            clc                  ; A=A+$57 X=A ; [SP-11838]
            rts                  ; A=A+$57 X=A ; [SP-11836]
            DB      $18,$00,$60
frame_data_64E5  rts                  ; A=A+$57 X=A ; [SP-11837]

; ---
            DB      $40,$01,$06,$06,$30,$30,$00,$63,$00,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; ---

frame_data_6502  rol  a               ; A=A+$57 X=A ; [SP-11858]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-11858]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-11858]
            eor  $06,X           ; A=A+$57 X=A ; [SP-11858]
            brk  #$00            ; A=A+$57 X=A ; [SP-11861]

; --- Data region (119 bytes, mostly zeros) ---
            DS      15
            DB      $2E,$07,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      37
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (119 bytes) ---

frame_data_6582  rol  a               ; A=A+$57 X=A ; [SP-12026]
            ora  !$0000,X        ; A=A+$57 X=A ; [SP-12026]

; --- Data region (124 bytes) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      25
            DB      $78,$7F,$7F,$1F,$00,$40,$7F,$01,$00,$00,$00,$00,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$80,$80,$80,$80
            DB      $80,$80,$80,$80,$A0,$83,$E0,$8F
            ASC     " U*U*U*U*U*U*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (124 bytes) ---

frame_data_6602  rol  a               ; A=A+$57 X=A ; [SP-12121]
            ora  !$0000          ; A=A+$57 X=A ; [SP-12121]

; --- Data region (65 bytes) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      4
            DB      $7E,$00,$70,$01,$7C,$01,$70,$03,$00,$0C,$00,$00,$00,$00,$00,$00
            DS      4
            DB      $02,$70,$0F,$60
frame_data_6646
            DB      $1F
; --- End data region (65 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-12186]
            DB      $3F
            brk  #$00            ; [SP-12186]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$AA,$C5,$AA,$D5,$A2,$95,$AA,$D4,$A2,$D5,$AA,$95,$AA,$80
; Address table (4 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$FC,$9F,$80,$A0,$C5,$A2,$C5,$AA,$D5,$82
            ASC     "E*E*T*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (55 bytes) ---

frame_data_6682  rol  a               ; A=A+$57 X=A ; [SP-12210]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-12210]
            eor  $1A,X           ; A=A+$57 X=A ; [SP-12210]
            brk  #$00            ; A=A+$57 X=A ; [SP-12213]

; --- Data region (56 bytes) ---
            DB      $58,$2A,$0D,$00,$60,$2A,$35,$40,$55,$2A,$55,$2A,$0D,$30,$55,$2A
            DB      $55,$2A,$0D,$30,$55,$01,$58,$6A,$00,$2B,$55,$2A,$55,$06,$AA,$D5
            DS      5
            DB      $7E,$00,$70,$01,$7C,$01,$78,$03,$70,$1F,$40,$7F,$7F,$7F,$7F,$07
            DB      $38,$60
frame_data_66C0
            DB      $0F
; --- End data region (56 bytes) ---

            brk  #$00            ; A=A+$57 X=A ; [SP-12220]
            bvs  $66D4           ; A=A+$57 X=A ; [SP-12220]
            DB      $60
frame_data_66C6
            DB      $1F
; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-12220]
            DB      $3F
            brk  #$00            ; [SP-12220]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80
            DB      $D5,$AA,$D5,$A8,$D5,$AA,$D5,$8A,$E8,$80,$E0,$8F,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_6702  rol  a               ; A=A+$57 X=A ; [SP-12253]
            ora  !$0000,X        ; A=A+$57 X=A ; [SP-12253]
            DS      3
            DB      $60
frame_data_670A  rol  a               ; A=A+$57 X=A ; [SP-12259]
            eor  $3A,X           ; A=A+$57 X=A ; [SP-12259]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-12259]
            ora  $5540           ; A=A+$57 X=A ; [SP-12259]
            asl  $00             ; A=A+$57 X=A ; [SP-12259]

; --- Data region (43 bytes) ---
            DB      $2B,$0D,$30,$55,$01,$00,$2B,$0D,$30,$55,$01,$58,$6A,$00,$2B,$0D
            DS      3
            DB      $AA,$D5,$00,$00,$00,$00,$00,$7E,$01,$78,$07,$7C,$01,$78,$03,$00
            DB      $1F,$00,$3F,$40,$1F,$60
frame_data_673D
            DB      $0F
            DB      $3C
; --- End data region (43 bytes) ---

; Interrupt return (RTI)
            rti                  ; [SP-12266]

; ---
            DB      $1F
            DB      $00,$00,$70,$0F,$60
frame_data_6746
            DB      $1F
; ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-12266]
            DB      $3F
            brk  #$03            ; [SP-12266]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$AA
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$FC,$9F,$C0,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_6782  rol  a               ; A=A+$57 X=A ; [SP-12299]
            ora  !$0000          ; A=A+$57 X=A ; [SP-12299]

; --- Data region (67 bytes) ---
            DS      4
            DB      $40,$55,$2A,$55,$06,$00,$40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00
            DB      $2B,$0D,$30,$55,$01,$58,$6A,$00,$2E,$55,$2A,$55,$06,$AA,$D5,$00
            DS      18
            DB      $70,$03,$00,$00,$00,$00,$3C,$00,$00,$00,$60
frame_data_67C7
            DB      $7F
            DB      $07
; --- End data region (67 bytes) ---

            brk  #$00            ; [SP-12346]

; --- Data region (95 bytes, text data) ---
            DS      4
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$60
; --- End data region (95 bytes) ---

frame_data_682A  rol  a               ; A=A+$57 X=A ; [SP-12364]
            eor  $7E,X           ; A=A+$57 X=A ; [SP-12364]
            DB      $7F
            DB      $7F
            DB      $7F
            brk  #$60            ; [SP-12364]
frame_data_6832  rol  a               ; A=A+$57 X=A ; [SP-12362]
            eor  $6E,X           ; A=A+$57 X=A ; [SP-12362]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-12362]
            ora  $5540           ; A=A+$57 X=A ; [SP-12362]
            asl  $2B40           ; A=A+$57 X=A ; [SP-12362]
            ora  $5530           ; A=A+$57 X=A ; [SP-12362]
            DB      $03
; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-12362]

; ---
            DB      $2B,$0D,$30,$55,$03,$5C,$6A,$00,$00,$00,$60
; ---

frame_data_684D  eor  $06,X           ; A=A+$57 X=A ; [SP-12367]
            tax                  ; A=A+$57 X=A ; [SP-12367]
            cmp  $00,X           ; A=A+$57 X=A ; [SP-12367]
            brk  #$00            ; A=A+$57 X=A ; [SP-12370]

; --- Data region (86 bytes, mostly zeros) ---
            DS      9
            DB      $18,$33,$00,$00,$00,$00,$03,$00,$0C,$03,$00,$00,$00,$00,$00,$00
            DB      $30,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$00,$00,$00,$00,$00
            DS      3
            DB      $D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      23
            DB      $AA,$D5,$60
; --- End data region (86 bytes) ---

frame_data_68AA  rol  a               ; A=A+$57 X=A ; [SP-12487]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-12487]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-12487]
            eor  $06,X           ; A=A+$57 X=A ; [SP-12487]
            cli                  ; A=A+$57 X=A ; [SP-12487]
            rol  a               ; A=A+$57 X=A ; [SP-12487]
            DB      $07
            brk  #$40            ; A=A+$57 X=A ; [SP-12487]

; --- Data region (41 bytes) ---
            DB      $2B,$35,$40,$55,$2A,$55,$2A,$0D,$30,$55,$2A,$55,$2A,$0D,$30,$55
            DB      $2A,$55,$7A,$00,$2B,$55,$2A,$55,$06,$AA,$D5,$00,$00,$00,$00,$00
            DS      4
            DB      $03,$00,$00,$18,$60
; --- End data region (41 bytes) ---

frame_data_68DF  clc                  ; A=A+$57 X=A ; [SP-12499]
            clc                  ; A=A+$57 X=A ; [SP-12499]
            rts                  ; A=A+$57 X=A ; [SP-12497]
            DB      $18,$00,$60
frame_data_68E5  rts                  ; A=A+$57 X=A ; [SP-12498]

; ---
            DB      $40,$01,$06,$06,$30,$60,$00,$63,$00,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; ---

frame_data_6902  rol  a               ; A=A+$57 X=A ; [SP-12523]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-12523]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-12523]
            eor  $06,X           ; A=A+$57 X=A ; [SP-12523]
            brk  #$00            ; A=A+$57 X=A ; [SP-12526]

; --- Data region (119 bytes) ---
            DS      15
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      37
            DB      $AA,$D5,$00,$00,$00,$70,$70,$78,$08,$79,$38,$1C,$22,$3E,$00,$44
            DB      $23,$00,$08,$1E,$0E,$0E,$00,$0E,$0F,$47,$63,$09,$01,$70,$09,$71
            DB      $79,$79,$09,$71,$01,$00,$00,$00,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$60
; --- End data region (119 bytes) ---

frame_data_6982  rol  a               ; A=A+$57 X=A ; [SP-12651]
            ora  !$0000          ; A=A+$57 X=A ; [SP-12651]

; --- Data region (124 bytes) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      3
            DB      $60,$00,$06,$06,$0C,$40,$01,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      5
            DB      $40,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$00,$00,$00,$00,$00,$AA,$D5,$AA
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$80,$80,$80
            DB      $80,$80,$80,$80,$80,$F8,$87,$F8,$83
            ASC     " U*U*U*U*U*U*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (124 bytes) ---

frame_data_6A02  rol  a               ; A=A+$57 X=A ; [SP-12740]
            ora  !$0000,X        ; A=A+$57 X=A ; [SP-12740]

; --- Data region (65 bytes, mostly zeros) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      4
            DB      $7E,$00,$70,$01,$7C,$01,$7E,$7F,$00,$00,$00,$00,$00,$00,$00,$00
            DS      5
            DB      $70,$0F,$60
frame_data_6A46
            DB      $1F
; --- End data region (65 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-12803]
            DB      $3F
            brk  #$00            ; [SP-12803]

; ---
            DS      4
            DB      $AA,$D5,$8A,$85,$AA,$D5,$A2,$95,$AA
frame_data_6A58
            DB      $D4
; ---

            ldx  #$C5            ; A=A+$57 X=$00C5 ; [SP-12814]

; --- Data region (39 bytes) ---
            DB      $AA,$95,$AA,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$FC,$BF,$98
            DB      $A0,$C5,$A2,$C1,$AA,$D5,$80
            ASC     "A*D*T*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (39 bytes) ---

frame_data_6A82  rol  a               ; A=A+$57 X=$00C5 ; [SP-12830]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-12830]
            eor  $1A,X           ; -> $00DF ; A=A+$57 X=$00C5 ; [SP-12830]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-12833]

; --- Data region (51 bytes) ---
            DB      $58,$2A,$1D,$00,$70,$2A,$35,$40,$55,$2A,$55,$2A,$0D,$30,$55,$2A
            DB      $55,$2A,$0D,$30,$55,$01,$58,$6A,$00,$2B,$55,$2A,$55,$06,$AA,$D5
            DS      5
            DB      $7E,$00,$70,$01,$7C,$01,$78,$03,$00,$1F,$00,$7F,$60
frame_data_6ABB
            DB      $3F
; --- End data region (51 bytes) ---

            bvs  $6AC5           ; A=A+$57 X=$00C5 ; [SP-12842]
            bvs  $6B20           ; A=A+$57 X=$00C5 ; [SP-12842]
frame_data_6AC0
            DB      $0F
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-12840]
            bvs  $6AD4           ; A=A+$57 X=$00C5 ; [SP-12840]
            DB      $60
frame_data_6AC6
            DB      $1F
; Interrupt return (RTI)
            rti                  ; A=A+$57 X=$00C5 ; [SP-12840]
            DB      $3F
            brk  #$00            ; [SP-12840]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A0
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$8A,$FE,$81,$F8,$83,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_6B02  rol  a               ; A=A+$57 X=$00C5 ; [SP-12876]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-12876]

; --- Data region (56 bytes) ---
            DS      3
            DB      $40,$2B,$55,$2A,$55,$2A,$07,$40,$55,$06,$00,$2B,$0D,$30,$55,$01
            DB      $00,$2B,$0D,$30,$55,$01,$58,$6A,$00,$2B,$1D,$00,$00,$00,$AA,$D5
            DS      5
            DB      $7E,$03,$7C,$07,$7C,$01,$78,$03,$00,$1F,$00,$3F,$40,$1F,$60
frame_data_6B3D
            DB      $0F
; --- End data region (56 bytes) ---

            rol  $1F40,X         ; -> $2005 ; A=A+$57 X=$00C5 ; [SP-12895]

; --- Data region (65 bytes) ---
            DB      $00,$00,$70,$1F,$70,$1F,$40,$3F,$40,$03,$00,$00,$00,$00,$AA,$D5
; Address table (6 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$FC,$BF,$C0,$80,$00
            DS      10
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (65 bytes) ---

frame_data_6B82  rol  a               ; A=A+$57 X=$00C5 ; [SP-12925]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-12925]

; --- Data region (164 bytes) ---
            DS      4
            DB      $40,$55,$2A,$55,$06,$00,$40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00
            DB      $2B,$0D,$30,$55,$01,$58,$6A,$00,$2C,$55,$2A,$55,$06,$AA,$D5,$00
            DS      18
            DB      $70,$01,$00,$00,$00,$00,$0E,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      3
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$60
; --- End data region (164 bytes) ---

frame_data_6C2A  rol  a               ; A=A+$57 X=$00C5 ; [SP-12996]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-12996]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-12996]
            eor  $01,X           ; -> $00C6 ; A=A+$57 X=$00C5 ; [SP-12996]
            bvs  frame_data_6C5D      ; A=A+$57 X=$00C5 ; [SP-12996]
            eor  $46,X           ; -> $010B ; A=A+$57 X=$00C5 ; [SP-12996]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-12996]
            ora  $5540,X         ; -> $5605 ; A=A+$57 X=$00C5 ; [SP-12996]

; --- Data region (35 bytes) ---
            DB      $1A,$60,$2A,$0D,$30,$55,$06,$60,$2A,$0D,$30,$55,$06,$56,$6A,$00
            DB      $7E,$01,$30,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      3
; --- End data region (35 bytes) ---

; XREF: 1 ref (1 branch) from frame_data_6C2A
frame_data_6C5D  bvs  frame_data_6C7E      ; A=A+$57 X=$00C5 ; [SP-13015]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13015]

; ---
            DB      $00,$40,$01,$00,$46,$01,$00,$30,$30,$00,$03,$00,$18,$00,$00,$00
            DS      6
            DB      $AA,$00,$00,$00,$00,$00,$00
; ---

frame_data_6C7E  brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13042]

; --- Data region (130 bytes) ---
            DB      $D5,$00,$7E,$7F,$7F,$7F,$7F,$7F,$00,$00,$00,$00,$00,$00,$00,$00
            DS      23
            DB      $AA,$D5,$40,$2B,$55,$2A,$55,$2A,$55,$03,$70,$2A,$03,$00,$00,$2B
            DB      $1D,$00,$57,$2A,$55,$2A,$07,$60,$55,$2A,$55,$2A,$0D,$60,$55,$2A
            DB      $55,$3A,$00,$2E,$55,$2A,$55,$03,$AA,$D5,$00,$00,$00,$00,$00,$00
            DB      $00,$00,$40,$01,$00,$00,$0C,$30,$0C,$0C,$30,$0C,$00,$30,$30,$60
            DB      $00,$03,$03,$18,$40,$41,$31,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (130 bytes) ---

frame_data_6D02  rol  a               ; A=A+$57 X=$00C5 ; [SP-13137]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13137]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13137]
            eor  $03,X           ; -> $00C8 ; A=A+$57 X=$00C5 ; [SP-13137]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13140]

; --- Data region (119 bytes) ---
            DS      15
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      37
            DB      $AA,$D5,$00,$00,$00,$08,$09,$09,$51,$08,$11,$22,$22,$08,$00,$22
            DB      $44,$00,$0C,$11,$11,$11,$00,$11,$11,$22,$44,$18,$01,$08,$50,$08
            DB      $20,$08,$58,$09,$00,$00,$00,$00,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$60
; --- End data region (119 bytes) ---

frame_data_6D82  rol  a               ; A=A+$57 X=$00C5 ; [SP-13267]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-13267]

; --- Data region (45 bytes, mostly zeros) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      3
            DB      $60
frame_data_6DAE
            DB      $43
            DB      $07
            DB      $1E,$0F,$60
; --- End data region (45 bytes) ---

frame_data_6DB3  ora  ($00,X)         ; A=A+$57 X=$00C5 ; [SP-13317]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13320]

; --- Data region (75 bytes) ---
            DS      11
            DB      $70,$7F,$7F,$7F,$7F,$7F,$7F,$3F,$00,$00,$00,$00,$00,$AA,$D5,$AA
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$80,$80,$80
            DB      $80,$80,$80,$80,$80,$C0,$87,$FE,$80
            ASC     " U*U*U*U*U*U*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (75 bytes) ---

frame_data_6E02  rol  a               ; A=A+$57 X=$00C5 ; [SP-13356]
            and  $00,X           ; -> $00C5 ; A=A+$57 X=$00C5 ; [SP-13356]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13359]

; --- Data region (64 bytes) ---
            DS      16
            DB      $7F,$7F,$1F,$2B,$0D,$00,$00,$00,$00,$00,$00,$78,$7F,$7F,$7F,$00
            DB      $AA,$D5,$00,$00,$00,$00,$00,$7E,$00,$70,$01,$7C,$41,$7F,$7F,$00
            DS      12
            DB      $70,$0F,$60
frame_data_6E46
            DB      $1F
; --- End data region (64 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=$00C5 ; [SP-13408]
            DB      $3F
            brk  #$00            ; [SP-13408]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$8A,$81,$AA,$D5,$A0,$95,$88,$D4,$82,$C5,$A2,$85,$AA,$80
; Address table (4 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$F8,$FF,$B0,$A0,$C1,$80,$C1,$AA,$D4,$80,$C0,$AA,$C0,$8A,$D4
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_6E82  rol  a               ; A=A+$57 X=$00C5 ; [SP-13435]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13435]
            eor  $1A,X           ; -> $00DF ; A=A+$57 X=$00C5 ; [SP-13435]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13438]

; --- Data region (51 bytes) ---
            DB      $58,$2A,$35,$00,$58,$2A,$35,$40,$55,$2A,$55,$2A,$0D,$30,$55,$2A
            DB      $55,$2A,$0D,$30,$55,$01,$58,$6A,$00,$2B,$55,$2A,$55,$06,$AA,$D5
            DS      5
            DB      $7E,$00,$70,$01,$7C,$01,$78,$03,$00,$1F,$00,$7F,$60
frame_data_6EBB
            DB      $3F
; --- End data region (51 bytes) ---

            bvs  $6ECD           ; A=A+$57 X=$00C5 ; [SP-13447]
            brk  #$60            ; A=A+$57 X=$00C5 ; [SP-13447]
frame_data_6EC0
            DB      $0F
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13445]
            bvs  $6ED4           ; A=A+$57 X=$00C5 ; [SP-13445]
            DB      $60
frame_data_6EC6
            DB      $1F
; Interrupt return (RTI)
            rti                  ; A=A+$57 X=$00C5 ; [SP-13445]
            DB      $3F
            brk  #$00            ; [SP-13445]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A0
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$F0,$83,$FE,$80,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_6F02  rol  a               ; A=A+$57 X=$00C5 ; [SP-13481]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-13481]

; --- Data region (56 bytes) ---
            DS      4
            DB      $2B,$55,$2A,$55,$2A,$03,$40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00
            DB      $2B,$0D,$30,$55,$01,$58,$6A,$00,$2B,$75,$00,$00,$00,$AA,$D5,$00
            DS      4
            DB      $7E,$07,$7E,$07,$7C,$01,$78,$03,$01,$1F,$00,$3F,$40,$1F,$60
frame_data_6F3D
            DB      $0F
; --- End data region (56 bytes) ---

            rol  $3F40,X         ; -> $4005 ; A=A+$57 X=$00C5 ; [SP-13500]

; --- Data region (65 bytes) ---
            DB      $00,$00,$70,$7F,$7F,$1F,$40,$7F,$70,$01,$00,$00,$00,$00,$AA,$D5
; Address table (6 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$A8,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$8A,$80,$F8,$FF,$E0,$80,$00
            DS      10
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (65 bytes) ---

frame_data_6F82  rol  a               ; A=A+$57 X=$00C5 ; [SP-13530]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-13530]

; ---
            DS      4
            DB      $60
; ---

frame_data_6F8B  eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13534]
            eor  $0E,X           ; -> $00D3 ; A=A+$57 X=$00C5 ; [SP-13534]
            brk  #$40            ; A=A+$57 X=$00C5 ; [SP-13537]

; --- Data region (153 bytes) ---
            DB      $55,$06,$00,$2B,$0D,$30,$55,$01,$00,$2B,$0D,$30,$55,$01,$58,$6A
            DB      $00,$78,$7F,$2F,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00
            DS      11
            DB      $78,$01,$00,$00,$00,$00,$06,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      3
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$60
; --- End data region (153 bytes) ---

frame_data_702A  rol  a               ; A=A+$57 X=$00C5 ; [SP-13605]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13605]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13605]
            eor  $03,X           ; -> $00C8 ; A=A+$57 X=$00C5 ; [SP-13605]
            cli                  ; A=A+$57 X=$00C5 ; [SP-13605]
            rol  a               ; A=A+$57 X=$00C5 ; [SP-13605]
            eor  $03,X           ; -> $00C8 ; A=A+$57 X=$00C5 ; [SP-13605]
            DB      $57
            rol  a               ; A=A+$57 X=$00C5 ; [SP-13605]

; --- Data region (123 bytes) ---
            DB      $35,$40,$55,$3A,$70,$2A,$0D,$30,$55,$0E,$70,$2A,$0D,$30,$55,$0E
            DB      $57,$6A,$00,$2B,$7F,$3F,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$00
            DB      $00,$30,$00,$00,$00,$00,$40,$01,$00,$00,$00,$40,$01,$00,$46,$01
            DB      $00,$30,$30,$00,$03,$00,$18,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$00,$2B,$55,$2A,$55,$2A
            DB      $55,$01,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      16
            DB      $AA,$D5,$00,$2B,$55,$2A,$55,$2A,$55,$01,$60
; --- End data region (123 bytes) ---

frame_data_70B2  ror  a               ; A=A+$57 X=$00C5 ; [SP-13694]
            ora  ($00,X)         ; A=A+$57 X=$00C5 ; [SP-13694]
            brk  #$2E            ; A=A+$57 X=$00C5 ; [SP-13697]

; --- Data region (75 bytes) ---
            DB      $0D,$00,$56,$2A,$55,$2A,$03,$40,$55,$2A,$75,$2B,$0D,$40,$55,$2A
            DB      $55,$1A,$00,$2C,$55,$2A,$55,$01,$AA,$D5,$00,$00,$00,$00,$00,$00
            DB      $00,$00,$60,$00,$00,$70,$0D,$30,$0C,$0C,$30,$0E,$00,$70,$30,$60
            DB      $00,$03,$63,$18,$46,$41,$31,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (75 bytes) ---

frame_data_7102  rol  a               ; A=A+$57 X=$00C5 ; [SP-13745]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13745]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13745]
            eor  $01,X           ; -> $00C6 ; A=A+$57 X=$00C5 ; [SP-13745]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13748]

; --- Data region (119 bytes) ---
            DS      15
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      37
            DB      $AA,$D5,$00,$00,$00,$08,$08,$79,$20,$78,$10,$02,$3E,$08,$00,$22
            DB      $40,$00,$08,$1E,$0E,$08,$00,$11,$0F,$22,$40,$28,$01,$70,$20,$70
            DB      $20,$38,$28,$71,$00,$00,$00,$00,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$60
; --- End data region (119 bytes) ---

frame_data_7182  rol  a               ; A=A+$57 X=$00C5 ; [SP-13874]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-13874]

; --- Data region (124 bytes) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      3
            DB      $40,$7F,$03,$7C,$07,$70,$01,$00,$03,$00,$00,$00,$00,$00,$00,$00
            DS      5
            DB      $78,$7F,$7F,$7F,$7F,$7F,$7F,$07,$00,$00,$00,$00,$00,$AA,$D5,$AA
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$80,$80,$80
            DB      $80,$80,$80,$80,$80,$F0,$86,$BF,$80
            ASC     " U*U*U*U*U*U*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (124 bytes) ---

frame_data_7202  rol  a               ; A=A+$57 X=$00C5 ; [SP-13963]
            adc  $01,X           ; -> $00C6 ; A=A+$57 X=$00C5 ; [SP-13963]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-13966]

; ---
            DS      10
            DB      $7C,$7F,$7F,$7F,$01,$40,$55,$2A,$75,$2B,$0D,$40,$3F,$00,$60
frame_data_7220
            DB      $1F
; ---

            brk  #$2C            ; A=A+$57 X=$00C5 ; [SP-13984]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-13984]

; --- Data region (34 bytes) ---
            DB      $55,$01,$AA,$D5,$00,$00,$00,$00,$00,$7E,$00,$70,$01,$7C,$41,$7F
            DB      $7F,$00,$00,$00,$20,$00,$00,$00,$00,$00,$00,$00,$00,$00,$70,$0F
            DB      $60
frame_data_7246
            DB      $1F
; --- End data region (34 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=$00C5 ; [SP-14004]
            DB      $3F
            brk  #$00            ; [SP-14004]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$82,$80,$A8,$D4,$A0,$85,$88,$D4,$80,$C1,$A2,$85,$88,$80
; Address table (4 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$8C,$F6,$B1,$A0,$81,$80,$81,$AA,$94,$80,$80,$8A,$C0,$8A,$D0
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_7282  rol  a               ; A=A+$57 X=$00C5 ; [SP-14026]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-14026]
            eor  $1A,X           ; -> $00DF ; A=A+$57 X=$00C5 ; [SP-14026]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-14029]

; --- Data region (53 bytes) ---
            DB      $58,$2A,$75,$00,$5C,$2A,$35,$40,$55,$6A,$5F,$2A,$0D,$30,$55,$7A
            DB      $5F,$2A,$0D,$30,$55,$01,$58,$6A,$00,$2B,$55,$7F,$55,$06,$AA,$D5
            DS      5
            DB      $7E,$00,$70,$01,$7C,$01,$78,$03,$00,$1F,$00,$3F,$40,$1F,$60
frame_data_72BD
            DB      $0F
; --- End data region (53 bytes) ---

            brk  #$40            ; A=A+$57 X=$00C5 ; [SP-14038]

; ---
            DB      $1F
            DB      $00,$00,$70,$0F,$60
frame_data_72C6
            DB      $1F
; ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=$00C5 ; [SP-14035]
            DB      $3F
            brk  #$00            ; [SP-14035]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A8
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$91,$87,$BF,$80,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_7302  rol  a               ; A=A+$57 X=$00C5 ; [SP-14068]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-14068]

; --- Data region (56 bytes) ---
            DS      4
            DB      $2E,$55,$2A,$55,$6A,$01,$40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00
            DB      $2B,$0D,$30,$55,$01,$58,$6A,$00,$2B,$55,$7F,$7F,$00,$AA,$D5,$00
            DS      4
            DB      $7C,$7F,$7F,$03,$7C,$01,$78,$43,$01,$1F,$00,$3F,$40,$1F,$60
frame_data_733D
            DB      $0F
; --- End data region (56 bytes) ---

            rol  $3F60,X         ; -> $4025 ; A=A+$57 X=$00C5 ; [SP-14088]

; ---
            DB      $00,$00,$78,$7F,$7F,$3F,$60
frame_data_7348
            DB      $7F
            DB      $7F
; ---

            ora  ($00,X)         ; [SP-14086]

; --- Data region (54 bytes) ---
            DS      3
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A8
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$8A,$80,$8C,$F6,$B1,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (54 bytes) ---

frame_data_7382  rol  a               ; A=A+$57 X=$00C5 ; [SP-14119]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-14119]

; --- Data region (164 bytes) ---
            DS      4
            DB      $30,$55,$2A,$55,$1A,$00,$40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00
            DB      $2B,$0D,$30,$55,$01,$58,$6A,$00,$00,$00,$38,$55,$06,$AA,$D5,$00
            DS      18
            DB      $78,$00,$00,$00,$00,$00,$02,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      3
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$60
; --- End data region (164 bytes) ---

frame_data_742A  rol  a               ; A=A+$57 X=$00C5 ; [SP-14202]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-14202]
            eor  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-14202]
            eor  $06,X           ; -> $00CB ; A=A+$57 X=$00C5 ; [SP-14202]
            cli                  ; A=A+$57 X=$00C5 ; [SP-14202]
            rol  a               ; A=A+$57 X=$00C5 ; [SP-14202]
            eor  $01,X           ; -> $00C6 ; A=A+$57 X=$00C5 ; [SP-14202]
            lsr  $2A,X           ; -> $00EF ; A=A+$57 X=$00C5 ; [SP-14202]
            and  $40,X           ; -> $0105 ; A=A+$57 X=$00C5 ; [SP-14202]
            eor  $6A,X           ; -> $012F ; A=A+$57 X=$00C5 ; [SP-14202]
            DB      $5F
            rol  a               ; A=A+$57 X=$00C5 ; [SP-14202]
            ora  $5530           ; A=A+$57 X=$00C5 ; [SP-14202]

; --- Data region (160 bytes) ---
            DB      $7A,$5F,$2A,$0D,$30,$55,$7A,$55,$6A,$00,$2B,$55,$2A,$55,$06,$AA
            DB      $D5,$00,$00,$00,$00,$00,$00,$00,$30,$00,$00,$00,$00,$60,$00,$00
            DB      $00,$00,$60,$00,$00,$63,$00,$00,$00,$18,$00,$00,$00,$0C,$00,$00
            DS      7
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$40,$2B,$55,$2A,$55,$2A
            DB      $55,$03,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      16
            DB      $AA,$D5,$00,$7E,$7F,$7F,$7F,$7F,$7F,$00,$40,$3F,$00,$00,$00,$7C
            DB      $07,$00,$7C,$7F,$7F,$7F,$01,$00,$7F,$7F,$1F,$7E,$07,$00,$7F,$7F
            DB      $7F,$0F,$00,$78,$7F,$7F,$7F,$00,$AA,$D5,$00,$00,$00,$00,$00,$00
            DS      5
            DB      $18,$1F,$60
frame_data_74DF
            DB      $07
; --- End data region (160 bytes) ---

            asl  $60             ; A=A+$57 X=$00C5 ; [SP-14322]

; ---
frame_data_74E2
            DB      $1B,$00,$58,$1F,$30,$40,$01,$3E,$0C,$7C,$60
; ---

anim_data_74ED  rts                  ; A=A+$57 X=$00C5 ; [SP-14319]

; ---
            DB      $60,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$00,$00,$00,$00,$00,$00
            DB      $00,$00,$D5,$60
; ---

frame_data_7502  rol  a               ; A=A+$57 X=$00C5 ; [SP-14341]
            eor  $7E,X           ; -> $0143 ; A=A+$57 X=$00C5 ; [SP-14341]
            DB      $7F
            DB      $7F
            DB      $7F
            brk  #$00            ; [SP-14341]

; --- Data region (120 bytes) ---
            DS      16
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      32
            DB      $02,$00,$00,$00,$00,$AA,$D5,$00,$00,$00,$08,$09,$09,$20,$48,$10
            DB      $32,$22,$08,$00,$22,$44,$00,$08,$10,$11,$11,$00,$11,$09,$22,$46
            DB      $48,$01,$00,$21,$00,$21,$08,$08,$01,$01,$00,$00,$00,$AA,$00,$00
            DS      6
            DB      $D5,$60
; --- End data region (120 bytes) ---

frame_data_7582  rol  a               ; A=A+$57 X=$00C5 ; [SP-14479]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-14479]

; --- Data region (124 bytes) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      3
            DB      $40,$7F,$03,$7C,$07,$7C,$01,$00,$03,$00,$00,$00,$00,$00,$00,$00
            DS      5
            DB      $7C,$7F,$1F,$70,$7F,$7F,$7F,$00,$00,$00,$00,$00,$00,$AA,$D5,$AA
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$80,$80,$80
; Address table (3 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $C6,$9F,$80
            ASC     " U*U*U*U*U*U*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (124 bytes) ---

frame_data_7602  rol  a               ; A=A+$57 X=$00C5 ; [SP-14565]
            eor  $03,X           ; -> $00C8 ; A=A+$57 X=$00C5 ; [SP-14565]
            brk  #$00            ; A=A+$57 X=$00C5 ; [SP-14568]

; --- Data region (64 bytes) ---
            DB      $00,$00,$40,$7F,$00,$00,$00,$7C,$07,$00,$56,$2A,$55,$2A,$03,$60
            DB      $55,$2A,$55,$2B,$0D,$60,$75,$00,$70,$3A,$00,$2E,$55,$2A,$55,$03
            DB      $AA,$D5,$00,$00,$00,$00,$00,$7E,$00,$70,$01,$7C,$01,$78,$03,$00
            DB      $18,$00,$30,$7E,$70,$1F,$00,$0E,$7F,$01,$00,$00,$70,$0F,$60
frame_data_7646
            DB      $1F
; --- End data region (64 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=$00C5 ; [SP-14584]
            DB      $3F
            brk  #$00            ; [SP-14584]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$82,$80,$A8,$D0,$80,$85,$88,$D4,$80,$C0,$A2,$85,$88,$80
; Address table (4 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$8C,$CC,$9F,$A0,$81,$80,$80,$AA,$94,$80,$80,$8A,$80,$8A,$C0
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_7682  rol  a               ; A=A+$57 X=$00C5 ; [SP-14607]
            eor  $7E,X           ; -> $0143 ; A=A+$57 X=$00C5 ; [SP-14607]
            DB      $7F
            DB      $0F
            brk  #$00            ; [SP-14607]

; --- Data region (53 bytes) ---
            DB      $58,$2A,$55,$01,$56,$2A,$35,$40,$55,$3A,$70,$2A,$0D,$30,$55,$0E
            DB      $70,$2A,$0D,$30,$55,$01,$58,$6A,$00,$2B,$75,$00,$7F,$03,$AA,$D5
            DS      5
            DB      $7E,$00,$70,$03,$7C,$01,$78,$03,$00,$1F,$00,$3F,$40,$1F,$60
frame_data_76BD
            DB      $0F
; --- End data region (53 bytes) ---

            rts                  ; A=A+$57 X=$00C5 ; [SP-14622]

; ---
            DB      $43
            DB      $1F
            DB      $00,$00,$70,$0F,$60
frame_data_76C6
            DB      $1F
; ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=$00C5 ; [SP-14623]
            DB      $3F
            brk  #$00            ; [SP-14623]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A8
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$8D,$C6,$9F,$80,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_7702  rol  a               ; A=A+$57 X=$00C5 ; [SP-14662]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-14662]

; --- Data region (124 bytes) ---
            DS      4
            DB      ",U*Uj"
            DB      $00 ; null terminator
            DB      $40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00,$2B,$0D,$30,$55,$01,$58
            DB      $6A,$00,$2B,$55,$2A,$55,$01,$AA,$D5,$00,$00,$00,$00,$00,$7C,$7F
            DB      $7F,$03,$7C,$01,$70,$67,$01,$1F,$00,$3F,$40,$1F,$60
frame_data_773D
            DB      $07
            DB      $7C
            DB      $70,$3F,$00,$00,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$00,$00,$00,$00,$00
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A8
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$8A,$80,$8C,$CC,$9F,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (124 bytes) ---

frame_data_7782  rol  a               ; A=A+$57 X=$00C5 ; [SP-14721]
            ora  !$0000          ; A=A+$57 X=$00C5 ; [SP-14721]

; ---
            DS      4
            DB      "8U*U:"
            DB      $00 ; null terminator
            DB      $40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00,$2B,$0D,$30,$55,$01,$58
            DB      $6A,$00,$00,$00,$60
; ---

frame_data_77A5  eor  $06,X           ; -> $00CB ; A=A+$57 X=$00C5 ; [SP-14738]
            tax                  ; A=A+$57 X=A ; [SP-14738]
            cmp  $00,X           ; A=A+$57 X=A ; [SP-14738]
            brk  #$00            ; A=A+$57 X=A ; [SP-14741]

; --- Data region (138 bytes) ---
            DS      16
            DB      $3C,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      3
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00
frame_data_7800
            DB      $D5
frame_data_7801
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$60,$2A,$55,$2A,$55,$2A,$55,$06
            DB      $58,$2A,$75,$00,$5C
; --- End data region (138 bytes) ---

            rol  a               ; A=A+$57 X=A ; [SP-14801]
            and  $40,X           ; A=A+$57 X=A ; [SP-14801]

; --- Data region (73 bytes) ---
            DB      $55,$2A,$55,$2A,$0D,$30,$55,$2A,$55,$2A,$0D,$30,$55,$2A,$55,$6A
            DB      $00,$2B,$55,$2A,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$00,$00,$70
            DB      $63,$30,$00,$00,$60,$00,$1F,$58,$07,$7F,$00,$00,$7B,$40,$3D,$18
            DB      $7F,$40,$71,$03,$7C,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$00
            DS      7
            DB      $D5,$60
; --- End data region (73 bytes) ---

frame_data_7882  rol  a               ; A=A+$57 X=A ; [SP-14840]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-14840]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-14840]
            eor  $06,X           ; A=A+$57 X=A ; [SP-14840]
            brk  #$00            ; A=A+$57 X=A ; [SP-14843]

; --- Data region (119 bytes, mostly zeros) ---
            DS      28
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$18,$76,$00
            DS      15
            DB      $38,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$00,$00,$00,$00,$00,$00
            DB      $00,$00,$D5,$60
; --- End data region (119 bytes) ---

frame_data_7902  rol  a               ; A=A+$57 X=A ; [SP-15005]
            eor  $03,X           ; A=A+$57 X=A ; [SP-15005]
            brk  #$00            ; A=A+$57 X=A ; [SP-15008]

; --- Data region (123 bytes) ---
            DS      19
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      32
            DB      $03,$00,$00,$00,$00,$AA,$D5,$00,$00,$00,$70,$70,$08,$20,$08,$39
            DB      $3C,$22,$08,$00,$44,$23,$00,$1C,$10,$0E,$0E,$00,$0E,$11,$47,$67
            DB      $09,$01,$78,$20,$78,$20,$78,$09,$79,$00,$00,$00,$00,$AA,$00,$00
            DS      6
            DB      $D5,$60
; --- End data region (123 bytes) ---

frame_data_7982  rol  a               ; A=A+$57 X=A ; [SP-15136]
            ora  !$0000          ; A=A+$57 X=A ; [SP-15136]

; --- Data region (67 bytes) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      4
            DB      $7F,$01,$78,$03,$7F,$01,$40,$03,$00,$0C,$00,$00,$00,$00,$00,$00
            DS      4
            DB      $3C,$78,$0F,$60
frame_data_79C6
            DB      $7F
            DB      $7F
            DB      $3F
; --- End data region (67 bytes) ---

            brk  #$00            ; [SP-15202]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80
; Address table (4 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$EE,$8F,$80
            ASC     " U*U*U*U*U*U*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5,$60
; --- End data region (55 bytes) ---

frame_data_7A02  rol  a               ; A=A+$57 X=A ; [SP-15223]
            eor  $7E,X           ; A=A+$57 X=A ; [SP-15223]
            DB      $7F
            DB      $0F
            brk  #$00            ; [SP-15223]
            DB      $60
frame_data_7A0A  ror  a               ; A=A+$57 X=A ; [SP-15221]
            ora  ($00,X)         ; A=A+$57 X=A ; [SP-15221]
            brk  #$2E            ; A=A+$57 X=A ; [SP-15224]

; --- Data region (56 bytes) ---
            DB      $0D,$00,$57,$2A,$55,$2A,$07,$30,$55,$2A,$55,$2A,$0D,$30,$55,$01
            DB      $58,$6A,$00,$2B,$55,$2A,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$7E
            DB      $00,$70,$01,$7C,$01,$78,$03,$00,$1C,$00,$78,$7F,$79,$7F,$00,$7E
            DB      $7F,$07,$00,$00,$70,$0F,$60
frame_data_7A46
            DB      $1F
; --- End data region (56 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-15234]
            DB      $3F
            brk  #$00            ; [SP-15234]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$A0,$90,$80,$85,$80,$90,$80,$C0,$80,$81,$80,$80
            DB      $80,$80,$80,$80,$80,$8A,$80,$80,$80,$8E,$8E,$8F,$A0,$81,$80,$80
            DB      $88,$90,$80,$80,$8A,$80,$8A,$C0,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_7A82  rol  a               ; A=A+$57 X=A ; [SP-15255]
            eor  $03,X           ; A=A+$57 X=A ; [SP-15255]
            brk  #$00            ; A=A+$57 X=A ; [SP-15258]

; --- Data region (55 bytes) ---
            DB      $00,$00,$58,$2A,$55,$03,$57,$2A,$35,$40,$55,$1A,$60,$2A,$0D,$30
            DB      $55,$06,$60,$2A,$0D,$30,$55,$01,$58,$6A,$00,$2B,$1D,$00,$00,$00
            DB      $AA,$D5,$00,$00,$00,$00,$00,$7E,$00,$70,$07,$7C,$01,$78,$03,$00
            DB      $1F,$00,$3F,$40,$1F,$60
frame_data_7ABD
            DB      $0F
; --- End data region (55 bytes) ---

            sei                  ; A=A+$57 X=A ; [SP-15271]

; ---
            DB      $47
            DB      $1F
            DB      $00,$00,$70,$0F,$60
frame_data_7AC6
            DB      $1F
; ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-15272]
            DB      $3F
            brk  #$00            ; [SP-15272]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A8
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$EE,$8F,$80,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_7B02  rol  a               ; A=A+$57 X=A ; [SP-15308]
            ora  !$0000          ; A=A+$57 X=A ; [SP-15308]

; --- Data region (124 bytes) ---
            DS      4
            DB      "8U*U:"
            DB      $00 ; null terminator
            DB      $40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00,$2B,$0D,$30,$55,$01,$58
            DB      $6A,$00,$2B,$55,$2A,$55,$03,$AA,$D5,$00,$00,$00,$00,$00,$78,$7F
            DB      $7F,$01,$7C,$01,$70,$7F,$00,$1F,$00,$3F,$40,$1F,$60
frame_data_7B3D
            DB      $07
            DB      $7C
            DB      $3F,$3F,$00,$70,$7F,$7F,$7F,$7F,$7F,$7F,$3F,$00,$00,$00,$00,$00
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$A0
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$8A,$80,$8E,$8E,$8F,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (124 bytes) ---

frame_data_7B82  rol  a               ; A=A+$57 X=A ; [SP-15364]
            ora  !$0000,X        ; A=A+$57 X=A ; [SP-15364]

; --- Data region (164 bytes) ---
            DS      4
            DB      ",U*Uj"
            DB      $00 ; null terminator
            DB      $40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00,$2B,$0D,$30,$55,$01,$58
            DB      $6A,$00,$00,$00,$40,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$00,$00
            DS      12
            DB      $1E,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      3
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$60
; --- End data region (164 bytes) ---

frame_data_7C2A  rol  a               ; A=A+$57 X=A ; [SP-15444]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-15444]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-15444]
            eor  $06,X           ; A=A+$57 X=A ; [SP-15444]
            cli                  ; A=A+$57 X=A ; [SP-15444]
            rol  a               ; A=A+$57 X=A ; [SP-15444]
            and  $00,X           ; A=A+$57 X=A ; [SP-15444]
            cli                  ; A=A+$57 X=A ; [SP-15444]
frame_data_7C36  rol  a               ; A=A+$57 X=A ; [SP-15444]
            and  $40,X           ; A=A+$57 X=A ; [SP-15444]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-15444]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-15444]
            ora  $5530           ; A=A+$57 X=A ; [SP-15444]
            rol  a               ; A=A+$57 X=A ; [SP-15444]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-15444]
            ora  $5530           ; A=A+$57 X=A ; [SP-15444]
            rol  a               ; A=A+$57 X=A ; [SP-15444]
            eor  $6A,X           ; A=A+$57 X=A ; [SP-15444]
            brk  #$2B            ; A=A+$57 X=A ; [SP-15447]

; ---
            DB      $55,$2A,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$00,$00,$30,$46,$19
            DB      $00,$00,$30,$40,$31,$70,$40,$31,$00,$40,$41,$01,$07,$0C,$0C,$60
; ---

frame_data_7C6B  clc                  ; A=A+$57 X=A ; [SP-15450]
            asl  $46             ; A=A+$57 X=A ; [SP-15450]
            ora  ($00,X)         ; A=A+$57 X=A ; [SP-15450]
            brk  #$00            ; A=A+$57 X=A ; [SP-15453]

; ---
            DS      5
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; ---

frame_data_7C82  rol  a               ; A=A+$57 X=A ; [SP-15474]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-15474]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-15474]
            eor  $06,X           ; A=A+$57 X=A ; [SP-15474]
            brk  #$00            ; A=A+$57 X=A ; [SP-15477]

; --- Data region (119 bytes, mostly zeros) ---
            DS      28
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      24
            DB      $AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$70,$43,$7F
            DB      $7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$0F
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (119 bytes) ---

frame_data_7D02  rol  a               ; A=A+$57 X=A ; [SP-15612]
            adc  $00,X           ; A=A+$57 X=A ; [SP-15612]
            brk  #$00            ; A=A+$57 X=A ; [SP-15615]

; --- Data region (123 bytes, mostly zeros) ---
            DS      19
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      31
            DB      $40,$03,$00,$00,$00,$00,$AA,$D5,$00,$00,$00,$00,$00,$00,$00,$00
            DS      30
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (123 bytes) ---

frame_data_7D82  rol  a               ; A=A+$57 X=A ; [SP-15783]
            ora  !$0000          ; A=A+$57 X=A ; [SP-15783]

; --- Data region (65 bytes) ---
            DS      20
            DB      $2B,$0D,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$AA,$D5,$00
            DS      4
            DB      $7E,$00,$70,$01,$7C,$01,$40,$03,$00,$1E,$00,$00,$00,$00,$00,$00
            DS      4
            DB      $0E,$70,$0F,$60
anim_data_7DC6
            DB      $3F
; --- End data region (65 bytes) ---

            rts                  ; A=A+$57 X=A ; [SP-15843]
            DB      $3F
            brk  #$00            ; [SP-15843]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80
; Address table (4 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $80,$FC,$87,$80
            ASC     " U*U*U*U*U*U*"
            DB      $00 ; null terminator
            DS      7
            DB      $D5
frame_data_7E01
            DB      $60
; --- End data region (55 bytes) ---

frame_data_7E02  rol  a               ; A=A+$57 X=A ; [SP-15866]
            eor  $2A,X           ; A=A+$57 X=A ; [SP-15866]
            eor  $1A,X           ; A=A+$57 X=A ; [SP-15866]
            brk  #$00            ; A=A+$57 X=A ; [SP-15869]

; --- Data region (62 bytes) ---
            DB      $70,$2A,$03,$00,$00,$2B,$1D,$40,$55,$2A,$55,$2A,$0D,$30,$55,$2A
            DB      $55,$2A
frame_data_7E1B
            DB      $0D,$30,$55,$01,$58,$6A,$00,$2B,$55,$2A,$55,$06,$AA,$D5,$00,$00
            DS      3
            DB      $7E,$00,$70,$01,$7C
frame_data_7E33
            DB      $01,$78,$03,$00,$1E,$00,$7E,$7F,$7F,$7F,$01,$7E,$7F,$0F,$00,$00
            DB      $70,$0F,$60
frame_data_7E46
            DB      $1F
; --- End data region (62 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-15882]
            DB      $3F
            brk  #$00            ; [SP-15882]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$81,$80,$90,$80,$80,$80,$81,$80,$80
            DB      $80,$A0,$80,$80,$D4,$AA,$80,$80,$80,$8A,$8A,$80,$A0,$80,$80,$80
            DB      $88,$80,$80,$80,$88,$80,$82,$C0,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_7E82  rol  a               ; A=A+$57 X=A ; [SP-15903]
            adc  $00,X           ; A=A+$57 X=A ; [SP-15903]
            brk  #$00            ; A=A+$57 X=A ; [SP-15906]

; --- Data region (64 bytes) ---
            DB      $00,$00,$58,$2A,$55,$46,$55,$2A,$35,$40,$55,$0E,$40,$2B,$0D,$30
            DB      $55,$03,$40,$2B,$0D,$30,$55,$01,$58,$6A,$00,$2B,$0D,$00,$00,$00
            DB      $AA,$D5,$00,$00,$00,$00,$00,$7E,$00,$70,$07,$7C,$01,$78,$03,$00
            DB      $1F,$00,$3F,$40,$1F,$60
frame_data_7EBD
            DB      $0F
            DB      $7C
            DB      $4F
            DB      $1F
            DB      $00,$00,$70,$0F,$60
frame_data_7EC6
            DB      $1F
; --- End data region (64 bytes) ---

; Interrupt return (RTI)
            rti                  ; A=A+$57 X=A ; [SP-15914]
            DB      $3F
            brk  #$00            ; [SP-15914]

; --- Data region (55 bytes) ---
            DS      4
            DB      $AA,$D5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$AA
            DB      $D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$80,$FC,$87,$80,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (55 bytes) ---

frame_data_7F02  rol  a               ; A=A+$57 X=A ; [SP-15950]
            ora  !$0000          ; A=A+$57 X=A ; [SP-15950]

; --- Data region (43 bytes) ---
            DS      4
            DB      $30,$55,$2A,$55,$1A,$00,$40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00
            DB      $2B,$0D,$30,$55,$01
frame_data_7F1F
; Jump table (2 entries)
            DW      frame_data_6A58
            DW      anim_data_2B00
            DB      $55,$2A,$55,$06,$AA,$D5,$00,$00,$00,$00,$00,$60
frame_data_7F2F
            DB      $7F
            DB      $3F
; --- End data region (43 bytes) ---

            brk  #$7E            ; [SP-15968]
            DB      $03,$60
frame_data_7F35
            DB      $3F
            brk  #$1F            ; A=A+$57 X=A ; [SP-15968]
            brk  #$3F            ; A=A+$57 X=A ; [SP-15968]

; --- Data region (72 bytes) ---
            DB      $40,$1F,$60
frame_data_7F3D
            DB      $07
            DB      $7C
            DB      $1F,$7F
frame_data_7F41
            DB      $00,$78,$7F,$7F,$7F,$7F,$7F,$7F,$07,$00,$00,$00,$00,$00,$AA,$D5
; Address table (7 entries)
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DW      frame_data_8080
            DB      $95,$A8,$85,$A8,$C1,$AA,$D0,$82,$80,$8A,$8A,$80,$80,$00,$00,$00
            DS      8
            DB      $AA,$00,$00,$00,$00,$00,$00,$00,$00,$D5,$60
; --- End data region (72 bytes) ---

frame_data_7F82  rol  a               ; A=A+$57 X=A ; [SP-16004]
            and  $00,X           ; A=A+$57 X=A ; [SP-16004]
            brk  #$00            ; A=A+$57 X=A ; [SP-16007]

; --- Data region (250 bytes) ---
            DS      3
            DB      $2E,$55,$2A,$55,$6A,$01,$40,$55,$06,$00,$2B,$0D,$30,$55,$01,$00
            DB      $2B,$0D,$30,$55,$01,$58,$6A,$00,$00,$00,$40,$55,$06,$AA,$D5,$00
            DS      18
            DB      $06,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
            DS      3
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5
            DB      $AA,$D5,$AA,$D5,$AA,$D5,$AA,$D5,$AA,$00,$00,$00,$00,$00,$00,$00
            DB      $00,$5E,$3D,$5F,$3C,$61,$3C,$63,$3C,$65,$3C,$66,$3D,$66,$3E,$65
            DB      $3F,$63,$3F,$62,$3E,$62,$3D,$61,$3B,$60,$3A,$60,$39,$5F,$38,$5F
            DB      $37,$5E,$36,$5E,$35,$5D,$34,$5D,$33,$5C,$31,$5B,$30,$59,$30,$58
            DB      $30,$57,$31,$57,$32,$58,$33,$5A,$33,$5B,$32,$5D,$32,$5E,$32,$5F
            DB      $31,$60,$31,$61,$30,$63,$30,$65,$30,$67,$30,$69,$30,$6B,$30,$6D
            DB      $30,$6F,$30,$71,$30,$73,$30,$75,$30,$77,$30,$79,$30,$7B,$30,$7D
            DB      $30,$7F,$30,$81,$30,$83,$30,$85,$30,$87,$30,$89,$30,$8B,$30,$8D
            DB      $30,$8F,$30,$91,$30,$93,$30,$95,$30,$97,$30,$99,$30,$9B,$30,$9D
            DB      $30
frame_data_8080
            DB      $9F
; --- End data region (250 bytes) ---

            bmi  $8024           ; A=A+$57 X=A ; [SP-16085]
            bmi  $8028           ; A=A+$57 X=A ; [SP-16085]

; --- Data region (411 bytes, text data) ---
            DB      $30,$A5,$30,$A7,$30,$A9,$30,$AB,$30,$AD,$30,$AF,$30,$B1,$30,$B3
            DB      $30,$B5,$30,$B7,$30,$B9,$30,$BB,$30,$BD,$30,$BF,$30,$C1,$30,$C3
            DB      $30,$C5,$30,$C7,$30,$C9,$30,$CB,$30,$CD,$30,$CF,$30,$D1,$30,$D3
            DB      $30,$D4,$30,$D5,$31,$D6,$31,$D7,$32,$69,$39,$6B,$39,$6C,$39,$6D
            DB      $38,$6D,$37,$6C,$36,$6C,$35,$6B,$34,$6B,$33,$6A,$32,$68,$32,$67
            DB      $32,$66,$33,$66,$34,$67,$35,$67,$36,$68,$37,$68,$38,$73,$39,$74
            DB      $38,$74,$37,$73,$36,$73,$35,$72,$34,$72,$33,$71,$32,$75,$38,$76
            DB      $39,$78,$39,$81,$39,$7F,$39,$7E,$39,$7D,$38,$7D,$37,$7C,$36,$7C
            DB      $35,$7B,$34,$7B,$33,$7C,$32,$7E,$32,$7F,$33,$80,$34,$81,$35,$81
            DB      $36,$82,$37,$82,$38,$83,$39,$83,$3A,$84,$3B,$84,$3C,$85,$3D,$85
            DB      $3E,$80,$33,$81,$32,$95,$3E,$95,$3D,$94,$3C,$94,$3B,$93,$3A,$93
            DB      $39,$92,$38,$92,$37,$91,$36,$91,$35,$90,$34,$90,$33,$8F,$32,$96
            DB      $3F,$98,$3F,$99,$3F,$9A,$3E,$9A,$3D,$99,$3C,$99,$3B,$98,$3A,$98
            DB      $39,$96,$39,$99,$38,$99,$37,$98,$36,$98,$35,$97,$34,$97,$33,$96
            DB      $32,$94,$32,$92,$32,$91,$33,$A0,$39,$A1,$38,$A1,$37,$A0,$36,$A0
            DB      $35,$9F,$34,$9F,$33,$9E,$32,$A2,$38,$A3,$39,$A5,$39,$AB,$39,$AA
            DB      $38,$AA,$37,$A9,$36,$A9,$35,$A8,$34,$A8,$33,$A7,$32,$AC,$3C,$AC
            DB      $3B,$B3,$3C,$B3,$3B,$B2,$3A,$B2,$39,$B1,$38,$B1,$37,$B0,$36,$B0
            DB      $35,$AF,$34,$AF,$33,$B0,$32,$B2,$32,$B3,$32,$B4,$33,$AF,$39,$B1
            DB      $39,$B4,$39,$BC,$39,$BB,$38,$BB,$37,$BA,$36,$BA,$35,$B9,$34,$B9
            DB      $33,$B8,$32,$BD,$3C,$BD,$3B,$C5,$38,$C4,$39,$C2,$39,$C1,$39,$C0
            DB      $38,$C0,$37,$C1,$36,$C2,$35,$C3,$34,$C3,$33,$C2,$32,$C0,$32,$BF
            DB      $32,$BE,$33,$CF,$3E,$CF,$3D,$CE,$3C,$CE,$3B,$CD,$3A,$CD,$39,$CC
            DB      $38,$CC,$37,$CB,$36,$CB,$35,$CA,$34,$CA,$33,$C9,$32,$CF,$39,$D0
            DB      $39,$D1,$38,$D1,$37,$D0,$36,$D0,$35,$CF,$34,$CF,$33,$D0,$32,$00
            DB      $4D,$33,$36,$20,$20,$CF,$1E,$59,$4C,$4F,$42
; --- End data region (411 bytes) ---

; ===========================================================================
;                         ENTRY POINT ($8220)
; ===========================================================================
;
; Execution begins here via JMP from $2000. This is the first code that runs
; after the boot sector loads EXOD into memory at $2000-$86FF. The sequence:
;
;   1. Clear keyboard strobe (discard any key held during disk load)
;   2. Run the full intro animation sequence (title → serpent → castle →
;      text crawl → Exodus reveal → sound effect → final frames)
;   3. Print "BRUN BOOT" via the inline string printer, which chains to
;      the Applesoft BRUN command to load the next stage (BOOT binary)
;
; The trailing bytes after the null terminator ($86,$24,$84,$25,$20,$22,
; $FC,$60) are dead code — a small stub that would save cursor position
; and call $FC22 (HOME), but execution never reaches it because the
; "BRUN BOOT" command transfers control to the BOOT loader.
;
; XREF: 1 ref (1 jump) from $002000
intro_entry  bit  $C010           ; Clear keyboard strobe — discard held key
            jsr  intro_sequence   ; Run full intro animation
            jsr  intro_print_string ; Print inline string (below)

; --- inline string: chain-load command ---
            DB      $04
            ASC     "BRUN"
            ASC     " BOOT"
            DB      $8D             ; carriage return
            DB      $00             ; null terminator
            DB      $86,$24,$84,$25,$20,$22,$FC,$60  ; dead code (cursor save + HOME stub)
; ---


; ===========================================================================
; intro_print_string — Inline String Printer ($823D)
; ===========================================================================
;
; EXOD's own copy of the inline string printing pattern used throughout the
; Ultima III engine (SUBS has print_inline_str at $4732). The technique is
; a classic 6502 idiom: the caller uses JSR to this routine, and the null-
; terminated string follows immediately after the JSR instruction in the
; caller's code stream. On entry, the return address on the stack points
; to the byte BEFORE the string (6502 JSR pushes PC+2, not PC+3).
;
; Algorithm:
;   1. Pull return address from stack into $FE/$FF (string pointer - 1)
;   2. Increment pointer, read byte — if zero, we're done
;   3. Set high bit (ORA #$80) for Apple II screen output conventions
;   4. Call ROM COUT ($FDED) to output the character
;   5. Loop until null terminator
;   6. Push final pointer value back as return address — RTS will jump
;      to the byte after the null, resuming execution past the string
;
; This is functionally identical to SUBS print_inline_str but is a separate
; copy because EXOD runs before SUBS is loaded into memory. The "BRUN BOOT"
; string at the entry point is the only caller in EXOD.
;
; Entry:  Return address on stack points to string data - 1
; Exit:   Execution resumes at byte after null terminator
; Clobbers: A, Y, $FE/$FF
;
intro_print_string  pla                  ; pull return addr low → string ptr low
            sta  $FE
            pla                  ; pull return addr high → string ptr high
            sta  $FF
            ldy  #$00            ; Y stays 0 — all indexing via $FE/$FF inc

intro_print_next  inc  $FE             ; advance pointer (pre-increment)
            bne  intro_print_char
            inc  $FF             ; handle page crossing
intro_print_char  lda  ($FE),Y         ; read next string byte
            beq  intro_print_done ; null terminator → done
            ora  #$80            ; set high bit for Apple II display
            jsr  $FDED           ; ROM COUT — output character
            jmp  intro_print_next

intro_print_done  lda  $FF             ; push final pointer as return address
            pha                  ;   high byte first (6502 stack convention)
            lda  $FE
            pha                  ;   low byte second
            rts                  ; RTS adds 1 → resumes after null terminator

; ===========================================================================
; intro_sequence — Main Intro Sequence Orchestrator ($825E)
; ===========================================================================
;
; Runs the entire Ultima III title/intro animation, a carefully choreographed
; multi-stage presentation that was a landmark for 1983 Apple II software.
; The sequence uses HGR page 1/2 double-buffering to achieve smooth animation
; on hardware with no vertical blank interrupt — each frame is drawn to the
; hidden page, then the visible page is toggled via soft switches.
;
; Stage sequence:
;   1. SETUP: Copy animation frame data from $2400→$8800 (4 pages) and
;      $2800→$0800 (56 pages) to prepare HGR buffers
;   2. MODE: Switch to full-screen HGR mode (HIRES+MIXCLR+LOWSCR+TXTCLR)
;   3. SWAP: Swap $0400-$0800 with $8800-$8C00 (staging area ↔ HGR page 2)
;   4. PRNG: Seed PRNG state ($19/$1A) for randomized dissolve/speaker effects
;   5. WAIT: Drain keyboard buffer — loop clearing strobe + WAIT($FF) × 5,
;      repeat while any key is held (prevents accidental skip from boot)
;   6. WIPE TITLE: Dissolve title screen with 4-byte step (256 positions)
;   7. PAUSE 2s, check for skip
;   8. WIPE SERPENT: Dissolve serpent graphic with 2-byte step, mask transition
;   9. PAUSE 5s, check for skip
;  10. CASTLE: Load castle scene (no dissolve — direct blit, page 1 only)
;  11. PAUSE 2s, TEXT CRAWL: Vertical scroll from $8000 data
;  12. PAUSE 2s, EXODUS: Load Exodus graphic via blit
;  13. PAUSE 6s, REVEAL: Progressive column-by-column reveal animation
;  14. PAUSE 4s, FRAME 3 + SOUND EFFECT + FRAME 4: Final dramatic frames
;  15. PAUSE 5s
;  16. FINISH: Swap HGR buffers back, return
;
; Every pause calls intro_check_key — if the user presses any key, execution
; short-circuits to intro_finish via stack unwinding (PLA×2 + JMP).
;
; Zero-page usage:
;   $19/$1A  PRNG accumulator (seeded $E3/$9D)
;   $1B      HGR page toggle ($00=page 1, $60=page 2)
;
; Called by: intro_entry
;
intro_sequence  ldx  #$04            ; 4 pages to copy
            lda  #$24            ; source: $2400 (animation frame data)
            ldy  #$88            ; dest: $8800 (HGR page 2 staging area)
            jsr  intro_memcpy
            ldx  #$38            ; 56 pages to copy (entire HGR area)
            lda  #$28            ; source: $2800
            ldy  #$08            ; dest: $0800 (HGR page 2 buffer? — actually text page 2 area)
            jsr  intro_memcpy

; --- Switch to full-screen HGR mode ---
            bit  $C057           ; HIRES — enable hi-res graphics
            bit  $C052           ; MIXCLR — full screen (no text window)
            bit  $C054           ; LOWSCR — display page 1
            bit  $C050           ; TXTCLR — graphics mode on

            jsr  intro_memswap   ; swap $0400-$0800 ↔ $8800-$8C00

; --- Seed PRNG for dissolve effects ---
            lda  #$E3
            sta  $19             ; PRNG accumulator low
            lda  #$9D
            sta  $1A             ; PRNG accumulator high
            lda  #$60
            sta  $1B             ; page toggle state ($60 = page 2 initially)

; --- Wait for keyboard to be released ---
; Prevents accidental skip if user held a key during disk loading.
; Outer loop: clear strobe, delay ~1.3 seconds (5 × WAIT($FF)), check KBD.
; Repeats until no key is held.
intro_wait_nokey  ldy  #$05            ; 5 delay iterations

intro_delay_loop  lda  #$FF            ; maximum WAIT delay (~0.26 sec per call)
            bit  $C010           ; clear keyboard strobe each iteration
            jsr  $FCA8           ; ROM WAIT — delay A×(A+1)/2 cycles
            dey
            bne  intro_delay_loop

            lda  $C000           ; read keyboard
            bmi  intro_wait_nokey ; bit 7 set = key held → wait more

; --- Choreographed intro stages ---
            jsr  intro_wipe_title      ; stage 6: dissolve title
            ldy  #$02
            jsr  intro_check_key       ; pause ~0.5s, check skip
            jsr  intro_wipe_serpent    ; stage 8: dissolve serpent
            ldy  #$05
            jsr  intro_check_key       ; pause ~1.3s, check skip
            lda  #$00
            sta  $1B             ; lock to page 1 for castle scene
            bit  $C054           ; ensure page 1 displayed
            jsr  intro_load_castle     ; stage 10: castle scene
            ldy  #$02
            jsr  intro_check_key       ; pause ~0.5s
            jsr  intro_text_crawl      ; stage 11: vertical text scroll
            ldy  #$02
            jsr  intro_check_key       ; pause ~0.5s
            jsr  intro_load_exodus     ; stage 12: Exodus graphic
            ldy  #$06
            jsr  intro_check_key       ; pause ~1.5s
            jsr  intro_reveal_anim    ; stage 13: column reveal
            ldy  #$04
            jsr  intro_check_key       ; pause ~1.0s
            jsr  intro_load_frame_3   ; stage 14a: dramatic frame 3
            jsr  intro_sound_effect   ; stage 14b: ominous sound
            jsr  intro_load_frame_4   ; stage 14c: final frame
            ldy  #$05
            jsr  intro_check_key       ; pause ~1.3s

; --- Cleanup: restore HGR buffers ---
; Also the target for intro_key_pressed skip (via PLA×2 + JMP).
intro_finish  jsr  intro_memswap   ; swap $0400-$0800 ↔ $8800-$8C00
            rts

; ===========================================================================
; intro_wipe_title — Title Screen Dissolve Animation ($82E6)
; ===========================================================================
;
; Progressively dissolves the title screen using a randomized pixel mask.
; The effect works by blitting the source image through intro_hgr_blit with
; an increasing threshold ($18) — the PRNG in the blit routine compares
; against this threshold to decide whether each pixel transfers or stays
; blank. Incrementing by 4 per frame creates 64 dissolve steps (256/4).
;
; The dissolve uses double-buffering: each frame is drawn to the hidden
; HGR page, then intro_toggle_page swaps the visible page. This creates
; flicker-free animation despite the Apple II having no vsync interrupt.
;
; After the dissolve loop, $17 is set to $00 (full transparency) and the
; image is blitted twice more (once per page) to ensure both HGR pages
; show the complete final image — essential because the next animation
; stage may start on either page.
;
; Parameters:
;   $0B/$0A = source high page / blit parameter ($08/$01)
;   $17     = pixel mask ($FF = randomized dissolve)
;   $18     = dissolve threshold (0→252, step 4)
;   A=$08, X=$26, Y=$4D → blit dimensions for title region
;
intro_wipe_title   lda  #$08
            sta  $0B             ; source high page
            lda  #$01
            sta  $0A             ; blit width parameter
            lda  #$FF
            sta  $17             ; $FF = randomized dissolve mode
            lda  #$00
            sta  $18             ; dissolve threshold starts at 0

intro_wipe_title_loop lda  #$08            ; source page for blit
            ldx  #$26            ; X dimension / scanline count
            ldy  #$4D            ; Y dimension / column count
            jsr  intro_hgr_blit  ; blit with current dissolve threshold
            jsr  intro_toggle_page ; flip visible HGR page
            lda  $18
            clc
            adc  #$04            ; advance threshold by 4 (64 total steps)
            sta  $18
            cmp  #$00            ; wrapped past 255 → dissolve complete
            bne  intro_wipe_title_loop

; --- Final: blit complete image to both pages ---
            lda  #$00
            sta  $17             ; $00 = no mask (full transfer)
            lda  #$08
            ldx  #$26
            ldy  #$4D
            jsr  intro_hgr_blit  ; final blit to hidden page
            jsr  intro_toggle_page ; swap pages
            lda  #$08
            ldx  #$26
            ldy  #$4D
            jsr  intro_hgr_blit  ; final blit to other page (now hidden)
            jsr  intro_toggle_page ; both pages now show complete image
            rts

; ===========================================================================
; intro_wipe_serpent — Serpent Dissolve Animation ($832A)
; ===========================================================================
;
; Same dissolve technique as intro_wipe_title but with different parameters:
; - Source at $55xx (serpent graphic in the data blob)
; - Smaller blit region (X=$1F, Y=$2B vs title's X=$26, Y=$4D)
; - Finer dissolve step ($02 vs title's $04) → 128 steps for smoother effect
;
; The serpent is the iconic sea serpent that appears in the Ultima III intro
; between the title screen and the castle scene. The slower dissolve (half
; the step size) gives it a more dramatic, lingering reveal.
;
intro_wipe_serpent lda  #$55
            sta  $0B             ; source high page (serpent graphic)
            lda  #$05
            sta  $0A             ; blit width parameter
            lda  #$FF
            sta  $17             ; randomized dissolve mode
            lda  #$00
            sta  $18             ; threshold starts at 0

intro_wipe_serpent_loop lda  #$55            ; serpent source page
            ldx  #$1F            ; scanline count
            ldy  #$2B            ; column count
            jsr  intro_hgr_blit  ; blit with current threshold
            jsr  intro_toggle_page ; flip visible page
            lda  $18
            clc
            adc  #$02            ; step by 2 (128 total dissolve frames)
            sta  $18
            cmp  #$00            ; wrapped → dissolve complete
            bne  intro_wipe_serpent_loop

; --- Final: blit complete image to both pages ---
            lda  #$00
            sta  $17             ; no mask
            lda  #$55
            ldx  #$1F
            ldy  #$2B
            jsr  intro_hgr_blit  ; final blit to hidden page
            jsr  intro_toggle_page
            lda  #$55
            ldx  #$1F
            ldy  #$2B
            jsr  intro_hgr_blit  ; final blit to other page
            jsr  intro_toggle_page
            rts

; ===========================================================================
; intro_load_castle — Castle Scene Direct Blit ($836E)
; ===========================================================================
;
; Loads the castle scene graphic directly (no dissolve — $17=$00 means full
; transfer). Unlike the title and serpent stages, this scene displays on
; page 1 only (intro_sequence sets $1B=$00 before calling). The castle is
; a smaller image (X=$03 scanlines, Y=$09 columns) rendered from $84xx data.
;
intro_load_castle  lda  #$84
            sta  $0B             ; source high page (castle graphic)
            lda  #$08
            sta  $0A             ; blit width parameter
            lda  #$00
            sta  $17             ; no dissolve mask (direct transfer)
            lda  #$84            ; source page for blit call
            ldx  #$03            ; scanline count
            ldy  #$09            ; column count
            jsr  intro_hgr_blit
            rts

; ===========================================================================
; intro_text_crawl — Vertical Text Scroll Animation ($8384)
; ===========================================================================
;
; Reads coordinate pairs from a data stream at $8000 and plots character
; pairs at each position, creating a vertical scrolling text effect over
; the castle scene. Each entry in the data stream is a pair of bytes:
;   byte 0 → $0A (column/X position)
;   byte 1 → $0B = $BF - byte (row/Y position, inverted from bottom)
;
; The $BF subtraction maps the data's Y coordinates to Apple II HGR rows
; counted from the bottom of the screen ($BF = scanline 191).
;
; A WAIT($40) delay between each character pair controls scroll speed.
; The stream ends with a $00 byte.
;
; Data pointer: $00/$01, initialized to $8000
;
intro_text_crawl lda  #$00
            sta  $00             ; data pointer low = $00
            lda  #$80
            sta  $01             ; data pointer high = $80 → read from $8000

intro_crawl_loop ldx  #$00
            lda  ($00,X)         ; read next byte from data stream
            beq  intro_crawl_done ; $00 = end of stream
            sta  $0A             ; column position
            jsr  intro_inc_ptr   ; advance data pointer
            lda  #$BF            ; $BF = bottom of HGR screen (scanline 191)
            sec
            sbc  ($00,X)         ; subtract to get row from bottom
            sta  $0B             ; row position
            jsr  intro_inc_ptr   ; advance data pointer
            jsr  intro_plot_pair ; plot character pair at ($0A, $0B)
            lda  #$40            ; scroll delay
            jsr  $FCA8           ; ROM WAIT
            jmp  intro_crawl_loop

intro_crawl_done rts

; ===========================================================================
; intro_load_exodus — Exodus Graphic Blit ($83AD)
; ===========================================================================
;
; Blits the "EXODUS" title graphic from $92xx data. Direct transfer (the
; dissolve mask $17 was set to $00 by intro_sequence before the castle stage
; and remains $00). Larger region than the castle (X=$20 scanlines, Y=$05).
;
intro_load_exodus  lda  #$92
            sta  $0B             ; source high page
            lda  #$04
            sta  $0A             ; blit width
            lda  #$92            ; source page for blit
            ldx  #$20            ; scanline count
            ldy  #$05            ; column count
            jsr  intro_hgr_blit
            rts

; ===========================================================================
; intro_load_frame_3 / intro_load_frame_4 — Dramatic Final Frames ($83BF/$83D1)
; ===========================================================================
;
; These two functions display the final dramatic frames of the intro sequence.
; Frame 3 blits from $A8xx, frame 4 from $98xx — both use the same dimensions
; (X=$0D scanlines, Y=$10 columns) and blit width ($0E). They are called
; back-to-back with a sound effect between them, creating a visual "hit" effect.
;
; The LDA #$A8 in frame 3 is flagged as a redundant load (already in A from
; the STA $0B above), but it's harmless — the 6502 has no register forwarding,
; and the original programmer likely valued clarity over the 2-cycle saving.
;
intro_load_frame_3  lda  #$0E
            sta  $0A             ; blit width
            lda  #$A8
            sta  $0B             ; source high page (frame 3 at $A8xx)
            lda  #$A8            ; source page (redundant but harmless)
            ldx  #$0D            ; scanline count
            ldy  #$10            ; column count
            jsr  intro_hgr_blit
            rts

intro_load_frame_4  lda  #$0E
            sta  $0A             ; blit width (same as frame 3)
            lda  #$A8
            sta  $0B             ; source high page (shared with frame 3)
            lda  #$98            ; different source page ($98xx)
            ldx  #$0D            ; scanline count
            ldy  #$10            ; column count
            jsr  intro_hgr_blit
            rts

; ===========================================================================
; intro_hgr_blit — Core HGR Block Blit with Dissolve ($83E3)
; ===========================================================================
;
; The central graphics routine in EXOD — a scanline-by-scanline block
; transfer from source data to HGR screen memory, with three pixel transfer
; modes controlled by the $17 mask byte:
;
;   $17 = $00: Direct transfer — every non-zero source pixel is copied.
;              Zero source pixels are also copied (clearing the dest).
;   $17 = $FF: Dissolve mode — non-zero source pixels are passed through
;              a PRNG threshold test. The PRNG generates a value compared
;              against $18: if PRNG ≤ $18, the pixel transfers; otherwise
;              $00 is written. Increasing $18 from 0→255 creates a gradual
;              dissolve-in effect.
;   $17 bit 7 clear (but non-zero): Skip mode — non-zero source pixels
;              that pass BIT $17 with N=0 are skipped (store $00).
;
; The PRNG is a simple additive generator: new_high = old_low + $1D + old_high,
; new_low = old_low + $1D. This is the same PRNG used by intro_prng_mod.
; During dissolve mode, each pixel that DOES transfer also toggles the
; Apple II speaker ($C030), creating the distinctive "rain on a tin roof"
; audio effect that accompanies the dissolve animation.
;
; Apple II HGR scanline addressing:
;   The Apple II HGR memory layout is famously non-linear — consecutive
;   scanlines are NOT at consecutive addresses. The lookup tables at
;   $1B00 (low bytes) and $1BC0 (high bytes) provide the base address
;   for each scanline. The EOR with $1B implements page selection:
;   $1B=$00 → page 1 ($2000-$3FFF), $1B=$60 → page 2 ($4000-$5FFF).
;
; Parameters:
;   A   = source start page ($0C)
;   X   = column count per row ($0F)
;   Y   = row count ($0E)
;   $0A = blit width parameter (starting column offset)
;   $0B = destination scanline start (saved/restored across call)
;   $17 = pixel mask mode
;   $18 = dissolve threshold (0-255)
;   $19/$1A = PRNG state
;
; Zero-page workspace:
;   $0C/$0D = source page / column counter
;   $0E/$0F = row counter / column count
;   $10/$11 = destination scanline address (page-selected)
;   $12/$13 = source scanline address (always page 2 base, ORA #$40)
;   $14     = pixel temp storage
;   $15     = threshold aligned to 8 ($18 AND $F8)
;
intro_hgr_blit sta  $0C             ; source start page
            stx  $0F             ; column count per row
            lda  $0B
            pha                  ; save $0B (restored at exit)
            lda  $18
            and  #$F8            ; align threshold to 8-pixel boundary
            sta  $15
            sty  $0E             ; row count

; --- Outer loop: one iteration per scanline row ---
intro_blit_row lda  $0F
            sta  $0D             ; reset column counter for this row
            ldy  $0B             ; destination scanline index
            lda  $1B00,Y         ; scanline base address low byte
            sta  $10
            lda  $1BC0,Y         ; scanline base address high byte
            eor  $1B             ; XOR with page toggle ($00 or $60)
            sta  $11             ; $10/$11 = dest scanline address
            ldy  $0C             ; source scanline index
            lda  $1B00,Y         ; source scanline base low
            sta  $12
            lda  $1BC0,Y         ; source scanline base high
            ora  #$40            ; force page 2 base (source always $4000+)
            sta  $13             ; $12/$13 = source scanline address
            ldy  $0A             ; starting column offset

; --- Inner loop: one iteration per pixel column ---
intro_blit_col lda  ($12),Y         ; read source pixel
            beq  intro_blit_store ; source = 0 → write zero (clear dest)
            bit  $17             ; test mask mode
            bpl  intro_blit_store ; N=0 → skip mode, write $00 (already in A=0 path? no — falls through)
            sta  $14             ; save source pixel
            lda  $19             ; PRNG step: accumulate +$1D
            adc  #$1D
            tax
            adc  $1A
            sta  $19             ; update PRNG high
            stx  $1A             ; update PRNG low
            cmp  $18             ; compare PRNG output to dissolve threshold
            bcc  intro_blit_draw ; PRNG < threshold → draw pixel
            beq  intro_blit_draw ; PRNG = threshold → draw pixel
            lda  #$00            ; PRNG > threshold → write black (pixel hidden)
            jmp  intro_blit_store

intro_blit_draw lda  $14             ; recover saved source pixel
            bit  $C030           ; toggle speaker — creates dissolve audio

intro_blit_store sta  ($10),Y         ; write pixel to dest scanline
            iny                  ; next column
            dec  $0D             ; decrement column counter
            bne  intro_blit_col

; --- Advance to next row ---
            inc  $0B             ; next dest scanline
            inc  $0C             ; next source scanline
            dec  $0E             ; decrement row counter
            bne  intro_blit_row

            pla                  ; restore saved $0B
            sta  $0B
            rts

; ===========================================================================
; intro_plot_pair / intro_plot_pixel — HGR Pixel Plotting ($844C/$8453)
; ===========================================================================
;
; intro_plot_pair plots TWO pixels at adjacent columns: first at column
; $0A+1 (via inc/jsr/dec), then falls through to plot at column $0A.
; This creates the double-wide pixels typical of Apple II HGR text rendering.
;
; intro_plot_pixel plots a single HGR pixel at position ($0A, $0B) using
; lookup tables for the Apple II's complex HGR byte/bit mapping:
;   $1B00/$1BC0 — scanline Y → base address (same tables as intro_hgr_blit)
;   $1C80       — column X → pixel bitmask (which bit within the HGR byte)
;   $1D80       — column X → byte offset (which byte within the scanline)
;
; The pixel is OR'd into the existing screen content (non-destructive),
; and is written to BOTH HGR pages simultaneously — $10/$11 for one page,
; $12/$13 for the other (EOR #$60 flips between $20xx and $40xx).
;
; This dual-page write ensures the text crawl is visible regardless of
; which page is currently displayed.
;
intro_plot_pair inc  $0A             ; plot at column+1 first
            jsr  intro_plot_pixel
            dec  $0A             ; restore column, fall through to plot at column

intro_plot_pixel ldy  $0B             ; Y = scanline row
            lda  $1B00,Y         ; scanline base address low
            sta  $10             ; page 1 pointer low
            sta  $12             ; page 2 pointer low (same base)
            lda  $1BC0,Y         ; scanline base address high
            sta  $11             ; page 1 pointer high
            eor  #$60            ; flip $20↔$40 for other HGR page
            sta  $13             ; page 2 pointer high
            ldx  $0A             ; X = column position
            lda  $1C80,X         ; pixel bitmask for this column
            ldy  $1D80,X         ; byte offset for this column
            ora  ($10),Y         ; OR pixel into page 1
            sta  ($10),Y
            ora  ($12),Y         ; OR pixel into page 2
            sta  ($12),Y
            rts

; ===========================================================================
; intro_inc_ptr — Increment 16-bit Data Pointer ($8476)
; ===========================================================================
;
; Increments the 16-bit pointer at $00/$01 with page-crossing support.
; Used by intro_text_crawl to advance through the coordinate data stream.
; A minimal utility — just INC low / BNE skip / INC high.
;
intro_inc_ptr   inc  $00             ; increment pointer low byte
            bne  intro_inc_ptr_done ; no page crossing → done
            inc  $01             ; handle page crossing
intro_inc_ptr_done rts

; --- Dead code: alternate inline string printer (39 bytes) ---
; Disassembles to a complete string printer using $08/$09 as pointer and
; JMP ($0800) indirect for return. This is likely an earlier version of
; intro_print_string that was superseded but never removed from the binary.
; The bytes are never executed — CIDAR flagged them as a data region.
            DB      $68,$85,$08,$68,$85,$09,$E6,$08,$D0,$02,$E6,$09,$A2,$00,$A1,$08
            DB      $F0,$0C,$20,$ED,$FD,$E6,$08,$D0,$F5,$E6,$09,$4C,$8B,$84,$E6,$08
            DB      $D0,$02,$E6,$09,$6C,$08,$00

; ===========================================================================
; intro_memcpy — Page-Aligned Block Memory Copy ($84A4)
; ===========================================================================
;
; Copies X pages (256 bytes each) from source to destination. This is the
; standard 6502 page-copy idiom: inner loop copies 256 bytes via Y counter
; wrapping, outer loop decrements X and increments source/dest high bytes.
;
; Parameters:
;   A = source high byte (stored to $01, low byte set to $00)
;   Y = destination high byte (stored to $05, low byte set to $00)
;   X = number of pages to copy
;
; Used by intro_sequence to set up animation data:
;   Copy 4 pages from $2400 → $8800 (animation frame staging)
;   Copy 56 pages from $2800 → $0800 (HGR buffer preparation)
;
intro_memcpy sta  $01             ; source high byte
            sty  $05             ; destination high byte
            lda  #$00
            sta  $00             ; source low byte = $00
            sta  $04             ; destination low byte = $00
            ldy  #$00            ; byte counter (wraps 0→255→0)

; --- Inner loop: copy 256 bytes ---
intro_memcpy_loop lda  ($00),Y         ; read from source
            sta  ($04),Y         ; write to destination
            iny
            bne  intro_memcpy_loop ; loop until Y wraps to 0

; --- Outer loop: advance pages, count down ---
            inc  $01             ; next source page
            inc  $05             ; next destination page
            dex                  ; decrement page counter
            bne  intro_memcpy_loop ; more pages to copy

            rts

; ===========================================================================
; intro_memswap — Swap Memory Blocks for HGR Page Flip ($84BF)
; ===========================================================================
;
; Swaps 4 pages (1024 bytes) between $0400-$07FF and $8800-$8BFF.
; The $0400 region is the Apple II text page 1 — during HGR mode this
; memory is available as a staging buffer. $8800 sits in the EXOD data
; area above the code section.
;
; Called twice by intro_sequence:
;   1. At setup — moves text screen content to $8800 for safekeeping,
;      copies animation staging data into $0400 for the HGR renderer
;   2. At cleanup (intro_finish) — restores the original text screen
;      content so the transition to BOOT text mode is clean
;
; Uses the stack as a temp register for the 3-way swap — the classic
; 6502 technique when you have only A/X/Y and need to exchange two
; memory locations without a temp ZP variable.
;
intro_memswap lda  #$00
            sta  $00             ; block A low = $00
            sta  $04             ; block B low = $00
            lda  #$04
            sta  $01             ; block A high = $04 → $0400
            lda  #$88
            sta  $05             ; block B high = $88 → $8800
            ldy  #$00            ; byte counter
            ldx  #$04            ; page counter (4 pages = 1024 bytes)

; --- Swap loop: exchange bytes using stack as temp ---
intro_memswap_loop lda  ($00),Y         ; read byte from block A
            pha                  ; save on stack
            lda  ($04),Y         ; read byte from block B
            sta  ($00),Y         ; write to block A
            pla                  ; recover original block A byte
            sta  ($04),Y         ; write to block B
            iny
            bne  intro_memswap_loop ; loop 256 bytes per page

            inc  $01             ; next page in block A
            inc  $05             ; next page in block B
            dex                  ; decrement page counter
            bne  intro_memswap_loop ; more pages to swap

            rts

; ===========================================================================
; intro_check_key — Interruptible Delay with Keyboard Skip ($84E6)
; ===========================================================================
;
; Combines a timed delay with keyboard polling, allowing the user to skip
; the intro at any point. Called 7 times by intro_sequence between stages.
;
; Algorithm:
;   Loop Y times: WAIT($FF) then check keyboard.
;   If no key pressed and Y > 0, continue looping.
;   If key pressed → skip to intro_finish via stack unwinding.
;
; The Y parameter controls pause duration:
;   Y=$02 ≈ 0.5 sec, Y=$04 ≈ 1.0 sec, Y=$05 ≈ 1.3 sec, Y=$06 ≈ 1.5 sec
;
; The skip mechanism is elegant: PLA×2 discards this function's own return
; address from the stack, then JMP intro_finish resumes at the cleanup code
; in intro_sequence. This works because intro_check_key is always called
; from intro_sequence — the PLA×2 effectively returns to intro_sequence's
; caller level, and intro_finish restores HGR buffers before returning.
;
; Entry: Y = number of delay iterations
; Exit:  Normal return (no key), or skip to intro_finish (key pressed)
;
intro_check_key   lda  #$FF            ; maximum WAIT delay (~0.26 sec)
            jsr  $FCA8           ; ROM WAIT
            lda  $C000           ; read keyboard
            bmi  intro_key_pressed ; bit 7 set = key pressed → skip
            dey                  ; count down delay iterations
            bne  intro_check_key  ; more iterations remaining

            rts                  ; timeout — return normally

; --- Key pressed: skip remaining intro ---
intro_key_pressed bit  $C010           ; clear keyboard strobe
            pla                  ; discard return address low byte
            pla                  ; discard return address high byte
            jmp  intro_finish    ; jump to cleanup in intro_sequence


; ===========================================================================
; intro_toggle_page — HGR Page 1/2 Toggle ($84FC)
; ===========================================================================
;
; Toggles the visible HGR page between page 1 ($2000) and page 2 ($4000)
; for double-buffered animation. The page state is tracked in zero-page $1B:
;   $1B = $00 → currently showing page 1 (after EOR → $60, show page 1)
;   $1B = $60 → currently showing page 2 (after EOR → $00, show page 2)
;
; The EOR #$60 is the toggle — $60 XOR $60 = $00, $00 XOR $60 = $60.
; The same $1B value is used by intro_hgr_blit's scanline address
; calculation (EOR $1B) to direct drawing to the correct page.
;
; Apple II soft switches:
;   $C054 (LOWSCR) = display page 1
;   $C055 (HISCR) = display page 2
;
; Note the inverted logic: when $1B becomes non-zero ($60) after the EOR,
; we show page 1 — because the drawing just completed on page 2 (the
; hidden page), so we want to KEEP showing page 1 until the next flip.
;
intro_toggle_page     lda  $1B             ; current page state
            eor  #$60            ; toggle: $00 ↔ $60
            sta  $1B
            bne  intro_show_page1 ; $1B=$60 → show page 1 (draw target = page 2)
            bit  $C055           ; $1B=$00 → show page 2 (HISCR)
            rts
intro_show_page1  bit  $C054           ; show page 1 (LOWSCR)
            rts

; ===========================================================================
; intro_sound_effect — Speaker Tone Generation ($850C)
; ===========================================================================
;
; Generates the ominous sound effect played between the final intro frames.
; The Apple II speaker is a 1-bit toggle ($C030) — reading this address
; flips the speaker cone, producing a click. To make a tone, you toggle
; it in a timed loop; varying the loop period changes the pitch.
;
; Structure:
;   Outer loop: 5 × 256 = 1280 speaker toggles total
;     1. Call intro_prng_mod(255) → random delay value (0-254)
;     2. Busy-wait X cycles (DEX/BNE inner loop)
;     3. Toggle speaker
;     4. Decrement $14 (inner counter, 256 iterations)
;     5. Decrement $15 (outer counter, 5 groups)
;
; The PRNG-modulated delay creates a randomized pitch that shifts between
; toggles, producing a chaotic "explosion" or "thunder" effect rather than
; a pure tone. This is a common 1980s Apple II audio technique — since the
; speaker can only click (no amplitude or waveform control), all timbral
; variety comes from varying the inter-click timing.
;
intro_sound_effect lda  #$00
            sta  $14             ; inner loop counter (wraps from 0 → 256 iters)
            lda  #$05
            sta  $15             ; outer loop counter (5 groups)

intro_sound_outer lda  #$FF            ; modulo base for PRNG → max 254
            jsr  intro_prng_mod  ; get random delay 0-254
            tax                  ; X = random delay count

intro_sound_inner dex                  ; busy-wait loop: X cycles
            bne  intro_sound_inner

            bit  $C030           ; toggle speaker cone
            dec  $14             ; inner counter (256 toggles per group)
            bne  intro_sound_outer

            dec  $15             ; outer counter (5 groups)
            bne  intro_sound_outer
            rts

; --- Dead code: alternate sound effect routine (31 bytes) ---
; Disassembles to a speaker routine that computes delay from ($FF - $0B) >> 2,
; then uses a timing loop with AND #$07 + ADC $0B for pitch variation.
; Never executed — likely an earlier draft of intro_sound_effect.
            DB      $A9,$FF,$38,$E5,$0B,$4A,$4A,$85,$14,$A9,$FF,$20,$48,$85,$29,$07
            DB      $18,$65,$0B,$AA,$CA,$D0,$FD,$2C,$30,$C0,$C6,$14,$D0,$EB,$60

; ===========================================================================
; intro_prng_mod — PRNG with Modulo Reduction ($8548)
; ===========================================================================
;
; Pseudo-random number generator that returns a value in [0, A-1].
; The PRNG state lives in $19/$1A (shared with intro_hgr_blit's dissolve).
;
; Algorithm:
;   1. Store modulo base (A) to self-modifying operand at $8569
;   2. If A=0, return immediately (avoid division by zero)
;   3. Advance PRNG state:
;      new_$19 = old_$19 + old_$1A  (additive step)
;      new_$1A = old_$19 + $17      (feedback with constant)
;   4. Reduce $1A modulo the stored base via repeated subtraction
;   5. Return reduced value in A
;
; The self-modifying code at $8569 is the CMP and SBC operand in the modulo
; loop — STA $8569 patches the comparison target at runtime. This is the
; standard 6502 technique for parameterized comparisons, since the 6502
; has no divide instruction and lacks enough registers for a parameter.
;
; The additive generator with constant $17 and cross-feedback between
; $19/$1A produces a reasonably well-distributed sequence for visual
; effects, though it would not pass modern statistical tests.
;
intro_prng_mod sta  $8569           ; SMC: patch modulo base into CMP/SBC operand
            cmp  #$00
            beq  intro_prng_done ; modulo 0 → return 0 (avoid infinite loop)
            lda  $19             ; PRNG state low
            pha                  ; save for feedback
            adc  $1A             ; new high = low + high
            sta  $19
            pla                  ; recover original low
            clc
            adc  #$17            ; new low = old_low + $17 (constant step)
            sta  $1A

; --- Modulo reduction: repeated subtraction ---
intro_prng_loop cmp  $8569           ; compare against modulo base (SMC target)
            bcc  intro_prng_done ; A < base → done
            sec
            sbc  $8569           ; A -= base
            jmp  intro_prng_loop ; repeat until A < base

intro_prng_done rts
            DB      $00              ; padding byte

; ===========================================================================
; intro_reveal_anim — Progressive Column Reveal ($856A)
; ===========================================================================
;
; Reveals the current HGR image column-by-column in a dramatic left-to-right
; sweep. This is the animation that unveils the final Exodus graphic after
; the direct blit. Uses page 1 only ($1B=$00).
;
; The animation runs 3 passes (Y=2,1,0), each with different parameters
; loaded from data tables at $85A9-$85B7. Each pass has:
;   - Start glyph: $85B5,Y → $71 (initial column to draw)
;   - Step size: $85A9,Y (column increment per frame)
;   - End glyph: $85AC,Y (termination condition for inner loop)
;   - Start offset: $0A (screen X position, begins at $2A)
;   - Offset step: $85AF,Y (X advance per outer iteration)
;   - Offset end: $85B2,Y (termination for outer loop)
;
; The interleaved passes create a curtain-like reveal effect — the first
; pass draws every 3rd column, the second fills in gaps, the third
; completes the image. A WAIT($D0) delay between columns controls speed.
;
; After all 3 passes, a final intro_draw_column(X=0) draws glyph 0 to
; clean up any remaining artifact at the leftmost position.
;
; Data tables (15 bytes at $85A9):
;   $85A9: step sizes    [+1, -1, +1]  (alternating direction)
;   $85AC: end glyphs    [$04, $FF, $04]
;   $85AF: offset steps  [+1, -1, +1]
;   $85B2: offset ends   [$34, $2B, $31]
;   $85B5: start glyphs  [$00, $03, $00]
;
intro_reveal_anim lda  #$00
            sta  $1B             ; lock to page 1
            bit  $C054           ; ensure page 1 displayed
            lda  #$2A
            sta  $0A             ; starting screen X position
            ldy  #$02            ; 3 passes: Y = 2, 1, 0

; --- Outer loop: one pass per Y value ---
intro_reveal_outer lda  $85B5,Y         ; load start glyph for this pass
            sta  $71             ; current glyph column

; --- Inner loop: draw columns across the image ---
intro_reveal_inner ldx  $71             ; X = current glyph index
            jsr  intro_draw_column ; render one glyph column
            lda  #$D0            ; inter-column delay
            jsr  $FCA8           ; ROM WAIT
            lda  $71
            clc
            adc  $85A9,Y         ; advance glyph by step size
            sta  $71
            cmp  $85AC,Y         ; reached end glyph?
            bne  intro_reveal_inner

; --- Advance screen position for next pass ---
            lda  $0A
            clc
            adc  $85AF,Y         ; advance screen X by offset step
            sta  $0A
            cmp  $85B2,Y         ; reached offset end?
            bne  intro_reveal_outer

; --- Next pass (Y counts down 2→1→0) ---
            dey
            bpl  intro_reveal_outer ; continue while Y ≥ 0

; --- Final cleanup: draw glyph 0 at final position ---
            ldx  #$00
            jsr  intro_draw_column
            rts

; --- Reveal animation parameter tables (15 bytes) ---
;   Index:        [0]  [1]  [2]
;   Step:          +1   -1   +1    (alternating scan direction)
;   End glyph:    $04  $FF  $04
;   Offset step:  +1   -1   +1
;   Offset end:   $34  $2B  $31
;   Start glyph:  $00  $03  $00
            DB      $01,$FF,$01,$04,$FF,$04,$01,$FF,$01,$34,$2B,$31,$00,$03,$00


; ===========================================================================
; intro_draw_column — Single Glyph Column Render ($85B8)
; ===========================================================================
;
; Draws a single column of the reveal animation — a vertical strip of glyph
; data rendered to the HGR screen. This is the most complex single function
; in EXOD, using extensive self-modifying code (SMC) to patch source and
; glyph data addresses into LDA instructions at runtime.
;
; The function renders a 16-scanline tall column ($0E=$10 rows) of glyph
; data, with each row consisting of 13 bytes ($0D) of pixel data. For
; each scanline:
;   1. Look up the HGR screen address via $1B00/$1BC0 tables
;   2. Write $80 (black with high bit set) at column-1 and column+13
;      as left/right border markers
;   3. Copy 13 bytes from the glyph source (via SMC addresses) to the
;      scanline, OR'ing each byte with $80 (Apple II HGR high bit)
;
; Self-modifying code targets (defined as EQUs at file top):
;   intro_draw_src_lo/hi   ($85F6/$85F7) — source address for row data
;   intro_draw_src2_lo/hi  ($85FD/$85FE) — duplicate source (used for
;                                          border byte lookup)
;   intro_draw_glyph_lo/hi ($862C/$862D) — glyph pixel data address
;                                          (incremented per byte drawn)
;
; The $0400,X lookup fetches glyph source addresses from a table that
; was loaded into the text page area by intro_memswap during setup.
;
; The column offset tables at $1D80/$1E80/$1E98/$1E9C provide the
; byte offset within each scanline for the given screen column ($0A).
; The carry flag from ASL selects between two table pairs, handling
; the left/right halves of the 280-pixel screen.
;
; Parameters:
;   A = saved to $1C (restored at exit)
;   X = glyph index (×2 → $0400 lookup → source address)
;   Y = saved to $1D (restored at exit)
;   $0A = screen column position
;
; Preserves: A, X, Y (saved to $1C/$1E/$1D, restored at exit)
;            $0A (saved/restored via stack)
;
intro_draw_column sta  $1C             ; save caller's A
            stx  $1E             ; save caller's X
            sty  $1D             ; save caller's Y
            lda  $0A
            pha                  ; save screen column (restored at exit)
            lda  #$A8
            sta  $0B             ; starting scanline = $A8

; --- Look up glyph source address from $0400 table ---
            txa                  ; glyph index
            asl  a               ; ×2 for 16-bit table entry
            tax
            lda  $0400,X         ; glyph source address low byte
            sta  intro_draw_src_lo  ; SMC: patch LDA operand
            sta  intro_draw_src2_lo ; SMC: patch second LDA operand
            lda  $0401,X         ; glyph source address high byte
            sta  intro_draw_src_hi  ; SMC: patch LDA operand
            sta  intro_draw_src2_hi ; SMC: patch second LDA operand

; --- Compute column byte offset from screen position ---
            lda  $0A             ; screen column
            asl  a               ; ×2 for 16-bit table lookup
            tax
            bcs  intro_draw_alt_base ; carry set → upper half of screen (col ≥ 128)
            lda  $1D80,X         ; column offset (lower half)
            sta  $1F
            lda  $1E98,X         ; glyph pointer table base (lower half)
            jmp  intro_draw_calc_src

intro_draw_alt_base lda  $1E80,X         ; column offset (upper half)
            sta  $1F
            lda  $1E9C,X         ; glyph pointer table base (upper half)

; --- Resolve glyph pixel data address ---
intro_draw_calc_src asl  a               ; ×2 for address lookup
            tax
            lda  $FFFF,X         ; glyph data address low (CIDAR placeholder)
            sta  intro_draw_glyph_lo ; SMC: patch inner loop LDA operand
            inx
            lda  $FFFF,X         ; glyph data address high
            sta  intro_draw_glyph_hi ; SMC: patch inner loop LDA operand
            lda  #$10
            sta  $0E             ; 16 scanline rows to render

; --- Outer loop: one iteration per scanline ---
intro_draw_row_loop ldy  $0B             ; current scanline index
            lda  $1B00,Y         ; scanline base address low
            sta  $10
            lda  $1BC0,Y         ; scanline base address high
            eor  $1B             ; apply page selection
            sta  $11             ; $10/$11 = HGR screen address for this row

; --- Write left border marker ---
            ldy  $1F             ; column byte offset
            dey                  ; one byte to the left
            lda  #$80            ; black pixel with high bit set
            sta  ($10),Y         ; left border

; --- Write right border marker ---
            lda  $1F
            clc
            adc  #$0D            ; 13 bytes to the right
            tay
            lda  #$80
            sta  ($10),Y         ; right border

; --- Inner loop: copy 13 glyph bytes to scanline ---
            lda  #$0D
            sta  $0D             ; 13 bytes per row
            ldy  $1F             ; reset to column start offset

intro_draw_byte lda  $FFFF           ; SMC target: reads from glyph data
            ora  #$80            ; set HGR high bit (Apple II color bit)
            sta  ($10),Y         ; write pixel byte to screen
            iny                  ; next screen byte
            inc  intro_draw_glyph_lo ; advance glyph source pointer
            bne  intro_draw_next_byte
            inc  intro_draw_glyph_hi ; handle page crossing
intro_draw_next_byte dec  $0D             ; 13 bytes per row
            bne  intro_draw_byte

; --- Advance to next scanline ---
            inc  $0B             ; next scanline
            dec  $0E             ; 16 rows total
            bne  intro_draw_row_loop

; --- Restore caller's registers and $0A ---
            pla
            sta  $0A             ; restore screen column
            lda  $1C             ; restore A
            ldx  $1E             ; restore X
            ldy  $1D             ; restore Y
            rts

; --- Padding to end of code section ---
            DS      17
