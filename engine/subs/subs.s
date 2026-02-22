; ===========================================================================
; SUBS.s — Ultima III: Exodus Shared Subroutine Library
; ===========================================================================
;
; Origin: Disassembled from SUBS#064100 by CIDAR (deasmiigs v2.0.0).
;         Labels symbolicated from raw CIDAR output (864 labels total across
;         all engine files). Reassembles byte-identical via asmiigs.
;
; Load Address: $4100 (ORG $4100)
; Size:         3,584 bytes ($0E00)
; Content:      Shared subroutine library used by both ULT3 (main engine)
;               and EXOD (boot/loader). Loaded once at startup and remains
;               resident throughout the game session.
;
; ---------------------------------------------------------------------------
; HISTORICAL CONTEXT
; ---------------------------------------------------------------------------
;
; In 1980s Apple II game development, memory was severely constrained:
; 48KB usable RAM, shared between code, data, and the two HGR display
; pages ($2000-$3FFF and $4000-$5FFF). To maximize the code budget,
; Origin Systems factored common routines into this shared library,
; loaded below the HGR page 2 boundary. Both the main game engine (ULT3,
; loaded at $5000) and the boot/title screen (EXOD, loaded at $2000)
; call into SUBS via a jump table at $46BA-$4731.
;
; The library sits at $4100-$4EFF, occupying the lower portion of the
; HGR page 2 region ($4000-$5FFF). Since Ultima III uses only HGR page 1
; ($2000-$3FFF) for its game display, page 2 memory is free for code.
; This is a common Apple II trick — many games "hide" code in the
; unused HGR page to reclaim 8KB of address space.
;
; The code uses several techniques characteristic of 6502 programming:
;   - Self-modifying code (SMC) to simulate indexed addressing modes
;     that the 6502 doesn't support natively
;   - The PLA/PLA return-address trick for inline string printing
;   - Computed goto via jump tables for dispatch
;   - Single-bit speaker toggle for audio synthesis
;   - Interleaved HGR scanline lookup tables to convert Y coordinates
;     to screen memory addresses (required because Apple II HGR memory
;     layout is non-linear — designed for NTSC CRT timing, not for
;     programmer convenience)
;
; ---------------------------------------------------------------------------
; MEMORY MAP
; ---------------------------------------------------------------------------
;
;   $4100-$4134  Zero-page initialization data (Applesoft BASIC stub)
;   $4135-$4210  HGR scanline address tables (lo/hi bytes for 192 rows)
;   $4211-$46B9  Tile sprite graphics data, viewport border graphics,
;                animation tables, jump dispatch table
;   $46BA-$4731  Jump table: 30 JMP instructions routing callers to
;                the subroutines below (stable entry points for ULT3/EXOD)
;   $4732-$4978  Computation: string printing, display primitives,
;                memory copy, BCD display, roster pointer math
;   $49FF-$4CE7  Display: viewport refresh, tile animation, cursor blink,
;                character name display, text window, wind direction
;   $4CE8-$4E3F  Sound: 10-effect SFX dispatcher using Apple II speaker
;   $4E40-$4E84  RNG: 16-byte additive pseudo-random number generator
;
; ---------------------------------------------------------------------------
; FUNCTION DIRECTORY
; ---------------------------------------------------------------------------
;
;   Address  Name                 Purpose
;   -------  ----                 -------
;   $4732    print_inline_str     Print null-terminated text after JSR
;   $4767    scroll_text_up       Scroll text window up one line
;   $47B2    save_text_ptr        Save/restore $FE/$FF across call
;   $4855    draw_hgr_stripe      Draw 8-pixel vertical stripe on HGR
;   $487B    clear_hgr_page       Zero-fill HGR page 1 ($2000-$3FFF)
;   $4893    plot_char_glyph      Render one 7x8 glyph to HGR screen
;   $48D9    swap_tile_frames     Swap tile animation frame pairs
;   $48FF    advance_ptr_128      Add $80 (128) to pointer $FE/$FF
;   $490D    print_digit          Print A as ASCII digit ('0'-'9')
;   $4916    print_bcd_byte       Print BCD byte as 2 decimal digits
;   $4935    calc_roster_ptr      Compute $9500+slot*64 roster address
;   $4955    copy_roster_to_plrs  Copy roster → PLRS active area
;   $496B    copy_plrs_to_roster  Copy PLRS active area → roster
;   $49FF    modulo               A = random() mod N
;   $4A13    update_viewport      Full viewport display refresh
;   $4A26    animate_tiles        Cycle tile animation frames
;   $4A8D    animate_cursor       Cursor blink via HGR XOR
;   $4BCA    setup_char_ptr       $FE/$FF = $4000 + slot*64
;   $4BE4    print_char_name      Print character name centered
;   $4C0C    draw_text_window     Wind direction text display
;   $4CE8    play_sfx             Sound effect dispatcher ($F6-$FF)
;   $4E40    get_random           16-byte additive PRNG
;
; ---------------------------------------------------------------------------
; ZERO-PAGE VARIABLE MAP
; ---------------------------------------------------------------------------
;
; The 6502's zero page ($00-$FF) is the fastest-access memory — instructions
; that reference ZP addresses are 1 byte shorter and 1 cycle faster than
; their absolute counterparts. Apple II games use ZP extensively as a
; register file, since the 6502 has only 3 general-purpose registers (A/X/Y).
;
;   $00/$01    map_cursor_x/y       Current position on world/town map
;   $02/$03    combat_cursor_x/y    Current position on combat grid
;   $0F        animation_slot       Tile animation table offset
;   $10        combat_active_flag   Nonzero = in combat (disables SFX)
;   $11        text_window_mode     Wind direction display index (0-4)
;   $95/$96    sfx_scratch          Sound effect working variables
;   $D0-$D5    display_state        Viewport rendering state
;   $D5        char_slot_id         Character slot for name display
;   $D7        char_name_index      Current byte offset in name string
;   $E1        party_size           Active party member count (1-4)
;   $E6-$E9    party_slots          Roster indices for party members
;   $F0-$F3    temp_work            General scratch registers
;   $F9/$FA    text_cursor_x/y      Text cursor: column/row on screen
;   $FC/$FD    dest_ptr             Destination pointer (copy ops)
;   $FE/$FF    src_ptr / data_ptr   Source/general data pointer
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
; print_inline_str — Print null-terminated string embedded after JSR
; ---------------------------------------------------------------------------
;
;   PURPOSE: Prints a string that is encoded directly in the instruction
;            stream following the JSR that called this routine. This is
;            the most important text output mechanism in Ultima III —
;            used 245 times in ULT3 alone for all game messages.
;
;   CALLING CONVENTION:
;            JSR print_inline_str   ; (or JSR $46BA which jumps here)
;            ASC "HELLO WORLD"      ; high-ASCII text (bit 7 set)
;            DB  $00                ; null terminator
;            ; execution resumes here after printing
;
;   PARAMS:  None explicit. The string data follows the JSR in memory.
;   RETURNS: A,X,Y clobbered. $F9/$FA = updated text cursor position.
;   CALLS:   plot_char_glyph, scroll_text_up
;
;   ALGORITHM — THE RETURN ADDRESS TRICK:
;   When the 6502 executes JSR, it pushes the return address minus one
;   onto the stack (this is a 6502 quirk — it pushes addr-1 because
;   RTS adds 1 before jumping). This routine exploits that by pulling
;   the return address off the stack and using it as a string pointer.
;   After printing all characters, it pushes the updated pointer back
;   onto the stack so RTS resumes execution at the byte AFTER the
;   null terminator — skipping over the string data as if it were a
;   multi-byte instruction.
;
;   This technique was widely used in 6502 games of the era (also seen
;   in Ultima IV, Wizardry, and Apple DOS 3.3's RWTS error handler).
;   It saves 5 bytes per call vs. loading a pointer and calling a
;   separate print routine — critical when you have 245 messages.
;
;   STRING FORMAT:
;   - Characters have bit 7 set (high-ASCII, Apple II convention)
;   - AND #$7F strips the high bit before rendering
;   - $FF = newline (scrolls text window, resets cursor to left edge)
;   - $00 = end of string (execution resumes after this byte)
;
; ---------------------------------------------------------------------------
print_inline_str     pla                  ; Pull return address lo from stack
            sta  $FE             ; $FE/$FF = return addr (points to
            pla                  ;   last byte of JSR instruction,
            sta  $FF             ;   i.e., one byte BEFORE the string)

; --- Main print loop: fetch next character from inline string ---
print_str_loop  ldy  #$00            ; Y=0 for indirect indexed addressing
            inc  $FE             ; Advance pointer to next string byte
            bne  print_str_fetch ; (16-bit increment: inc lo, then
            inc  $FF             ;  inc hi only if lo wrapped to 0)
print_str_fetch  lda  ($FE),Y         ; Fetch next character via pointer
            beq  print_str_done ; $00 = null terminator → done
            cmp  #$FF            ; $FF = newline control code
            beq  print_str_newline
            and  #$7F            ; Strip high bit (Apple II text convention)
            jsr  plot_char_glyph ; Render glyph to HGR screen at ($F9,$FA)
            inc  $F9             ; Advance text cursor column (x += 1)
            jmp  print_str_loop  ; Continue with next character

; --- Handle newline: scroll text area and reset cursor ---
print_str_newline  jsr  scroll_text_up   ; Scroll text window up one line
            lda  #$18            ; Reset cursor to column 24 (left edge
            sta  $F9             ;   of text window, in HGR coordinates)
            lda  #$17            ; Row 23 (bottom of text window)
            sta  $FA
            jmp  print_str_loop  ; Continue printing after the newline

