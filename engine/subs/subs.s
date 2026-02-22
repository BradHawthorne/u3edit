; ===========================================================================
; SUBS.s — Ultima III: Exodus Shared Subroutine Library
; ===========================================================================
;
; 3,584 bytes at $4100. Shared routines called by ULT3 and EXOD.
; Reassembled byte-identical from CIDAR disassembly via asmiigs.
;
; Subsystems:
;   $4100-$46B9  Data tables: HGR scanline addresses, sprite graphics,
;                jump dispatch table, inline string printer entry
;   $4732        print_inline_str  — Print text embedded after JSR $46BA
;   $4767        scroll_text_up    — Scroll text window, redraw viewport border
;   $47B2        save_text_ptr     — Save/restore text pointer $FE/$FF
;   $4855        draw_hgr_stripe   — Draw colored vertical stripe on HGR
;   $487B        clear_hgr_page    — Zero-fill HGR page 1 ($2000-$3FFF)
;   $4893        plot_char_glyph   — Plot 7x8 character glyph to HGR screen
;   $48D9        swap_tile_frames  — Swap tile animation frames in memory
;   $48FF        advance_ptr_128   — Add $80 to pointer $FE/$FF
;   $490D        print_digit       — Print single ASCII digit via plot_char
;   $4916        print_bcd_byte    — Print BCD byte as 2 decimal digits
;   $4935        calc_roster_ptr   — Compute roster slot address ($9500+N*64)
;   $4955        copy_roster_to_plrs — Copy roster records → active PLRS
;   $496B        copy_plrs_to_roster — Copy active PLRS → roster records
;   $49FF        modulo            — A mod $F3 (modular arithmetic)
;   $4A13        update_viewport   — Full viewport display refresh
;   $4A26        animate_tiles     — Cycle overworld tile animation frames
;   $4A8D        animate_cursor    — Cursor blink / text-mode tile animation
;   $4BCA        setup_char_ptr    — Set $FE/$FF = $4000 + slot*64
;   $4BE4        print_char_name   — Print character name centered on screen
;   $4C0C        draw_text_window  — Text window mode display and scrolling
;   $4CE8        play_sfx          — Sound effect dispatcher ($F6-$FF)
;   $4E40        get_random        — Pseudo-random number generator
;
; Zero-Page Usage:
;   $00/$01    map_cursor_x/y        Map/overworld position
;   $02/$03    combat_cursor_x/y     Combat grid position
;   $0F        animation_slot        Tile animation table offset
;   $10        combat_active_flag    Nonzero = in combat
;   $11        text_window_mode      Wind direction display index
;   $95/$96    sfx_scratch           Sound effect working variables
;   $D0-$D5    display_state         Viewport rendering state
;   $D7        char_name_index       Character name byte offset
;   $E1        party_size            Active party member count
;   $E6-$E9    party_slots           Roster indices for 4 party members
;   $F0-$F3    temp_work             General scratch registers
;   $F9/$FA    text_cursor_x/y       Text output cursor position
;   $FC/$FD    dest_ptr              Destination pointer (copy ops)
;   $FE/$FF    src_ptr / data_ptr    Source/general data pointer
;
; === Optimization Hints Report ===
; Total hints: 24
; Estimated savings: 81 cycles/bytes

; Address   Type              Priority  Savings  Description
; ---------------------------------------------------------------
; $004B01   PEEPHOLE          MEDIUM    4        Load after store: 2 byte pattern at $004B01
; $004B09   PEEPHOLE          MEDIUM    4        Load after store: 2 byte pattern at $004B09
; $004B33   PEEPHOLE          MEDIUM    4        Load after store: 2 byte pattern at $004B33
; $004B3B   PEEPHOLE          MEDIUM    4        Load after store: 2 byte pattern at $004B3B
; $004D62   PEEPHOLE          MEDIUM    4        Load after store: 2 byte pattern at $004D62
; $004DC8   PEEPHOLE          MEDIUM    7        Redundant PHA/PLA: 2 byte pattern at $004DC8
; $004DCA   PEEPHOLE          MEDIUM    7        Redundant PHA/PLA: 2 byte pattern at $004DCA
; $0047A0   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $00479E
; $0047A2   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $0047A0
; $0047A4   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $0047A2
; $0047A6   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $0047A4
; $0047A8   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $0047A6
; $0047AA   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $0047A8
; $0047AC   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $0047AA
; $0047AE   REDUNDANT_LOAD    MEDIUM    3        Redundant LDY: same value loaded at $0047AC
; $0047BF   REDUNDANT_LOAD    MEDIUM    3        Redundant LDA: same value loaded at $0047BB
; $0047D9   REDUNDANT_LOAD    MEDIUM    3        Redundant LDA: same value loaded at $0047D5
; $00485B   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for calc_roster_ptr
; $00485C   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for calc_roster_ptr
; $0048A0   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for calc_roster_ptr
; $0048A1   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for calc_roster_ptr
; $004BF6   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for calc_roster_ptr
; $004A22   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $004A22 followed by RTS
; $004A4B   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $004A4B followed by RTS

; Loop Analysis Report
; ====================
; Total loops: 61
;   for:       0
;   while:     51
;   do-while:  0
;   infinite:  0
;   counted:   10
; Max nesting: 14
;
; Detected Loops:
;   Header    Tail      Type      Nest  Counter
;   ------    ----      ----      ----  -------
;   $004861   $004878   while        6  X: 0 step 1
;   $004785   $00478C   while        8  Y: 0 step 1
;                       ~40 iterations
;   $00476F   $004791   while        7  X: 0 step 1
;                       ~184 iterations
;   $004732   $00479B   while        0  X: 0 step 1
;                       ~184 iterations
;   $004738   $00475D   while        7  -
;   $0048AE   $0048D6   while        9  -
;   $004738   $00474F   while        7  -
;   $004885   $004888   while        6  Y: 0 step 1
;   $004885   $004890   while        6  Y: 0 step 1
;   $0047BF   $0047D3   while        6  -
;   $0047D9   $0047F4   while        6  -
;   $0047FA   $004823   while        6  -
;   $00482D   $004836   while        6  -
;   $004893   $004921   while        6  Y: 0 step 1
;   $004893   $00492E   while        6  Y: 0 step 1
;   $004935   $00496B   while       11  X: 0 step -1
;   $004970   $004975   while       12  -
;   $00496B   $004978   while       11  -
;   $004E48   $004E4F   while        0  -
;   $004E53   $004E59   while        0  -
;   $004A04   $004A0B   while       12  -
;   $0048D9   $004A37   while        7  Y: 0 step 1
;   $0048E4   $0048F3   while       14  -
;   $0048D9   $0048FC   while        9  Y: 0 step 1
;   $0048D9   $004A4B   while        7  Y: 0 step 1
;   $0048D9   $004A46   while        7  Y: 0 step 1
;   $0048D9   $004A32   while        7  Y: 0 step 1
;   $004732   $004BC7   while        0  Y: 0 step 1
;   $004BCA   $004BDB   while        7  -
;   $004BE4   $004BE7   while        8  -
;   ... and 31 more loops

; Call Site Analysis Report
; =========================
; Total call sites: 6
;   JSR calls:      6
;   JSL calls:      0
;   Toolbox calls:  0
;
; Parameter Statistics:
;   Register params: 6
;   Stack params:    1
;
; Calling Convention Analysis:
;   Predominantly short calls (JSR/RTS)
;   Register-based parameter passing
;
; Call Sites (first 20):
;   $0045A4: JSR $000140 params: X Y
;   $004614: JSR $000140
;   $0048EC: JSR $0048FF params: A
;   $004960: JSR $000000 params: X
;   $004A58: JSR $004A8D params: X Y
;   $004CAC: JSR $004732 params: stack

; === Stack Frame Analysis (Sprint 5.3) ===
; Functions with frames: 12

; Function $004100: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $004732: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;      +72: param_72 (2 bytes, 1 accesses)

; Function $004767: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $004855: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00487B: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $004893: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0048D9: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0048FF: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $004935: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0049FF: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $004BCA: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $004E40: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no


; === Liveness Analysis Summary (Sprint 5.4) ===
; Functions analyzed: 12
; Functions with register params: 8
; Functions with register returns: 12
; Total dead stores detected: 28 (in 9 functions)
;
; Function Details:
;   $004100: params(AXY) returns(AXY) 
;   $004732: params(X) returns(AXY) [2 dead]
;   $004767: returns(AXY) [9 dead]
;   $004855: returns(AXY) [3 dead]
;   $00487B: returns(AXY) 
;   $004893: returns(AXY) [2 dead]
;   $0048D9: params(XY) returns(AXY) [3 dead]
;   $0048FF: params(XY) returns(AXY) [2 dead]
;   $004935: params(XY) returns(AXY) [2 dead]
;   $0049FF: params(AXY) returns(AXY) 
;   $004BCA: params(XY) returns(AXY) [1 dead]
;   $004E40: params(Y) returns(AXY) [4 dead]