; --- Done: push updated pointer back as return address ---
;   The pointer now points to the null terminator. When we push it
;   and RTS adds 1, execution resumes at the byte AFTER the null —
;   exactly where the caller's code continues.
print_str_done  lda  $FF             ; Push return address hi
            pha
            lda  $FE             ; Push return address lo
            pha
            rts                  ; "Return" to byte after the string

; ---------------------------------------------------------------------------
; scroll_text_up — Scroll the HGR text window up by one line
; ---------------------------------------------------------------------------
;
;   PURPOSE: Scrolls the bottom text area up one text line (8 pixel rows)
;            by copying each HGR scanline upward, then blanks the bottom
;            line with spaces. Called when text output reaches the end of
;            the text window during inline string printing.
;
;   PARAMS:  None. Operates on the text region of HGR page 1.
;   RETURNS: A,X,Y clobbered. $FE/$FF restored from stack.
;            $F9/$FA reset to left edge of bottom text line.
;   CALLS:   print_inline_str (to output blank spaces on cleared line)
;
;   APPLE II HGR MEMORY LAYOUT:
;   The Apple II's HGR screen memory is NOT linear. The 192 scanlines
;   are interleaved across three 1KB groups due to the video hardware's
;   CRT timing design (inherited from Wozniak's original circuit). To
;   scroll, we cannot simply block-copy — we must use the HGR address
;   lookup tables at $4300/$43C0 to find each scanline's memory address.
;
;   The scanline tables work as follows:
;     $4300+X = low byte of HGR address for scanline X
;     $43C0+X = high byte of HGR address for scanline X
;   We copy from scanline X+8 (source, via $4308/$43C8) to scanline X
;   (destination, via $4300/$43C0), shifting everything up by 8 rows
;   (one character height).
;
;   INLINE STRING TRICK FOR BLANK LINE:
;   After scrolling, the bottom row is cleared by calling print_inline_str
;   with 9 embedded $A0 bytes (high-ASCII space). These bytes happen to
;   disassemble as "LDY #$A0" instructions, but they are really string
;   data consumed by the inline string printer. This dual-interpretation
;   is a consequence of the Von Neumann architecture — code and data
;   share the same address space, and the print_inline_str routine reads
;   bytes that would otherwise execute as instructions.
;
; ---------------------------------------------------------------------------
scroll_text_up      lda  $FF             ; Save $FE/$FF on stack (caller's
            pha                  ;   string pointer must be preserved
            lda  $FE             ;   since this routine overwrites
            pha                  ;   $FE/$FF for scanline addressing)
            ldx  #$88            ; Start at scanline index $88 (text area)

; --- Outer loop: iterate scanlines $88..$B7 (text window region) ---
scroll_text_row   ldy  #$18            ; Y=$18: start column for text area
            lda  $4300,X         ; Dest scanline addr lo = hgr_lo[X]
            sta  $FE
            lda  $43C0,X         ; Dest scanline addr hi = hgr_hi[X]
            sta  $FF
            lda  $4308,X         ; Source scanline addr lo = hgr_lo[X+8]
            sta  $FC
            lda  $43C8,X         ; Source scanline addr hi = hgr_hi[X+8]
            sta  $FD

; --- Inner loop: copy 40 bytes (one full HGR scanline = 280 pixels) ---
;   Each HGR byte encodes 7 pixels + 1 palette bit. 40 × 7 = 280 px.
scroll_text_col   lda  ($FC),Y         ; Read pixel byte from source row
            sta  ($FE),Y         ; Write to dest row (8 scanlines up)
            iny
            cpy  #$28            ; 40 ($28) bytes per scanline
            bcc  scroll_text_col

            inx                  ; Next scanline
            cpx  #$B8            ; $B8 = end of text window region
            bcc  scroll_text_row

; --- Clear bottom line: reset cursor and print 9 spaces ---
            lda  #$18            ; Column $18 = left edge of text window
            sta  $F9
            lda  #$17            ; Row $17 = bottom text line
            sta  $FA
            jsr  print_inline_str ; Print inline spaces to clear the line
; --- Inline string: 9 × $A0 (high-ASCII space) + $00 null terminator ---
;   CIDAR disassembles these data bytes as LDY #$A0 instructions,
;   but they are read as string characters by print_inline_str.
;   This is harmless — the code never reaches them as instructions.
            ldy  #$A0            ; \
            ldy  #$A0            ; |
            ldy  #$A0            ; |
            ldy  #$A0            ; |  9 space characters ($A0)
            ldy  #$A0            ; |  filling the cleared text line
            ldy  #$A0            ; |
            ldy  #$A0            ; |
            ldy  #$A0            ; |
            ldy  #$A0            ; /
            brk  #$68            ; $00 = string null terminator

; ---------------------------------------------------------------------------
; save_text_ptr — Restore $FE/$FF from stack
; ---------------------------------------------------------------------------
;   PURPOSE: Companion to scroll_text_up — restores the caller's $FE/$FF
;            pointer from the stack where scroll_text_up saved it.
;            The BRK/$68 sequence above pushes values that this routine
;            then consumes: $68 is PLA opcode, effectively doing PLA+STA.
; ---------------------------------------------------------------------------
save_text_ptr  sta  $FE             ; Restore $FE from A (set by BRK handler)
            pla                  ; Pull saved $FF from stack
            sta  $FF
            rts
; ---------------------------------------------------------------------------
; draw_border_init — Draw the viewport border frame on HGR screen
; ---------------------------------------------------------------------------
;   PURPOSE: Clears HGR page 1 and draws the rectangular border frame
;            that separates the game viewport from the text/status areas.
;            Called once during display initialization. The border uses
;            alternating color stripes to create a visible frame on the
;            Apple II's unique color display.
;
;   APPLE II HGR COLOR MODEL:
;   On the Apple II, HGR color is an artifact of the NTSC video signal.
;   Adjacent pixels produce colors based on their phase alignment with
;   the NTSC color burst. Even-column pixels and odd-column pixels
;   produce different hues. The draw_hgr_stripe routine exploits this
;   by writing $AA (even phase) or $D5 (odd phase) to create colored
;   stripes. The $F1/$F2 scratch variables specify the X,Y position
;   of each stripe segment.
; ---------------------------------------------------------------------------
draw_border_init   jsr  clear_hgr_page  ; Zero-fill HGR page 1 ($2000-$3FFF)
            lda  #$00
            sta  $F2             ; $F2 = row counter

; --- Draw horizontal border lines (top and bottom of viewport) ---
;   For each of 24 rows ($18), draw a stripe at X=0 and X=$17
draw_border_horiz   lda  #$00
            sta  $F1             ; $F1 = column 0 (left border)
            jsr  draw_hgr_stripe
            lda  #$17
            sta  $F1             ; $F1 = column 23 (right border)
            jsr  draw_hgr_stripe
            inc  $F2
            lda  $F2
            cmp  #$18            ; 24 rows complete?
            bcc  draw_border_horiz

; --- Draw vertical border lines (left and right edges) ---
            lda  #$00
            sta  $F1             ; $F1 = starting column

draw_border_vert   lda  #$00
            sta  $F2             ; Row 0 (top edge)
            jsr  draw_hgr_stripe
; --- 7 NOPs: timing padding for consistent visual appearance ---
;   These NOPs ensure the vertical border drawing takes the same
;   number of cycles as the horizontal version, keeping the display
;   update visually smooth. On a 1 MHz 6502, 7 NOPs = 14 cycles.
            nop
            nop
            nop
            nop
            nop
            nop
            nop
            lda  #$17
            sta  $F2             ; Row $17 (bottom edge)
            jsr  draw_hgr_stripe
            inc  $F1             ; Next column
            lda  $F1
            cmp  #$17            ; 23 columns complete?
            bcc  draw_border_vert

; --- Draw bottom status area border (thick divider line) ---
;   The bottom border is 5 stripes thick at rows 0,4,8,12,16
;   for each column, creating a wide horizontal separator between
;   the game viewport and the text status area below it.
            lda  #$17
            sta  $F1             ; Start at column $17

draw_border_bottom   lda  #$00
            sta  $F2
            jsr  draw_hgr_stripe ; Row 0
            lda  #$04
            sta  $F2
            jsr  draw_hgr_stripe ; Row 4
            lda  #$08
            sta  $F2
            jsr  draw_hgr_stripe ; Row 8
            lda  #$0C
            sta  $F2
            jsr  draw_hgr_stripe ; Row 12
            lda  #$10
            sta  $F2
            jsr  draw_hgr_stripe ; Row 16
            inc  $F1             ; Next column
            lda  $F1
            cmp  #$28            ; 40 columns complete?
            bcc  draw_border_bottom

; --- Draw right edge border stripe ---
            lda  #$00
            sta  $F2
            lda  #$27            ; Column $27 = rightmost column (39)
            sta  $F1

draw_border_right   jsr  draw_hgr_stripe
            inc  $F2             ; Next row
            lda  $F2
            cmp  #$11            ; 17 rows complete?
            bcc  draw_border_right
            rts

; ---
            DB      $A2,$08,$BD,$00,$43,$85,$FE,$BD,$C0,$43,$85,$FF,$A0,$16,$A9,$80
            DB      $91,$FE,$88,$D0,$FB,$E8,$E0,$B8,$90,$E8,$60
; ---

; LUMA: epilogue_rts
; XREF: 1 ref (1 jump) from $0046C6
draw_border_done   rts                  ; A=[$00F2] X=$0089 Y=$00A0 ; [SP-35]

; ---------------------------------------------------------------------------
; draw_hgr_stripe — Draw one 8-pixel vertical stripe at ($F1, $F2)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Draws a single colored stripe (8 scanlines tall, 1 byte wide)
;            at the character position specified by $F1 (column) and $F2
;            (row). Used to draw the viewport border frame.
;
;   PARAMS:  $F1 = column position (0-39)
;            $F2 = row position (character row, 0 = top)
;   RETURNS: A,X,Y clobbered. $FE/$FF modified.
;
;   6502 IDIOM — ASL CHAIN (MULTIPLY BY 8):
;   Three ASL A instructions multiply the row number by 8, converting
;   character row coordinates to scanline indices (8 pixels per char).
;   ASL = Arithmetic Shift Left = multiply by 2. Three shifts = ×8.
;   This is the standard 6502 way to multiply by powers of 2, since
;   the processor has no MUL instruction.
;
;   APPLE II HGR COLOR TRICK:
;   The stripe pattern alternates between $AA and $D5 ($AA ^ $7F)
;   based on whether the column is even or odd. On the Apple II,
;   adjacent pixels in HGR mode produce different NTSC color artifacts
;   depending on their horizontal phase. By checking bit 0 of the
;   column (via LSR, which shifts it into the carry flag), the routine
;   selects the appropriate color phase pattern for that column.
;
; ---------------------------------------------------------------------------
draw_hgr_stripe  lda  #$08            ; 8 scanlines per character row
            sta  $F3             ; $F3 = loop counter (rows to draw)
            lda  $F2             ; A = character row number
            asl  a               ; × 2 }
            asl  a               ; × 4 } Row × 8 = scanline index
            asl  a               ; × 8 }
            tax                  ; X = scanline table index
            ldy  $F1             ; Y = column offset (byte position)

; --- Draw 8 scanlines of the stripe ---
draw_stripe_row lda  $4300,X         ; Look up HGR address for this scanline
            sta  $FE
            lda  $43C0,X
            sta  $FF
            tya                  ; Check column parity for color phase
            lsr  a               ; Carry = bit 0 of column number
            lda  #$AA            ; Color pattern A (even-phase pixels)
            bcs  draw_stripe_store ; If odd column, use pattern A as-is
            eor  #$7F            ; If even column, flip to pattern B ($D5)
draw_stripe_store sta  ($FE),Y         ; Write color byte to HGR screen
            inx                  ; Next scanline in the table
            dec  $F3             ; Decrement row counter
draw_stripe_next bne  draw_stripe_row

            rts

; ---------------------------------------------------------------------------
; clear_hgr_page — Zero-fill HGR page 1 ($2000-$3FFF)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Clears the entire HGR display page 1 by writing $00 to all
;            8,192 bytes ($2000-$3FFF). This produces a black screen.
;
;   PARAMS:  None.
;   RETURNS: A=0, X=page hi byte ($40), Y=0. $FE/$FF = $4000 (past end).
;
;   ALGORITHM:
;   Uses a page-at-a-time loop: the inner loop writes 256 bytes (one
;   full memory page) using Y as the index, then the outer loop advances
;   $FF to the next page. This is the standard 6502 pattern for filling
;   large memory regions — Y wraps from $FF to $00 on overflow, which
;   sets the BNE branch to fall through, triggering the page increment.
;
;   HGR PAGE 1 LAYOUT:
;   $2000-$3FFF = 8KB = 32 pages of 256 bytes. Each page contains
;   parts of several non-consecutive scanlines (due to Apple II's
;   interleaved HGR address layout). Clearing the entire range
;   guarantees a clean slate regardless of the interleaving pattern.
;
; ---------------------------------------------------------------------------
clear_hgr_page   lda  #$20            ; Start at $2000 (HGR page 1 base)
            sta  $FF
            lda  #$00
            sta  $FE
            ldy  #$00            ; Y = byte index within page

; --- Inner loop: fill one 256-byte page with zeros ---
clear_hgr_loop sta  ($FE),Y         ; Store $00 at ($FE),Y
            iny                  ; Next byte (wraps $FF → $00)
            bne  clear_hgr_loop  ; Continue until Y wraps to 0

; --- Outer loop: advance to next page until we reach $4000 ---
            inc  $FF             ; Next page ($21, $22, ... $3F)
            ldx  $FF
            cpx  #$40            ; Reached $4000? (past end of HGR)
            bcc  clear_hgr_loop  ; If not, clear next page

            rts

; ---------------------------------------------------------------------------
; plot_char_glyph — Render a 7×8 character glyph to HGR screen
; ---------------------------------------------------------------------------
;
;   PURPOSE: Plots a single character glyph (7 pixels wide × 8 pixels
;            tall) to HGR page 1 at the position specified by the text
;            cursor ($F9 = column, $FA = row). This is the fundamental
;            character rendering routine — all text display in the game
;            ultimately calls this function.
;
;   PARAMS:  A = character code (ASCII value, 0-127 range after AND #$7F)
;   RETURNS: A,X,Y clobbered. Glyph drawn to HGR screen.
;
;   CHARACTER ENCODING:
;   If A >= $60 (lowercase range), it's masked to $1F (5 bits), mapping
;   lowercase letters to the upper portion of the character set. Values
;   below $60 pass through directly. The resulting value is an index
;   into the font/glyph table at $FF00 (the Apple II character generator
;   ROM, mirrored or loaded into RAM).
;
;   SELF-MODIFYING CODE (SMC):
;   This routine uses SMC to patch the target address of STA instructions
;   at runtime. The 6502 has no (abs,Y) addressing mode for STA, so the
;   routine writes the HGR scanline address directly into the STA
;   instruction's operand bytes. Three locations are patched:
;     plot_char_smc_page ($48C0) — HGR page byte
;     plot_char_smc_lo   ($48C2) — HGR address low byte
;     plot_char_smc_hi   ($48C3) — HGR address high byte
;
;   This was a standard 6502 technique when indirect indexed addressing
;   was insufficient or too slow. The tradeoff: faster execution at the
;   cost of code that cannot run from ROM (since it writes to itself).
;   On the Apple II, all game code runs from RAM, so this is acceptable.
;
;   HGR SCANLINE ADVANCE:
;   After drawing each pixel row, the routine advances to the next
;   scanline by adding $80 to the HGR address. In Apple II HGR memory,
;   consecutive scanlines within a character cell are separated by $80
;   bytes (not consecutive). This is because the HGR memory is divided
;   into 8 groups of 3 banks, with $80 bytes between same-group rows.
;   The CLC/ADC #$80/BCC pattern handles the 16-bit addition and page
;   crossing in a cycle-efficient way.
;
; ---------------------------------------------------------------------------
plot_char_glyph   cmp  #$60            ; Lowercase ASCII range?
            bcc  plot_char_clip  ; No — use character code directly
            and  #$1F            ; Yes — mask to 5 bits (0-31)
plot_char_clip sta  $F0             ; $F0 = glyph index in font table
            ldy  $F9             ; Y = column position (X coord)
            ldx  $FA             ; X = row position (Y coord)
            txa
            asl  a               ; } Row × 8 = scanline table index
            asl  a               ; } (ASL chain: ×2, ×4, ×8)
            asl  a               ; }
            sta  $F1             ; $F1 = base scanline index
            lda  #$08
            sta  $F3             ; $F3 = row counter (8 pixel rows)
            lda  #$04            ; } SMC: patch the HGR page byte
            sta  plot_char_smc_page ; } in the STA instruction below

; --- Draw loop: render 8 rows of the glyph ---
plot_char_row ldx  $F1             ; Current scanline table index
            lda  $4300,X         ; } Look up HGR address for this scanline
            sta  plot_char_smc_lo ; } SMC: patch STA operand low byte
            lda  $43C0,X         ; }
            sta  plot_char_smc_hi ; } SMC: patch STA operand high byte
            ldx  $F0             ; X = glyph index
            lda  $FF00,X         ; Read glyph pixel data from font ROM
            sta  $FFFF,Y         ; SMC TARGET: write pixel byte to HGR