; Function Signature Report
; =========================
; Functions analyzed:    12
;   Leaf functions:      2
;   Interrupt handlers:  5
;   Stack params:        0
;   Register params:     12
;
; Function Signatures:
;   Entry     End       Conv       Return   Frame  Flags
;   -------   -------   --------   ------   -----  -----
;   $004100   $004732   register   A:X         0   I
;     Proto: uint32_t func_004100(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $004732   $004767   register   A:X         0   
;     Proto: uint32_t func_004732(uint16_t param_X);
;   $004767   $004855   register   A:X         0   
;   $004855   $00487B   register   A:X         0   L
;     Proto: uint32_t func_004855(void);
;   $00487B   $004893   register   A:X         0   I
;     Proto: uint32_t func_00487B(void);
;   $004893   $0048D9   register   A:X         0   L
;     Proto: uint32_t func_004893(void);
;   $0048D9   $0048FF   register   A:X         0   
;     Proto: uint32_t func_0048D9(uint16_t param_X, uint16_t param_Y);
;   $0048FF   $004935   register   A:X         0   
;     Proto: uint32_t func_0048FF(uint16_t param_X, uint16_t param_Y);
;   $004935   $0049FF   register   A:X         0   I
;     Proto: uint32_t func_004935(uint16_t param_X, uint16_t param_Y);
;   $0049FF   $004BCA   register   A:X         0   I
;     Proto: uint32_t func_0049FF(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $004BCA   $004E40   register   A:X         0   I
;     Proto: uint32_t func_004BCA(uint16_t param_X, uint16_t param_Y);
;   $004E40   $004F00   register   A:X         0   
;     Proto: uint32_t func_004E40(uint16_t param_Y);
;
; Flags: L=Leaf, J=JSL/RTL, I=Interrupt, F=FrameSetup

; Constant Propagation Analysis
; =============================
; Constants found: 12
; Loads with known value: 9
; Branches resolved: 0
; Compares resolved: 0
; Memory constants tracked: 0
;
; Final register state:
;   A: unknown
;   X: unknown
;   Y: $0006 (set at $004DFA)
;   S: [$0100-$01FF]
;   DP: undefined
;   DBR: undefined
;   PBR: undefined
;   P: undefined

; ============================================================================
; TYPE INFERENCE REPORT
; ============================================================================
;
; Entries analyzed: 204
; Bytes typed:      55
; Words typed:      64
; Pointers typed:   2
; Arrays typed:     42
; Structs typed:    87
;
; Inferred Types:
;   Address   Type       Conf   R    W   Flags  Name
;   -------   --------   ----   ---  --- -----  ----
;   $000060   BYTE       80%     6    0 P      byte_0060
;   $000040   BYTE       80%     5    0 P      byte_0040
;   $000070   BYTE       60%     3    0 P      byte_0070
;   $000030   BYTE       70%     4    0 P      byte_0030
;   $000000   STRUCT     80%    10    0 P      struct_0000 {size=255}
;   $000061   BYTE       60%     3    0 P      byte_0061
;   $00373E   ARRAY      75%     1    0 I      arr_373E [elem=1]
;   $000063   ARRAY      75%     1    0 I      arr_0063 [elem=1]
;   $000042   ARRAY      75%     3    0 IP     arr_0042 [elem=1]
;   $001162   ARRAY      75%     1    0 I      arr_1162 [elem=1]
;   $000010   BYTE       60%     3    0 P      byte_0010
;   $001070   ARRAY      75%     1    0 I      arr_1070 [elem=1]
;   $000008   BYTE       50%     2    0 P      byte_0008
;   $000002   BYTE       90%    43    1 P      byte_0002
;   $000003   BYTE       60%     2    1 P      byte_0003
;   $000033   BYTE       50%     2    0        byte_0033
;   $000027   ARRAY      75%     2    0 I      arr_0027 [elem=1]
;   $003F7E   ARRAY      75%     1    0 I      arr_3F7E [elem=1]
;   $001C1C   ARRAY      75%     1    0 I      arr_1C1C [elem=1]
;   $00701F   ARRAY      75%     1    0 I      arr_701F [elem=1]
;   $00001E   ARRAY      75%     1    0 I      arr_001E [elem=1]
;   $0000A8   BYTE       50%     1    1 P      byte_00A8
;   $00008A   ARRAY      75%     2    1 IP     arr_008A [elem=1]
;   $000082   FLAG       50%     2    1        flag_0082
;   $0000A2   FLAG       50%     2    0        flag_00A2
;   $0000A0   ARRAY      75%     0    1 I      arr_00A0 [elem=1]
;   $003430   WORD       90%     6    0        word_3430
;   $000025   BYTE       90%     7    0 P      byte_0025
;   $003400   STRUCT     70%     0    0        struct_3400 {size=49}
;   $000035   BYTE       60%     3    0 P      byte_0035
;   $00213D   ARRAY      85%     3    0 I      arr_213D [elem=1]
;   $000029   BYTE       60%     3    0        byte_0029
;   $003531   WORD       60%     3    0        word_3531
;   $00223D   ARRAY      85%     3    0 I      arr_223D [elem=1]
;   $00002A   BYTE       60%     3    0        byte_002A
;   $003632   WORD       90%     6    0        word_3632
;   $002622   ARRAY      85%     3    0 I      arr_2622 [elem=1]
;   $002723   ARRAY      85%     3    0 I      arr_2723 [elem=1]
;   $3B3733   LONG       90%     6    0        long_3B3733
;   $000001   BYTE       70%     4    0 P      byte_0001
;   $000005   BYTE       60%     3    0        byte_0005
;   $000006   BYTE       70%     4    0        byte_0006
;   $000D0D   WORD       50%     2    0        word_0D0D
;   $000E0E   WORD       50%     2    0        word_0E0E
;   $000D00   STRUCT     70%     0    0        struct_0D00 {size=14}
;   $000E00   STRUCT     70%     0    0        struct_0E00 {size=192}
;   $000011   BYTE       90%     6    1 P      byte_0011
;   $000015   ARRAY      85%     3    0 I      arr_0015 [elem=1]
;   $000016   ARRAY      90%     4    0 I      arr_0016 [elem=1]
;   $001919   ARRAY      80%     2    0 I      arr_1919 [elem=1]
;   $001A1A   ARRAY      75%     1    0 I      arr_1A1A [elem=1]
;   $001900   STRUCT     70%     0    0        struct_1900 {size=26}
;   $001D1D   ARRAY      80%     2    0 I      arr_1D1D [elem=1]
;   $001E1E   ARRAY      80%     2    0 I      arr_1E1E [elem=1]
;   $001D00   STRUCT     70%     0    0        struct_1D00 {size=30}
;   $001F1E   ARRAY      75%     1    0 I      arr_1F1E [elem=1]
;   $001E00   STRUCT     70%     0    0        struct_1E00 {size=31}
;   $000021   BYTE       50%     2    0 P      byte_0021
;   $000024   BYTE       60%     3    0        byte_0024
;   $000026   BYTE       60%     3    0        byte_0026
;   $0000FE   PTR        80%    22   22 P      ptr_00FE
;   $0000FF   BYTE       90%    12   15        byte_00FF
;   $0000F9   BYTE       90%    10    5        byte_00F9
;   $0000FA   BYTE       70%     0    4        byte_00FA
;   $004300   ARRAY      80%     2    0 I      arr_4300 [elem=1]
;   $0043C0   ARRAY      90%     4    0 I      arr_43C0 [elem=1]
;   $004308   ARRAY      75%     1    0 I      arr_4308 [elem=1]
;   $0000FC   PTR        80%     6    6 P      ptr_00FC
;   $0043C8   ARRAY      75%     1    0 I      arr_43C8 [elem=1]
;   $0000FD   BYTE       60%     0    3        byte_00FD
;   $0000F2   BYTE       90%     5    9        byte_00F2
;   $0000F1   BYTE       90%     5    6        byte_00F1
;   $0000F3   BYTE       90%     7    6        byte_00F3
;   $0000BD   BYTE       50%     2    0 P      byte_00BD
;   $0000F0   BYTE       90%     3    4 P      byte_00F0
;   $00FAA6   ARRAY      75%     1    0 I      arr_FAA6 [elem=1]
;   $0048C0   WORD       50%     1    1        word_48C0
;   $00FFFF   ARRAY      75%     0    1 I      arr_FFFF [elem=1]
;   $0048BF   WORD       50%     1    1        word_48BF
;   $004800   STRUCT     70%     0    0        struct_4800 {size=193}
;   $000800   ARRAY      75%     0    1 I      arr_0800 [elem=1]
;   $004934   WORD       50%     1    1        word_4934
;   $0000E6   ARRAY      75%     1    0 I      arr_00E6 [elem=1]
;   $0000CA   BYTE       50%     2    0 P      byte_00CA
;   $0000D1   BYTE       80%     2    3        byte_00D1
;   $0000D2   BYTE       80%     2    3        byte_00D2
;   $000018   BYTE       50%     2    0        byte_0018
;   $0000D0   BYTE       50%     1    2 IP     byte_00D0
;   $004A4F   WORD       50%     1    1        word_4A4F
;   $004A50   WORD       50%     1    1        word_4A50
;   $004A5D   WORD       50%     1    1        word_4A5D
;   $004A5E   WORD       50%     1    1        word_4A5E
;   $000009   ARRAY      80%     2    0 I      arr_0009 [elem=1]
;   $00093E   WORD       50%     1    1        word_093E
;   $00093F   WORD       50%     1    1        word_093F
;   $0009BE   WORD       50%     1    1        word_09BE
;   $0009BF   WORD       50%     1    1        word_09BF
;   $004B47   WORD       50%     2    0        word_4B47
;   $000900   STRUCT     80%     0    0        struct_0900 {size=192}
;   $000BBE   WORD       50%     1    1        word_0BBE
;   $004B00   STRUCT     70%     0    0        struct_4B00 {size=179}
;   $000C3E   WORD       50%     1    1        word_0C3E
;   $000CBE   WORD       50%     1    1        word_0CBE
;   $000C00   STRUCT     70%     0    0        struct_0C00 {size=192}
;   $000BBF   WORD       50%     1    1        word_0BBF
;   $000C3F   WORD       50%     1    1        word_0C3F
;   $000CBF   WORD       50%     1    1        word_0CBF
;   $000DBE   WORD       50%     1    1        word_0DBE
;   $000E3E   WORD       50%     1    1        word_0E3E
;   $000EBE   WORD       50%     1    1        word_0EBE
;   $000DBF   WORD       50%     1    1        word_0DBF
;   $000E3F   WORD       50%     1    1        word_0E3F
;   $000EBF   WORD       50%     1    1        word_0EBF
;   $004BB4   WORD       50%     1    1        word_4BB4
;   $004BB2   WORD       70%     3    1        word_4BB2
;   $000095   BYTE       90%     5    6        byte_0095
;   $004BB3   WORD       50%     1    1        word_4BB3
;   $00FA84   ARRAY      75%     1    0 I      arr_FA84 [elem=1]
;   $0000D5   BYTE       50%     2    0        byte_00D5
;   $0000D7   BYTE       60%     2    1        byte_00D7
;   $004CD3   WORD       50%     1    1        word_4CD3
;   $00C1C3   ARRAY      75%     1    0 I      arr_C1C3 [elem=1]
;   $00CFCE   ARRAY      75%     1    0 I      arr_CFCE [elem=1]
;   $00001F   FLAG       70%     4    0        flag_001F
;   $00C1C5   ARRAY      75%     1    0 I      arr_C1C5 [elem=1]
;   $00CFD3   ARRAY      75%     1    0 I      arr_CFD3 [elem=1]
;   $0000D4   ARRAY      75%     2    1 I      arr_00D4 [elem=1]
;   $00C5D7   ARRAY      75%     1    0 I      arr_C5D7 [elem=1]
;   $00C030   WORD       90%     9    0        word_C030
;   $004DB9   WORD       80%     4    1        word_4DB9
;   $004DB7   WORD       50%     2    0        word_4DB7
;   $004D00   STRUCT     75%     0    0        struct_4D00 {size=186}
;   $00D0CA   WORD       50%     2    0        word_D0CA
;   $00302C   ARRAY      80%     2    0 I      arr_302C [elem=1]
;   $00CA4D   ARRAY      80%     2    0 I      arr_CA4D [elem=1]
;   $004DB8   WORD       50%     2    0        word_4DB8
;   $000096   BYTE       90%     4    3        byte_0096
;   $004E61   ARRAY      85%     3    1 I      arr_4E61 [elem=1]
;   $004E00   STRUCT     70%     0    0        struct_4E00 {size=98}
;   $00C000   STRUCT     70%     3    0        struct_C000 {size=17}
;   $00C010   WORD       60%     3    0        word_C010
;   $000700   STRUCT     70%     1    1        struct_0700 {size=129}
;   $000680   WORD       50%     1    1        word_0680
;   $000600   STRUCT     70%     1    1        struct_0600 {size=129}
;   $000580   WORD       50%     1    1        word_0580
;   $000500   STRUCT     70%     1    1        struct_0500 {size=129}
;   $000480   WORD       50%     1    1        word_0480
;   $000400   STRUCT     70%     1    0        struct_0400 {size=129}

; ============================================================================
; SWITCH/CASE DETECTION REPORT
; ============================================================================
;
; Switches found:   4
;   Jump tables:    4
;   CMP chains:     0
;   Computed:       0
; Total cases:      0
; Max cases/switch: 0
;
; Detected Switches:
;
; Switch #1 at $004148:
;   Type:       jump_table
;   Table:      $003E1F
;   Index Reg:  X
;   Cases:      0
;
; Switch #2 at $0041A5:
;   Type:       jump_table
;   Table:      $001071
;   Index Reg:  X
;   Cases:      0
;
; Switch #3 at $00420C:
;   Type:       jump_table
;   Table:      $00781F
;   Index Reg:  X
;   Cases:      0
;
; Switch #4 at $00426B:
;   Type:       jump_table
;   Table:      $007F7F
;   Index Reg:  X
;   Cases:      0

; Cross-Reference Report
; ======================
; Total references: 426
;   Calls: 66  Jumps: 55  Branches: 202  Data: 102
;
; Target Address  Type     From Address
; -------------- -------- --------------
; $0001C9         JUMP     $004C79
;
; $000230         CALL     $004A22
;
; $000400         WRITE    $004ECF
; $000400         READ     $004EC9
;
; $000480         READ     $004EC3
; $000480         WRITE    $004ECC
;
; $000500         WRITE    $004EC6
; $000500         READ     $004EBD
;
; $000580         WRITE    $004EC0
; $000580         READ     $004EB7
;
; $000600         WRITE    $004EBA
; $000600         READ     $004EB1
;
; $000680         READ     $004EAB
; $000680         WRITE    $004EB4
;
; $000700         WRITE    $004EAE
; $000700         READ     $004EA5
;
; $000780         WRITE    $004EA8
;
; $00088F         WRITE    $004A6F
; $00088F         READ     $004A69
;
; $00090F         WRITE    $004A72
; $00090F         READ     $004A6C
;
; $000916         WRITE    $004AA9
; $000916         READ     $004AA3
;
; $000917         READ     $004A97
; $000917         WRITE    $004A9D
;
; $00093E         WRITE    $004AB6
; $00093E         READ     $004AB0
;
; $00093F         WRITE    $004ABF
; $00093F         READ     $004AB9
;
; $00098C         WRITE    $004A86
; $00098C         READ     $004A80
;
; $000996         READ     $004AA6
; $000996         WRITE    $004AAC
;
; $000997         WRITE    $004AA0
; $000997         READ     $004A9A
;
; $0009BE         WRITE    $004AC8
; $0009BE         READ     $004AC2
;
; $0009BF         READ     $004ACB
; $0009BF         WRITE    $004AD1
;
; $000A0C         WRITE    $004A89
; $000A0C         READ     $004A83
;
; $000BBE         WRITE    $004AE8
; $000BBE         READ     $004AE3
;
; $000BBF         WRITE    $004B01
; $000BBF         READ     $004AFC
;
; $000C3E         READ     $004AEB
; $000C3E         WRITE    $004AF0
;
; $000C3F         READ     $004B04
; $000C3F         WRITE    $004B09
;
; $000CBE         READ     $004AF3
; $000CBE         WRITE    $004AF8
;
; $000CBF         READ     $004B0C
; $000CBF         WRITE    $004B11
;
; $000DBE         READ     $004B15
; $000DBE         WRITE    $004B1A
;
; $000DBF         WRITE    $004B33
; $000DBF         READ     $004B2E
;
; $000E3E         WRITE    $004B22
; $000E3E         READ     $004B1D
;
; $000E3F         WRITE    $004B3B
; $000E3F         READ     $004B36
;
; $000EBE         WRITE    $004B2A
; $000EBE         READ     $004B25
;
; $000EBF         WRITE    $004B43
; $000EBF         READ     $004B3E
;
; $001071         INDIRECT  $0041A5
;
; $002020         CALL     $004564
; $002020         CALL     $004561
;
; $002824         CALL     $0043C0
;
; $003002         CALL     $0042DA
;
; $0041C0         BRANCH   $0041AE
;
; $0041F6         BRANCH   $0041F4
;
; $004213         BRANCH   $0041A1
;
; $004216         BRANCH   $0041A3
;
; $004225         BRANCH   $0041B3
;
; $00426B         BRANCH   $0042E7
;
; $00428B         BRANCH   $004309
;
; $00428D         BRANCH   $00430B
;
; $00428F         BRANCH   $00430D
;
; $00429A         BRANCH   $004295
;
; $00429B         BRANCH   $004319
;
; $00429D         BRANCH   $00431B
;
; $00429F         BRANCH   $00431D
;
; $0042A3         BRANCH   $0042F9
;
; $0042AB         BRANCH   $004329
;
; $0042AD         BRANCH   $00432B
;
; $0042AF         BRANCH   $00432D
;
; $0042BB         BRANCH   $004339
;
; $0042BD         BRANCH   $00433B
;
; $0042BF         BRANCH   $00433D
;
; $004311         BRANCH   $00430F
;
; $004321         BRANCH   $00431F
;
; $004331         BRANCH   $00432F
;
; $00435A         BRANCH   $004388
;
; $00435C         BRANCH   $00438A
;
; $00435E         BRANCH   $00438C
;
; $004360         BRANCH   $00438E
;
; $004369         BRANCH   $00433F
;
; $00436A         BRANCH   $004398
;
; $00436C         BRANCH   $00439A
;
; ... and 326 more references

; Stack Depth Analysis Report
; ===========================
; Entry depth: 0
; Current depth: -78
; Min depth: -139 (locals space: 139 bytes)
; Max depth: 0
;
; Stack Operations:
;   Push: 33  Pull: 53
;   JSR/JSL: 66  RTS/RTL: 95
;
; WARNING: Stack imbalance detected at $004102
;   Entry depth: 0, Return depth: -78
;
; Inferred Local Variables:
;   Stack frame size: 139 bytes
;   Offsets: S+$01 through S+$8B

; === Hardware Context Analysis ===
; Total I/O reads:  11
; Total I/O writes: 0
;
; Subsystem Access Counts:
;   Speaker         : 11
;
; Final Video Mode: TEXT40
; Memory State: 80STORE=0 RAMRD=0 RAMWRT=0 ALTZP=0 LC_BANK=2 LC_RD=0 LC_WR=0
; Speed Mode: Normal (1 MHz)
;
; Detected Hardware Patterns:
;   - Speaker toggle detected (11 accesses)

; Disassembly generated by DeAsmIIgs v2.0.0
; Source: D:\Projects\rosetta_v2\archaeology\games\rpg\u3p_dsk1\extracted\GAME\SUBS#064100
; Base address: $004100
; Size: 3584 bytes
; Analysis: 0 functions, 6 call sites, 12 liveness, stack: +0 max

        ; Emulation mode

; === Analysis Summary ===
; Basic blocks: 56
; CFG edges: 240
; Loops detected: 61
; Patterns matched: 312
; Branch targets: 141
; Functions: 12
; Call edges: 40
;
; Loops:
;   $004861: while loop
;   $004785: while loop
;   $00476F: while loop
;   $004732: while loop
;   $004738: while loop
;   $0048AE: while loop
;   $004738: while loop
;   $004885: while loop
;   $004885: while loop
;   $0047BF: while loop
;   $0047D9: while loop
;   $0047FA: while loop
;   $00482D: while loop
;   $004893: while loop
;   $004893: while loop
;   $004935: while loop
;   $004970: while loop
;   $00496B: while loop
;   $004E48: while loop
;   $004E53: while loop
;   $004A04: while loop
;   $0048D9: while loop
;   $0048E4: while loop
;   $0048D9: while loop
;   $0048D9: while loop
;   $0048D9: while loop
;   $0048D9: while loop
;   $004732: while loop
;   $004BCA: while loop
;   $004BE4: while loop
;   $004BCA: while loop
;   $004893: while loop
;   $004C00: while loop
;   $004732: while loop
;   $004732: while loop
;   $004732: while loop
;   $004732: while loop
;   $004732: while loop
;   $0049FF: while loop
;   $004C46: while loop
;   $004E35: loop
;   $004E2F: while loop
;   $004E0D: loop
;   $004E07: while loop
;   $004D54: while loop
;   $004D6D: loop
;   $004D76: loop
;   $004D6A: while loop
;   $004D65: while loop
;   $004D95: loop
;   $004D9E: loop
;   $004D92: while loop
;   $004D8D: while loop
;   $004DEC: loop
;   $004DEC: while loop
;   $004DDB: while loop
;   $004DDB: while loop
;   $004DC8: loop
;   $004DC0: while loop
;   $004D48: loop
;   $004D3A: loop
;
; Pattern summary:
;   GS/OS calls: 9
;
; Call graph:
;   $004100: 0 caller(s)
;   $004732: 6 caller(s)
;   $004767: 1 caller(s)
;   $004855: 10 caller(s)
;   $00487B: 1 caller(s)
;   $004893: 4 caller(s)
;   $0048D9: 4 caller(s)
;   $0048FF: 1 caller(s)
;   $004935: 1 caller(s)
;   $0049FF: 1 caller(s)
;   $004BCA: 2 caller(s)
;   $004E40: 4 caller(s)
;

; ===========================================================================
; Forward references — labels at mid-instruction addresses
; ===========================================================================

; NOTE: plot_char_smc_page enters mid-instruction — alternate decode: SBC ... / CLC / LDA $48BF
plot_char_smc_page EQU $48C0

; NOTE: plot_char_smc_lo enters mid-instruction — alternate decode: SBC ... / LDA ... / STA $48BF
plot_char_smc_lo EQU $48C2

; NOTE: plot_char_smc_hi enters mid-instruction — alternate decode: SBC ... / PHA / ADC #$80
plot_char_smc_hi EQU $48C3

; NOTE: text_scroll_entry enters mid-instruction — alternate decode: BPL $4BBA / CLC / LDA $FE
text_scroll_entry EQU $4BB3

; (4 forward-reference equates, 4 with alternate decode notes)

            ORG  $4100


; FUNC $004100: register -> A:X [I]
; Proto: uint32_t func_004100(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Liveness: params(A,X,Y) returns(A,X,Y)
; LUMA: int_brk
            brk  #$00            ; [SP-3]
            DB      $60
zp_init_2  ora  ($60,X)         ; [SP-1]
            ora  ($60,X)         ; [SP-1]
            ora  ($40,X)         ; [SP-1]
; LUMA: int_brk
            brk  #$78            ; [SP-4]

; ---
            DB      $07,$74,$0B,$64,$09,$44,$08,$68,$11,$70,$21,$30,$03,$10,$02,$10
            DB      $02,$18,$06,$00,$00,$00,$00,$60
; ---

zp_init_3  ora  ($61),Y         ; [SP-17]
            ora  ($61),Y         ; [SP-17]
            ora  ($41),Y         ; [SP-17]
            php                  ; [SP-18]
            DB      $7F
            DB      $07
            bvs  $4131           ; [SP-18]
            DB      $60
zp_init_4  ora  ($40,X)         ; [SP-16]
; LUMA: int_brk
            brk  #$60            ; [SP-19]
            DB      $01,$60
gfx_params_1
            DB      $0F
            bpl  gfx_stub_rts      ; [SP-19]
            php                  ; [SP-19]

; ---
            DB      $08,$04,$18,$03,$00,$00,$00
; ---

gfx_stub_rts  rts                  ; [SP-21]
            DB      $03,$60
gfx_params_2
            DB      $03
; LUMA: epilogue_rts
            rts                  ; [SP-21]

; --- Data region (62 bytes) ---
            DB      $03,$40,$01,$7C,$1F,$3E,$3E,$37,$76,$63,$63,$43,$61,$43,$61,$60
            DB      $03,$70,$07,$30,$06,$30,$06,$30,$06,$38,$0E,$20,$05,$60
sprite_data_1
            DB      $07
            DB      $22
            DB      $05 ; string length
            DB      "g7b6B"
            DB      $33,$72,$3F,$7A,$1F,$5A,$03,$4E,$03,$66,$07,$62,$0F,$72,$0C,$32
            DB      $0C,$32,$1C,$3A,$00,$00,$00,$60
; --- End data region (62 bytes) ---

sprite_data_2  ora  ($66,X)         ; [SP-25]
            ora  $1162,Y         ; [SP-25]
            DB      $42
            bpl  $4209           ; [SP-25]
            DB      $1F,$70,$03,$60
sprite_data_3  ora  ($40,X)         ; [SP-25]
; LUMA: int_brk
            brk  #$60            ; [SP-28]
            DB      $01,$60
sprite_data_4  ora  ($30,X)         ; [SP-28]
            DB      $03
            bpl  $419C           ; [SP-28]

; --- Data region (120 bytes) ---
            DB      $10,$02,$18,$06,$00,$00,$00,$10,$70,$10,$71,$7C,$71,$10,$21,$10
            DB      $7F,$13,$78,$3D,$70,$10,$20,$10,$70,$10,$70,$00,$58,$01,$08,$01
            DB      $08,$01,$0C,$03,$00,$00,$02,$00,$42,$03,$42,$03,$42,$03,$02,$01
            DB      $76,$0F,$6A,$17,$42,$23,$02,$21,$42,$23,$42,$03,$62,$06,$20,$04
            DB      $20,$04,$30,$0C,$00,$00,$00,$00,$71,$00,$71,$00,$71,$00,$22,$00
            DB      $7C,$03,$78,$05,$70,$04,$20,$7E,$70,$04,$70,$00,$58,$01,$04,$01
            DB      $02,$01,$03,$03,$00,$00,$00,$00,$10,$04,$70,$07,$66,$33,$66,$33
            DB      $46,$31,$7C,$1F,$78,$0F,$60
sprite_data_5
            DB      $03
; --- End data region (120 bytes) ---

; LUMA: epilogue_rts
            rts                  ; [SP-60]

; --- Data region (77 bytes) ---
            DB      $03,$70,$07,$30,$06,$30,$06,$30,$06,$38,$0E,$00,$00,$00,$00,$40
            DB      $03,$40,$03,$40,$03,$00,$01,$70,$0F,$08,$11,$64,$27,$02,$41,$40
            DB      $03,$00,$01,$40,$03,$20,$04,$20,$04,$20,$04,$30,$0C,$60
sprite_data_6
            DB      $03
            DB      $27
            DB      $02,$67,$03,$62,$03,$4F,$01,$7F,$1F,$7A,$3F,$72,$77,$62,$63,$60
            DB      $63,$70,$27,$78,$0F,$38,$0E,$18,$0C,$1C,$1C,$1C,$1C
; --- End data region (77 bytes) ---

sprite_data_7  bpl  sprite_data_8     ; [SP-62]

; --- Data region (34 bytes) ---
            DB      $72
            DB      $27
            DB      $57,$75
sprite_data_8
            DB      $27
            DB      $72
            DB      $4F,$79,$1F,$7C,$7F,$7F,$77,$77,$73,$67,$63,$63,$43,$61,$61,$43
            DB      $11,$44,$08,$08,$1C,$1C,$14,$14,$00,$00,$60
sprite_data_9
            DB      $03
; --- End data region (34 bytes) ---

; LUMA: int_disable
            sei                  ; [SP-67]

; ---
            DB      $0F,$4C,$19,$6E,$3D,$7E,$3F,$3C,$1E,$1C,$1C,$38,$0E,$0C,$18,$06
            DB      $30,$03,$60
; ---

sprite_data_10  asl  $30             ; [SP-65]
            DB      $0C
            clc                  ; [SP-65]
            clc                  ; [SP-65]

; ---
            DB      $0C,$00,$00,$00,$00,$00,$00,$0C,$00,$0F,$7E,$5C,$3F,$7E,$1F,$70
            DB      $07,$70,$01,$60
sprite_data_11
            DB      $03
; ---

; LUMA: epilogue_rts
            rts                  ; [SP-71]

; --- Data region (1151 bytes) ---
            DB      $07,$16,$1E,$0C,$30,$46,$31,$00,$1B,$00,$0E,$00,$00,$00,$00,$24
            DB      $12,$6E,$3B,$6F,$7B,$4F,$79,$7F,$7F,$7F,$7F,$6F,$7B,$6F,$7B,$47
            DB      $71,$67,$73,$63,$63,$21,$42,$20,$02,$30,$06,$00,$00,$82,$C0,$A0
            DB      $85,$A8,$95,$8A,$D0,$82,$C0,$A0,$C1,$A8,$C5,$8A,$C4,$82,$C4,$A2
            DB      $C4,$A2,$C5,$82,$C1,$8A,$D0,$A8,$95,$A0,$85,$82,$C0,$00,$00,$00
            DS      5
            DB      $80,$80,$80,$80,$80,$80,$80,$80,$00,$00,$00,$00,$00,$00,$00,$00
            DB      $80,$80,$80,$80,$80,$80,$80,$80,$00,$00,$00,$00,$00,$00,$00,$00
            DB      $80,$80,$80,$80,$80,$80,$80,$80,$00,$00,$00,$00,$00,$00,$00,$00
            DB      $80,$80,$80,$80,$80,$80,$80,$80,$28,$28,$28,$28,$28,$28,$28,$28
            DB      $A8,$A8,$A8,$A8,$A8,$A8,$A8,$A8,$28,$28,$28,$28,$28,$28,$28,$28
            DB      $A8,$A8,$A8,$A8,$A8,$A8,$A8,$A8,$28,$28,$28,$28,$28,$28,$28,$28
            DB      $A8,$A8,$A8,$A8,$A8,$A8,$A8,$A8,$28,$28,$28,$28,$28,$28,$28,$28
            DB      $A8,$A8,$A8,$A8,$A8,$A8,$A8,$A8,$50,$50,$50,$50,$50,$50,$50,$50
            DB      $D0,$D0,$D0,$D0,$D0,$D0,$D0,$D0,$50,$50,$50,$50,$50,$50,$50,$50
            DB      $D0,$D0,$D0,$D0,$D0,$D0,$D0,$D0,$50,$50,$50,$50,$50,$50,$50,$50
            DB      $D0,$D0,$D0,$D0,$D0,$D0,$D0,$D0,$50,$50,$50,$50,$50,$50,$50,$50
            DB      $D0,$D0,$D0,$D0,$D0,$D0,$D0,$D0,$20,$24,$28,$2C,$30,$34,$38,$3C
            DB      $20,$24,$28,$2C,$30,$34,$38,$3C,$21,$25,$29,$2D,$31,$35,$39,$3D
            DB      $21,$25,$29,$2D,$31,$35,$39,$3D,$22,$26,$2A,$2E,$32,$36,$3A,$3E
            DB      $22,$26,$2A,$2E,$32,$36,$3A,$3E,$23,$27,$2B,$2F,$33,$37,$3B,$3F
            DB      $23,$27,$2B,$2F,$33,$37,$3B,$3F,$20,$24,$28,$2C,$30,$34,$38,$3C
            DB      $20,$24,$28,$2C,$30,$34,$38,$3C,$21,$25,$29,$2D,$31,$35,$39,$3D
            DB      $21,$25,$29,$2D,$31,$35,$39,$3D,$22,$26,$2A,$2E,$32,$36,$3A,$3E
            DB      $22,$26,$2A,$2E,$32,$36,$3A,$3E,$23,$27,$2B,$2F,$33,$37,$3B,$3F
            DB      $23,$27,$2B,$2F,$33,$37,$3B,$3F,$20,$24,$28,$2C,$30,$34,$38,$3C
            DB      $20,$24,$28,$2C,$30,$34,$38,$3C,$21,$25,$29,$2D,$31,$35,$39,$3D
            DB      $21,$25,$29,$2D,$31,$35,$39,$3D,$22,$26,$2A,$2E,$32,$36,$3A,$3E
            DB      $22,$26,$2A,$2E,$32,$36,$3A,$3E,$23,$27,$2B,$2F,$33,$37,$3B,$3F
            DB      $23,$27,$2B,$2F,$33,$37,$3B,$3F,$00,$00,$00,$00,$00,$00,$00,$01
            DB      $01,$01,$01,$01,$01,$01,$02,$02,$02,$02,$02,$02,$02,$03,$03,$03
            DB      $03,$03,$03,$03,$04,$04,$04,$04,$04,$04,$04,$05,$05,$05,$05,$05
            DB      $05,$05,$06,$06,$06,$06,$06,$06,$06,$07,$07,$07,$07,$07,$07,$07
            DB      $08,$08,$08,$08,$08,$08,$08,$09,$09,$09,$09,$09,$09,$09,$0A,$0A
            DB      $0A,$0A,$0A,$0A,$0A,$0B,$0B,$0B,$0B,$0B,$0B,$0B,$0C,$0C,$0C,$0C
            DB      $0C,$0C,$0C,$0D,$0D,$0D,$0D,$0D,$0D,$0D,$0E,$0E,$0E,$0E,$0E,$0E
            DB      $0E,$0F,$0F,$0F,$0F,$0F,$0F,$0F,$10,$10,$10,$10,$10,$10,$10,$11
            DB      $11,$11,$11,$11,$11,$11,$12,$12,$12,$12,$12,$12,$12,$13,$13,$13
            DB      $13,$13,$13,$13,$14,$14,$14,$14,$14,$14,$14,$15,$15,$15,$15,$15
            DB      $15,$15,$16,$16,$16,$16,$16,$16,$16,$17,$17,$17,$17,$17,$17,$17
            DB      $18,$18,$18,$18,$18,$18,$18,$19,$19,$19,$19,$19,$19,$19,$1A,$1A
            DB      $1A,$1A,$1A,$1A,$1A,$1B,$1B,$1B,$1B,$1B,$1B,$1B,$1C,$1C,$1C,$1C
            DB      $1C,$1C,$1C,$1D,$1D,$1D,$1D,$1D,$1D,$1D,$1E,$1E,$1E,$1E,$1E,$1E
            DB      $1E,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$20,$20,$20,$20,$20,$20,$20,$21
            DB      $21,$21,$21,$21,$21,$21,$22,$22,$22,$22,$22,$22,$22,$23,$23,$23
            DB      $23,$23,$23,$23,$24,$24,$24,$24,$24,$24,$24,$25,$25,$25,$25,$25
            DB      $25,$25,$26,$26,$26,$26,$26,$26,$26,$27,$27,$27,$27,$27,$27,$27
            DB      $28,$28,$28,$28,$28,$28,$28,$01,$02,$04,$08,$10,$20,$40,$01,$02
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
            DB      $08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10
            DB      $20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40
            DB      $01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02
            DB      $04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08
            DB      $10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20
            DB      $40,$01,$02,$04,$08,$10,$20,$40,$01,$02,$04,$08,$10,$20,$40,$4C
            DB      $11 ; string length
            DB      $47,$4C,$32,$47,$4C,$67,$47,$4C,$B8,$47,$4C,$39,$48,$4C,$54,$48,$4C
            DB      $7B,$48,$4C,$93,$48,$4C,$D9,$48,$4C,$0D,$49,$4C,$16,$49,$4C,$35
            DB      $49,$4C,$55,$49,$4C,$68,$49,$4C,$7B,$49,$4C,$FF,$49,$4C,$40,$4E
            DB      $4C,$13,$4A,$4C,$26,$4A,$4C,$48,$4B,$4C,$C3,$4B,$4C,$CA,$4B,$4C
            DB      $DB,$4B,$4C,$16,$4C,$4C,$21,$4C,$4C,$D4,$4C,$4C,$E8,$4C,$4C,$71
            DB      $4E,$4C,$A2,$4E,$4C,$52,$4A,$68,$85,$FE,$68,$85,$FF,$A0,$00,$E6
            DB      $FE,$D0,$02,$E6,$FF,$B1,$FE,$F0,$08,$09,$80,$20,$ED,$FD,$4C,$19
            DB      $47,$A5,$FF,$48,$A5,$FE,$48,$60
; --- End data region (1151 bytes) ---


; ===========================================================================
; COMPUTATION (8 functions)
; ===========================================================================

; ---------------------------------------------------------------------------
; print_inline_str  [5 calls, 2 jumps]
;   Called by: text_wind_show, text_mode_1, text_mode_2, text_mode_3, scroll_text_col
;   Calls: plot_char_glyph, scroll_text_up
; ---------------------------------------------------------------------------

; FUNC $004732: register -> A:X []
; Proto: uint32_t func_004732(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [2 dead stores]
; XREF: 7 refs (5 calls) (2 jumps) from $0046BA, text_wind_show, text_mode_1, text_mode_2, text_mode_3, ...
print_inline_str     pla                  ; A=[stk] ; [SP-12]
            sta  $FE             ; A=[stk] ; [SP-12]
            pla                  ; A=[stk] ; [SP-11]
            sta  $FF             ; A=[stk] ; [SP-11]

; === while loop starts here [nest:7] ===
; XREF: 2 refs (2 jumps) from print_str_fetch, print_str_newline
print_str_loop  ldy  #$00            ; A=[stk] Y=$0000 ; [SP-11]
            inc  $FE             ; A=[stk] Y=$0000 ; [SP-11]
            bne  print_str_fetch      ; A=[stk] Y=$0000 ; [SP-11]
            inc  $FF             ; A=[stk] Y=$0000 ; [SP-11]
; LUMA: data_ptr_offset
; XREF: 1 ref (1 branch) from print_str_loop
print_str_fetch  lda  ($FE),Y         ; A=[stk] Y=$0000 ; [SP-11]
            beq  print_str_done      ; A=[stk] Y=$0000 ; [SP-11]
            cmp  #$FF            ; A=[stk] Y=$0000 ; [SP-11]
            beq  print_str_newline      ; A=[stk] Y=$0000 ; [SP-11]
            and  #$7F            ; A=A&$7F Y=$0000 ; [SP-11]
            jsr  plot_char_glyph       ; A=A&$7F Y=$0000 ; [SP-13]
            inc  $F9             ; A=A&$7F Y=$0000 ; [SP-13]
            jmp  print_str_loop      ; A=A&$7F Y=$0000 ; [SP-13]
; === End of while loop ===

; XREF: 1 ref (1 branch) from print_str_fetch
print_str_newline  jsr  scroll_text_up          ; A=A&$7F Y=$0000 ; [SP-15]
            lda  #$18            ; A=$0018 Y=$0000 ; [SP-15]
            sta  $F9             ; A=$0018 Y=$0000 ; [SP-15]
            lda  #$17            ; A=$0017 Y=$0000 ; [SP-15]
            sta  $FA             ; A=$0017 Y=$0000 ; [SP-15]
            jmp  print_str_loop      ; A=$0017 Y=$0000 ; [SP-15]
; === End of while loop ===

; XREF: 1 ref (1 branch) from print_str_fetch
print_str_done  lda  $FF             ; A=[$00FF] Y=$0000 ; [SP-15]
            pha                  ; A=[$00FF] Y=$0000 ; [SP-16]
            lda  $FE             ; A=[$00FE] Y=$0000 ; [SP-16]
            pha                  ; A=[$00FE] Y=$0000 ; [SP-17]
; LUMA: epilogue_rts
            rts                  ; A=[$00FE] Y=$0000 ; [SP-15]

; ---------------------------------------------------------------------------
; scroll_text_up  [1 call, 1 jump]
;   Called by: print_str_newline
;   Calls: print_inline_str
; ---------------------------------------------------------------------------

; FUNC $004767: register -> A:X []
; Liveness: returns(A,X,Y) [9 dead stores]
; XREF: 2 refs (1 call) (1 jump) from print_str_newline, $0046BD
scroll_text_up      lda  $FF             ; A=[$00FF] Y=$0000 ; [SP-15]
            pha                  ; A=[$00FF] Y=$0000 ; [SP-16]
            lda  $FE             ; A=[$00FE] Y=$0000 ; [SP-16]
            pha                  ; A=[$00FE] Y=$0000 ; [SP-17]
            ldx  #$88            ; A=[$00FE] X=$0088 Y=$0000 ; [SP-17]

; === while loop starts here (counter: X 'iter_x', range: 0..184, iters: 184) [nest:7] ===
; XREF: 1 ref (1 branch) from scroll_text_col
scroll_text_row   ldy  #$18            ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
; LUMA: data_array_x
            lda  $4300,X         ; -> $4388 ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
            sta  $FE             ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
; LUMA: data_array_x
            lda  $43C0,X         ; -> $4448 ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
            sta  $FF             ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
; LUMA: data_array_x
            lda  $4308,X         ; -> $4390 ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
            sta  $FC             ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
            lda  $43C8,X         ; -> $4450 ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
            sta  $FD             ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]

; === while loop starts here (counter: Y 'iter_y', range: 0..40, iters: 40) [nest:8] ===
; LUMA: data_ptr_offset
; XREF: 1 ref (1 branch) from scroll_text_col
scroll_text_col   lda  ($FC),Y         ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
            sta  ($FE),Y         ; A=[$00FE] X=$0088 Y=$0018 ; [SP-17]
            iny                  ; A=[$00FE] X=$0088 Y=$0019 ; [SP-17]
            cpy  #$28            ; A=[$00FE] X=$0088 Y=$0019 ; [SP-17]
            bcc  scroll_text_col       ; A=[$00FE] X=$0088 Y=$0019 ; [SP-17]
; === End of while loop (counter: Y) ===

            inx                  ; A=[$00FE] X=$0089 Y=$0019 ; [SP-17]
            cpx  #$B8            ; A=[$00FE] X=$0089 Y=$0019 ; [SP-17]
            bcc  scroll_text_row       ; A=[$00FE] X=$0089 Y=$0019 ; [SP-17]
; === End of while loop (counter: X) ===

            lda  #$18            ; A=$0018 X=$0089 Y=$0019 ; [SP-17]
            sta  $F9             ; A=$0018 X=$0089 Y=$0019 ; [SP-17]
            lda  #$17            ; A=$0017 X=$0089 Y=$0019 ; [SP-17]
            sta  $FA             ; A=$0017 X=$0089 Y=$0019 ; [SP-17]
            jsr  print_inline_str         ; A=$0017 X=$0089 Y=$0019 ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDY: same value loaded at $00479E ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDY: same value loaded at $0047A0 ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDY: same value loaded at $0047A2 ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDY: same value loaded at $0047A4 ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDY: same value loaded at $0047A6 ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDY: same value loaded at $0047A8 ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDY: same value loaded at $0047AA ; [SP-19]
            ldy  #$A0            ; A=$0017 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDY: same value loaded at $0047AC ; [SP-19]
; LUMA: int_brk
            brk  #$68            ; A=$0017 X=$0089 Y=$00A0 ; [SP-22]

; ---------------------------------------------------------------------------
; save_text_ptr
; ---------------------------------------------------------------------------
save_text_ptr  sta  $FE             ; A=$0017 X=$0089 Y=$00A0 ; [SP-22]
            pla                  ; A=[stk] X=$0089 Y=$00A0 ; [SP-21]
            sta  $FF             ; A=[stk] X=$0089 Y=$00A0 ; [SP-21]
; LUMA: epilogue_rts
            rts                  ; A=[stk] X=$0089 Y=$00A0 ; [SP-19]
; XREF: 1 ref (1 jump) from $0046C0
draw_border_init   jsr  clear_hgr_page       ; A=[stk] X=$0089 Y=$00A0 ; [SP-21]
            lda  #$00            ; A=$0000 X=$0089 Y=$00A0 ; [SP-21]
            sta  $F2             ; A=$0000 X=$0089 Y=$00A0 ; [SP-21]

; === while loop starts here [nest:6] ===
; XREF: 1 ref (1 branch) from draw_border_horiz
draw_border_horiz   lda  #$00            ; A=$0000 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDA: same value loaded at $0047BB ; [SP-21]
            sta  $F1             ; A=$0000 X=$0089 Y=$00A0 ; [SP-21]
            jsr  draw_hgr_stripe      ; A=$0000 X=$0089 Y=$00A0 ; [SP-23]
            lda  #$17            ; A=$0017 X=$0089 Y=$00A0 ; [SP-23]
            sta  $F1             ; A=$0017 X=$0089 Y=$00A0 ; [SP-23]
            jsr  draw_hgr_stripe      ; A=$0017 X=$0089 Y=$00A0 ; [SP-25]
            inc  $F2             ; A=$0017 X=$0089 Y=$00A0 ; [SP-25]
            lda  $F2             ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-25]
            cmp  #$18            ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-25]
            bcc  draw_border_horiz       ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-25]
; === End of while loop ===

            lda  #$00            ; A=$0000 X=$0089 Y=$00A0 ; [SP-25]
            sta  $F1             ; A=$0000 X=$0089 Y=$00A0 ; [SP-25]

; === while loop starts here [nest:6] ===
; XREF: 1 ref (1 branch) from draw_border_vert
draw_border_vert   lda  #$00            ; A=$0000 X=$0089 Y=$00A0 ; [OPT] REDUNDANT_LOAD: Redundant LDA: same value loaded at $0047D5 ; [SP-25]
            sta  $F2             ; A=$0000 X=$0089 Y=$00A0 ; [SP-25]
            jsr  draw_hgr_stripe      ; A=$0000 X=$0089 Y=$00A0 ; [SP-27]
            nop                  ; A=$0000 X=$0089 Y=$00A0 ; [SP-27]
            nop                  ; A=$0000 X=$0089 Y=$00A0 ; [SP-27]
            nop                  ; A=$0000 X=$0089 Y=$00A0 ; [SP-27]
            nop                  ; A=$0000 X=$0089 Y=$00A0 ; [SP-27]
            nop                  ; A=$0000 X=$0089 Y=$00A0 ; [SP-27]
            nop                  ; A=$0000 X=$0089 Y=$00A0 ; [SP-27]
            nop                  ; A=$0000 X=$0089 Y=$00A0 ; [SP-27]
            lda  #$17            ; A=$0017 X=$0089 Y=$00A0 ; [SP-27]
            sta  $F2             ; A=$0017 X=$0089 Y=$00A0 ; [SP-27]
            jsr  draw_hgr_stripe      ; A=$0017 X=$0089 Y=$00A0 ; [SP-29]
            inc  $F1             ; A=$0017 X=$0089 Y=$00A0 ; [SP-29]
            lda  $F1             ; A=[$00F1] X=$0089 Y=$00A0 ; [SP-29]
            cmp  #$17            ; A=[$00F1] X=$0089 Y=$00A0 ; [SP-29]
            bcc  draw_border_vert       ; A=[$00F1] X=$0089 Y=$00A0 ; [SP-29]
; === End of while loop ===

            lda  #$17            ; A=$0017 X=$0089 Y=$00A0 ; [SP-29]
            sta  $F1             ; A=$0017 X=$0089 Y=$00A0 ; [SP-29]

; === while loop starts here [nest:6] ===
; XREF: 1 ref (1 branch) from draw_border_bottom
draw_border_bottom   lda  #$00            ; A=$0000 X=$0089 Y=$00A0 ; [SP-29]
            sta  $F2             ; A=$0000 X=$0089 Y=$00A0 ; [SP-29]
            jsr  draw_hgr_stripe      ; A=$0000 X=$0089 Y=$00A0 ; [SP-31]
            lda  #$04            ; A=$0004 X=$0089 Y=$00A0 ; [SP-31]
            sta  $F2             ; A=$0004 X=$0089 Y=$00A0 ; [SP-31]
            jsr  draw_hgr_stripe      ; A=$0004 X=$0089 Y=$00A0 ; [SP-33]
            lda  #$08            ; A=$0008 X=$0089 Y=$00A0 ; [SP-33]
            sta  $F2             ; A=$0008 X=$0089 Y=$00A0 ; [SP-33]
            jsr  draw_hgr_stripe      ; A=$0008 X=$0089 Y=$00A0 ; [SP-35]
            lda  #$0C            ; A=$000C X=$0089 Y=$00A0 ; [SP-35]
            sta  $F2             ; A=$000C X=$0089 Y=$00A0 ; [SP-35]
            jsr  draw_hgr_stripe      ; A=$000C X=$0089 Y=$00A0 ; [SP-37]
            lda  #$10            ; A=$0010 X=$0089 Y=$00A0 ; [SP-37]
            sta  $F2             ; A=$0010 X=$0089 Y=$00A0 ; [SP-37]
            jsr  draw_hgr_stripe      ; A=$0010 X=$0089 Y=$00A0 ; [SP-39]
            inc  $F1             ; A=$0010 X=$0089 Y=$00A0 ; [SP-39]
            lda  $F1             ; A=[$00F1] X=$0089 Y=$00A0 ; [SP-39]
            cmp  #$28            ; A=[$00F1] X=$0089 Y=$00A0 ; [SP-39]
            bcc  draw_border_bottom       ; A=[$00F1] X=$0089 Y=$00A0 ; [SP-39]
            lda  #$00            ; A=$0000 X=$0089 Y=$00A0 ; [SP-39]
            sta  $F2             ; A=$0000 X=$0089 Y=$00A0 ; [SP-39]
            lda  #$27            ; A=$0027 X=$0089 Y=$00A0 ; [SP-39]
            sta  $F1             ; A=$0027 X=$0089 Y=$00A0 ; [SP-39]

; === while loop starts here [nest:6] ===
; XREF: 1 ref (1 branch) from draw_border_right
draw_border_right   jsr  draw_hgr_stripe      ; A=$0027 X=$0089 Y=$00A0 ; [SP-41]
            inc  $F2             ; A=$0027 X=$0089 Y=$00A0 ; [SP-41]
            lda  $F2             ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-41]
            cmp  #$11            ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-41]
            bcc  draw_border_right       ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-41]
; LUMA: epilogue_rts
            rts                  ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-39]

; ---
            DB      $A2,$08,$BD,$00,$43,$85,$FE,$BD,$C0,$43,$85,$FF,$A0,$16,$A9,$80
            DB      $91,$FE,$88,$D0,$FB,$E8,$E0,$B8,$90,$E8,$60
; ---

; LUMA: epilogue_rts
; XREF: 1 ref (1 jump) from $0046C6
draw_border_done   rts                  ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-35]

; ---------------------------------------------------------------------------
; draw_hgr_stripe  [10 calls]
;   Called by: draw_border_bottom, draw_border_vert, draw_border_horiz, draw_border_right
; ---------------------------------------------------------------------------

; FUNC $004855: register -> A:X [L]
; Proto: uint32_t func_004855(void);
; Liveness: returns(A,X,Y) [3 dead stores]
; XREF: 10 refs (10 calls) from draw_border_bottom, draw_border_vert, draw_border_bottom, draw_border_horiz, draw_border_vert, ...
draw_hgr_stripe  lda  #$08            ; A=$0008 X=$0089 Y=$00A0 ; [SP-35]
            sta  $F3             ; A=$0008 X=$0089 Y=$00A0 ; [SP-35]
            lda  $F2             ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-35]
            asl  a               ; A=[$00F2] X=$0089 Y=$00A0 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for calc_roster_ptr ; [SP-35]
            asl  a               ; A=[$00F2] X=$0089 Y=$00A0 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for calc_roster_ptr ; [SP-35]
            asl  a               ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-35]
            tax                  ; A=[$00F2] X=[$00F2] Y=$00A0 ; [SP-35]
            ldy  $F1             ; A=[$00F2] X=[$00F2] Y=$00A0 ; [SP-35]