; --- Advance HGR pointer to next scanline (+$80 bytes) ---
;   In Apple II HGR, successive scanlines within one character cell are
;   separated by exactly $80 (128) bytes. Adding $80 to the address
;   moves to the next row of the same glyph. If the low byte overflows
;   past $FF, we increment the high byte (page crossing).
            clc
            lda  $48BF           ; SMC TARGET: current HGR addr low byte
            adc  #$80            ; Add $80 to advance one scanline
            sta  $48BF           ; SMC: store updated low byte back
            bcc  plot_char_next  ; No page crossing? Skip hi increment
            inc  plot_char_smc_page ; Page crossed — increment high byte
plot_char_next inc  $F1             ; Next scanline table index
            dec  $F3             ; Decrement row counter
            bne  plot_char_row   ; Loop until all 8 rows drawn

            rts

; ---------------------------------------------------------------------------
; swap_tile_frames — Swap tile animation frame data in sprite memory
; ---------------------------------------------------------------------------
;
;   PURPOSE: Cycles tile animation by swapping pixel data between two
;            animation frames stored in the sprite graphics area ($0800).
;            Each tile has an "A" frame and a "B" frame; this routine
;            exchanges them so the next display refresh shows the
;            alternate frame, creating the illusion of movement (e.g.,
;            water rippling, torches flickering).
;
;   PARAMS:  Y = tile animation slot index (0, $40, $42, $44 for
;                different animation groups: water, fire, cursor, etc.)
;   RETURNS: A,X,Y clobbered. Sprite data modified in place.
;   CALLS:   advance_ptr_128
;
;   ALGORITHM:
;   The sprite data is arranged in pages at $0800. For each tile being
;   animated, the routine walks through the frame data at $0800+Y,
;   $0880+Y, $0900+Y, etc. (128 bytes apart), swapping bytes between
;   the current frame (in X) and the stored frame (in memory). After
;   walking all pages up to $1000, the final value is saved back.
;   Y advances by 1 each iteration; if Y becomes odd (bit 0 set via
;   LSR/BCS), the routine restarts for the paired tile (each animation
;   set covers 2 tiles).
;
; ---------------------------------------------------------------------------
swap_tile_frames lda  #$00            ; $FE/$FF = $0800 (sprite data base)
            sta  $FE
            lda  #$08
            sta  $FF
            ldx  $0F80,Y         ; Load current animation frame byte

; --- Swap loop: exchange frame data through sprite pages ---
swap_tile_loop lda  ($FE),Y         ; Read current sprite byte
            pha                  ; Save it on stack
            txa                  ; Get the "other" frame byte
            sta  ($FE),Y         ; Write it to current position
            pla                  ; Retrieve saved byte
            tax                  ; X = now holds the swapped byte
            jsr  advance_ptr_128 ; Advance pointer by $80 (next page)
            lda  $FF             ; Check if we've reached $1000
            cmp  #$10            ; (page $10 = past sprite area)
            bcc  swap_tile_loop  ; Continue if still in sprite range

; --- Save final swapped value and advance to next tile ---
            txa
            sta  $0800,Y         ; Store final frame byte back
            iny                  ; Next tile in the animation pair
            tya
            lsr  a               ; Check if Y is odd (bit 0 → carry)
            bcs  swap_tile_frames ; If odd, restart for the paired tile

            rts

; ---------------------------------------------------------------------------
; advance_ptr_128 — Add $80 (128) to the 16-bit pointer at $FE/$FF
; ---------------------------------------------------------------------------
;
;   PURPOSE: Utility to advance $FE/$FF by 128 bytes. Used by
;            swap_tile_frames to step through sprite data pages.
;
;   6502 IDIOM — 16-BIT ADDITION:
;   The 6502 has no 16-bit add instruction. To add a value to a 16-bit
;   pointer, we add to the low byte first (with carry clear), then add
;   zero-with-carry to the high byte. The ADC #$00 propagates any carry
;   from the low byte addition, handling page boundary crossing.
;
; ---------------------------------------------------------------------------
advance_ptr_128  clc                  ; Clear carry for addition
            lda  $FE             ; Load pointer low byte
            adc  #$80            ; Add 128 ($80)
            sta  $FE             ; Store updated low byte
            lda  $FF             ; Load pointer high byte
            adc  #$00            ; Add carry (0 or 1 from low byte overflow)
            sta  $FF             ; Store updated high byte
            rts

; ---------------------------------------------------------------------------
; print_digit — Print a single decimal digit (0-9) to HGR screen
; ---------------------------------------------------------------------------
;   PARAMS:  A = digit value (0-9)
;   RETURNS: A clobbered. $F9 incremented (cursor advances right).
;
;   ASCII CONVERSION: Adding $30 converts a binary digit 0-9 to the
;   ASCII character codes '0'-'9' ($30-$39). This is the universal
;   binary-to-ASCII conversion used on every computer since the 1960s.
; ---------------------------------------------------------------------------
print_digit  clc
            adc  #$30            ; Convert digit (0-9) to ASCII ('0'-'9')
            jsr  plot_char_glyph ; Render the digit character
            inc  $F9             ; Advance text cursor right
            rts

; ---------------------------------------------------------------------------
; print_bcd_byte — Print a BCD-encoded byte as two decimal digits
; ---------------------------------------------------------------------------
;   PURPOSE: Displays a Binary Coded Decimal byte as its two-digit
;            decimal representation. BCD stores each decimal digit in
;            a 4-bit nibble: byte $42 displays as "42", not "66".
;
;   PARAMS:  A = BCD value ($00-$99)
;   RETURNS: A clobbered. $F9 advanced by 2 (two digits printed).
;
;   BCD ENCODING IN ULTIMA III:
;   All character stats (STR, DEX, INT, WIS), HP, gold, food, and
;   experience are stored in BCD format. This was a common choice in
;   1980s games because it makes display trivial — no division needed
;   to extract decimal digits. The tradeoff is that arithmetic requires
;   the SED (Set Decimal) flag, and BCD wastes ~17% of the byte range
;   ($9A-$FF are invalid BCD values). For a game where stats rarely
;   exceed 99, BCD is elegant: one byte = two displayable digits.
;
;   ALGORITHM:
;   1. Save original byte to temp ($4934)
;   2. Extract high nibble: AND #$F0, then four LSRs to shift right
;   3. Add $30 to convert to ASCII, print as tens digit
;   4. Reload original byte, extract low nibble: AND #$0F
;   5. Add $30 to convert to ASCII, print as ones digit
;
; ---------------------------------------------------------------------------
print_bcd_byte sta  $4934           ; Save BCD byte to temp storage
            and  #$F0            ; Isolate high nibble (tens digit)
            lsr  a               ; } Shift right 4 positions to get
            lsr  a               ; } the tens digit as a value 0-9
            lsr  a               ; } (LSR = Logical Shift Right)
            lsr  a               ; }
            adc  #$30            ; Convert to ASCII '0'-'9'
            jsr  plot_char_glyph ; Print tens digit
            inc  $F9             ; Advance cursor
            lda  $4934           ; Reload original BCD byte
            and  #$0F            ; Isolate low nibble (ones digit)
            clc
            adc  #$30            ; Convert to ASCII
            jsr  plot_char_glyph ; Print ones digit
            inc  $F9             ; Advance cursor
            rts
            DB      $00          ; Padding byte

; ---------------------------------------------------------------------------
; calc_roster_ptr — Compute roster slot address → $FE/$FF, PLRS addr → $FC/$FD
; ---------------------------------------------------------------------------
;
;   PURPOSE: Given a party member index (X = 0..3), computes two pointers:
;            $FE/$FF = address of that member's roster record ($9500+slot*64)
;            $FC/$FD = address of that member's PLRS record ($4000+X*64)
;
;   PARAMS:  X = party member index (0-3)
;            $E6-$E9 (party_slots) = roster slot IDs for each member
;   RETURNS: $FE/$FF = roster address, $FC/$FD = PLRS address
;            A,X,Y clobbered.
;
;   6502 IDIOM — MULTIPLY BY 64 VIA LSR/ROR:
;   To compute slot * 64, the 6502 programmer uses shift operations:
;     slot * 64 = slot * 256 / 4
;   The value is loaded into A (which represents the high byte of a
;   16-bit value), then LSR A / ROR $FE is done twice, effectively
;   dividing the 16-bit value by 4. Since the roster record was already
;   treated as a ×256 value (in the high byte), this yields ×64.
;   The SBC #$01 before shifting adjusts for 1-based roster slot IDs.
;
;   PLRS ADDRESS:
;   The PLRS (active player records) live at $4000. Each member occupies
;   64 bytes, so the address is $4000 + X * 64. The CLC/ROR/ROR/ROR
;   sequence computes X * 64 by placing X in the top 3 bits of a byte
;   (via 3 right rotations with carry clear), yielding bits 7:6 = X[1:0]
;   times $40, which is stored as the low byte with $40 as high byte.
;
; ---------------------------------------------------------------------------
calc_roster_ptr    lda  #$00
            sta  $FE             ; Clear low byte of roster address
            lda  $E6,X           ; Load roster slot ID for party member X
            sec
            sbc  #$01            ; Adjust to 0-based (slots are 1-based)
            lsr  a               ; } Divide by 4 to convert ×256 to ×64
            ror  $FE             ; } (LSR shifts A right, ROR rotates
            lsr  a               ; }  the carry bit into $FE's high bit)
            ror  $FE             ; }
calc_roster_offset clc
            adc  #$95            ; High byte = $95 + quotient → $9500 base
            sta  $FF             ; $FE/$FF now = $9500 + (slot-1)*64
            lda  #$40            ; PLRS base high byte = $40 ($4000)
            sta  $FD
            txa                  ; A = party member index (0-3)
            clc                  ; Clear carry for the ROR chain
            ror  a               ; } X * 64 computed by rotating the
            ror  a               ; } index into the top bits of a byte:
            ror  a               ; } 3 RORs move bits 1:0 to bits 7:6
            sta  $FC             ; $FC/$FD = $4000 + X*64
            rts

; ---------------------------------------------------------------------------
; copy_roster_to_plrs — Load roster records into active PLRS memory
; ---------------------------------------------------------------------------
;
;   PURPOSE: Copies character records from the roster file (ROST, at
;            $9500) into the active player area (PLRS, at $4000) for
;            all current party members. Called when loading a saved game
;            or entering a new area.
;
;   PARAMS:  $E1 = party_size (1-4)
;            $E6-$E9 = roster slot IDs for each party member
;   RETURNS: All party members' 64-byte records copied to PLRS.
;
;   CHARACTER RECORD SIZE:
;   Each character occupies exactly 64 bytes ($40), containing name,
;   stats, equipment, inventory, and status. See FILE_FORMATS.md for
;   the complete field layout. The 64-byte size was chosen because it
;   is a power of 2, making address computation efficient via shifts.
;
; ---------------------------------------------------------------------------
copy_roster_to_plrs  ldx  $E1             ; X = party_size
            dex                  ; Convert to 0-based index (3..0)
            jsr  calc_roster_ptr ; Compute roster → PLRS addresses
            ldy  #$3F            ; Y = byte offset (63..0, backward copy)
            lda  ($FE),Y         ; Copy one byte: roster → PLRS
            sta  ($FC),Y
            dey                  ; Next byte (counting down)
            bpl  $495D           ; Continue until Y goes negative
            dex                  ; Next party member
            bpl  $4958           ; Continue until all members copied
            rts

; ---------------------------------------------------------------------------
; copy_plrs_to_roster — Save active PLRS records back to roster
; ---------------------------------------------------------------------------
;
;   PURPOSE: The reverse of copy_roster_to_plrs. Copies modified character
;            data from the active PLRS area ($4000) back to the roster
;            ($9500) for all party members. Called when saving the game
;            or before writing to disk.
;
;   PARAMS:  Same as copy_roster_to_plrs.
; ---------------------------------------------------------------------------
copy_plrs_to_roster ldx  $E1             ; X = party_size
            dex                  ; Convert to 0-based index

; --- Outer loop: iterate party members (X = member index) ---
copy_plrs_slot jsr  calc_roster_ptr ; Get addresses for member X
            ldy  #$3F            ; 64 bytes per character record

; --- Inner loop: copy 64 bytes from PLRS ($FC) → roster ($FE) ---
copy_plrs_byte lda  ($FC),Y         ; Read from PLRS (active area)
            sta  ($FE),Y         ; Write to roster (save area)
            dey
            bpl  copy_plrs_byte  ; Continue until Y < 0

            dex                  ; Next party member
            bpl  copy_plrs_slot  ; Continue until all done

            rts

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
; modulo — Return random() mod N
; ---------------------------------------------------------------------------
;
;   PURPOSE: Generates a random number in the range [0, A-1] by getting
;            a random byte and computing it modulo A. Used to select
;            random wind directions for the text window display.
;
;   PARAMS:  A = modulus (divisor)
;   RETURNS: A = random value mod N (also stored in $F3)
;   CALLS:   get_random
;
;   ALGORITHM:
;   Since the 6502 has no division instruction, modulo is computed via
;   repeated subtraction: subtract N from the random value until the
;   result is less than N. This is O(256/N) in the worst case, which
;   is acceptable when N is small (here N=9 for wind directions, so
;   at most ~28 iterations at 1 MHz ≈ 0.3ms).
;
; ---------------------------------------------------------------------------
modulo  sta  $F3             ; Save divisor
            jsr  get_random      ; A = random byte (0-255)

; --- Repeated subtraction loop ---
modulo_loop cmp  $F3             ; Is A < N?
            bcc  modulo_done     ; Yes → done, A is the remainder
            sec
            sbc  $F3             ; No → subtract N and try again
            jmp  modulo_loop

modulo_done cmp  #$00            ; Set flags based on result
            sta  $F3             ; Store result in $F3
            rts
; ---------------------------------------------------------------------------
; update_viewport — Full display refresh cycle
; ---------------------------------------------------------------------------
;   PURPOSE: Called once per game turn to refresh all display components:
;            text window, tile animations, viewport rendering, and the
;            external display hook (at $0230, typically the Mockingboard
;            music driver or a NOP stub).
;
;   This is the main display pipeline — the order matters because tile
;   animation must complete before viewport rendering reads the updated
;   sprite data.
; ---------------------------------------------------------------------------
update_viewport    jsr  draw_text_window ; 1. Update wind direction text
            jsr  animate_tiles   ; 2. Cycle tile animation frames
            jsr  $4A52           ; 3. Render viewport tiles (inline)
            jsr  $4AB0           ; 4. Render viewport overlays (inline)
            jsr  $4B48           ; 5. Render viewport border refresh
            jsr  $0230           ; 6. External hook (music/sound driver)
            rts

; ---------------------------------------------------------------------------
; animate_tiles — Cycle overworld tile animation frames
; ---------------------------------------------------------------------------
;
;   PURPOSE: Advances tile animation by swapping sprite frame data for
;            animated tiles (water, fire, cursor). Uses countdown
;            timers so different tile groups animate at different rates.
;
;   TILE ANIMATION SYSTEM:
;   Ultima III animates tiles by maintaining two copies of each animated
;   tile's pixel data. On each animation tick, the copies are swapped,
;   so the display alternates between frame A and frame B. This creates
;   the illusion of movement (rippling water, flickering torches) using
;   only 8 bytes of sprite data per frame — an efficient approach for
;   the Apple II's limited memory.
;
;   The animation slots are:
;     Y=$00 — Set 1: Water/ocean tiles (animates every 2 ticks)
;     Y=$40 — Set 2: Always animated (fire/torch tiles)
;     Y=$42 — Set 3: Secondary animation (animates every 2 ticks)
;     Y=$44 — Set 4: Tertiary animation (always)
;
; ---------------------------------------------------------------------------
animate_tiles    dec  anim_counter_1  ; Decrement set 1 countdown
            bne  anim_tiles_set2 ; Skip set 1 if counter hasn't reached 0
            lda  #$02            ; Reset counter (animate every 2 turns)
            sta  anim_counter_1
            ldy  #$00            ; Swap animation set 1 (Y=$00)
            jsr  swap_tile_frames
anim_tiles_set2 ldy  #$40            ; Always swap set 2 (Y=$40)
            jsr  swap_tile_frames
            dec  anim_counter_2  ; Decrement set 3 countdown
            bne  anim_tiles_set3 ; Skip if not ready
            lda  #$02
            sta  anim_counter_2
            ldy  #$42            ; Swap animation set 3 (Y=$42)
            jsr  swap_tile_frames
anim_tiles_set3 ldy  #$44            ; Always swap set 4 (Y=$44)
            jsr  swap_tile_frames
            rts

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
; animate_cursor — Blink the player cursor by swapping sprite data
; ---------------------------------------------------------------------------
;
;   PURPOSE: Creates the cursor blink effect by swapping two pairs of
;            bytes in the sprite data area. The cursor alternates between
;            a visible and invisible state by exchanging the pixel data
;            between two locations in HGR memory. This runs on a countdown
;            timer so the blink rate is visually comfortable.
;
;   SPRITE DATA SWAP:
;   The two pairs swapped are at $0916/$0996 and $0917/$0997 — these
;   are within the sprite data tables that define the cursor tile's
;   appearance. Swapping makes the cursor appear to flash on and off.
;
; ---------------------------------------------------------------------------
animate_cursor dec  anim_counter_5   ; Decrement blink timer
            bne  anim_cursor_done ; Not time yet → skip
            lda  #$01            ; Reset timer (blink every frame)
            sta  anim_counter_5