; === while loop starts here (counter: X 'iter_x') [nest:6] ===
; LUMA: data_array_x
; XREF: 1 ref (1 branch) from draw_stripe_next
draw_stripe_row lda  $4300,X         ; A=[$00F2] X=[$00F2] Y=$00A0 ; [SP-35]
            sta  $FE             ; A=[$00F2] X=[$00F2] Y=$00A0 ; [SP-35]
; LUMA: data_array_x
            lda  $43C0,X         ; A=[$00F2] X=[$00F2] Y=$00A0 ; [SP-35]
            sta  $FF             ; A=[$00F2] X=[$00F2] Y=$00A0 ; [SP-35]
            tya                  ; A=$00A0 X=[$00F2] Y=$00A0 ; [SP-35]
            lsr  a               ; A=$00A0 X=[$00F2] Y=$00A0 ; [SP-35]
            lda  #$AA            ; A=$00AA X=[$00F2] Y=$00A0 ; [SP-35]
            bcs  draw_stripe_store   ; A=$00AA X=[$00F2] Y=$00A0 ; [SP-35]
            eor  #$7F            ; A=A^$7F X=[$00F2] Y=$00A0 ; [SP-35]
; XREF: 1 ref (1 branch) from draw_stripe_row
draw_stripe_store sta  ($FE),Y         ; A=A^$7F X=[$00F2] Y=$00A0 ; [SP-35]
            inx                  ; A=A^$7F X=X+$01 Y=$00A0 ; [SP-35]
            dec  $F3             ; A=A^$7F X=X+$01 Y=$00A0 ; [SP-35]
draw_stripe_next bne  draw_stripe_row   ; A=A^$7F X=X+$01 Y=$00A0 ; [SP-35]
; === End of while loop (counter: X) ===

; LUMA: epilogue_rts
            rts                  ; A=A^$7F X=X+$01 Y=$00A0 ; [SP-33]

; ---------------------------------------------------------------------------
; clear_hgr_page  [1 call, 1 jump]
;   Called by: draw_border_init
; ---------------------------------------------------------------------------

; FUNC $00487B: register -> A:X [I]
; Proto: uint32_t func_00487B(void);
; Liveness: returns(A,X,Y)
; XREF: 2 refs (1 call) (1 jump) from draw_border_init, $0046C9
clear_hgr_page   lda  #$20            ; A=$0020 X=X+$01 Y=$00A0 ; [SP-33]
            sta  $FF             ; A=$0020 X=X+$01 Y=$00A0 ; [SP-33]
            lda  #$00            ; A=$0000 X=X+$01 Y=$00A0 ; [SP-33]
            sta  $FE             ; A=$0000 X=X+$01 Y=$00A0 ; [SP-33]
            ldy  #$00            ; A=$0000 X=X+$01 Y=$0000 ; [SP-33]

; === while loop starts here (counter: Y 'iter_y') [nest:6] ===
; XREF: 2 refs (2 branches) from clear_hgr_loop, clear_hgr_loop
clear_hgr_loop sta  ($FE),Y         ; A=$0000 X=X+$01 Y=$0000 ; [SP-33]
            iny                  ; A=$0000 X=X+$01 Y=$0001 ; [SP-33]
            bne  clear_hgr_loop    ; A=$0000 X=X+$01 Y=$0001 ; [SP-33]
; === End of while loop (counter: Y) ===

            inc  $FF             ; A=$0000 X=X+$01 Y=$0001 ; [SP-33]
            ldx  $FF             ; A=$0000 X=X+$01 Y=$0001 ; [SP-33]
            cpx  #$40            ; A=$0000 X=X+$01 Y=$0001 ; [SP-33]
            bcc  clear_hgr_loop    ; A=$0000 X=X+$01 Y=$0001 ; [SP-33]
; === End of while loop (counter: Y) ===

; LUMA: epilogue_rts
            rts                  ; A=$0000 X=X+$01 Y=$0001 ; [SP-31]

; ---------------------------------------------------------------------------
; plot_char_glyph  [11 calls, 1 jump]
;   Called by: copy_plrs_byte, print_digit, rng_done, print_bcd_byte, print_str_fetch, print_name_loop
; ---------------------------------------------------------------------------

; FUNC $004893: register -> A:X [L]
; Proto: uint32_t func_004893(void);
; Liveness: returns(A,X,Y) [2 dead stores]
; XREF: 12 refs (11 calls) (1 jump) from copy_plrs_byte, copy_plrs_byte, print_digit, copy_plrs_byte, $0046CC, ...
plot_char_glyph   cmp  #$60            ; A=$0000 X=X+$01 Y=$0001 ; [SP-31]
            bcc  plot_char_clip    ; A=$0000 X=X+$01 Y=$0001 ; [SP-31]
            and  #$1F            ; A=A&$1F X=X+$01 Y=$0001 ; [SP-31]
; XREF: 1 ref (1 branch) from plot_char_glyph
plot_char_clip sta  $F0             ; A=A&$1F X=X+$01 Y=$0001 ; [SP-31]
            ldy  $F9             ; A=A&$1F X=X+$01 Y=$0001 ; [SP-31]
            ldx  $FA             ; A=A&$1F X=X+$01 Y=$0001 ; [SP-31]
            txa                  ; A=X X=X+$01 Y=$0001 ; [SP-31]
            asl  a               ; A=X X=X+$01 Y=$0001 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for calc_roster_ptr ; [SP-31]
            asl  a               ; A=X X=X+$01 Y=$0001 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for calc_roster_ptr ; [SP-31]
            asl  a               ; A=X X=X+$01 Y=$0001 ; [SP-31]
            sta  $F1             ; A=X X=X+$01 Y=$0001 ; [SP-31]
            lda  #$08            ; A=$0008 X=X+$01 Y=$0001 ; [SP-31]
            sta  $F3             ; A=$0008 X=X+$01 Y=$0001 ; [SP-31]
            lda  #$04            ; A=$0004 X=X+$01 Y=$0001 ; [SP-31]
            sta  plot_char_smc_page    ; A=$0004 X=X+$01 Y=$0001 ; [SP-31] ; WARNING: Self-modifying code -> plot_char_smc_page

; === while loop starts here [nest:9] ===
; XREF: 1 ref (1 branch) from plot_char_next
plot_char_row ldx  $F1             ; A=$0004 X=X+$01 Y=$0001 ; [SP-31]
; LUMA: data_array_x
            lda  $4300,X         ; A=$0004 X=X+$01 Y=$0001 ; [SP-31]
            sta  plot_char_smc_lo    ; A=$0004 X=X+$01 Y=$0001 ; [SP-31] ; WARNING: Self-modifying code -> plot_char_smc_lo
; LUMA: data_array_x
            lda  $43C0,X         ; A=$0004 X=X+$01 Y=$0001 ; [SP-31]
            sta  plot_char_smc_hi    ; A=$0004 X=X+$01 Y=$0001 ; [SP-31] ; WARNING: Self-modifying code -> plot_char_smc_hi
            ldx  $F0             ; A=$0004 X=X+$01 Y=$0001 ; [SP-31]
; LUMA: data_array_x
            lda  $FF00,X         ; A=$0004 X=X+$01 Y=$0001 ; [SP-31]
            sta  $FFFF,Y         ; -> $0000 ; A=$0004 X=X+$01 Y=$0001 ; [SP-31]
            clc                  ; A=$0004 X=X+$01 Y=$0001 ; [SP-31]
; LUMA: hw_keyboard_read
            lda  $48BF           ; A=[$48BF] X=X+$01 Y=$0001 ; [SP-31]
            adc  #$80            ; A=A+$80 X=X+$01 Y=$0001 ; [SP-31]
            sta  $48BF           ; A=A+$80 X=X+$01 Y=$0001 ; [SP-31] ; WARNING: Self-modifying code -> $48BF
            bcc  plot_char_next    ; A=A+$80 X=X+$01 Y=$0001 ; [SP-31]
            inc  plot_char_smc_page    ; A=A+$80 X=X+$01 Y=$0001 ; [SP-31]
; XREF: 1 ref (1 branch) from plot_char_smc_hi
plot_char_next inc  $F1             ; A=A+$80 X=X+$01 Y=$0001 ; [SP-31]
            dec  $F3             ; A=A+$80 X=X+$01 Y=$0001 ; [SP-31]
            bne  plot_char_row    ; A=A+$80 X=X+$01 Y=$0001 ; [SP-31]
; === End of while loop ===

; LUMA: epilogue_rts
            rts                  ; A=A+$80 X=X+$01 Y=$0001 ; [SP-29]

; ---------------------------------------------------------------------------
; swap_tile_frames  [4 calls, 1 jump, 1 branch]
;   Called by: anim_tiles_set2, anim_tiles_set3, animate_tiles
;   Calls: advance_ptr_128
; ---------------------------------------------------------------------------