; --- Swap cursor sprite pair 1: $0917 ↔ $0997 ---
            ldx  $0917
            ldy  $0997
            sty  $0917
            stx  $0997
; --- Swap cursor sprite pair 2: $0916 ↔ $0996 ---
            ldx  $0916
            ldy  $0996
            sty  $0916
            stx  $0996
anim_cursor_done rts

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
; setup_char_ptr — Compute PLRS character record address from slot ID
; ---------------------------------------------------------------------------
;
;   PURPOSE: Sets $FE/$FF = $4000 + $D5 * 64, where $D5 is the character
;            slot ID. This points to the character's 64-byte record in
;            the active PLRS area. Used by print_char_name to locate
;            the character's name field.
;
;   PARAMS:  $D5 = character slot ID (0-19)
;   RETURNS: $FE/$FF = character record base address
;
;   6502 IDIOM — MULTIPLY BY 64:
;   Same technique as calc_roster_ptr: place the slot ID in the high
;   byte, then two LSR/ROR pairs divide the 16-bit value by 4,
;   yielding slot × 64. The high byte is then set to $40 (PLRS base).
;
; ---------------------------------------------------------------------------
setup_char_ptr lda  #$00
            sta  $FE             ; Clear low byte
            lda  $D5             ; Load character slot ID
            lsr  a               ; } Divide 16-bit value by 4:
            ror  $FE             ; } slot * 256 / 4 = slot * 64
            lsr  a               ; } (two iterations of LSR A / ROR $FE)
            ror  $FE             ; }
            lda  #$40            ; High byte = $40 (PLRS at $4000)
            sta  $FF
            rts

; ---------------------------------------------------------------------------
; print_char_name — Print character name centered on HGR display
; ---------------------------------------------------------------------------
;
;   PURPOSE: Displays a character's name from their PLRS record,
;            horizontally centered within the display area. Names are
;            null-terminated strings in the first 14 bytes of the
;            character record (max 13 characters + null at offset $0D).
;
;   PARAMS:  $D5 = character slot ID
;   RETURNS: Name displayed on HGR screen at computed position.
;
;   CENTERING ALGORITHM:
;   1. Scan to find the null terminator → Y = name length
;   2. Divide length by 2 (LSR) → half-width
;   3. Subtract from column $1F (center of display) → starting column
;   4. Compute display row from slot ID: $D5 * 4 + 1
;   5. Print each character using plot_char_glyph
;
; ---------------------------------------------------------------------------
print_char_name jsr  setup_char_ptr   ; $FE/$FF → character record
            ldy  #$00            ; Start at first byte of name
            lda  ($FE),Y         ; Check if name is empty
            beq  print_name_done ; Empty name → nothing to print

; --- Find name length by scanning for null terminator ---
find_name_end iny
            lda  ($FE),Y
            bne  find_name_end   ; Continue until null byte found

; --- Center the name horizontally ---
            tya                  ; A = name length
            lsr  a               ; A = half-width (length / 2)
            sta  $F0
            lda  #$1F            ; $1F = center column of display
            sec
            sbc  $F0             ; Starting column = center - half
            sta  $F9             ; Set text cursor X position
            lda  $D5             ; Compute row from slot ID:
            asl  a               ; } $D5 * 4 + 1 gives vertical position
            asl  a               ; } (each character gets 4 rows of space)
            adc  #$01            ; } +1 for spacing
            sta  $FA             ; Set text cursor Y position
            lda  #$00
            sta  $D7             ; $D7 = character index within name

; --- Print loop: render each character of the name ---
print_name_loop jsr  setup_char_ptr   ; Recalculate pointer (may be clobbered)
            ldy  $D7             ; Y = current character offset
            lda  ($FE),Y         ; Load character byte
            beq  print_name_done ; Null terminator → done
            and  #$7F            ; Strip high bit (Apple II convention)
            jsr  plot_char_glyph ; Render glyph to HGR screen
            inc  $F9             ; Advance cursor column
            inc  $D7             ; Next character in name
            jmp  print_name_loop

print_name_done rts

; --- Data region (38 bytes) ---
            DB      $A5,$00,$85,$02,$A5,$01,$85,$03,$4C,$21,$4C,$A5,$03,$85,$FF,$A9
            DB      $00,$A8,$46,$FF,$6A,$46,$FF,$6A,$65,$02,$85,$FE,$18,$A5,$FF,$69
            DB      $10,$85,$FF,$B1,$FE,$60
; --- End data region (38 bytes) ---


; ---------------------------------------------------------------------------
; draw_text_window — Display wind direction in the text status area
; ---------------------------------------------------------------------------
;
;   PURPOSE: Shows the current wind direction ("NORTH WIND", "SOUTH WIND",
;            etc.) in the HGR text area. The wind direction changes
;            periodically on a countdown timer, selecting a new random
;            direction via the modulo function.
;
;   GAME DESIGN CONTEXT:
;   Wind direction affects ship movement in Ultima III. When sailing,
;   the wind determines which directions are easy (with the wind) vs.
;   hard (against the wind) to travel. The text window shows the current
;   wind to help the player plan navigation. The wind changes randomly
;   every 8 display refreshes.
;
;   SELF-MODIFYING CODE:
;   text_wind_counter is a self-modifying operand embedded in the code
;   stream — the STA instruction writes to the immediate operand of a
;   later CMP instruction, effectively using the instruction stream as
;   a timer variable. This saves a byte vs. using a separate data
;   location, a common 6502 space optimization.
;
;   WIND DIRECTION ENCODING ($11):
;   0 = calm (no wind), 1-4 = N/E/S/W directional winds.
;   The modulo generates values 0-8, with 0-4 used directly and 5-8
;   remapped to 1-4 (doubling the chance of directional vs. calm wind).
;
;   Each direction is displayed via an inline string containing the
;   direction name followed by " WIND" in high-ASCII.
;
; ---------------------------------------------------------------------------
draw_text_window  dec  text_wind_counter ; Decrement update timer
            bpl  text_wind_show  ; Timer >= 0? Just redisplay current wind
            lda  #$08            ; Reset timer to 8 (change wind every 8th call)
            sta  text_wind_counter ; SMC: writes into instruction operand

; --- Select new random wind direction ---
;   Generate random(9): values 0-4 used directly, 5-8 → 1-4.
;   Reroll if result equals current wind (prevent "no change" flicker).
text_wind_rng lda  #$09            ; Modulus = 9
            jsr  modulo          ; A = random(0..8)
            cmp  #$05            ; Value in directional range (5-8)?
            bcc  text_wind_set   ; No (0-4) → use as-is
            sec
            sbc  #$04            ; Map 5→1, 6→2, 7→3, 8→4
            cmp  $11             ; Same as current wind?
            beq  text_wind_rng   ; Yes → reroll to ensure change

text_wind_set sta  $11             ; Store new wind direction
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
; play_sfx — Sound effect dispatcher (10 effects, $F6-$FF)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Plays one of 10 sound effects using the Apple II's built-in
;            speaker. The effect ID is passed in A and dispatched via a
;            CMP chain to the appropriate synthesis routine.
;
;   PARAMS:  A = sound effect ID ($F6-$FF). Values outside this range
;                are silently ignored (no effect played).
;   RETURNS: A,X,Y clobbered.
;
;   COMBAT MUTE:
;   If $10 (combat_active_flag) is nonzero, all sound effects are
;   suppressed. This prevents audio from interfering with the combat
;   system's timing-sensitive animation loops.
;
;   APPLE II SPEAKER HARDWARE:
;   The Apple II has a single-bit speaker controlled by reading address
;   $C030 (SPKR). Each read toggles the speaker cone between its two
;   positions. To produce a tone, the program toggles the speaker at
;   a specific rate — faster toggling = higher pitch. The speaker is
;   the ONLY native audio output; there is no DAC, no volume control,
;   and no hardware tone generator. All sound synthesis is done in
;   software via carefully timed CPU loops. At 1 MHz, the maximum
;   achievable frequency is ~500 kHz (toggle every other cycle), but
;   the speaker's mechanical response limits useful output to ~20 kHz.
;
;   EFFECT TABLE:
;     $FF = sfx_beep_hi     — Short high-pitched beep (menu select)
;     $FE = sfx_beep_lo     — Longer low-pitched beep (text display)
;     $FD = sfx_sweep       — Frequency sweep up then down (spell cast)
;     $FC = sfx_noise       — Random noise burst (combat hit)
;     $FB = sfx_buzz        — Descending buzz (damage taken)
;     $FA = sfx_chirp       — Rising chirp (item pickup)
;     $F9 = sfx_sweep_alt   — Alternate sweep parameters (spell variant)
;     $F8 = sfx_descend     — Descending tone (falling/dungeon)
;     $F7 = sfx_ascend      — Ascending tone with echo (level up)
;     $F6 = sfx_short_desc  — Short descending tone (minor event)
;
; ---------------------------------------------------------------------------
play_sfx  sta  $F0             ; Save effect ID
            lda  $10             ; Check combat_active_flag
            beq  sfx_dispatch    ; Zero = not in combat, allow SFX
            rts                  ; Nonzero = in combat, mute all SFX