; FUNC $0048D9: register -> A:X []
; Proto: uint32_t func_0048D9(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [3 dead stores]
; XREF: 6 refs (4 calls) (1 jump) (1 branch) from anim_tiles_set2, anim_tiles_set3, swap_tile_loop, animate_tiles, anim_tiles_set2, ...
swap_tile_frames lda  #$00            ; A=$0000 X=X+$01 Y=$0001 ; [SP-29]
            sta  $FE             ; A=$0000 X=X+$01 Y=$0001 ; [SP-29]
            lda  #$08            ; A=$0008 X=X+$01 Y=$0001 ; [SP-29]
            sta  $FF             ; A=$0008 X=X+$01 Y=$0001 ; [SP-29]
            ldx  $0F80,Y         ; -> $0F81 ; A=$0008 X=X+$01 Y=$0001 ; [SP-29]

; === while loop starts here [nest:14] ===
; XREF: 1 ref (1 branch) from swap_tile_loop
swap_tile_loop lda  ($FE),Y         ; A=$0008 X=X+$01 Y=$0001 ; [SP-29]
            pha                  ; A=$0008 X=X+$01 Y=$0001 ; [SP-30]
            txa                  ; A=X X=X+$01 Y=$0001 ; [SP-30]
            sta  ($FE),Y         ; A=X X=X+$01 Y=$0001 ; [SP-30]
            pla                  ; A=[stk] X=X+$01 Y=$0001 ; [SP-29]
            tax                  ; A=[stk] X=[stk] Y=$0001 ; [SP-29]
            jsr  advance_ptr_128      ; Call $0048FF(A)
            lda  $FF             ; A=[$00FF] X=[stk] Y=$0001 ; [SP-31]
            cmp  #$10            ; A=[$00FF] X=[stk] Y=$0001 ; [SP-31]
            bcc  swap_tile_loop  ; A=[$00FF] X=[stk] Y=$0001 ; [SP-31]
; === End of while loop ===

            txa                  ; A=[stk] X=[stk] Y=$0001 ; [SP-31]
            sta  $0800,Y         ; -> $0801 ; A=[stk] X=[stk] Y=$0001 ; [SP-31]
            iny                  ; A=[stk] X=[stk] Y=$0002 ; [SP-31]
            tya                  ; A=$0002 X=[stk] Y=$0002 ; [SP-31]
            lsr  a               ; A=$0002 X=[stk] Y=$0002 ; [SP-31]
            bcs  swap_tile_frames     ; A=$0002 X=[stk] Y=$0002 ; [SP-31]
; === End of while loop (counter: Y) ===

            rts                  ; A=$0002 X=[stk] Y=$0002 ; [SP-29]

; ---------------------------------------------------------------------------
; advance_ptr_128  [1 call]
;   Called by: swap_tile_loop
; ---------------------------------------------------------------------------

; FUNC $0048FF: register -> A:X []
; Proto: uint32_t func_0048FF(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [2 dead stores]
; XREF: 1 ref (1 call) from swap_tile_loop
advance_ptr_128  clc                  ; A=$0002 X=[stk] Y=$0002 ; [SP-29]
            lda  $FE             ; A=[$00FE] X=[stk] Y=$0002 ; [SP-29]
            adc  #$80            ; A=A+$80 X=[stk] Y=$0002 ; [SP-29]
            sta  $FE             ; A=A+$80 X=[stk] Y=$0002 ; [SP-29]
            lda  $FF             ; A=[$00FF] X=[stk] Y=$0002 ; [SP-29]
            adc  #$00            ; A=A X=[stk] Y=$0002 ; [SP-29]
            sta  $FF             ; A=A X=[stk] Y=$0002 ; [SP-29]
            rts                  ; A=A X=[stk] Y=$0002 ; [SP-27]

; ---------------------------------------------------------------------------
; print_digit  [1 jump]
;   Calls: plot_char_glyph
; ---------------------------------------------------------------------------
; XREF: 1 ref (1 jump) from $0046D2
print_digit  clc                  ; A=A X=[stk] Y=$0002 ; [SP-27]
            adc  #$30            ; A=A+$30 X=[stk] Y=$0002 ; [SP-27]
            jsr  plot_char_glyph       ; A=A+$30 X=[stk] Y=$0002 ; [SP-29]
            inc  $F9             ; A=A+$30 X=[stk] Y=$0002 ; [SP-29]
            rts                  ; A=A+$30 X=[stk] Y=$0002 ; [SP-27]
; XREF: 1 ref (1 jump) from $0046D5
print_bcd_byte sta  $4934           ; A=A+$30 X=[stk] Y=$0002 ; [SP-27]
            and  #$F0            ; A=A&$F0 X=[stk] Y=$0002 ; [SP-27]
            lsr  a               ; A=A&$F0 X=[stk] Y=$0002 ; [SP-27]
            lsr  a               ; A=A&$F0 X=[stk] Y=$0002 ; [SP-27]
            lsr  a               ; A=A&$F0 X=[stk] Y=$0002 ; [SP-27]
            lsr  a               ; A=A&$F0 X=[stk] Y=$0002 ; [SP-27]
            adc  #$30            ; A=A+$30 X=[stk] Y=$0002 ; [SP-27]
            jsr  plot_char_glyph       ; A=A+$30 X=[stk] Y=$0002 ; [SP-29]
            inc  $F9             ; A=A+$30 X=[stk] Y=$0002 ; [SP-29]
            lda  $4934           ; A=[$4934] X=[stk] Y=$0002 ; [SP-29]
            and  #$0F            ; A=A&$0F X=[stk] Y=$0002 ; [SP-29]
            clc                  ; A=A&$0F X=[stk] Y=$0002 ; [SP-29]
            adc  #$30            ; A=A+$30 X=[stk] Y=$0002 ; [SP-29]
            jsr  plot_char_glyph       ; A=A+$30 X=[stk] Y=$0002 ; [SP-31]
            inc  $F9             ; A=A+$30 X=[stk] Y=$0002 ; [SP-31]
            rts                  ; A=A+$30 X=[stk] Y=$0002 ; [SP-29]
            DB      $00

; ---------------------------------------------------------------------------
; calc_roster_ptr  [2 calls, 1 jump]
;   Called by: copy_roster_to_plrs, copy_plrs_slot
; ---------------------------------------------------------------------------

; FUNC $004935: register -> A:X [I]
; Proto: uint32_t func_004935(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [2 dead stores]
; XREF: 3 refs (2 calls) (1 jump) from copy_roster_to_plrs, $0046D8, copy_plrs_slot
calc_roster_ptr    lda  #$00            ; A=$0000 X=[stk] Y=$0002 ; [SP-32]
            sta  $FE             ; A=$0000 X=[stk] Y=$0002 ; [SP-35]
            lda  $E6,X           ; A=$0000 X=[stk] Y=$0002 ; [SP-35]
            sec                  ; A=$0000 X=[stk] Y=$0002 ; [SP-35]
            sbc  #$01            ; A=A-$01 X=[stk] Y=$0002 ; [SP-35]
            lsr  a               ; A=A-$01 X=[stk] Y=$0002 ; [SP-35]
            ror  $FE             ; A=A-$01 X=[stk] Y=$0002 ; [SP-35]
            lsr  a               ; A=A-$01 X=[stk] Y=$0002 ; [SP-35]
            ror  $FE             ; A=A-$01 X=[stk] Y=$0002 ; [SP-35]
calc_roster_offset clc                  ; A=A-$01 X=[stk] Y=$0002 ; [SP-35]
            adc  #$95            ; A=A+$95 X=[stk] Y=$0002 ; [SP-35]
            sta  $FF             ; A=A+$95 X=[stk] Y=$0002 ; [SP-35]
            lda  #$40            ; A=$0040 X=[stk] Y=$0002 ; [SP-35]
            sta  $FD             ; A=$0040 X=[stk] Y=$0002 ; [SP-35]
            txa                  ; A=[stk] X=[stk] Y=$0002 ; [SP-35]
            clc                  ; A=[stk] X=[stk] Y=$0002 ; [SP-35]
            ror  a               ; A=[stk] X=[stk] Y=$0002 ; [SP-35]
            ror  a               ; A=[stk] X=[stk] Y=$0002 ; [SP-35]
            ror  a               ; A=[stk] X=[stk] Y=$0002 ; [SP-35]
            sta  $FC             ; A=[stk] X=[stk] Y=$0002 ; [SP-35]
            rts                  ; A=[stk] X=[stk] Y=$0002 ; [SP-33]

; ---------------------------------------------------------------------------
; copy_roster_to_plrs  [1 jump]
;   Calls: calc_roster_ptr
; ---------------------------------------------------------------------------
; XREF: 1 ref (1 jump) from $0046DB
copy_roster_to_plrs  ldx  $E1             ; A=[stk] X=[stk] Y=$0002 ; [SP-33]
            dex                  ; A=[stk] X=X-$01 Y=$0002 ; [SP-33]
            jsr  calc_roster_ptr        ; A=[stk] X=X-$01 Y=$0002 ; [SP-35]
            ldy  #$3F            ; A=[stk] X=X-$01 Y=$003F ; [SP-35]
            lda  ($FE),Y         ; A=[stk] X=X-$01 Y=$003F ; [SP-35]
            sta  ($FC),Y         ; A=[stk] X=X-$01 Y=$003F ; [SP-35]
            dey                  ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
            bpl  $495D           ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
            dex                  ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
            bpl  $4958           ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
            rts                  ; A=[stk] X=X-$01 Y=$003E ; [SP-33]
; XREF: 1 ref (1 jump) from $0046DE
copy_plrs_to_roster ldx  $E1             ; A=[stk] X=X-$01 Y=$003E ; [SP-33]
            dex                  ; A=[stk] X=X-$01 Y=$003E ; [SP-33]

; === while loop starts here [nest:11] ===
; XREF: 1 ref (1 branch) from copy_plrs_byte
copy_plrs_slot jsr  calc_roster_ptr        ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
            ldy  #$3F            ; A=[stk] X=X-$01 Y=$003F ; [SP-35]

; === while loop starts here [nest:12] ===
; XREF: 1 ref (1 branch) from copy_plrs_byte
copy_plrs_byte lda  ($FC),Y         ; A=[stk] X=X-$01 Y=$003F ; [SP-35]
            sta  ($FE),Y         ; A=[stk] X=X-$01 Y=$003F ; [SP-35]
            dey                  ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
            bpl  copy_plrs_byte     ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
; === End of while loop ===

            dex                  ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
            bpl  copy_plrs_slot     ; A=[stk] X=X-$01 Y=$003E ; [SP-35]
; === End of while loop ===

            rts                  ; A=[stk] X=X-$01 Y=$003E ; [SP-33]

; --- Data region (132 bytes) ---
            DB      $A9,$00,$85,$D1,$85,$D2,$20,$71,$4E,$C9,$B0,$90,$F9,$C9,$BA,$B0
            DB      $F5,$38,$E9,$B0,$85,$D1,$18,$69,$30,$20,$93,$48,$E6,$F9,$20,$71
            DB      $4E,$C9,$8D,$D0,$0B,$A5,$D1,$85,$D2,$A9,$00,$85,$D1,$4C,$E3,$49
            DB      $C9,$88,$D0,$0A,$C6,$F9,$A9,$20,$20,$93,$48,$4C,$7B,$49,$C9,$B0
            DB      $90,$DC,$C9,$BA,$B0,$D8,$38,$E9,$B0,$85,$D2,$18,$69,$30,$20,$93
            DB      $48,$E6,$F9,$20,$71,$4E,$C9,$8D,$F0,$0E,$C9,$88,$D0,$F5,$C6,$F9
            DB      $A9,$20,$20,$93,$48,$4C,$99,$49,$A9,$00,$A6,$D1,$F0,$06,$18,$69
            DB      $0A,$CA,$D0,$FA,$18,$65,$D2,$85,$D3,$A5,$D1,$0A,$0A,$0A,$0A,$65
            DB      $D2,$85,$D0,$60
; --- End data region (132 bytes) ---


; ===========================================================================
; DISPLAY (6 functions)
; ===========================================================================

; ---------------------------------------------------------------------------
; modulo  [1 call, 1 jump]
;   Called by: text_wind_rng
;   Calls: get_random
; ---------------------------------------------------------------------------

; FUNC $0049FF: register -> A:X [I]
; Proto: uint32_t func_0049FF(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Liveness: params(A,X,Y) returns(A,X,Y)
; XREF: 2 refs (1 call) (1 jump) from $0046E4, text_wind_rng
modulo  sta  $F3             ; A=[stk] X=X-$01 Y=$003E ; [SP-45]
            jsr  get_random       ; A=[stk] X=X-$01 Y=$003E ; [SP-47]

; === while loop starts here [nest:12] ===
; XREF: 1 ref (1 jump) from modulo_loop
modulo_loop cmp  $F3             ; A=[stk] X=X-$01 Y=$003E ; [SP-47]
            bcc  modulo_done   ; A=[stk] X=X-$01 Y=$003E ; [SP-47]
            sec                  ; A=[stk] X=X-$01 Y=$003E ; [SP-47]
            sbc  $F3             ; A=[stk] X=X-$01 Y=$003E ; [SP-47]
            jmp  modulo_loop   ; A=[stk] X=X-$01 Y=$003E ; [SP-47]
; === End of while loop ===

; XREF: 1 ref (1 branch) from modulo_loop
modulo_done cmp  #$00            ; A=[stk] X=X-$01 Y=$003E ; [SP-47]
            sta  $F3             ; A=[stk] X=X-$01 Y=$003E ; [SP-47]
            rts                  ; A=[stk] X=X-$01 Y=$003E ; [SP-45]
; XREF: 1 ref (1 jump) from $0046EA
update_viewport    jsr  draw_text_window      ; A=[stk] X=X-$01 Y=$003E ; [SP-47]
            jsr  animate_tiles        ; A=[stk] X=X-$01 Y=$003E ; [SP-49]
            jsr  $4A52           ; A=[stk] X=X-$01 Y=$003E ; [SP-51]
            jsr  $4AB0           ; A=[stk] X=X-$01 Y=$003E ; [SP-53]
            jsr  $4B48           ; A=[stk] X=X-$01 Y=$003E ; [SP-55]
            jsr  $0230           ; A=[stk] X=X-$01 Y=$003E ; [OPT] TAIL_CALL: Tail call: JSR/JSL at $004A22 followed by RTS ; [SP-57]
            rts                  ; A=[stk] X=X-$01 Y=$003E ; [SP-55]

; ---------------------------------------------------------------------------
; animate_tiles  [1 call, 1 jump]
;   Called by: update_viewport
;   Calls: swap_tile_frames
; ---------------------------------------------------------------------------
; XREF: 2 refs (1 call) (1 jump) from update_viewport, $0046ED
animate_tiles    dec  anim_counter_1     ; A=[stk] X=X-$01 Y=$003E ; [SP-55]
            bne  anim_tiles_set2     ; A=[stk] X=X-$01 Y=$003E ; [SP-55]
            lda  #$02            ; A=$0002 X=X-$01 Y=$003E ; [SP-55]
            sta  anim_counter_1     ; A=$0002 X=X-$01 Y=$003E ; [SP-55]
            ldy  #$00            ; A=$0002 X=X-$01 Y=$0000 ; [SP-55]
            jsr  swap_tile_frames     ; A=$0002 X=X-$01 Y=$0000 ; [SP-57]
; XREF: 1 ref (1 branch) from animate_tiles
anim_tiles_set2 ldy  #$40            ; A=$0002 X=X-$01 Y=$0040 ; [SP-57]
            jsr  swap_tile_frames     ; A=$0002 X=X-$01 Y=$0040 ; [SP-59]
            dec  anim_counter_2     ; A=$0002 X=X-$01 Y=$0040 ; [SP-59]
            bne  anim_tiles_set3     ; A=$0002 X=X-$01 Y=$0040 ; [SP-59]
            lda  #$02            ; A=$0002 X=X-$01 Y=$0040 ; [SP-59]
            sta  anim_counter_2     ; A=$0002 X=X-$01 Y=$0040 ; [SP-59]
            ldy  #$42            ; A=$0002 X=X-$01 Y=$0042 ; [SP-59]
            jsr  swap_tile_frames     ; A=$0002 X=X-$01 Y=$0042 ; [SP-61]
; XREF: 1 ref (1 branch) from anim_tiles_set2
anim_tiles_set3 ldy  #$44            ; A=$0002 X=X-$01 Y=$0044 ; [SP-61]
            jsr  swap_tile_frames     ; A=$0002 X=X-$01 Y=$0044 ; [OPT] TAIL_CALL: Tail call: JSR/JSL at $004A4B followed by RTS ; [SP-63]
            rts                  ; A=$0002 X=X-$01 Y=$0044 ; [SP-61]

; ---
anim_counter_1
            DB      $02
anim_counter_2
            DB      $07,$04,$20,$5F,$4A,$20,$76,$4A,$20,$8D,$4A,$60
anim_counter_3
            DB      $03
anim_counter_4
            DB      $02
anim_counter_5
            DB      $01,$CE,$5C,$4A,$D0,$11
; ---

swap_viewport_buf  lda  #$03            ; A=$0003 X=X-$01 Y=$0044 ; [SP-64]
            sta  anim_counter_3     ; A=$0003 X=X-$01 Y=$0044 ; [SP-64]
            ldx  $088F           ; A=$0003 X=X-$01 Y=$0044 ; [SP-64]
            ldy  $090F           ; A=$0003 X=X-$01 Y=$0044 ; [SP-64]
            sty  $088F           ; A=$0003 X=X-$01 Y=$0044 ; [SP-64]
            stx  $090F           ; A=$0003 X=X-$01 Y=$0044 ; [SP-64]
            rts                  ; A=$0003 X=X-$01 Y=$0044 ; [SP-62]

; ---
            DB      $CE,$5D,$4A,$D0,$11,$A9,$02,$8D,$5D,$4A,$AE,$8C,$09,$AC,$0C,$0A
            DB      $8C,$8C,$09,$8E,$0C,$0A,$60
; ---


; ---------------------------------------------------------------------------
; animate_cursor  [1 call]
;   Called by: anim_counter_2
; ---------------------------------------------------------------------------
; XREF: 1 ref (1 call) from anim_counter_2
animate_cursor dec  anim_counter_5     ; A=$0003 X=X-$01 Y=$0044 ; [SP-60]
            bne  anim_cursor_done ; A=$0003 X=X-$01 Y=$0044 ; [SP-60]
            lda  #$01            ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            sta  anim_counter_5     ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            ldx  $0917           ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            ldy  $0997           ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            sty  $0917           ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            stx  $0997           ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            ldx  $0916           ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            ldy  $0996           ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            sty  $0916           ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
            stx  $0996           ; A=$0001 X=X-$01 Y=$0044 ; [SP-60]
; XREF: 1 ref (1 branch) from animate_cursor
anim_cursor_done rts                  ; A=$0001 X=X-$01 Y=$0044 ; [SP-58]

; --- Data region (76 bytes) ---
            DB      $AD,$3E,$09,$0A,$69,$00,$8D,$3E,$09,$AD,$3F,$09,$0A,$69,$00,$8D
            DB      $3F,$09,$AD,$BE,$09,$0A,$69,$00,$8D,$BE,$09,$AD,$BF,$09,$0A,$69
            DB      $00,$8D,$BF,$09,$EE,$47,$4B,$AD,$47,$4B,$4A,$90,$38,$4A,$90,$1C
            DB      $4A,$90,$4B,$AD,$BE,$0B,$49,$1E,$8D,$BE,$0B,$AD,$3E,$0C,$49,$1E
            DB      $8D,$3E,$0C,$AD,$BE,$0C,$49,$1E,$8D,$BE,$0C,$60
; --- End data region (76 bytes) ---

; XREF: 1 ref (1 branch) from anim_cursor_done
toggle_cursor_1 lda  $0BBF           ; A=[$0BBF] X=X-$01 Y=$0044 ; [SP-56]
            eor  #$1E            ; A=A^$1E X=X-$01 Y=$0044 ; [SP-56]
            sta  $0BBF           ; A=A^$1E X=X-$01 Y=$0044 ; [OPT] PEEPHOLE: Load after store: 2 byte pattern at $004B01 ; [SP-56]
            lda  $0C3F           ; A=[$0C3F] X=X-$01 Y=$0044 ; [SP-56]
            eor  #$1E            ; A=A^$1E X=X-$01 Y=$0044 ; [SP-56]
            sta  $0C3F           ; A=A^$1E X=X-$01 Y=$0044 ; [OPT] PEEPHOLE: Load after store: 2 byte pattern at $004B09 ; [SP-56]
            lda  $0CBF           ; A=[$0CBF] X=X-$01 Y=$0044 ; [SP-56]
            eor  #$1E            ; A=A^$1E X=X-$01 Y=$0044 ; [SP-56]
            sta  $0CBF           ; A=A^$1E X=X-$01 Y=$0044 ; [SP-56]
            rts                  ; A=A^$1E X=X-$01 Y=$0044 ; [SP-54]

; ---
            DB      $AD,$BE,$0D,$49,$1E,$8D,$BE,$0D,$AD,$3E,$0E,$49,$1E,$8D,$3E,$0E
            DB      $AD,$BE,$0E,$49,$1E,$8D,$BE,$0E,$60
; ---

; XREF: 1 ref (1 branch) from anim_cursor_done
toggle_cursor_2 lda  $0DBF           ; A=[$0DBF] X=X-$01 Y=$0044 ; [SP-52]
            eor  #$1E            ; A=A^$1E X=X-$01 Y=$0044 ; [SP-52]
            sta  $0DBF           ; A=A^$1E X=X-$01 Y=$0044 ; [OPT] PEEPHOLE: Load after store: 2 byte pattern at $004B33 ; [SP-52]
            lda  $0E3F           ; A=[$0E3F] X=X-$01 Y=$0044 ; [SP-52]
            eor  #$1E            ; A=A^$1E X=X-$01 Y=$0044 ; [SP-52]
            sta  $0E3F           ; A=A^$1E X=X-$01 Y=$0044 ; [OPT] PEEPHOLE: Load after store: 2 byte pattern at $004B3B ; [SP-52]
            lda  $0EBF           ; A=[$0EBF] X=X-$01 Y=$0044 ; [SP-52]
            eor  #$1E            ; A=A^$1E X=X-$01 Y=$0044 ; [SP-52]
            sta  $0EBF           ; A=A^$1E X=X-$01 Y=$0044 ; [SP-52]
            rts                  ; A=A^$1E X=X-$01 Y=$0044 ; [SP-50]

; --- Data region (107 bytes) ---
            DB      $00,$CE,$B4,$4B,$F0,$5F,$CE,$B2,$4B,$10,$05,$A9,$0F,$8D,$B2,$4B
            DB      $AD,$B2,$4B,$0A,$0A,$0A,$0A,$0A,$85,$FC,$A9,$41,$69,$00,$85,$FD
            DB      $AD,$B2,$4B,$0A,$69,$20,$C9,$3E,$D0,$02,$A9,$18,$A8,$A9,$08,$85
            DB      $FF,$A9,$00,$85,$FE,$A2,$00,$A1,$FC,$85,$95,$B1,$FE,$81,$FC,$A5
            DB      $95,$91,$FE,$E6,$FC,$C8,$A1,$FC,$85,$95,$B1,$FE,$81,$FC,$A5,$95
            DB      $91,$FE,$E6,$FC,$88,$20,$B5,$4B,$CE,$B3,$4B,$D0,$DA,$A9,$10,$8D
            DB      $B3,$4B,$4C,$48,$4B,$A9,$05,$8D,$B4,$4B,$60
; --- End data region (107 bytes) ---

; XREF: 3 refs from toggle_cursor_2, toggle_cursor_2, toggle_cursor_2
advance_scanline bpl  advance_scan_jmp ; A=A^$1E X=X-$01 Y=$0044 ; [SP-53]
; XREF: 1 ref from toggle_cursor_2
advance_scan_clc ora  $18             ; A=A^$1E X=X-$01 Y=$0044 ; [SP-53]
            lda  $FE             ; A=[$00FE] X=X-$01 Y=$0044 ; [SP-53]
            adc  #$80            ; A=A+$80 X=X-$01 Y=$0044 ; [SP-53]
            sta  $FE             ; A=A+$80 X=X-$01 Y=$0044 ; [SP-53]
            lda  $FF             ; A=[$00FF] X=X-$01 Y=$0044 ; [SP-53]
            adc  #$00            ; A=A X=X-$01 Y=$0044 ; [SP-53]
            sta  $FF             ; A=A X=X-$01 Y=$0044 ; [SP-53]
            rts                  ; A=A X=X-$01 Y=$0044 ; [SP-51]
            DB      $86
; XREF: 1 ref (1 branch) from advance_scanline
advance_scan_jmp sbc  $FA84,Y         ; -> $FAC8 ; A=A X=X-$01 Y=$0044 ; [SP-51]
            jmp  print_inline_str         ; A=A X=X-$01 Y=$0044 ; [SP-51]
; === End of while loop (counter: Y) ===


; ---------------------------------------------------------------------------
; setup_char_ptr  [2 calls, 1 jump]
;   Called by: print_char_name, print_name_loop
; ---------------------------------------------------------------------------

; FUNC $004BCA: register -> A:X [I]
; Proto: uint32_t func_004BCA(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [1 dead stores]
; XREF: 3 refs (2 calls) (1 jump) from $0046F6, print_char_name, print_name_loop
setup_char_ptr lda  #$00            ; A=$0000 X=X-$01 Y=$0044 ; [SP-51]
            sta  $FE             ; A=$0000 X=X-$01 Y=$0044 ; [SP-51]
            lda  $D5             ; A=[$00D5] X=X-$01 Y=$0044 ; [SP-51]
            lsr  a               ; A=[$00D5] X=X-$01 Y=$0044 ; [SP-51]
            ror  $FE             ; A=[$00D5] X=X-$01 Y=$0044 ; [SP-51]
            lsr  a               ; A=[$00D5] X=X-$01 Y=$0044 ; [SP-51]
            ror  $FE             ; A=[$00D5] X=X-$01 Y=$0044 ; [SP-51]
            lda  #$40            ; A=$0040 X=X-$01 Y=$0044 ; [SP-51]
            sta  $FF             ; A=$0040 X=X-$01 Y=$0044 ; [SP-51]
            rts                  ; A=$0040 X=X-$01 Y=$0044 ; [SP-49]
; XREF: 1 ref (1 jump) from $0046F9
print_char_name jsr  setup_char_ptr    ; A=$0040 X=X-$01 Y=$0044 ; [SP-51]
            ldy  #$00            ; A=$0040 X=X-$01 Y=$0000 ; [SP-51]
            lda  ($FE),Y         ; A=$0040 X=X-$01 Y=$0000 ; [SP-51]
            beq  print_name_done ; A=$0040 X=X-$01 Y=$0000 ; [SP-51]

; === while loop starts here [nest:8] ===
; XREF: 1 ref (1 branch) from find_name_end
find_name_end iny                  ; A=$0040 X=X-$01 Y=$0001 ; [SP-51]
            lda  ($FE),Y         ; A=$0040 X=X-$01 Y=$0001 ; [SP-51]
            bne  find_name_end ; A=$0040 X=X-$01 Y=$0001 ; [SP-51]
; === End of while loop ===

            tya                  ; A=$0001 X=X-$01 Y=$0001 ; [SP-51]
            lsr  a               ; A=$0001 X=X-$01 Y=$0001 ; [SP-51]
            sta  $F0             ; A=$0001 X=X-$01 Y=$0001 ; [SP-51]
            lda  #$1F            ; A=$001F X=X-$01 Y=$0001 ; [SP-51]
            sec                  ; A=$001F X=X-$01 Y=$0001 ; [SP-51]
            sbc  $F0             ; A=$001F X=X-$01 Y=$0001 ; [SP-51]
            sta  $F9             ; A=$001F X=X-$01 Y=$0001 ; [SP-51]
            lda  $D5             ; A=[$00D5] X=X-$01 Y=$0001 ; [SP-51]
            asl  a               ; A=[$00D5] X=X-$01 Y=$0001 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for calc_roster_ptr ; [SP-51]
            asl  a               ; A=[$00D5] X=X-$01 Y=$0001 ; [SP-51]
            adc  #$01            ; A=A+$01 X=X-$01 Y=$0001 ; [SP-51]
            sta  $FA             ; A=A+$01 X=X-$01 Y=$0001 ; [SP-51]
            lda  #$00            ; A=$0000 X=X-$01 Y=$0001 ; [SP-51]
            sta  $D7             ; A=$0000 X=X-$01 Y=$0001 ; [SP-51]

; === while loop starts here [nest:6] ===
; XREF: 1 ref (1 jump) from print_name_loop
print_name_loop jsr  setup_char_ptr    ; A=$0000 X=X-$01 Y=$0001 ; [SP-53]
            ldy  $D7             ; A=$0000 X=X-$01 Y=$0001 ; [SP-53]
            lda  ($FE),Y         ; A=$0000 X=X-$01 Y=$0001 ; [SP-53]
            beq  print_name_done ; A=$0000 X=X-$01 Y=$0001 ; [SP-53]
            and  #$7F            ; A=A&$7F X=X-$01 Y=$0001 ; [SP-53]
            jsr  plot_char_glyph       ; A=A&$7F X=X-$01 Y=$0001 ; [SP-55]
            inc  $F9             ; A=A&$7F X=X-$01 Y=$0001 ; [SP-55]
            inc  $D7             ; A=A&$7F X=X-$01 Y=$0001 ; [SP-55]
            jmp  print_name_loop ; A=A&$7F X=X-$01 Y=$0001 ; [SP-55]
; === End of while loop ===

; XREF: 2 refs (2 branches) from print_name_loop, print_char_name
print_name_done rts                  ; A=A&$7F X=X-$01 Y=$0001 ; [SP-53]

; --- Data region (38 bytes) ---
            DB      $A5,$00,$85,$02,$A5,$01,$85,$03,$4C,$21,$4C,$A5,$03,$85,$FF,$A9
            DB      $00,$A8,$46,$FF,$6A,$46,$FF,$6A,$65,$02,$85,$FE,$18,$A5,$FF,$69
            DB      $10,$85,$FF,$B1,$FE,$60
; --- End data region (38 bytes) ---


; ---------------------------------------------------------------------------
; draw_text_window  [1 call]
;   Called by: update_viewport
;   Calls: modulo, print_inline_str
; ---------------------------------------------------------------------------
; XREF: 1 ref (1 call) from update_viewport
draw_text_window  dec  text_wind_counter      ; A=A&$7F X=X-$01 Y=$0001 ; [SP-51]
            bpl  text_wind_show   ; A=A&$7F X=X-$01 Y=$0001 ; [SP-51]
            lda  #$08            ; A=$0008 X=X-$01 Y=$0001 ; [SP-51]
            sta  text_wind_counter      ; A=$0008 X=X-$01 Y=$0001 ; [SP-51] ; WARNING: Self-modifying code -> text_wind_counter

; === while loop starts here [nest:5] ===
; XREF: 1 ref (1 branch) from text_wind_rng
text_wind_rng lda  #$09            ; A=$0009 X=X-$01 Y=$0001 ; [SP-51]
            jsr  modulo      ; A=$0009 X=X-$01 Y=$0001 ; [SP-53]
            cmp  #$05            ; A=$0009 X=X-$01 Y=$0001 ; [SP-53]
            bcc  text_wind_set   ; A=$0009 X=X-$01 Y=$0001 ; [SP-53]
            sec                  ; A=$0009 X=X-$01 Y=$0001 ; [SP-53]
            sbc  #$04            ; A=A-$04 X=X-$01 Y=$0001 ; [SP-53]
            cmp  $11             ; A=A-$04 X=X-$01 Y=$0001 ; [SP-53]
            beq  text_wind_rng   ; A=A-$04 X=X-$01 Y=$0001 ; [SP-53]
; === End of while loop ===

; XREF: 1 ref (1 branch) from text_wind_rng
text_wind_set sta  $11             ; A=A-$04 X=X-$01 Y=$0001 ; [SP-53]
; XREF: 1 ref (1 branch) from draw_text_window
text_wind_show lda  $F9             ; A=[$00F9] X=X-$01 Y=$0001 ; [SP-53]
            pha                  ; A=[$00F9] X=X-$01 Y=$0001 ; [SP-54]
            lda  #$06            ; A=$0006 X=X-$01 Y=$0001 ; [SP-54]
            sta  $F9             ; A=$0006 X=X-$01 Y=$0001 ; [SP-54]
            lda  #$17            ; A=$0017 X=X-$01 Y=$0001 ; [SP-54]
            sta  $FA             ; A=$0017 X=X-$01 Y=$0001 ; [SP-54]
            lda  $11             ; A=[$0011] X=X-$01 Y=$0001 ; [SP-54]
            bne  text_mode_1      ; A=[$0011] X=X-$01 Y=$0001 ; [SP-54]
            jsr  print_inline_str         ; A=[$0011] X=X-$01 Y=$0001 ; [SP-56]
            ora  $C1C3,X         ; S1_xC3 - Slot 1 ROM offset $C3 {Slot}
            cpy  $A0CD           ; A=[$0011] X=X-$01 Y=$0001 ; [SP-56]
            DB      $D7
            cmp  #$CE            ; A=[$0011] X=X-$01 Y=$0001 ; [SP-56]

; ---
            DB      $C4
text_mode_data
            DB      $D3
            DB      $1F
            DB      $00,$4C,$CF,$4C
; ---

; XREF: 1 ref (1 branch) from text_wind_show
text_mode_1  cmp  #$01            ; A=[$0011] X=X-$01 Y=$0001 ; [SP-56]
            bne  text_mode_2      ; A=[$0011] X=X-$01 Y=$0001 ; [SP-56]
            jsr  print_inline_str         ; A=[$0011] X=X-$01 Y=$0001 ; [SP-58]
            ora  $CFCE,X         ; SLOTEXP_x7CE - Slot expansion ROM offset $7CE {Slot}

; ---
            DB      $D2
            DB      $D4
            DB      $C8,$A0,$D7,$C9,$CE,$C4,$1F,$00,$4C,$CF,$4C
; ---

; XREF: 1 ref (1 branch) from text_mode_1
text_mode_2  cmp  #$02            ; A=[$0011] X=X-$01 Y=$0001 ; [SP-61]
            bne  text_mode_3      ; A=[$0011] X=X-$01 Y=$0001 ; [SP-61]
            jsr  print_inline_str         ; A=[$0011] X=X-$01 Y=$0001 ; [SP-63]
            ora  $C1C5,X         ; S1_xC5 - Slot 1 ROM offset $C5 {Slot}

; ---
            DB      $D3
            DB      $D4
            DB      $A0,$A0,$D7,$C9,$CE,$C4,$1F,$00,$4C,$CF,$4C
; ---

; XREF: 1 ref (1 branch) from text_mode_2
text_mode_3  cmp  #$03            ; A=[$0011] X=X-$01 Y=$0001 ; [SP-66]
            bne  text_mode_4      ; A=[$0011] X=X-$01 Y=$0001 ; [SP-66]
            jsr  print_inline_str         ; Call $004732(1 stack)
            ora  $CFD3,X         ; SLOTEXP_x7D3 - Slot expansion ROM offset $7D3 {Slot}
            cmp  $D4,X           ; A=[$0011] X=X-$01 Y=$0001 ; [SP-68]
            iny                  ; A=[$0011] X=X-$01 Y=$0002 ; [SP-68]
            ldy  #$D7            ; A=[$0011] X=X-$01 Y=$00D7 ; [SP-68]
            cmp  #$CE            ; A=[$0011] X=X-$01 Y=$00D7 ; [SP-68]
            cpy  $1F             ; A=[$0011] X=X-$01 Y=$00D7 ; [SP-68]
            brk  #$4C            ; A=[$0011] X=X-$01 Y=$00D7 ; [SP-71]
            DB      $CF,$4C
; XREF: 1 ref (1 branch) from text_mode_3
text_mode_4  jsr  print_inline_str         ; A=[$0011] X=X-$01 Y=$00D7 ; [SP-71]
            ora  $C5D7,X         ; S5_xD7 - Slot 5 ROM offset $D7 {Slot}

; ---
            DB      $D3
            DB      $D4
            DB      $A0,$A0,$D7,$C9,$CE,$C4,$1F,$00,$68,$85,$F9,$60
; ---

; XREF: 1 ref from draw_text_window
; *** MODIFIED AT RUNTIME by $4C43 ***
text_wind_counter  ora  ($C5,X)         ; A=[$0011] X=X-$01 Y=$00D7 ; [SP-72]
            ora  ($D0),Y         ; A=[$0011] X=X-$01 Y=$00D7 ; [SP-72]
            ora  #$A5            ; A=A|$A5 X=X-$01 Y=$00D7 ; [SP-72]
            asl  $16C9           ; A=A|$A5 X=X-$01 Y=$00D7 ; [SP-72]
            bne  text_wind_zero      ; A=A|$A5 X=X-$01 Y=$00D7 ; [SP-72]
            lda  #$FF            ; A=$00FF X=X-$01 Y=$00D7 ; [SP-72]
            rts                  ; A=$00FF X=X-$01 Y=$00D7 ; [SP-70]
            DB      $A5,$11,$F0,$F3
; XREF: 1 ref (1 branch) from text_wind_counter
text_wind_zero  lda  #$00            ; A=$0000 X=X-$01 Y=$00D7 ; [SP-70]
            rts                  ; A=$0000 X=X-$01 Y=$00D7 ; [SP-68]

; ---------------------------------------------------------------------------
; play_sfx  [1 jump]
; ---------------------------------------------------------------------------
; XREF: 1 ref (1 jump) from $004705
play_sfx  sta  $F0             ; A=$0000 X=X-$01 Y=$00D7 ; [SP-68]
            lda  $10             ; A=[$0010] X=X-$01 Y=$00D7 ; [SP-68]
            beq  sfx_dispatch      ; A=[$0010] X=X-$01 Y=$00D7 ; [SP-68]
            rts                  ; A=[$0010] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from play_sfx
sfx_dispatch  lda  $F0             ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            cmp  #$FF            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_FE      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_beep_hi      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_dispatch
sfx_check_FE  cmp  #$FE            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_FD      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_beep_lo      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_FE
sfx_check_FD  cmp  #$FD            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_FC      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_sweep      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_FD
sfx_check_FC  cmp  #$FC            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_FB      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_noise      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_FC
sfx_check_FB  cmp  #$FB            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_FA      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_buzz      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_FB
sfx_check_FA  cmp  #$FA            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_F9      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_chirp      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_FA
sfx_check_F9  cmp  #$F9            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_F8      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_sweep_alt      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_F9
sfx_check_F8  cmp  #$F8            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_F7      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_descend      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_F8
sfx_check_F7  cmp  #$F7            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_check_F6      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_ascend      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_F7
sfx_check_F6  cmp  #$F6            ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            bne  sfx_return      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
            jmp  sfx_short_desc      ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-66]
; XREF: 1 ref (1 branch) from sfx_check_F6
sfx_return  rts                  ; A=[$00F0] X=X-$01 Y=$00D7 ; [SP-64]
; XREF: 1 ref (1 jump) from sfx_dispatch
sfx_beep_hi  ldy  #$10            ; A=[$00F0] X=X-$01 Y=$0010 ; [SP-64]

; === loop starts here (counter: Y, range: 16..0, iters: 16) ===
; XREF: 1 ref (1 branch) from sfx_beep_hi_loop
sfx_beep_hi_loop  lda  #$30            ; A=$0030 X=X-$01 Y=$0010 ; [SP-64]
            jsr  $FCA8           ; WAIT - Apple II delay routine
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dey                  ; A=$0030 X=X-$01 Y=$000F ; [SP-66]
            bne  sfx_beep_hi_loop      ; A=$0030 X=X-$01 Y=$000F ; [SP-66]
; === End of loop (counter: Y) ===

            rts                  ; A=$0030 X=X-$01 Y=$000F ; [SP-64]
; XREF: 1 ref (1 jump) from sfx_check_FE
sfx_beep_lo  ldy  #$30            ; A=$0030 X=X-$01 Y=$0030 ; [SP-64]

; === loop starts here (counter: Y, range: 48..0, iters: 48) ===
; XREF: 1 ref (1 branch) from sfx_beep_lo_loop
sfx_beep_lo_loop  lda  #$18            ; A=$0018 X=X-$01 Y=$0030 ; [SP-64]
            jsr  $FCA8           ; WAIT - Apple II delay routine
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dey                  ; A=$0018 X=X-$01 Y=$002F ; [SP-66]
            bne  sfx_beep_lo_loop      ; A=$0018 X=X-$01 Y=$002F ; [SP-66]
; === End of loop (counter: Y) ===

            rts                  ; A=$0018 X=X-$01 Y=$002F ; [SP-64]

; === while loop starts here (counter: X 'i') ===
; XREF: 2 refs (2 jumps) from sfx_sweep_alt, sfx_check_FD
sfx_sweep  stx  sfx_save_x     ; A=$0018 X=X-$01 Y=$002F ; [SP-64]
            sty  sfx_duration     ; A=$0018 X=X-$01 Y=$002F ; [SP-64]
            lda  sfx_save_x     ; A=[$4DB6] X=X-$01 Y=$002F ; [SP-64]
            sta  sfx_period_1     ; A=[$4DB6] X=X-$01 Y=$002F ; [SP-64]
            lda  #$01            ; A=$0001 X=X-$01 Y=$002F ; [SP-64]
            sta  sfx_period_2     ; A=$0001 X=X-$01 Y=$002F ; [OPT] PEEPHOLE: Load after store: 2 byte pattern at $004D62 ; [SP-64]

; === while loop starts here [nest:1] ===
; XREF: 1 ref (1 branch) from sfx_sweep_wait2
sfx_sweep_outer  lda  sfx_duration     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            sta  $F3             ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]

; === while loop starts here [nest:2] ===
; XREF: 1 ref (1 branch) from sfx_sweep_wait2
sfx_sweep_half1  ldx  sfx_period_1     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]

; === loop starts here (counter: X) [nest:3] ===
; XREF: 1 ref (1 branch) from sfx_sweep_wait1
sfx_sweep_wait1  dex                  ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_sweep_wait1      ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            ldx  sfx_period_2     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]

; === loop starts here (counter: X) [nest:3] ===
; XREF: 1 ref (1 branch) from sfx_sweep_wait2
sfx_sweep_wait2  dex                  ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_sweep_wait2      ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dec  $F3             ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_sweep_half1      ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            dec  sfx_period_1     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            inc  sfx_period_2     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            lda  sfx_period_2     ; A=[$4DB9] X=X-$01 Y=$002F ; [SP-64]
            cmp  #$1B            ; A=[$4DB9] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_sweep_outer      ; A=[$4DB9] X=X-$01 Y=$002F ; [SP-64]

; === while loop starts here [nest:1] ===
; XREF: 1 ref (1 branch) from sfx_sweep_dn_wait2
sfx_sweep_dn_outer  lda  sfx_duration     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            sta  $F3             ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]

; === while loop starts here [nest:2] ===
; XREF: 1 ref (1 branch) from sfx_sweep_dn_wait2
sfx_sweep_dn_half1  ldx  sfx_period_1     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]

; === loop starts here (counter: X) [nest:3] ===
; XREF: 1 ref (1 branch) from sfx_sweep_dn_wait1
sfx_sweep_dn_wait1  dex                  ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_sweep_dn_wait1      ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            ldx  sfx_period_2     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]

; === loop starts here (counter: X) [nest:3] ===
; XREF: 1 ref (1 branch) from sfx_sweep_dn_wait2
sfx_sweep_dn_wait2  dex                  ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_sweep_dn_wait2      ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dec  $F3             ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_sweep_dn_half1      ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            dec  sfx_period_2     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            inc  sfx_period_1     ; A=[$4DB7] X=X-$01 Y=$002F ; [SP-64]
            lda  sfx_period_2     ; A=[$4DB9] X=X-$01 Y=$002F ; [SP-64]
            cmp  #$00            ; A=[$4DB9] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_sweep_dn_outer      ; A=[$4DB9] X=X-$01 Y=$002F ; [SP-64]
            rts                  ; A=[$4DB9] X=X-$01 Y=$002F ; [SP-62]
sfx_save_x
            DB      $C0
sfx_duration
            DB      $10