; --- Dispatch chain: compare A against each effect ID ---
;   This cascading CMP/BNE pattern is the 6502 equivalent of a switch
;   statement. A jump table would be more compact for 10 cases, but
;   the IDs are sequential from $F6-$FF, so the chain is simple.
sfx_dispatch  lda  $F0             ; Reload effect ID
            cmp  #$FF
            bne  sfx_check_FE
            jmp  sfx_beep_hi     ; → High beep
sfx_check_FE  cmp  #$FE
            bne  sfx_check_FD
            jmp  sfx_beep_lo     ; → Low beep
sfx_check_FD  cmp  #$FD
            bne  sfx_check_FC
            jmp  sfx_sweep       ; → Frequency sweep
sfx_check_FC  cmp  #$FC
            bne  sfx_check_FB
            jmp  sfx_noise       ; → Random noise
sfx_check_FB  cmp  #$FB
            bne  sfx_check_FA
            jmp  sfx_buzz        ; → Buzz
sfx_check_FA  cmp  #$FA
            bne  sfx_check_F9
            jmp  sfx_chirp       ; → Chirp
sfx_check_F9  cmp  #$F9
            bne  sfx_check_F8
            jmp  sfx_sweep_alt   ; → Alternate sweep
sfx_check_F8  cmp  #$F8
            bne  sfx_check_F7
            jmp  sfx_descend     ; → Descending tone
sfx_check_F7  cmp  #$F7
            bne  sfx_check_F6
            jmp  sfx_ascend      ; → Ascending tone
sfx_check_F6  cmp  #$F6
            bne  sfx_return
            jmp  sfx_short_desc  ; → Short descending
sfx_return  rts                  ; Unknown ID → no effect
; ---------------------------------------------------------------------------
; SOUND EFFECT IMPLEMENTATIONS
; ---------------------------------------------------------------------------
;
;   All sound effects work by toggling the Apple II speaker ($C030) at
;   controlled intervals. The speaker is a 1-bit output — each BIT $C030
;   instruction toggles the speaker cone. The audible pitch depends on
;   how frequently the toggle occurs, which is controlled by delay loops.
;
;   The Apple II Monitor ROM provides a WAIT routine at $FCA8 that delays
;   for approximately (26 + 27*A + 5*A*A)/2 cycles. This is used by the
;   beep effects to control the half-period between speaker toggles.
;
;   HISTORICAL NOTE:
;   This "1-bit audio" technique was universal on the Apple II because
;   there was literally no other way to make sound. The same approach
;   was used by every Apple II game from 1977 to 1993. The Mockingboard
;   sound card (optional, supported by Ultima III) provided hardware
;   tone generators, but the built-in speaker effects here serve as
;   the fallback for systems without a Mockingboard.
;
; ---------------------------------------------------------------------------

; --- sfx_beep_hi ($FF): Short high-pitched beep ---
;   16 cycles of speaker toggle with delay=$30 between each.
;   Produces a brief "tick" sound at ~2 kHz. Used for menu selections.
sfx_beep_hi  ldy  #$10            ; 16 toggle cycles

sfx_beep_hi_loop  lda  #$30            ; Delay value → ~530 cycle wait
            jsr  $FCA8           ; Apple II Monitor WAIT routine
            bit  $C030           ; Toggle speaker (SPKR soft switch)
            dey
            bne  sfx_beep_hi_loop

            rts

; --- sfx_beep_lo ($FE): Longer low-pitched beep ---
;   48 cycles with delay=$18. Lower frequency, longer duration.
;   Used for text display confirmation and general UI feedback.
sfx_beep_lo  ldy  #$30            ; 48 toggle cycles

sfx_beep_lo_loop  lda  #$18            ; Shorter delay → lower pitch
            jsr  $FCA8           ; WAIT
            bit  $C030           ; Toggle speaker
            dey
            bne  sfx_beep_lo_loop

            rts

; --- sfx_sweep ($FD): Frequency sweep up then down ---
;   Two-phase sweep: first sweeps UP (period_1 decreasing, period_2
;   increasing), then sweeps DOWN (reverse). Creates a classic "zap"
;   or "spell cast" sound. The asymmetric half-periods produce a
;   waveform that sounds like a rising then falling pitch.
;
;   PARAMS (via registers):
;     X = initial period for half 1 (default $C0 from sfx_save_x)
;     Y = duration multiplier (number of cycles per sweep step)
;
sfx_sweep  stx  sfx_save_x      ; Save initial sweep parameters
            sty  sfx_duration
            lda  sfx_save_x
            sta  sfx_period_1    ; Period for first half of waveform
            lda  #$01
            sta  sfx_period_2    ; Period for second half (starts short)

; --- Phase 1: sweep frequency UP (period_1 shrinks, period_2 grows) ---
sfx_sweep_outer  lda  sfx_duration     ; Duration cycles per step
            sta  $F3             ; $F3 = inner loop counter

sfx_sweep_half1  ldx  sfx_period_1     ; X = delay for first half-cycle
sfx_sweep_wait1  dex                  ; Burn cycles proportional to period
            bne  sfx_sweep_wait1
            bit  $C030           ; Toggle speaker (first half-period)
            ldx  sfx_period_2     ; X = delay for second half-cycle
sfx_sweep_wait2  dex
            bne  sfx_sweep_wait2
            bit  $C030           ; Toggle speaker (second half-period)
            dec  $F3             ; Repeat for duration cycles
            bne  sfx_sweep_half1
; --- Adjust sweep: shorten half 1, lengthen half 2 → pitch rises ---
            dec  sfx_period_1
            inc  sfx_period_2
            lda  sfx_period_2
            cmp  #$1B            ; Sweep until period_2 reaches $1B
            bne  sfx_sweep_outer

; --- Phase 2: sweep frequency DOWN (reverse of phase 1) ---
sfx_sweep_dn_outer  lda  sfx_duration
            sta  $F3

sfx_sweep_dn_half1  ldx  sfx_period_1
sfx_sweep_dn_wait1  dex
            bne  sfx_sweep_dn_wait1
            bit  $C030           ; Toggle speaker
            ldx  sfx_period_2
sfx_sweep_dn_wait2  dex
            bne  sfx_sweep_dn_wait2
            bit  $C030           ; Toggle speaker
            dec  $F3
            bne  sfx_sweep_dn_half1
; --- Reverse sweep: lengthen half 1, shorten half 2 → pitch falls ---
            dec  sfx_period_2
            inc  sfx_period_1
            lda  sfx_period_2
            cmp  #$00            ; Sweep until period_2 reaches 0
            bne  sfx_sweep_dn_outer
            rts
sfx_save_x
            DB      $C0
sfx_duration
            DB      $10
sfx_period_1
            DB      $FB
sfx_period_2
            DB      $2C
; --- sfx_noise ($FC): Random noise burst ---
;   Produces white noise by toggling the speaker at random intervals.
;   Each iteration gets a random value (0-15), adds a base delay ($F3),
;   and uses that as the half-period. The randomized timing creates an
;   aperiodic waveform that sounds like static or an explosion.
;
;   The PHA/PLA pairs in the delay loop are NOT redundant — they burn
;   exactly 7 cycles each (3 PHA + 4 PLA), providing fine-grained
;   timing control. This is a standard 6502 idiom for cycle-precise
;   delays without consuming registers: push-pull pairs add a known
;   fixed delay per iteration. Here, each DEX loop iteration takes
;   7+7+2+3 = 19 cycles, giving precise control over the noise
;   character by adjusting X.
;
;   PARAMS:  $F3 = base delay (saved from X on entry)
;            $D4 = duration counter (128 toggles)
;
sfx_noise  stx  $F3             ; Save base delay parameter
            lda  #$80            ; 128 speaker toggles
            sta  $D4             ; Duration counter

sfx_noise_loop  jsr  get_random       ; Get random value (0-255)
            and  #$0F            ; Mask to 0-15
            adc  $F3             ; Add base delay → randomized period
            tax                  ; X = delay loop count

sfx_noise_delay  pha                  ; } PHA/PLA burn 7 cycles per pair —
            pla                  ; } this is a 6502 timing idiom, not
            pha                  ; } dead code. Two pairs = 14 cycles
            pla                  ; } added per inner loop iteration.
            dex                  ; Decrement delay counter
            bne  sfx_noise_delay ; Loop until delay exhausted
            bit  $C030           ; Toggle speaker
            dec  $D4             ; Decrement duration
            bne  sfx_noise_loop  ; Next noise burst
            rts