sfx_period_1
            DB      $FB
sfx_period_2
            DB      $2C
; XREF: 1 ref (1 jump) from sfx_check_FC
sfx_noise  stx  $F3             ; A=[$4DB9] X=X-$01 Y=$002F ; [SP-62]
            lda  #$80            ; A=$0080 X=X-$01 Y=$002F ; [SP-62]
            sta  $D4             ; A=$0080 X=X-$01 Y=$002F ; [SP-62]

; === while loop starts here [nest:1] ===
; XREF: 1 ref (1 branch) from sfx_noise_delay
sfx_noise_loop  jsr  get_random       ; A=$0080 X=X-$01 Y=$002F ; [SP-64]
            and  #$0F            ; A=A&$0F X=X-$01 Y=$002F ; [SP-64]
            adc  $F3             ; A=A&$0F X=X-$01 Y=$002F ; [SP-64]
            tax                  ; A=A&$0F X=A Y=$002F ; [SP-64]

; === loop starts here (counter: X) [nest:2] ===
; XREF: 1 ref (1 branch) from sfx_noise_delay
sfx_noise_delay  pha                  ; A=A&$0F X=A Y=$002F ; [OPT] PEEPHOLE: Redundant PHA/PLA: 2 byte pattern at $004DC8 ; [SP-65]
            pla                  ; A=[stk] X=A Y=$002F ; [SP-64]
            pha                  ; A=[stk] X=A Y=$002F ; [OPT] PEEPHOLE: Redundant PHA/PLA: 2 byte pattern at $004DCA ; [SP-65]
            pla                  ; A=[stk] X=A Y=$002F ; [SP-64]
            dex                  ; A=[stk] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_noise_delay      ; A=[stk] X=X-$01 Y=$002F ; [SP-64]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dec  $D4             ; A=[stk] X=X-$01 Y=$002F ; [SP-64]
            bne  sfx_noise_loop      ; A=[stk] X=X-$01 Y=$002F ; [SP-64]
            rts                  ; A=[stk] X=X-$01 Y=$002F ; [SP-62]
; XREF: 1 ref (1 jump) from sfx_check_FB
sfx_buzz  ldx  #$00            ; A=[stk] X=$0000 Y=$002F ; [SP-62]
            sta  $95             ; A=[stk] X=$0000 Y=$002F ; [SP-62]

; === while loop starts here [nest:1] ===
; XREF: 2 refs (2 branches) from sfx_buzz_loop, sfx_buzz_loop
sfx_buzz_loop  inx                  ; A=[stk] X=$0001 Y=$002F ; [SP-62]
            bne  sfx_buzz_loop      ; A=[stk] X=$0001 Y=$002F ; [SP-62]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dec  $95             ; A=[stk] X=$0001 Y=$002F ; [SP-62]
            ldx  $95             ; A=[stk] X=$0001 Y=$002F ; [SP-62]
            bne  sfx_buzz_loop      ; A=[stk] X=$0001 Y=$002F ; [SP-62]
            rts                  ; A=[stk] X=$0001 Y=$002F ; [SP-60]
; XREF: 1 ref (1 jump) from sfx_check_FA
sfx_chirp  ldx  #$A0            ; A=[stk] X=$00A0 Y=$002F ; [SP-60]
            txa                  ; A=$00A0 X=$00A0 Y=$002F ; [SP-60]
            tay                  ; A=$00A0 X=$00A0 Y=$00A0 ; [SP-60]

; === loop starts here (counter: X) [nest:1] ===
; XREF: 2 refs (2 branches) from sfx_chirp_loop, sfx_chirp_loop
sfx_chirp_loop  dex                  ; A=$00A0 X=$009F Y=$00A0 ; [SP-60]
            bne  sfx_chirp_loop      ; A=$00A0 X=$009F Y=$00A0 ; [SP-60]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dey                  ; A=$00A0 X=$009F Y=$009F ; [SP-60]
            tya                  ; A=$009F X=$009F Y=$009F ; [SP-60]
            tax                  ; A=$009F X=$009F Y=$009F ; [SP-60]
            bne  sfx_chirp_loop      ; A=$009F X=$009F Y=$009F ; [SP-60]
            rts                  ; A=$009F X=$009F Y=$009F ; [SP-58]
; XREF: 1 ref (1 jump) from sfx_check_F9
sfx_sweep_alt  ldx  #$E0            ; A=$009F X=$00E0 Y=$009F ; [SP-58]
            ldy  #$06            ; A=$009F X=$00E0 Y=$0006 ; [SP-58]
            jmp  sfx_sweep      ; A=$009F X=$00E0 Y=$0006 ; [SP-58]
; XREF: 1 ref (1 jump) from sfx_check_F8
sfx_descend  lda  #$40            ; A=$0040 X=$00E0 Y=$0006 ; [SP-58]
            sta  $95             ; A=$0040 X=$00E0 Y=$0006 ; [SP-58]
            lda  #$E0            ; A=$00E0 X=$00E0 Y=$0006 ; [SP-58]
            sta  $96             ; A=$00E0 X=$00E0 Y=$0006 ; [SP-58]

; === while loop starts here ===
; XREF: 1 ref (1 branch) from sfx_descend_wait
sfx_descend_loop  jsr  get_random       ; A=$00E0 X=$00E0 Y=$0006 ; [SP-60]
            ora  $96             ; A=$00E0 X=$00E0 Y=$0006 ; [SP-60]
            tax                  ; A=$00E0 X=$00E0 Y=$0006 ; [SP-60]

; === loop starts here (counter: X) [nest:1] ===
; XREF: 1 ref (1 branch) from sfx_descend_wait
sfx_descend_wait  dex                  ; A=$00E0 X=$00DF Y=$0006 ; [SP-60]
            bne  sfx_descend_wait      ; A=$00E0 X=$00DF Y=$0006 ; [SP-60]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dec  $96             ; A=$00E0 X=$00DF Y=$0006 ; [SP-60]
            lda  $96             ; A=[$0096] X=$00DF Y=$0006 ; [SP-60]
            cmp  $95             ; A=[$0096] X=$00DF Y=$0006 ; [SP-60]
            bcs  sfx_descend_loop      ; A=[$0096] X=$00DF Y=$0006 ; [SP-60]
            rts                  ; A=[$0096] X=$00DF Y=$0006 ; [SP-58]
; XREF: 1 ref (1 jump) from sfx_check_F7
sfx_ascend  lda  #$FF            ; A=$00FF X=$00DF Y=$0006 ; [SP-58]
            sta  $95             ; A=$00FF X=$00DF Y=$0006 ; [SP-58]
            lda  #$00            ; A=$0000 X=$00DF Y=$0006 ; [SP-58]
            sta  $96             ; A=$0000 X=$00DF Y=$0006 ; [SP-58]
            jmp  sfx_rise_fall_loop      ; A=$0000 X=$00DF Y=$0006 ; [SP-58]
; XREF: 1 ref (1 jump) from sfx_check_F6
sfx_short_desc  lda  #$08            ; A=$0008 X=$00DF Y=$0006 ; [SP-58]
            sta  $95             ; A=$0008 X=$00DF Y=$0006 ; [SP-58]
            lda  #$00            ; A=$0000 X=$00DF Y=$0006 ; [SP-58]
            sta  $96             ; A=$0000 X=$00DF Y=$0006 ; [SP-58]

; === while loop starts here ===
; XREF: 2 refs (1 jump) (1 branch) from sfx_rise_fall_wait, sfx_ascend
sfx_rise_fall_loop  jsr  get_random       ; A=$0000 X=$00DF Y=$0006 ; [SP-60]
            ora  $96             ; A=$0000 X=$00DF Y=$0006 ; [SP-60]
            tax                  ; A=$0000 X=$0000 Y=$0006 ; [SP-60]

; === loop starts here (counter: X) [nest:1] ===
; XREF: 1 ref (1 branch) from sfx_rise_fall_wait
sfx_rise_fall_wait  dex                  ; A=$0000 X=$FFFF Y=$0006 ; [SP-60]
            bne  sfx_rise_fall_wait      ; A=$0000 X=$FFFF Y=$0006 ; [SP-60]
            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dec  $95             ; A=$0000 X=$FFFF Y=$0006 ; [SP-60]
            bne  sfx_rise_fall_loop      ; A=$0000 X=$FFFF Y=$0006 ; [SP-60]
            rts                  ; A=$0000 X=$FFFF Y=$0006 ; [SP-58]

; ---------------------------------------------------------------------------
; get_random  [4 calls, 1 jump]
;   Called by: sfx_noise_loop, sfx_descend_loop, modulo, sfx_rise_fall_loop
; ---------------------------------------------------------------------------

; FUNC $004E40: register -> A:X []
; Proto: uint32_t func_004E40(uint16_t param_Y);
; Liveness: params(Y) returns(A,X,Y) [4 dead stores]
; XREF: 5 refs (4 calls) (1 jump) from sfx_noise_loop, sfx_descend_loop, modulo, sfx_rise_fall_loop, $0046E7
get_random   txa                  ; A=$FFFF X=$FFFF Y=$0006 ; [SP-58]
            pha                  ; A=$FFFF X=$FFFF Y=$0006 ; [SP-59]
            clc                  ; A=$FFFF X=$FFFF Y=$0006 ; [SP-59]
            ldx  #$0E            ; A=$FFFF X=$000E Y=$0006 ; [SP-59]
            lda  $4E70           ; A=[$4E70] X=$000E Y=$0006 ; [SP-59]

; === while loop starts here ===
; XREF: 1 ref (1 branch) from rng_add_loop
rng_add_loop adc  $4E61,X         ; -> $4E6F ; A=[$4E70] X=$000E Y=$0006 ; [SP-59]
            sta  $4E61,X         ; -> $4E6F ; A=[$4E70] X=$000E Y=$0006 ; [SP-59]
            dex                  ; A=[$4E70] X=$000D Y=$0006 ; [SP-59]
            bpl  rng_add_loop    ; A=[$4E70] X=$000D Y=$0006 ; [SP-59]
; === End of while loop ===

            ldx  #$0F            ; A=[$4E70] X=$000F Y=$0006 ; [SP-59]

; === while loop starts here ===
; XREF: 1 ref (1 branch) from rng_inc_loop
rng_inc_loop inc  $4E61,X         ; -> $4E70 ; A=[$4E70] X=$000F Y=$0006 ; [SP-59]
            bne  rng_done    ; A=[$4E70] X=$000F Y=$0006 ; [SP-59]
            dex                  ; A=[$4E70] X=$000E Y=$0006 ; [SP-59]
            bpl  rng_inc_loop    ; A=[$4E70] X=$000E Y=$0006 ; [SP-59]
; === End of while loop ===

; XREF: 1 ref (1 branch) from rng_inc_loop
rng_done pla                  ; A=[stk] X=$000E Y=$0006 ; [SP-58]
            tax                  ; A=[stk] X=[stk] Y=$0006 ; [SP-58]
            lda  $4E61           ; A=[$4E61] X=[stk] Y=$0006 ; [SP-58]
            rts                  ; A=[$4E61] X=[stk] Y=$0006 ; [SP-56]

; --- Data region (159 bytes) ---
            DB      $AC,$D0,$AC,$D4,$BA,$00,$AD,$00,$C0,$10,$FB,$2C,$10,$C0,$48,$29
            DB      $8E,$9F,$4E,$8C,$A0,$4E,$CE,$A1,$4E,$D0,$08,$A9,$50,$8D,$A1,$4E
            DB      $20,$A2,$4E,$A9,$00,$20,$93,$48,$AD,$00,$C0,$10,$E9,$2C,$10,$C0
            DB      $48,$A9,$20,$20,$93,$48,$68,$AE,$9F,$4E,$AC,$A0,$4E,$60,$00,$00
            DB      $80,$AE,$80,$07,$AD,$00,$07,$8D,$80,$07,$AD,$80,$06,$8D,$00,$07
            DB      $AD,$00,$06,$8D,$80,$06,$AD,$80,$05,$8D,$00,$06,$AD,$00,$05,$8D
            DB      $80,$05,$AD,$80,$04,$8D,$00,$05,$AD,$00,$04,$8D,$80,$04,$8E,$00
            DB      $04 ; string length
            DB      $60,$46,$D7,$C8
            ASC     "ICH WEAPON:"
            DB      $FF,$00,$AD,$00,$C0,$10,$FB,$2C,$10,$C0,$C9,$C2,$90,$34,$C9,$D1
            DB      $B0,$30,$38,$E9,$C1,$85,$F0,$20,$F6,$46,$A0,$30,$B1,$FE,$C5