; --- sfx_buzz ($FB): Descending buzz ---
;   Produces a buzzing tone that descends in pitch until silence.
;   The inner loop counts X from 0→255 (256 iterations = ~1.3ms at
;   1 MHz), then toggles the speaker. $95 is both the outer duration
;   counter AND the reload value for X — as $95 decreases, the period
;   gets shorter (pitch rises briefly) then wraps, creating a complex
;   descending buzz texture.
;
;   Actually, the clever part: $95 starts at whatever A was on entry
;   (the saved effect ID), then counts down. Each outer loop reloads
;   X from $95, so as the outer counter shrinks, the inner delay also
;   shrinks → the pitch rises as the sound fades out, creating an
;   characteristic "damage taken" buzz-squeal.
;
sfx_buzz  ldx  #$00            ; Inner delay starts at 0 (wraps to 256)
            sta  $95             ; Duration AND pitch parameter

sfx_buzz_loop  inx                  ; } Count X from 0→255 (256 cycles)
            bne  sfx_buzz_loop   ; } ~1280 cycles = ~1.3ms delay
            bit  $C030           ; Toggle speaker
            dec  $95             ; Decrease duration AND next period
            ldx  $95             ; Reload inner count from shrinking outer
            bne  sfx_buzz_loop   ; Continue until $95 reaches zero
            rts
; --- sfx_chirp ($FA): Rising chirp ---
;   Produces a chirp that rises in pitch. Y serves as both the outer
;   loop counter (total duration) and the source for X (inner delay).
;   Each outer iteration: X=Y, count down X to 0, toggle speaker,
;   then DEY. Since Y decreases each time, the inner delay shrinks
;   → the period shortens → pitch rises. The chirp starts at ~160
;   cycles per half-period (~3.1 kHz) and sweeps up to maximum speed.
;
;   This is the inverse of sfx_buzz: buzz descends, chirp ascends.
;   Used for item pickup, positive feedback events.
;
sfx_chirp  ldx  #$A0            ; Starting period = $A0 (160 decimal)
            txa                  ; Copy to A
            tay                  ; Y = duration counter AND delay source

sfx_chirp_loop  dex                  ; } Count down inner delay
            bne  sfx_chirp_loop  ; } (X iterations × 5 cycles each)
            bit  $C030           ; Toggle speaker
            dey                  ; Decrease outer counter
            tya                  ; } Copy Y → X for next inner delay
            tax                  ; } (shrinking Y = shrinking delay = rising pitch)
            bne  sfx_chirp_loop  ; Continue until Y reaches zero
            rts
; --- sfx_sweep_alt ($F9): Alternate frequency sweep ---
;   Reuses the sfx_sweep engine with different starting parameters:
;   X=$E0 (wider initial period) and Y=$06 (shorter duration per step).
;   This produces a deeper, faster sweep compared to sfx_sweep's
;   default X=$C0/Y=$10. Used for spell variant sounds.
;
sfx_sweep_alt  ldx  #$E0            ; Wider starting period than default $C0
            ldy  #$06            ; Faster sweep (fewer cycles per step)
            jmp  sfx_sweep       ; Reuse sweep engine with new params
; --- sfx_descend ($F8): Descending tone with random jitter ---
;   Produces a descending tone from high to low pitch with random
;   variation in each cycle. The period starts at $E0 and decreases
;   toward $40, with each half-period augmented by a random value
;   (ORA with $96 ensures the random bits only ADD to the base delay,
;   never reduce it). This creates an organic, slightly noisy descent.
;
;   $95 = floor (stop when period reaches this value)
;   $96 = current base period (decreasing → pitch RISES, but the name
;         "descend" refers to the pitch contour from high randomized
;         values down to the floor)
;
sfx_descend  lda  #$40            ; Stop threshold (minimum period)
            sta  $95
            lda  #$E0            ; Starting period (long = low pitch)
            sta  $96

sfx_descend_loop  jsr  get_random       ; Get random value
            ora  $96             ; Merge with base period (adds jitter)
            tax                  ; X = jittered delay count

sfx_descend_wait  dex                  ; } Count down delay
            bne  sfx_descend_wait ; }
            bit  $C030           ; Toggle speaker
            dec  $96             ; Shorten base period (raise pitch)
            lda  $96
            cmp  $95             ; Reached floor?
            bcs  sfx_descend_loop ; No → continue descending
            rts
; --- sfx_ascend ($F7): Ascending tone with jitter ---
;   Shares the sfx_rise_fall_loop engine with sfx_short_desc, but with
;   different parameters: $95=255 (long duration), $96=0 (start silent).
;   The random ORA with an increasing $96... wait — $95 is the COUNTER
;   and $96 is the base period. With $96=$00, ORA produces pure random
;   values, creating a noise-like ascending texture (255 toggles).
;   Used for level-up or ascending effects.
;
sfx_ascend  lda  #$FF            ; 255 toggles (long duration)
            sta  $95
            lda  #$00            ; Base period = 0 (pure random timing)
            sta  $96
            jmp  sfx_rise_fall_loop

; --- sfx_short_desc ($F6): Short descending tone ---
;   Same engine as sfx_ascend but with only 8 toggles ($95=$08).
;   Very brief sound — a quick "blip" for minor events.
;
sfx_short_desc  lda  #$08            ; Only 8 toggles (very short)
            sta  $95
            lda  #$00            ; Base period = 0 (pure random timing)
            sta  $96

; --- Shared rise/fall engine ---
;   Used by both sfx_ascend and sfx_short_desc. Each iteration:
;   1. Get random value, OR with base period ($96)
;   2. Use result as delay → toggle speaker
;   3. Decrement duration counter ($95)
;   The random component creates organic, non-mechanical sound.
;
sfx_rise_fall_loop  jsr  get_random       ; Random value (0-255)
            ora  $96             ; Merge with base period
            tax                  ; X = delay count

sfx_rise_fall_wait  dex                  ; } Count down delay
            bne  sfx_rise_fall_wait ; }
            bit  $C030           ; Toggle speaker
            dec  $95             ; Decrement duration
            bne  sfx_rise_fall_loop ; Continue until zero
            rts

; ---------------------------------------------------------------------------
; get_random — 16-byte additive pseudo-random number generator
; ---------------------------------------------------------------------------
;
;   PURPOSE: Returns a pseudo-random byte in A. Used by the sound effects
;            (noise, descend, rise/fall) and by the modulo function for
;            game-wide randomness (wind direction, combat rolls, etc.).
;
;   PARAMS:  None (reads/writes internal state at $4E61-$4E70)
;   RETURNS: A = pseudo-random byte
;            X preserved (saved on stack), Y preserved
;
;   ALGORITHM — ADDITIVE CONGRUENTIAL GENERATOR:
;   The RNG maintains a 16-byte state vector at $4E61-$4E70. Each call:
;
;   Phase 1 (Mixing): Starting with the last byte ($4E70) as a seed,
;   add it cascading through the state array: state[i] += accumulator,
;   where the accumulator carries forward (no CLC between iterations,
;   so overflow bits propagate). This creates avalanche diffusion —
;   each byte affects all subsequent bytes.
;
;   Phase 2 (Increment): Scan from the end of the array, incrementing
;   each byte. Stop as soon as one doesn't wrap to zero (carry-chain
;   increment of a 16-byte counter). This ensures the state never
;   gets stuck in an all-zeros cycle.
;
;   The output is state[0] ($4E61), giving decent 8-bit randomness
;   for game purposes. This is NOT cryptographically secure, but it's
;   more than adequate for a 1983 RPG. The 16-byte state provides
;   a period of approximately 2^128 before repeating.
;
;   HISTORICAL CONTEXT:
;   This is a variant of the "lagged Fibonacci" generator, a class of
;   PRNGs popular in the 1970s-80s because they require only addition
;   (no multiplication), making them fast on 8-bit CPUs. The cascading
;   add with carry propagation is a clever way to get mixing across
;   the entire state vector in a single pass.
;
; ---------------------------------------------------------------------------
get_random   txa                  ; Save X on stack (will be restored)
            pha
            clc                  ; Clear carry for first addition
            ldx  #$0E            ; Start at state[14] (second-to-last)
            lda  $4E70           ; Load state[15] as initial seed/accumulator

; --- Phase 1: Cascading addition (mixing pass) ---
;   Add accumulator into each state byte from [14] down to [0].
;   Carry propagates naturally between iterations, creating
;   cross-byte diffusion. After 15 iterations every byte in the
;   state has been influenced by the seed.
rng_add_loop adc  $4E61,X         ; accumulator += state[X]
            sta  $4E61,X         ; state[X] = accumulated sum
            dex                  ; Move to previous byte
            bpl  rng_add_loop    ; Continue through state[0]

; --- Phase 2: Increment the state (prevent stuck-at-zero) ---
;   Increment state bytes from [15] downward. Stop as soon as a
;   byte doesn't overflow to zero. This is equivalent to adding 1
;   to a 128-bit integer stored little-endian, ensuring the state
;   vector always changes between calls.
            ldx  #$0F            ; Start at state[15]

rng_inc_loop inc  $4E61,X         ; Increment state[X]
            bne  rng_done        ; Didn't wrap to zero → done
            dex                  ; Wrapped → carry to next byte
            bpl  rng_inc_loop    ; Continue through entire state

rng_done pla                  ; Restore X from stack
            tax
            lda  $4E61           ; Return state[0] as random byte
            rts

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
