; ===========================================================================
; ULT3.s — Ultima III: Exodus Main Game Engine
; ===========================================================================
;
; HISTORICAL CONTEXT:
;   This is the main engine binary for Ultima III: Exodus, released by
;   Origin Systems in 1983 for the Apple II. At 17,408 bytes ($5000-$93FF),
;   it implements the complete RPG game loop: overworld exploration, town
;   navigation, dungeon crawling, tactical combat, magic, equipment, shops,
;   NPC dialog, file I/O, and rendering — all in 6502 assembly.
;
;   The engine was written by Dr. Kenneth W. Arnold under contract to
;   Richard Garriott (Lord British). Ultima III was the first game in the
;   series to feature a party-based combat system on a tactical grid,
;   moving beyond the single-character model of Ultima I and II. This
;   file contains the implementation of that system.
;
;   The code is organized as a monolithic state machine: the game_main_loop
;   at $65B0 polls for keyboard input, dispatches to command handlers, and
;   processes turns. There is no operating system, no memory allocator, no
;   interrupt-driven I/O. The program owns the entire machine.
;
; ARCHITECTURE:
;   17,408 bytes loaded at $5000 via ProDOS BLOAD.
;   68% executable code, 32% inline string data and name tables.
;   245 inline strings embedded via JSR $46BA (SUBS print_inline_str).
;   The inline strings serve as primary documentation of function purpose.
;   Reassembled byte-identical from CIDAR disassembly via asmiigs.
;
; CODE/DATA INTERLEAVING:
;   Unlike modern binaries with separate text/data sections, 6502 code
;   freely intermixes executable instructions with inline data. The JSR
;   $46BA inline string printer reads bytes AFTER the JSR instruction as
;   string data, advancing the return address past the string. CIDAR's
;   disassembler cannot always distinguish these data bytes from code,
;   so many "instructions" in this listing are actually high-ASCII text
;   being misinterpreted. Data regions are marked with --- Data region ---
;   comments where identified.
;
; MEMORY MAP:
;   $0000-$00FF  Zero page — fast-access variables (see below)
;   $0100-$01FF  6502 hardware stack
;   $0200-$03FF  ProDOS/Monitor scratch area, BLOAD command buffers
;   $0400-$07FF  Apple II text page 1 (40×24 text, not used in HGR mode)
;   $0800-$0FFF  Sprite data tables, animation buffers
;   $1000-$1FFF  Map viewport data, tile caches
;   $2000-$3FFF  HGR page 1 (280×192 pixels, primary display)
;   $4000-$40FF  PLRS — active character records (4 × 64 bytes)
;   $4100-$4EFF  SUBS — shared subroutine library
;   $4F00-$4FFF  Runtime creature tracking (5 × 32-entry arrays)
;   $5000-$93FF  ULT3 — THIS FILE (main engine)
;   $9900-$99BF  CON — active combat map (192 bytes)
;   $B400-$B7FF  ProDOS file I/O buffer area
;
; SUBSYSTEM DIRECTORY:
;   $5000-$54FF  Boot/Init — file loading, game setup, quit handler
;   $5506-$58E8  Character Records — XOR decrypt/encrypt, field access
;   $58E9-$5C62  Character Read — stat lookup, class validation
;   $5C63-$6457  Character Write — BCD arithmetic, combat turn processing
;   $6458-$65AF  File I/O — BSAVE/BLOAD PLRS, PRTY, overlays
;   $65B0-$6F42  Game Main Loop — central state machine, input dispatch
;   $6F43-$7086  Location Logic — location type checks, world transitions
;   $7087-$71FF  Combat Math — BCD multiply, damage, HP management
;   $7200-$731F  Combat End — victory/defeat, XOR checksum
;   $7320-$7445  Status Display — party status, cursor save/restore
;   $7446-$746F  Keyboard Input — key polling, input wait
;   $7470-$75AD  Turn Processing — move resolution, MP regen, poison
;   $75AE-$761C  Magic System — spell casting, MP checks, effects
;   $761D-$772C  Equipment — weapon/armor handling, class restrictions
;   $772D-$79FF  Shops — buy/sell transactions, gold management
;   $7961-$7A80  Overworld Movement — surface navigation, ship boarding
;   $7A0C-$7C0B  Dungeon System — level navigation, torch light
;   $7C0C-$7DFF  Tile Logic — passability, special tiles, map I/O
;   $7E00-$88FF  Rendering — viewport, combat sprites, animation
;   $897A-$8CFF  Name Table — 921 bytes, all entity names (high-ASCII)
;   $93DE        HGR Math — scanline address computation
;
; FORWARD REFERENCES (EQU, mid-instruction entry points):
;   These are addresses referenced BEFORE they appear in the linear code.
;   The assembler needs EQU directives to resolve them. Several enter
;   mid-instruction — the bytes at those addresses have dual meaning
;   depending on entry point (a common 6502 size optimization trick).
;
;   $5882  input_return_to_loop    Return from input to main loop
;   $658D  game_loop_vblank        VBlank sync point
;   $65B0  game_main_loop          Central state machine entry
;   $71F6  combat_dead_xor_addr    Death state XOR address
;   $746E  input_wait_restore_y    Input wait Y register restore
;   $7CFC  tile_lookup_data        Combat tile lookup table
;   $882D  render_party_drop_jmp   Party render jump point
;   $882F  render_animate          Animation frame handler
;   $8880  render_party_exit       Party render exit point
;
; ZERO-PAGE VARIABLE MAP:
;   The 6502's zero page ($00-$FF) provides 256 bytes of fast-access
;   storage with shorter instruction encoding (2 bytes vs. 3 for absolute
;   addressing). ULT3 uses it as a register file for game state:
;
;   $00/$01    map_cursor_x/y        Current position on overworld/town map
;   $02/$03    combat_cursor_x/y     Position on 11×11 combat grid
;   $0A-$0D    direction_flags       Passability flags for N/S/E/W
;   $0E        transport_type        Movement mode (foot/horse/ship/raft)
;   $0F        animation_slot        Tile animation table offset
;   $10        combat_active_flag    Nonzero suppresses SFX during combat
;   $11        wind_direction        Current wind (0=calm, 1-4=N/E/S/W)
;   $13        dungeon_level         Current dungeon depth (0-7)
;   $36/$37    checksum_lo/hi        Anti-cheat XOR checksum
;   $95/$96    scratch_pair          Temporary calculation storage
;   $B0-$B2    disk_io_flags         ProDOS disk I/O state machine
;   $CB        light_timer           Torch/light duration counter
;   $CC        special_timer         Special effect countdown
;   $CD        target_index          Combat target selection
;   $CE        current_tile          Tile ID at player position
;   $D0        command_state         Current command/action being processed
;   $D1/$D2    calc_scratch          Multi-byte calculation workspace
;   $D5        char_slot_id          Active character slot (0-19)
;   $D6        saved_slot_id         Saved slot during nested operations
;   $D7        spell_id              Current spell being cast
;   $E0-$E9    PRTY mirror           Party state (see PRTY format in MEMORY)
;   $F0-$F3    temp_work             General scratch registers
;   $F5/$F6    distance_calc         Distance computation workspace
;   $F9/$FA    text_cursor_x/y       Text output cursor position
;   $FB        effect_counter        Visual effect countdown
;   $FC/$FD    alt_pointer           Secondary data pointer
;   $FE/$FF    data_pointer          Primary data pointer (character records)
;
; === Optimization Hints Report ===
; Total hints: 31
; Estimated savings: 70 cycles/bytes

; Address   Type              Priority  Savings  Description
; ---------------------------------------------------------------
; $006F69   PEEPHOLE          MEDIUM    4        Load after store: 2 byte pattern at $006F69
; $006F7C   PEEPHOLE          MEDIUM    4        Load after store: 2 byte pattern at $006F7C
; $0077AE   PEEPHOLE          MEDIUM    7        Redundant PHA/PLA: 2 byte pattern at $0077AE
; $007B4A   REDUNDANT_LOAD    MEDIUM    3        Redundant LDA: same value loaded at $007B3F
; $005896   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $005897   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $005C86   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $005C87   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $007A3B   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $007E08   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $007E1B   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $007E1C   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $00879C   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $00879D   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $00879E   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0088BF   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0088C0   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0088C1   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0088C2   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0088E6   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0088E7   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0088E8   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0088E9   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0093E1   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0093E2   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $0093E3   STRENGTH_RED      LOW       1        Multiple ASL A: consider using lookup table for render_encrypt_records
; $005C90   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $005C90 followed by RTS
; $0074B0   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $0074B0 followed by RTS
; $007728   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $007728 followed by RTS
; $007993   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $007993 followed by RTS
; $008476   TAIL_CALL         HIGH      6        Tail call: JSR/JSL at $008476 followed by RTS

; Loop Analysis Report
; ====================
; Total loops: 175
;   for:       0
;   while:     169
;   do-while:  0
;   infinite:  0
;   counted:   6
; Max nesting: 34
;
; Detected Loops:
;   Header    Tail      Type      Nest  Counter
;   ------    ----      ----      ----  -------
;   $005E60   $005F53   while       15  Y: 0 step 1
;   $0071F4   $0071F8   while       29  -
;   $0071B8   $0071C9   while       28  -
;   $007320   $007338   while       28  -
;   $007350   $00741A   while       33  Y: 0 step 1
;   $00732D   $00741D   while       27  Y: 0 step 1
;   $007229   $00734D   while       27  -
;   $0050B3   $0050BE   while        3  -
;   $006E35   $006E43   while       14  -
;   $00746D   $007477   while       32  -
;   $00715F   $0074F8   while       13  Y: 0 step 1
;   $007166   $00716A   while       19  -
;   $00716F   $0074FC   while       16  Y: 0 step 1
;   $007178   $00717D   while       24  -
;   $00715F   $007521   while       13  Y: 0 step 1
;   $00716F   $007525   while       15  Y: 0 step 1
;   $0071EB   $0075A2   while       16  Y: 0 step 1
;   $007586   $0075A7   while       23  -
;   $008902   $00890B   while       10  -
;   $0088F4   $008911   while        9  -
;   $00755D   $00758C   while       25  -
;   $0074A4   $0075A9   while       22  -
;   $007107   $00759F   while       12  Y: 0 step 1
;   $007181   $007583   while       14  Y: 0 step 1
;   $0065B0   $007226   while       11  X: 0 step 1
;   $0065B9   $0065BB   while       17  -
;   $007209   $007224   while       28  -
;   $00657D   $007215   while       11  X: 0 step 1
;   $00658D   $00658F   while       16  -
;   $00715F   $00753F   while       13  Y: 0 step 1
;   ... and 145 more loops

; Call Site Analysis Report
; =========================
; Total call sites: 342
;   JSR calls:      340
;   JSL calls:      2
;   Toolbox calls:  0
;
; Parameter Statistics:
;   Register params: 284
;   Stack params:    30
;
; Calling Convention Analysis:
;   Predominantly short calls (JSR/RTS)
;   Register-based parameter passing
;
; Call Sites (first 20):
;   $005000: JSR $00B60F
;   $005052: JSR $0046BA params: A stack
;   $00526A: JSR $004705 params: A X Y
;   $00529D: JSR $0046BA params: A
;   $0052FB: JSR $0046BA params: A
;   $0053CE: JSR $0046BA
;   $0053F4: JSR $005449 params: A Y stack
;   $005436: JSR $005449 params: A Y
;   $005452: JSR $0046BA
;   $00546A: JSR $00707A
;   $005475: JSR $0046BA params: A Y
;   $005493: JSR $0046BA params: A
;   $00549D: JSR $008932
;   $0054A0: JSR $0046BA
;   $0054B9: JSL $556655
;   $005542: JSR $005885 params: A
;   $005551: JSR $007D41 params: A Y
;   $00555D: JSR $004705 params: A
;   $005560: JSR $0084C7
;   $00556A: JSR $005885 params: A
;   ... and 322 more call sites

; === Stack Frame Analysis (Sprint 5.3) ===
; Functions with frames: 45

; Function $0058E9: none
;   Frame: 0 bytes, Locals: 0, Params: 8
;   Leaf: no, DP-relative: no
;   Stack slots:
;      +76: param_76 (2 bytes, 1 accesses)
;     +169: param_169 (2 bytes, 1 accesses)
;      +32: param_32 (2 bytes, 1 accesses)
;      +72: param_72 (2 bytes, 1 accesses)

; Function $005C63: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00657D: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +160: param_160 (2 bytes, 1 accesses)

; Function $0065B0: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +160: param_160 (2 bytes, 1 accesses)

; Function $006F43: none
;   Frame: 0 bytes, Locals: 0, Params: 4
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +173: param_173 (2 bytes, 1 accesses)
;     +208: param_208 (2 bytes, 1 accesses)

; Function $006F5D: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $006F8B: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00707A: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +133: param_133 (2 bytes, 1 accesses)

; Function $007107: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007145: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00715F: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00716F: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007181: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +169: param_169 (2 bytes, 1 accesses)

; Function $0071B4: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0071EB: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007200: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;      +32: param_32 (2 bytes, 1 accesses)

; Function $007320: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007338: none
;   Frame: 0 bytes, Locals: 0, Params: 4
;   Leaf: no, DP-relative: no
;   Stack slots:
;       +3: param_3 (2 bytes, 1 accesses)
;      +76: param_76 (2 bytes, 2 accesses)

; Function $007446: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007470: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0075AE: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0075BA: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +169: param_169 (2 bytes, 1 accesses)

; Function $00761D: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00763B: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $00772D: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0077A2: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007961: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007A0C: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007A81: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007C0C: push_only
;   Frame: 2 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no
;   Saves: A

; Function $007C37: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007CC6: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007DFC: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;     +169: param_169 (2 bytes, 1 accesses)

; Function $007E08: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007E0D: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007E18: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $007E31: push_only
;   Frame: 2 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Saves: A
;   Stack slots:
;     +169: param_169 (2 bytes, 1 accesses)

; Function $007E85: none
;   Frame: 0 bytes, Locals: 0, Params: 2
;   Leaf: no, DP-relative: no
;   Stack slots:
;      +76: param_76 (2 bytes, 2 accesses)

; Function $00881F: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $008881: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0088BD: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0088E4: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $008932: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $008973: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no

; Function $0093DE: none
;   Frame: 0 bytes, Locals: 0, Params: 0
;   Leaf: no, DP-relative: no


; === Liveness Analysis Summary (Sprint 5.4) ===
; Functions analyzed: 45
; Functions with register params: 35
; Functions with register returns: 45
; Total dead stores detected: 149 (in 35 functions)
;
; Function Details:
;   $0058E9: returns(AXY) [24 dead]
;   $005C63: params(XY) returns(AXY) [3 dead]
;   $00657D: params(X) returns(AXY) [6 dead]
;   $0065B0: params(X) returns(AXY) [1 dead]
;   $006F43: params(XY) returns(AXY) [3 dead]
;   $006F5D: params(XY) returns(AXY) 
;   $006F8B: params(XY) returns(AXY) [1 dead]
;   $00707A: params(AXY) returns(AXY) 
;   $007107: params(AX) returns(AXY) [4 dead]
;   $007145: params(AXY) returns(AXY) [1 dead]
;   $00715F: params(Y) returns(AXY) [1 dead]
;   $00716F: params(AXY) returns(AXY) [1 dead]
;   $007181: params(AX) returns(AXY) [2 dead]
;   $0071B4: params(X) returns(AXY) [2 dead]
;   $0071EB: returns(AXY) [1 dead]
;   $007200: params(Y) returns(AXY) [1 dead]
;   $007320: params(XY) returns(AXY) 
;   $007338: returns(AXY) [22 dead]
;   $007446: params(XY) returns(AXY) [1 dead]
;   $007470: params(XY) returns(AXY) [2 dead]
;   $0075AE: params(X) returns(AXY) [1 dead]
;   $0075BA: params(X) returns(AXY) [1 dead]
;   $00761D: params(AX) returns(AXY) [3 dead]
;   $00763B: params(X) returns(AXY) [1 dead]
;   $00772D: params(X) returns(AXY) [8 dead]
;   $0077A2: returns(AXY) [2 dead]
;   $007961: returns(AXY) [5 dead]
;   $007A0C: params(XY) returns(AXY) 
;   $007A81: params(XY) returns(AXY) 
;   $007C0C: params(AXY) returns(AXY) [3 dead]
;   $007C37: params(XY) returns(AXY) [10 dead]
;   $007CC6: returns(AXY) [7 dead]
;   $007DFC: params(XY) returns(AXY) 
;   $007E08: params(AXY) returns(AXY) 
;   $007E0D: params(AXY) returns(AXY) 
;   $007E18: params(X) returns(AXY) [4 dead]
;   $007E31: params(AXY) returns(AXY) [3 dead]
;   $007E85: returns(AXY) [9 dead]
;   $00881F: params(X) returns(AXY) [7 dead]
;   $008881: params(XY) returns(AXY) 
;   $0088BD: returns(AXY) [3 dead]
;   $0088E4: returns(AXY) [2 dead]
;   $008932: returns(AXY) [2 dead]
;   $008973: params(AXY) returns(AXY) 
;   $0093DE: params(X) returns(AXY) [2 dead]

; Function Signature Report
; =========================
; Functions analyzed:    45
;   Leaf functions:      10
;   Interrupt handlers:  12
;   Stack params:        0
;   Register params:     45
;
; Function Signatures:
;   Entry     End       Conv       Return   Frame  Flags
;   -------   -------   --------   ------   -----  -----
;   $0058E9   $005C63   register   A:X         0   I
;     Proto: uint32_t func_0058E9(void);
;   $005C63   $00657D   register   A:X         0   JI
;     Proto: uint32_t func_005C63(uint16_t param_X, uint16_t param_Y);
;   $00657D   $0065B0   register   A:X         0   
;     Proto: uint32_t func_00657D(uint16_t param_X);
;   $0065B0   $006F43   register   A:X         0   JI
;     Proto: uint32_t func_0065B0(uint16_t param_X);
;   $006F43   $006F5D   register   A:X         0   L
;     Proto: uint32_t func_006F43(uint16_t param_X, uint16_t param_Y);
;   $006F5D   $006F8B   register   A:X         0   
;     Proto: uint32_t func_006F5D(uint16_t param_X, uint16_t param_Y);
;   $006F8B   $00707A   register   A:X         0   
;     Proto: uint32_t func_006F8B(uint16_t param_X, uint16_t param_Y);
;   $00707A   $007107   register   A:X         0   
;     Proto: uint32_t func_00707A(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $007107   $007145   register   A:X         0   
;     Proto: uint32_t func_007107(uint16_t param_A, uint16_t param_X);
;   $007145   $00715F   register   A:X         0   
;     Proto: uint32_t func_007145(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $00715F   $00716F   register   A:X         0   L
;     Proto: uint32_t func_00715F(uint16_t param_Y);
;   $00716F   $007181   register   A:X         0   L
;     Proto: uint32_t func_00716F(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $007181   $0071B4   register   A:X         0   
;     Proto: uint32_t func_007181(uint16_t param_A, uint16_t param_X);
;   $0071B4   $0071EB   register   A:X         0   
;     Proto: uint32_t func_0071B4(uint16_t param_X);
;   $0071EB   $007200   register   A:X         0   L
;     Proto: uint32_t func_0071EB(void);
;   $007200   $007320   register   A:X         0   I
;     Proto: uint32_t func_007200(uint16_t param_Y);
;   $007320   $007338   register   A:X         0   L
;     Proto: uint32_t func_007320(uint16_t param_X, uint16_t param_Y);
;   $007338   $007446   register   A:X         0   
;   $007446   $007470   register   A:X         0   
;     Proto: uint32_t func_007446(uint16_t param_X, uint16_t param_Y);
;   $007470   $0075AE   register   A:X         0   
;     Proto: uint32_t func_007470(uint16_t param_X, uint16_t param_Y);
;   $0075AE   $0075BA   register   A:X         0   L
;     Proto: uint32_t func_0075AE(uint16_t param_X);
;   $0075BA   $00761D   register   A:X         0   I
;     Proto: uint32_t func_0075BA(uint16_t param_X);
;   $00761D   $00763B   register   A:X         0   
;     Proto: uint32_t func_00761D(uint16_t param_A, uint16_t param_X);
;   $00763B   $00772D   register   A:X         0   
;     Proto: uint32_t func_00763B(uint16_t param_X);
;   $00772D   $0077A2   register   A:X         0   
;     Proto: uint32_t func_00772D(uint16_t param_X);
;   $0077A2   $007961   register   A:X         0   I
;     Proto: uint32_t func_0077A2(void);
;   $007961   $007A0C   register   A:X         0   
;   $007A0C   $007A81   register   A:X         0   I
;     Proto: uint32_t func_007A0C(uint16_t param_X, uint16_t param_Y);
;   $007A81   $007C0C   register   A:X         0   I
;     Proto: uint32_t func_007A81(uint16_t param_X, uint16_t param_Y);
;   $007C0C   $007C37   register   A:X         0   I
;     Proto: uint32_t func_007C0C(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $007C37   $007CC6   register   A:X         0   I
;     Proto: uint32_t func_007C37(uint16_t param_X, uint16_t param_Y);
;   $007CC6   $007DFC   register   A:X         0   
;   $007DFC   $007E08   register   A:X         0   L
;     Proto: uint32_t func_007DFC(uint16_t param_X, uint16_t param_Y);
;   $007E08   $007E0D   register   A:X         0   
;     Proto: uint32_t func_007E08(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $007E0D   $007E18   register   A:X         0   L
;     Proto: uint32_t func_007E0D(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $007E18   $007E31   register   A:X         0   L
;     Proto: uint32_t func_007E18(uint16_t param_X);
;   $007E31   $007E85   register   A:X         0   
;     Proto: uint32_t func_007E31(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $007E85   $00881F   register   A:X         0   I
;     Proto: uint32_t func_007E85(void);
;   $00881F   $008881   register   A:X         0   
;     Proto: uint32_t func_00881F(uint16_t param_X);
;   $008881   $0088BD   register   A:X         0   
;     Proto: uint32_t func_008881(uint16_t param_X, uint16_t param_Y);
;   $0088BD   $0088E4   register   A:X         0   L
;     Proto: uint32_t func_0088BD(void);
;   $0088E4   $008932   register   A:X         0   
;     Proto: uint32_t func_0088E4(void);
;   $008932   $008973   register   A:X         0   
;     Proto: uint32_t func_008932(void);
;   $008973   $0093DE   register   A:X         0   JI
;     Proto: uint32_t func_008973(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
;   $0093DE   $009400   register   A:X         0   
;     Proto: uint32_t func_0093DE(uint16_t param_X);
;
; Flags: L=Leaf, J=JSL/RTL, I=Interrupt, F=FrameSetup

; Constant Propagation Analysis
; =============================
; Constants found: 492
; Loads with known value: 435
; Branches resolved: 0
; Compares resolved: 0
; Memory constants tracked: 45
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
;   $00B404 = $00FF (abs)
;   $00001F = $0078 (dp)
;   $0000CC = $000A (dp)
;   $0000D0 = $0000 (dp)
;   $000002 = $00FB (dp)
;   $000000 = $004B (dp)
;   $000385 = $00CD (abs)
;   $009998 = $0078 (abs)
;   $0056E7 = $00FF (abs)
;   $0000FE = $0000 (abs)
;   $0000D5 = $0003 (dp)
;   $0000B0 = $0000 (dp)
;   $0000B1 = $0000 (dp)
;   $000001 = $0038 (dp)
;   $0000D7 = $00FF (dp)
;   $006FAE = $000C (abs)
;   $006FA1 = $000C (abs)
;   $006FAF = $0004 (abs)
;   $001D65 = $000C (abs)
;   $0000F0 = $006C (dp)
;   ... and 25 more

; ============================================================================
; TYPE INFERENCE REPORT
; ============================================================================
;
; Entries analyzed: 512
; Bytes typed:      68
; Words typed:      130
; Pointers typed:   4
; Arrays typed:     111
; Structs typed:    448
;
; Inferred Types:
;   Address   Type       Conf   R    W   Flags  Name
;   -------   --------   ----   ---  --- -----  ----
;   $0000A0   FLAG       90%    78    0 IP     flag_00A0
;   $0000D0   ARRAY      75%    31   21 IP     arr_00D0 [elem=1]
;   $0000D4   FLAG       60%    24    1 IP     flag_00D4
;   $00C204   WORD       60%     0    3        word_C204
;   $000000   STRUCT     80%    77   14 IP     struct_0000 {size=256}
;   $8DC1D3   LONG       70%     4    0        long_8DC1D3
;   $8DCDD3   LONG       70%     4    0        long_8DCDD3
;   $0000FA   BYTE       90%     3   16        byte_00FA
;   $0000F9   BYTE       90%    11   19        byte_00F9
;   $001E31   ARRAY      75%     1    0 I      arr_1E31 [elem=1]
;   $001E32   ARRAY      75%     1    0 I      arr_1E32 [elem=1]
;   $001E33   ARRAY      75%     1    0 I      arr_1E33 [elem=1]
;   $001E34   ARRAY      75%     1    0 I      arr_1E34 [elem=1]
;   $0000CB   BYTE       90%     5    6 P      byte_00CB
;   $000010   BYTE       90%     4    2        byte_0010
;   $0000B2   BYTE       90%    15    1        byte_00B2
;   $0000B0   BYTE       90%     4   30        byte_00B0
;   $0000B1   BYTE       90%     0   39        byte_00B1
;   $00C010   WORD       90%    11    0        word_C010
;   $000013   BYTE       90%    13    2 I      byte_0013
;   $00A900   ARRAY      85%     4    2 I      arr_A900 [elem=1]
;   $000085   PTR        80%     6    1 IP     ptr_0085
;   $000012   BYTE       90%     4    2        byte_0012
;   $00F2EF   WORD       60%     3    0        word_F2EF
;   $000001   BYTE       90%    35   16 P      byte_0001
;   $E8F4F5   LONG       60%     3    0        long_E8F4F5
;   $0000E1   FLAG       90%    19    0 I      flag_00E1
;   $0000F3   BYTE       90%    13    6 P      byte_00F3
;   $0000FE   BYTE       90%   171  144 P      byte_00FE
;   $0000FF   PTR        80%    53   12 P      ptr_00FF
;   $00CE00   ARRAY      80%     2    0 I      arr_CE00 [elem=1]
;   $005222   ARRAY      75%     1    0 I      arr_5222 [elem=1]
;   $005223   ARRAY      75%     1    0 I      arr_5223 [elem=1]
;   $009900   STRUCT     70%     1    0 I      struct_9900 {size=165}
;   $009A59   ARRAY      75%     1    0 I      arr_9A59 [elem=1]
;   $5FF15D   LONG       50%     0    2        long_5FF15D
;   $000060   BYTE       50%     4    0 IP     byte_0060
;   $000061   PTR        80%     2    0 P      ptr_0061
;   $0000C5   FLAG       90%    12    0 P      flag_00C5
;   $007769   WORD       50%     2    0        word_7769
;   $0000C1   ARRAY      95%    32    0 I      arr_00C1 [elem=1]
;   $A1C5D6   LONG       60%     3    0        long_A1C5D6
;   $00B769   WORD       50%     2    0        word_B769
;   $00C8D7   WORD       60%     3    0        word_C8D7
;   $00D4CF   WORD       90%     8    0        word_D4CF
;   $0000D2   FLAG       90%    57    5 IP     flag_00D2
;   $0000A1   FLAG       90%    20    0 P      flag_00A1
;   $00001F   BYTE       90%     4    6 I      byte_001F
;   $0000F4   BYTE       80%     5    0 P      byte_00F4
;   $0000E3   BYTE       90%     8    4 P      byte_00E3
;   $002000   WORD       90%    24    0        word_2000
;   $00A420   ARRAY      85%     3    0 I      arr_A420 [elem=1]
;   $004F40   ARRAY      95%    10    2 I      arr_4F40 [elem=1]
;   $000002   BYTE       90%    21   55 P      byte_0002
;   $004F60   ARRAY      95%    10    2 I      arr_4F60 [elem=1]
;   $000003   BYTE       90%    25   55        byte_0003
;   $004F20   ARRAY      95%     4    2 I      arr_4F20 [elem=1]
;   $004F00   STRUCT     70%     9    5 I      struct_4F00 {size=33}
;   $0000CE   BYTE       90%    45    5 IP     byte_00CE
;   $00000E   BYTE       90%    15    6        byte_000E
;   $E4F2E1   LONG       60%     3    0        long_E4F2E1
;   $0000E0   BYTE       90%     1    9        byte_00E0
;   $0000D5   BYTE       90%    32   27 I      byte_00D5
;   $0000D6   BYTE       90%    15    5 P      byte_00D6
;   $00F7A0   ARRAY      75%     1    0 I      arr_F7A0 [elem=1]
;   $ADBFED   LONG       50%     2    0        long_ADBFED
;   $0000C3   FLAG       90%    18    0 IP     flag_00C3
;   $0000C4   FLAG       90%    18    0 P      flag_00C4
;   $0000C7   BYTE       60%     4    0 IP     byte_00C7
;   $00C5D0   ARRAY      75%     1    0 I      arr_C5D0 [elem=1]
;   $0000D7   BYTE       90%    21    6        byte_00D7
;   $0054B7   ARRAY      75%     1    0 I      arr_54B7 [elem=1]
;   $0054B8   ARRAY      75%     1    0 I      arr_54B8 [elem=1]
;   $00F700   ARRAY      75%     1    0 I      arr_F700 [elem=1]
;   $0000A2   ARRAY      75%     1    0 I      arr_00A2 [elem=1]
;   $0000A9   ARRAY      75%     1    0 I      arr_00A9 [elem=1]
;   $0000DC   ARRAY      75%     1    0 I      arr_00DC [elem=1]
;   $0000EC   ARRAY      75%     2    0 I      arr_00EC [elem=1]
;   $0000F6   ARRAY      75%     5    3 IP     arr_00F6 [elem=1]
;   $0000FC   PTR        80%     4    5 IP     ptr_00FC
;   $00004D   ARRAY      75%     1    0 I      arr_004D [elem=1]
;   $000054   ARRAY      75%     1    0 I      arr_0054 [elem=1]
;   $00005E   ARRAY      75%     1    0 I      arr_005E [elem=1]
;   $00006E   ARRAY      75%     1    0 I      arr_006E [elem=1]
;   $0000B6   ARRAY      75%     1    0 I      arr_00B6 [elem=1]
;   $0000BD   ARRAY      95%    11    0 I      arr_00BD [elem=1]
;   $00007E   ARRAY      75%     1    0 I      arr_007E [elem=1]
;   $000066   ARRAY      75%     1    0 I      arr_0066 [elem=1]
;   $00008A   ARRAY      75%     2    0 IP     arr_008A [elem=1]
;   $000070   ARRAY      75%    13    0 I      arr_0070 [elem=1]
;   $000011   ARRAY      75%     1    0 I      arr_0011 [elem=1]
;   $0000E2   BYTE       90%    35   11        byte_00E2
;   $005521   WORD       60%     1    2        word_5521
;   $0000C9   FLAG       90%    23    0 IP     flag_00C9
;   $008520   ARRAY      75%     1    0 I      arr_8520 [elem=1]
;   $0000B9   ARRAY      80%     2    0 I      arr_00B9 [elem=1]
;   $0099A4   ARRAY      95%    11    3 I      arr_99A4 [elem=1]
;   $0000FB   BYTE       90%    18   20        byte_00FB
;   $0000CC   BYTE       90%    19    5 IP     byte_00CC
;   $009998   ARRAY      95%     7    5 I      arr_9998 [elem=1]
;   $009980   ARRAY      95%    10    1 I      arr_9980 [elem=1]
;   $009988   ARRAY      95%    11    1 I      arr_9988 [elem=1]
;   $0056E7   WORD       60%     1    2        word_56E7
;   $00D7A0   ARRAY      75%     1    0 I      arr_D7A0 [elem=1]
;   $ADBFCD   LONG       70%     4    0        long_ADBFCD
;   $005BDC   WORD       60%     1    2        word_5BDC
;   $0000D3   FLAG       90%    18    3 IP     flag_00D3
;   $0058B7   WORD       50%     2    0        word_58B7
;   $0058B8   WORD       50%     2    0        word_58B8
;   $005800   STRUCT     70%     0    0        struct_5800 {size=185}
;   $00C030   WORD       50%     2    0        word_C030
;   $004300   ARRAY      85%     3    0 I      arr_4300 [elem=1]
;   $0043C0   ARRAY      85%     3    0 I      arr_43C0 [elem=1]
;   $0000FD   BYTE       60%     0    3        byte_00FD
;   $0000E5   FLAG       60%     3    0        flag_00E5
;   $0000F2   BYTE       90%     7    2 I      byte_00F2
;   $0079B7   ARRAY      75%     1    0 I      arr_79B7 [elem=1]
;   $0079CA   ARRAY      75%     1    0 I      arr_79CA [elem=1]
;   $007900   STRUCT     70%     0    0        struct_7900 {size=160}
;   $0000E4   BYTE       90%     4    4 P      byte_00E4
;   $000009   BYTE       60%     3    0        byte_0009
;   $000014   BYTE       90%     5    3        byte_0014
;   $00000F   BYTE       60%     0    3        byte_000F
;   $006378   WORD       60%     2    1        word_6378
;   $005900   STRUCT     70%     0    0        struct_5900 {size=250}
;   $00008D   BYTE       50%     5    0 IP     byte_008D
;   $00CECF   WORD       60%     3    0        word_CECF
;   $00FBA9   ARRAY      75%     1    0 I      arr_FBA9 [elem=1]
;   $000004   BYTE       90%    13   11        byte_0004
;   $000005   BYTE       90%    12   11        byte_0005
;   $C4C5D9   LONG       50%     2    0        long_C4C5D9
;   $0000F1   BYTE       90%     4    2        byte_00F1
;   $0000A4   ARRAY      75%     1    0 I      arr_00A4 [elem=1]
;   $000084   ARRAY      80%     2    0 I      arr_0084 [elem=1]
;   $000086   ARRAY      75%     2    0 IP     arr_0086 [elem=1]
;   $000020   ARRAY      95%     6    0 I      arr_0020 [elem=1]
;   $0000C6   FLAG       60%     4    0        flag_00C6
;   $0000AC   FLAG       70%     4    0        flag_00AC
;   $0000BA   WORD       50%     4    0 P      word_00BA
;   $0000CD   BYTE       90%    11    3 IP     byte_00CD
;   $D4CED5   LONG       50%     2    0        long_D4CED5
;   $000046   BYTE       50%     5    0 IP     byte_0046
;   $00D5CF   ARRAY      90%     6    0 I      arr_D5CF [elem=1]
;   $0000CF   FLAG       50%     8    0        flag_00CF
;   $0000AD   ARRAY      75%     4    0 I      arr_00AD [elem=1]
;   $0000F0   FLAG       50%    19   14 I      flag_00F0
;   $00F4E9   WORD       50%     2    0        word_F4E9
;   $A0C5D3   LONG       80%     5    0        long_A0C5D3
;   $0000D1   BYTE       90%    11    6 IP     byte_00D1
;   $00BA20   ARRAY      75%     1    0 I      arr_BA20 [elem=1]
;   $00EFA0   ARRAY      75%     1    0 I      arr_EFA0 [elem=1]
;   $0000E6   ARRAY      90%     4    2 IP     arr_00E6 [elem=1]
;   $0000D8   FLAG       90%    10    0 P      flag_00D8
;   $0000C2   BYTE       50%     3    0 IP     byte_00C2
;   $006AB9   WORD       60%     1    2        word_6AB9
;   $002C00   WORD       50%     1    1        word_2C00
;   $0062A6   WORD       50%     1    1        word_62A6
;   $0062A7   WORD       50%     1    1        word_62A7
;   $006200   STRUCT     70%     0    0        struct_6200 {size=168}
;   $00A0CF   WORD       60%     3    0        word_A0CF
;   $00FF20   ARRAY      75%     1    0 I      arr_FF20 [elem=1]
;   $006300   STRUCT     70%     0    0        struct_6300 {size=121}
;   $008DC4   WORD       50%     2    0        word_8DC4
;   $0009A5   ARRAY      75%     1    0 I      arr_09A5 [elem=1]
;   $C3C9D4   LONG       60%     3    0        long_C3C9D4
;   $00CCC5   ARRAY      75%     1    0 I      arr_CCC5 [elem=1]
;   $0000ED   BYTE       60%     3    0        byte_00ED
;   $0000AE   FLAG       50%     3    0        flag_00AE
;   $A3A0F2   LONG       60%     3    0        long_A3A0F2
;   $006A07   ARRAY      80%     2    0 I      arr_6A07 [elem=1]
;   $006A12   ARRAY      75%     1    0 I      arr_6A12 [elem=1]
;   $0000D9   FLAG       80%     7    0 P      flag_00D9
;   $00CF20   ARRAY      75%     1    0 I      arr_CF20 [elem=1]
;   $00E720   ARRAY      75%     1    0 I      arr_E720 [elem=1]
;   $004F80   ARRAY      95%     2    3 I      arr_4F80 [elem=1]
;   $00A500   WORD       90%     6    1        word_A500
;   $00A988   ARRAY      75%     1    0 I      arr_A988 [elem=1]
;   $00FFA1   ARRAY      75%     2    0 I      arr_FFA1 [elem=1]
;   $C1A0D5   LONG       50%     2    0        long_C1A0D5
;   $0005A5   ARRAY      75%     1    0 I      arr_05A5 [elem=1]
;   $0000EF   ARRAY      75%     1    0 I      arr_00EF [elem=1]
;   $FFA1CE   LONG       50%     2    0        long_FFA1CE
;   $006A1D   ARRAY      75%     1    0 I      arr_6A1D [elem=1]
;   $00ECE5   ARRAY      75%     1    0 I      arr_ECE5 [elem=1]
;   $D3CECF   LONG       50%     2    0        long_D3CECF
;   $00CBC1   WORD       60%     3    0        word_CBC1
;   $001800   WORD       50%     2    0        word_1800
;   $0000A8   WORD       50%     2    0        word_00A8
;   $00C1A8   WORD       50%     2    0        word_C1A8
;   $00835E   WORD       90%     6    1        word_835E
;   $006FAE   WORD       50%     1    1        word_6FAE
;   $006FA1   WORD       70%     3    1        word_6FA1
;   $006FAF   WORD       50%     1    1        word_6FAF
;   $006F00   STRUCT     75%     0    0        struct_6F00 {size=176}
;   $006FA4   WORD       70%     3    1        word_6FA4
;   $00B4A8   ARRAY      75%     1    0 I      arr_B4A8 [elem=1]
;   $001D65   WORD       50%     0    2        word_1D65
;   $007997   ARRAY      85%     3    0 I      arr_7997 [elem=1]
;   $00799F   ARRAY      85%     3    0 I      arr_799F [elem=1]
;   $0062A5   WORD       50%     1    1        word_62A5
;   $00C000   STRUCT     70%     3    0        struct_C000 {size=17}
;   $00FE91   ARRAY      95%     1    4 I      arr_FE91 [elem=1]
;   $0050A8   ARRAY      75%     1    0 I      arr_50A8 [elem=1]
;   $000071   ARRAY      75%     1    0 I      arr_0071 [elem=1]
;   $00732B   WORD       50%     1    1        word_732B
;   $00732C   WORD       50%     1    1        word_732C
;   $007300   STRUCT     70%     0    0        struct_7300 {size=45}
;   $0020A4   ARRAY      75%     1    0 I      arr_20A4 [elem=1]
;   $0075AC   WORD       50%     1    1        word_75AC
;   $0075AD   WORD       60%     2    1        word_75AD
;   $00772C   WORD       50%     1    1        word_772C
;   $004FFC   WORD       60%     2    1        word_4FFC
;   $004FFE   WORD       50%     1    1        word_4FFE
;   $004FFD   WORD       80%     2    3        word_4FFD
;   $004FFF   WORD       50%     1    1        word_4FFF
;   $8D02A5   LONG       50%     2    0        long_8D02A5
;   $AE0286   LONG       50%     2    0        long_AE0286
;   $00A54F   ARRAY      80%     2    0 I      arr_A54F [elem=1]
;   $004C00   ARRAY      75%     1    0 I      arr_4C00 [elem=1]
;   $0079A7   ARRAY      75%     1    0 I      arr_79A7 [elem=1]
;   $0079AF   ARRAY      75%     1    0 I      arr_79AF [elem=1]
;   $00C7A0   ARRAY      75%     2    0 I      arr_C7A0 [elem=1]
;   $006000   ARRAY      75%     1    0 I      arr_6000 [elem=1]
;   $00240F   ARRAY      75%     1    0 I      arr_240F [elem=1]
;   $001F37   ARRAY      75%     1    0 I      arr_1F37 [elem=1]
;   $001338   ARRAY      75%     1    0 I      arr_1338 [elem=1]
;   $001E22   ARRAY      75%     1    0 I      arr_1E22 [elem=1]
;   $007BAC   ARRAY      75%     1    0 I      arr_7BAC [elem=1]
;   $007BB9   ARRAY      75%     1    0 I      arr_7BB9 [elem=1]
;   $001A14   ARRAY      75%     1    0 I      arr_1A14 [elem=1]
;   $000404   ARRAY      75%     1    0 I      arr_0404 [elem=1]
;   $00D6CC   ARRAY      75%     1    0 I      arr_D6CC [elem=1]
;   $00C5C8   ARRAY      75%     1    0 I      arr_C5C8 [elem=1]
;   $0099A0   ARRAY      95%     5    3 I      arr_99A0 [elem=1]
;   $0000A5   ARRAY      75%     1    0 I      arr_00A5 [elem=1]
;   $0000F7   BYTE       50%     1    1        byte_00F7
;   $0000F8   BYTE       50%     1    1        byte_00F8
;   $000018   ARRAY      95%     7    0 I      arr_0018 [elem=1]
;   $00835F   WORD       60%     2    1        word_835F
;   $00ADAD   WORD       70%     4    0        word_ADAD
;   $0099AC   ARRAY      85%     2    1 I      arr_99AC [elem=1]
;   $0099A8   ARRAY      90%     2    2 I      arr_99A8 [elem=1]
;   $008914   ARRAY      80%     2    0 I      arr_8914 [elem=1]
;   $009990   ARRAY      90%     2    2 I      arr_9990 [elem=1]
;   $00AD83   ARRAY      75%     1    0 I      arr_AD83 [elem=1]
;   $008583   ARRAY      75%     1    0 I      arr_8583 [elem=1]
;   $002088   ARRAY      75%     1    0 I      arr_2088 [elem=1]
;   $000520   ARRAY      75%     1    0 I      arr_0520 [elem=1]
;   $00835D   WORD       60%     3    0        word_835D
;   $008300   STRUCT     70%     0    0        struct_8300 {size=94}
;   $000285   ARRAY      75%     0    1 I      arr_0285 [elem=1]
;   $00004C   ARRAY      75%     1    0 I      arr_004C [elem=1]
;   $00CC00   STRUCT     70%     1    0 I      struct_CC00 {size=214}
;   $00CB00   STRUCT     70%     0    0        struct_CB00 {size=194}
;   $AB00D7   LONG       50%     2    0        long_AB00D7
;   $00D0D2   LONG       50%     2    0        long_D0D2

; ============================================================================
; SWITCH/CASE DETECTION REPORT
; ============================================================================
;
; Switches found:   66
;   Jump tables:    2
;   CMP chains:     64
;   Computed:       0
; Total cases:      185
; Max cases/switch: 10
;
; Detected Switches:
;
; Switch #1 at $00530A:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;        40   $00531E     sw_530A_case_40
;        44   $00533C     sw_530A_case_44
;
; Switch #2 at $0053AE:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      8
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       195   $005401     sw_53AE_case_195
;       208   $005401     sw_53AE_case_208
;       201   $005401     sw_53AE_case_201
;       215   $005425     sw_53AE_case_215
;       204   $005425     sw_53AE_case_204
;       193   $005425     sw_53AE_case_193
;       196   $0053E1     sw_53AE_case_196
;       210   $0053E1     sw_53AE_case_210
;
; Switch #3 at $0053F7:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       215   $005425     sw_53F7_case_215
;       195   $005401     sw_53F7_case_195
;
; Switch #4 at $0054F9:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       128   $005500     sw_54F9_case_128
;     deflt   $00586E     sw_54F9_default
;
; Switch #5 at $005502:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;        48   $005509     sw_5502_case_48
;     deflt   $00586E     sw_5502_default
;
; Switch #6 at $00552D:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       128   $005534     sw_552D_case_128
;     deflt   $00586E     sw_552D_default
;
; Switch #7 at $005572:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;         1   $005579     sw_5572_case_1
;     deflt   $00586E     sw_5572_default
;
; Switch #8 at $00558C:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;         1   $005593     sw_558C_case_1
;     deflt   $00586E     sw_558C_default
;
; Switch #9 at $005602:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       128   $005609     sw_5602_case_128
;     deflt   $00586E     sw_5602_default
;
; Switch #10 at $005670:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       128   $005677     sw_5670_case_128
;     deflt   $00586E     sw_5670_default
;
; Switch #11 at $0056BF:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       128   $0056C6     sw_56BF_case_128
;     deflt   $00586E     sw_56BF_default
;
; Switch #12 at $0056C8:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;        50   $0056CF     sw_56C8_case_50
;     deflt   $00586E     sw_56C8_default
;
; Switch #13 at $005724:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;         1   $00572B     sw_5724_case_1
;     deflt   $00586E     sw_5724_default
;
; Switch #14 at $005770:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       208   $005777     sw_5770_case_208
;     deflt   $00586E     sw_5770_default
;
; Switch #15 at $005792:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;         1   $005799     sw_5792_case_1
;     deflt   $00586E     sw_5792_default
;
; Switch #16 at $0057B3:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $0064D5
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;         1   $0057BA     sw_57B3_case_1
;     deflt   $0064D5     sw_57B3_default
;
; Switch #17 at $0057F1:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       196   $0057F8     sw_57F1_case_196
;     deflt   $00586E     sw_57F1_default
;
; Switch #18 at $005843:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $00586E
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       193   $00584A     sw_5843_case_193
;     deflt   $00586E     sw_5843_default
;
; Switch #19 at $005A41:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $005933
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;       248   $005A48     sw_5A41_case_248
;     deflt   $005933     sw_5A41_default
;
; Switch #20 at $005AA4:
;   Type:       cmp_chain
;   Index Reg:  A
;   Cases:      2
;   Default:    $005279
;   Case Details:
;     Value   Target      Label
;     -----   --------    -----
;        22   $005AAB     sw_5AA4_case_22
;     deflt   $005279     sw_5AA4_default
;
; ... and 46 more switches

; Cross-Reference Report
; ======================
; Total references: 2288
;   Calls: 923  Jumps: 389  Branches: 782  Data: 186
;
; Target Address  Type     From Address
; -------------- -------- --------------
; $0000A0         READ     $006985
; $0000A0         READ     $006AD3
;
; $0000A8         READ     $006DB8
; $0000A8         READ     $006E16
;
; $0000A9         WRITE    $009075
;
; $0000AE         READ     $006C2D
;
; $0000BE         READ     $0060E0
; $0000BE         READ     $007FF2
;
; $0000FE         INDIRECT  $0054B4
; $0000FE         INDIRECT  $008DAF
; $0000FE         INDIRECT  $00521F
;
; $000230         CALL     $008586
; $000230         CALL     $005B0A
; $000230         CALL     $007958
; $000230         CALL     $005AFA
; $000230         CALL     $007731
; $000230         CALL     $007984
; $000230         CALL     $005AEE
; $000230         CALL     $007B54
; $000230         CALL     $005097
; $000230         CALL     $006357
; $000230         CALL     $006345
; $000230         CALL     $0052B5
; $000230         CALL     $006AB3
; $000230         CALL     $0076C2
; $000230         CALL     $006336
; $000230         CALL     $006F23
; $000230         CALL     $007961
; $000230         CALL     $006F36
; $000230         CALL     $006947
;
; $000328         CALL     $0086F7
; $000328         CALL     $0056A2
; $000328         CALL     $00745B
; $000328         CALL     $007D5F
; $000328         CALL     $0085B6
; $000328         CALL     $00813D
; $000328         CALL     $0056B0
; $000328         CALL     $006F30
; $000328         CALL     $005644
; $000328         CALL     $0081D8
; $000328         CALL     $006F1B
; $000328         CALL     $0081F7
; $000328         CALL     $0084C1
; $000328         CALL     $005636
; $000328         CALL     $007B8A
; $000328         CALL     $00911B
; $000328         CALL     $00869E
; $000328         CALL     $00848B
; $000328         CALL     $008805
; $000328         CALL     $005B63
; $000328         CALL     $0087CA
; $000328         CALL     $007D6D
; $000328         CALL     $0087B9
; $000328         CALL     $0086EC
; $000328         CALL     $008521
;
; $0003A3         CALL     $00748F
; $0003A3         CALL     $005362
; $0003A3         CALL     $007D79
; $0003A3         CALL     $007346
; $0003A3         CALL     $006E3E
; $0003A3         CALL     $005031
;
; $0003AF         CALL     $008FC2
; $0003AF         CALL     $006E35
;
; $0003F0         INDIRECT  $0072C1
; $0003F0         INDIRECT  $005038
; $0003F0         INDIRECT  $0072DB
; $0003F0         INDIRECT  $0058C4
;
; $0013C6         WRITE    $008F52
;
; $001800         CALL     $008F31
; $001800         CALL     $008580
; $001800         CALL     $008E26
; $001800         CALL     $008E61
; $001800         CALL     $008F57
; $001800         READ     $006E01
; $001800         READ     $006DA3
; $001800         CALL     $008D0A
; $001800         CALL     $008EB8
; $001800         CALL     $009385
; $001800         CALL     $008E8D
; $001800         CALL     $0091D1
; $001800         CALL     $006E52
;
; $001D65         WRITE    $006FCD
; $001D65         WRITE    $006FC5
;
; $001DFF         READ     $008195
;
; $002000         READ     $00601B
; $002000         READ     $0052A6
; $002000         WRITE    $0078FE
; $002000         READ     $005E27
; $002000         READ     $005B89
; $002000         WRITE    $007929
; $002000         READ     $00610B
; $002000         READ     $006125
; $002000         READ     $0061BC
; $002000         READ     $00640E
; $002000         READ     $0062CA
; $002000         WRITE    $00918C
; $002000         READ     $00553D
; $002000         READ     $0066EF
; $002000         READ     $006778
; $002000         READ     $006793
;
; ... and 2188 more references

; Stack Depth Analysis Report
; ===========================
; Entry depth: 0
; Current depth: -2385
; Min depth: -2385 (locals space: 2385 bytes)
; Max depth: 0
;
; Stack Operations:
;   Push: 137  Pull: 58
;   JSR/JSL: 924  RTS/RTL: 108
;
; WARNING: Stack imbalance detected at $0050B4
;   Entry depth: 0, Return depth: -2385
;
; Inferred Local Variables:
;   Stack frame size: 2385 bytes
;   Offsets: S+$01 through S+$951

; === Hardware Context Analysis ===
; Total I/O reads:  6
; Total I/O writes: 0
;
; Subsystem Access Counts:
;   Keyboard        : 5
;   Speaker         : 1
;
; Final Video Mode: TEXT40
; Memory State: 80STORE=0 RAMRD=0 RAMWRT=0 ALTZP=0 LC_BANK=2 LC_RD=0 LC_WR=0
; Speed Mode: Normal (1 MHz)
;
; Detected Hardware Patterns:
;   - Speaker toggle detected (1 accesses)

; Disassembly generated by DeAsmIIgs v2.0.0
; Source: D:\Projects\rosetta_v2\archaeology\games\rpg\u3p_dsk1\extracted\GAME\ULT3#065000
; Base address: $005000
; Size: 17408 bytes
; Analysis: 0 functions, 342 call sites, 45 liveness, stack: +0 max

        ; Emulation mode

; === Analysis Summary ===
; Basic blocks: 177
; CFG edges: 979
; Loops detected: 175
; Patterns matched: 297
; Branch targets: 351
; Functions: 45
; Call edges: 128
;
; Loops:
;   $005E60: while loop
;   $0071F4: while loop
;   $0071B8: while loop
;   $007320: while loop
;   $007350: while loop
;   $00732D: while loop
;   $007229: while loop
;   $0050B3: while loop
;   $006E35: while loop
;   $00746D: while loop
;   $00715F: while loop
;   $007166: while loop
;   $00716F: while loop
;   $007178: while loop
;   $00715F: while loop
;   $00716F: while loop
;   $0071EB: while loop
;   $007586: while loop
;   $008902: while loop
;   $0088F4: while loop
;   $00755D: while loop
;   $0074A4: while loop
;   $007107: while loop
;   $007181: while loop
;   $0065B0: while loop
;   $0065B9: while loop
;   $007209: while loop
;   $00657D: while loop
;   $00658D: while loop
;   $00715F: while loop
;   $00716F: while loop
;   $00715F: while loop
;   $00716F: while loop
;   $007338: while loop
;   $007483: while loop
;   $007A1D: while loop
;   $007A1D: while loop
;   $007A85: while loop
;   $007DFC: while loop
;   $007A85: while loop
;   $007B60: while loop
;   $007A85: while loop
;   $005C63: while loop
;   $005C69: while loop
;   $007A85: while loop
;   $007A85: while loop
;   $007A85: while loop
;   $0052B3: while loop
;   $007FC1: while loop
;   $007FC7: while loop
;   $007FC7: while loop
;   $007BE0: while loop
;   $007A85: while loop
;   $007BE0: while loop
;   $007AAA: while loop
;   $007AAA: while loop
;   $007A98: while loop
;   $007A85: while loop
;   $0050A7: while loop
;   $0050A7: while loop
;   $0050A7: while loop
;   $005C63: while loop
;   $0058E9: while loop
;   $0058F7: loop
;   $0058EB: while loop
;   $0058E9: while loop
;   $0058E9: while loop
;   $0058E9: while loop
;   $006E7F: while loop
;   $0088CE: while loop
;   $007338: while loop
;   $0085EE: while loop
;   $007E85: while loop
;   $007E8D: while loop
;   $007E8D: while loop
;   $007E0D: while loop
;   $007E0D: while loop
;   $007E8D: while loop
;   $007DFC: while loop
;   $007DFC: while loop
;   $007E18: while loop
;   $007E31: while loop
;   $007E8D: while loop
;   $007E18: while loop
;   $007E31: while loop
;   $007E18: while loop
;   $007E31: while loop
;   $007E8D: while loop
;   $007E8D: while loop
;   $007E18: while loop
;   $007E18: while loop
;   $0085EE: while loop
;   $0085EE: while loop
;   $008643: while loop
;   $0058E9: while loop
;   $0058E9: while loop
;   $008888: while loop
;   $008869: while loop
;   $0086EC: while loop
;   $0086B5: while loop
;   $0085EE: while loop
;   $0086CE: while loop
;   $007E18: while loop
;   $00716F: while loop
;   $007181: while loop
;   $007181: while loop
;   $007E18: while loop
;   $007338: while loop
;   $0085EE: while loop
;   $00882D: while loop
;   $008159: while loop
;   $007470: while loop
;   $007338: while loop
;   $0075BA: while loop
;   $008159: while loop
;   $008164: while loop
;   $0085BE: while loop
;   $008535: while loop
;   $00853D: while loop
;   $007470: while loop
;   $007338: while loop
;   $007FB0: while loop
;   $008D13: while loop
;   $0071B4: while loop
;   $008D13: while loop
;   $007CC6: while loop
;   $008D13: while loop
;   $0075BA: while loop
;   $00763B: while loop
;   $008D13: while loop
;   $009322: while loop
;   $00917A: while loop
;   $00907C: while loop
;   $005457: while loop
;   $007087: loop
;   $00572B: while loop
;   $00588F: while loop
;   $00585D: while loop
;   $006307: while loop
;   $00632F: while loop
;   $0064E4: while loop
;   $0065FB: while loop
;   $0067D6: while loop
;   $005288: while loop
;   $005288: while loop
;   $005288: while loop
;   $00744C: while loop
;   $007002: while loop
;   $007002: while loop
;   $007024: while loop
;   $007024: while loop
;   $007051: while loop
;   $00704A: while loop
;   $00763B: while loop
;   $0077AE: loop
;   $0077AC: loop
;   $0077AA: while loop
;   $007CA8: while loop
;   $007CA8: while loop
;   $007CA8: while loop
;   $007D26: while loop
;   $007D26: while loop
;   $007D26: while loop
;   $007E77: loop
;   $007E77: loop
;   $008964: while loop
;   $00894D: while loop
;   $00894D: while loop
;   $008941: while loop
;   $00893D: while loop
;   $006E35: while loop
;   $0088C0: while loop
;   $008914: while loop
;   $0088D9: while loop
;   $008FA0: while loop
;
; Pattern summary:
;   Function prologues: 5
;
; Call graph:
;   $0058E9: 7 caller(s)
;   $005C63: 2 caller(s)
;   $00657D: 1 caller(s)
;   $0065B0: 1 caller(s)
;   $006F43: 1 caller(s)
;   $006F5D: 1 caller(s)
;   $006F8B: 2 caller(s)
;   $00707A: 1 caller(s)
;   $007107: 1 caller(s)
;   $007145: 1 caller(s)
;   $00715F: 4 caller(s)
;   $00716F: 5 caller(s)
;   $007181: 6 caller(s)
;   $0071B4: 2 caller(s)
;   $0071EB: 1 caller(s)
;   $007200: 1 caller(s)
;   $007320: 2 caller(s)
;   $007338: 8 caller(s)
;   $007446: 2 caller(s)
;   $007470: 3 caller(s)
;   $0075AE: 5 caller(s)
;   $0075BA: 3 caller(s)
;   $00761D: 1 caller(s)
;   $00763B: 1 caller(s)
;   $00772D: 2 caller(s)
;   $0077A2: 1 caller(s)
;   $007961: 1 caller(s)
;   $007A0C: 1 caller(s)
;   $007A81: 1 caller(s)
;   $007C0C: 3 caller(s)
;   $007C37: 3 caller(s)
;   $007CC6: 1 caller(s)
;   $007DFC: 6 caller(s)
;   $007E08: 2 caller(s)
;   $007E0D: 4 caller(s)
;   $007E18: 11 caller(s)
;   $007E31: 3 caller(s)
;   $007E85: 1 caller(s)
;   $00881F: 1 caller(s)
;   $008881: 1 caller(s)
;   $0088BD: 2 caller(s)
;   $0088E4: 7 caller(s)
;   $008932: 1 caller(s)
;   $008973: 2 caller(s)
;   $0093DE: 6 caller(s)
;

; ===========================================================================
; Forward references — labels at mid-instruction addresses
; ===========================================================================

; NOTE: input_return_to_loop enters mid-instruction — alternate decode: JMP $6E35
input_return_to_loop   EQU $5882

; NOTE: game_loop_vblank enters mid-instruction — alternate decode: LDA $B2 / BNE $658D / JSR $46B7
game_loop_vblank  EQU $658D

; NOTE: game_main_loop enters mid-instruction — alternate decode: LDA $B0 / PHA / LDA #$00
game_main_loop    EQU $65B0

; NOTE: combat_dead_xor_addr enters mid-instruction — alternate decode: BVC $7180 / BPL $71F4 / LDX #$50
combat_dead_xor_addr  EQU $71F6

; NOTE: input_wait_restore_y enters mid-instruction — alternate decode: BRK #$20 / LDA $B769 / ORA #$55
input_wait_restore_y EQU $746E

; NOTE: tile_lookup_data enters mid-instruction — alternate decode: CMP ... / CMP ... / ORA ...
tile_lookup_data  EQU $7CFC

; NOTE: render_party_drop_jmp enters mid-instruction — alternate decode: EOR ($A0) / BMI $8802 / INC $4CF0,X
render_party_drop_jmp EQU $882D

; NOTE: render_party_exit enters mid-instruction — alternate decode: RTS
render_party_exit   EQU $8880

; NOTE: render_get_tile_char enters mid-instruction — alternate decode: JSR $46E7 / AND #$03 / BEQ $8889
render_get_tile_char     EQU $8881

; NOTE: render_offset_end enters mid-instruction — alternate decode: INC $FF49,X / STA ($FE),Y / DEX
render_offset_end EQU $88D9

render_animate       EQU $882F

; (11 forward-reference equates, 10 with alternate decode notes)

            ORG  $5000

; ###########################################################################
; ###                                                                     ###
; ###               BOOT / INITIALIZATION ($5000-$54FF)                   ###
; ###                                                                     ###
; ###########################################################################
;
;   The boot sequence runs once when the game starts. It loads supporting
;   data files from disk (UPDT patch file, SOSA/SOSM sound data), then
;   initializes the game state and enters the main loop.
;
;   APPLE II BOOT SEQUENCE:
;   ProDOS loads ULT3 at $5000 and jumps to the first instruction. The
;   JSR $B60F call enters the ProDOS BASIC.SYSTEM interpreter to execute
;   the BLOAD commands that follow as inline text strings. This is a clever
;   bootstrap: the engine uses the BASIC interpreter's own BLOAD command
;   to load its supporting files, then takes over the machine entirely.
;
;   The $46B7 call is to SUBS' command processor, which reads the text
;   commands after the JSR as Apple II DOS/ProDOS commands.
;
; ---------------------------------------------------------------------------

            jsr  $B60F           ; Enter ProDOS BASIC.SYSTEM command processor
            jsr  $46B7           ; Execute inline BLOAD commands:

; --- Inline BLOAD commands (read by BASIC.SYSTEM, not executed as 6502) ---
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D UPDT"
            DB      $8D
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D SOSA"
            DB      $8D
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D SOSM"
            DB      $8D
            DB      $00 ; null terminator
            DB      $A9,$B4,$A2,$2D,$A0,$80,$20,$A3,$03,$C9,$C5,$F0,$03,$6C,$F0,$03
            DB      $20,$C0,$46,$20,$38,$73,$20,$4A,$50,$20,$5D,$6F,$4C,$87,$50,$A9
            DB      $00,$85,$FA,$A9,$1E,$85,$F9,$20,$BA,$46,$1D,$31,$1E,$00,$A9,$1E
            DB      $85,$F9,$A9,$04,$85,$FA,$20,$BA,$46,$1D,$32,$1E,$00,$A9,$1E,$85
            DB      $F9
boot_init_data_1
            DB      $A9,$08,$85
boot_init_data_2
            DB      $FA,$20,$BA,$46,$1D,$33,$1E,$00,$A9,$1E,$85,$F9,$A9,$0C,$85,$FA
            DB      $20,$BA,$46,$1D,$34,$1E,$00,$60
; --- End data region (129 bytes) ---

; ---------------------------------------------------------------------------
; boot_setup_game — Initialize game state after loading
; ---------------------------------------------------------------------------
;
;   PURPOSE: Called once after all data files are loaded. Sets up the
;            ProDOS file I/O buffer, clears game flags, and enters the
;            main game loop. This is the transition from boot to gameplay.
;
;   INITIALIZATION:
;     $B403/$B404 = ProDOS I/O buffer address ($5800 + $FF prefix)
;     $CB = 0 (light timer — no torch lit)
;     $10 = 0 (combat_active_flag — not in combat)
;     $B2 = 0 (disk I/O complete flag)
;     $B0/$B1 = 1 (disk I/O request flags — trigger initial load)
;     $C010 = clear keyboard strobe (discard any boot-time keypresses)
;
; ---------------------------------------------------------------------------
boot_setup_game  lda  #$58            ; ProDOS I/O buffer at $5800
            sta  $B403
            lda  #$FF            ; Buffer prefix byte
            sta  $B404
            lda  #$00
            sta  $CB             ; Clear torch timer
            sta  $10             ; Clear combat flag
            jsr  $0230           ; Call ProDOS MLI setup
            lda  #$00
            sta  $B2             ; Clear disk I/O complete flag
            lda  #$01
            sta  $B0             ; Request initial file load
            sta  $B1             ; Request initial display update
            bit  $C010           ; Clear keyboard strobe (KBDSTRB)

; ---------------------------------------------------------------------------
; boot_check_quit — Integrity check and main loop entry point
; ---------------------------------------------------------------------------
;
;   ANTI-CHEAT CHECKSUM:
;   Compares $36/$37 against expected values ($4A/$B4). If the checksum
;   has been tampered with (e.g., by a memory editor), the game exits
;   via PLA/RTS. This is a simple integrity check — the XOR checksum at
;   combat_checksum_xor maintains these values during normal gameplay.
;
;   This label is also the re-entry point from world_move_start after
;   each overworld turn — it's the top of the main game loop.
;
; ---------------------------------------------------------------------------
boot_check_quit  lda  $36             ; Load checksum low byte
            cmp  #$4A            ; Expected value?
            bne  boot_clear_floor ; Yes, or first entry → continue
            lda  $37             ; Load checksum high byte
            cmp  #$B4            ; Expected value?
            beq  boot_clear_floor ; Match → continue (normal)

boot_quit_pop_rts  pla                  ; Checksum mismatch → pop return addr
            rts                  ; and exit to caller (game terminates)

boot_clear_floor  lda  #$00
            sta  $13             ; Clear dungeon level (surface)
            jsr  combat_check_party_alive  ; Check if any party members alive
            cmp  #$0F            ; A=$0000 ; [SP-35]
            bne  boot_quit_pop_rts      ; A=$0000 ; [SP-35]
; === End of while loop ===

            lda  #$18            ; A=$0018 ; [SP-35]
            sta  $F9             ; A=$0018 ; [SP-35]
            lda  #$17            ; A=$0017 ; [SP-35]
            sta  $FA             ; A=$0017 ; [SP-35]
            jsr  $46BA           ; A=$0017 ; [SP-37]
            ora  $A900,X         ; A=$0017 ; [SP-37]
            and  $85             ; A=$0017 ; [SP-37]
            DB      $12
            dec  $12             ; A=$0017 ; [SP-37]

; --- Data region (307 bytes) ---
            DB      $F0,$54,$20,$65,$76,$20,$EA,$46,$A9,$19,$85,$F9,$A9,$17,$85,$FA
            DB      $18,$20,$1F,$BA,$10,$E8,$2C,$10,$C0,$C9,$C1,$90,$07,$C9,$DB,$B0
            DB      $03,$4C,$E9,$51,$C9,$8D,$D0,$03,$4C,$47,$51,$C9,$8B,$D0,$03,$4C
            DB      $47,$51,$C9,$AF,$D0,$03,$4C,$70,$51,$C9,$8A,$D0,$03,$4C,$70,$51
            DB      $C9,$95,$D0,$03,$4C,$99,$51,$C9,$88,$D0,$03,$4C,$C1,$51,$A2,$00
            DB      $86,$CD,$C9,$A0,$D0,$0C,$20,$BA,$46,$D0,$E1,$F3,$F3,$FF,$00,$4C
            DB      $35,$6E,$20,$BA,$46,$D7,$C8,$C1,$D4,$BF,$FF,$00,$A9,$FE,$20,$05
            DB      $47,$4C,$35,$6E,$20,$BA,$46,$CE,$EF,$F2,$F4,$E8,$FF,$00,$A9,$01
            DB      $20,$02,$47,$F0,$03,$4C,$56,$52,$A5,$0A,$20,$2D,$72,$F0,$03,$4C
            DB      $56,$52,$C6,$01,$A5,$01,$29,$3F,$85,$01,$4C,$35,$6E,$20,$BA,$46
            DB      $D3,$EF,$F5,$F4,$E8,$FF,$00,$A9,$03,$20,$02,$47,$F0,$03,$4C,$56
            DB      $52,$A5,$0B,$20,$2D,$72,$F0,$03,$4C,$56,$52,$E6,$01,$A5,$01,$29
            DB      $3F,$85,$01,$4C,$35,$6E,$20,$BA,$46,$C5,$E1,$F3,$F4,$FF,$00,$A9
            DB      $02,$20,$02,$47,$F0,$03,$4C,$56,$52,$A5,$0C,$20,$2D,$72,$F0,$03
            DB      $4C,$56,$52,$E6,$00,$A5,$00,$29,$3F,$85,$00,$4C,$35,$6E,$20,$BA
            DB      $46,$D7,$E5,$F3,$F4,$FF,$00,$A9,$04,$20,$02,$47,$F0,$03,$4C,$56
            DB      $52,$A5,$0D,$20,$2D,$72,$F0,$03,$4C,$56,$52,$C6,$00,$A5,$00,$29
            DB      $3F,$85,$00,$4C,$35,$6E,$A2,$00,$86,$CD,$48,$A9,$52,$48,$A9,$07
            DB      $48,$A9,$A3,$85,$FE,$A9,$03,$85,$FF,$EE,$05,$52,$A9,$03,$A2,$A3
            DB      $A0,$33,$6B
; --- End data region (307 bytes) ---

; ---------------------------------------------------------------------------
; input_dispatch_entry — Keyboard command router
; ---------------------------------------------------------------------------
;
;   PURPOSE: Converts a keypress into a function call. This is the central
;            command dispatch for Ultima III's turn-based input system.
;
;   ALGORITHM:
;   The player presses a letter key (A-Z). The engine:
;   1. Subtracts $C1 (high-ASCII 'A') to get index 0-25
;   2. Doubles the index (×2) since each table entry is a 16-bit address
;   3. Reads a function pointer from the jump table at $5222
;   4. Stores the address in $FE/$FF and jumps indirect
;
;   JUMP TABLE at $5222:
;   26 entries (A-Z), each a 16-bit address (lo/hi) of the handler:
;     A=Attack, B=Board, C=Cast, D=Descend/Direction, E=Enter,
;     F=(combat), G=Get, H=Hand equip, I=Ignite, J=Join Gold,
;     K=Klimb, L=(reserved), M=Mix, N=Negate, O=Other command,
;     P=Peer, Q=Quit&Save, R=Ready weapon, S=Steal, T=Transact,
;     U=Use, V=Volume, W=Wear armor, X=X-it, Y=Yell, Z=Ztats
;
;   DESIGN CONTEXT:
;   This single-letter command vocabulary was a hallmark of early Ultima
;   games and influenced by mainframe text adventures. Each command maps
;   to exactly one keypress — no menus, no mouse, no multi-key combos.
;   The indirect jump table is the fastest dispatch method on the 6502,
;   taking only ~20 cycles from keypress to handler entry.
;
;   NOTE: The bytes CE 00 CE / 05 52 / C9 1A are actually the tail end
;   of inline data from the previous region — CIDAR disassembles them as
;   INC $CE00,X / ORA $52 / CMP #$1A but they execute as part of the
;   data flow from the calling code above.
;
; ---------------------------------------------------------------------------
input_dispatch_entry  inc  $CE00,X         ; (data flow from above — not a real INC)
            ora  $52             ; (continuation of data flow)
            cmp  #$1A            ; Compare key index against 26 (A-Z range)
            bne  input_dispatch_jump      ; Not in range → skip table lookup
            pla                  ; Pull key character from stack
            sec
            sbc  #$C1            ; Convert high-ASCII 'A'-'Z' → index 0-25
            asl  a               ; ×2 for 16-bit table entries
            tay                  ; Y = table offset
            lda  $5222,Y         ; Load handler address (lo byte)
            sta  $FE             ; → $FE = address lo
            lda  $5223,Y         ; Load handler address (hi byte)
            sta  $FF             ; → $FF = address hi
input_dispatch_jump  jmp  ($00FE)         ; Jump indirect to command handler

; ---
            DB      $99,$52,$F5,$52,$5C,$53,$10,$59,$1E,$59,$9A,$5A,$69,$5B,$8F,$5D
            DB      $F1,$5F,$4E,$60
; ---

input_load_cmd_offset  ldy  $D160,X         ; A=A-$C1 Y=A ; [SP-71]
; LUMA: epilogue_rts
            rts                  ; A=A-$C1 Y=A ; [SP-69]
            DB      $F6,$60
input_parse_action  lda  ($61,X)         ; A=A-$C1 Y=A ; [SP-69]
            DB      $E2
            adc  ($9D,X)         ; A=A-$C1 Y=A ; [SP-69]

; --- Data region (53 bytes, text data) ---
            DB      $64,$05,$65,$00,$66,$C5,$66,$64,$67,$F4,$68,$4D,$69,$77,$69,$28
            DB      $6A,$5A,$6A,$BA,$6A,$20,$BA,$46,$C9,$CE,$D6,$C1,$CC,$C9,$C4,$A0
            DB      $CD,$CF,$D6,$C5,$A1,$FF,$00,$A9,$FF,$20,$05,$47,$AD,$69,$B7,$C9
            DB      $AA,$D0,$02,$68,$60
; --- End data region (53 bytes) ---

; XREF: 1 ref (1 branch) from input_parse_action
input_jump_to_loop  jmp  game_loop_end_turn   ; A=A-$C1 Y=A ; [SP-70]

; ---
            DB      $20,$BA,$46,$BC,$AD,$D7,$C8,$C1,$D4,$BF,$FF,$00,$4C,$68,$52
input_not_here_msg
            DB      $20,$BA,$46,$CE,$CF,$D4,$A0,$C8,$C5,$D2,$C5,$A1,$FF
; ---

; LUMA: int_brk
            brk  #$4C            ; A=A-$C1 Y=A ; [SP-71]
            pla                  ; A=[stk] Y=A ; [SP-71]

; ---
            DB      $52,$A9,$7A,$85,$1F,$20,$BA,$46,$C1,$F4,$F4,$E1,$E3,$EB,$AD,$00
            DB      $20,$73,$7D,$20,$A4,$7C,$10,$04,$4C,$88,$52
; ---


; ---------------------------------------------------------------------------
; input_combat_render_unit — Render a creature on the combat/overworld map
; ---------------------------------------------------------------------------
;
;   PURPOSE: Draws a single creature from the tracking arrays onto the
;            map display. Used during combat and overworld rendering to
;            place creature sprites at their current positions.
;
;   CREATURE TRACKING ARRAYS ($4F00-$4F9F):
;   The engine maintains 5 parallel arrays of 32 entries each:
;     $4F00,X = creature type/ID (bit 0 set = alive)
;     $4F20,X = terrain tile under creature (saved for restore)
;     $4F40,X = creature X position on map
;     $4F60,X = creature Y position on map
;     $4F80,X = behavior flags (AI mode in upper 2 bits)
;
;   TILE APPEARANCE LOGIC:
;   If the creature has a saved-terrain value ($4F20,X ≠ 0):
;     - Extract creature appearance: (saved_terrain >> 2) & 3
;     - Add $24 to get tile index ($24-$27 = creature animation frames)
;   This gives 4 animation frames for creature movement.
;
;   After rendering, the creature type ($4F00,X) is checked:
;     - If $1E (ship type) and transport is not $16 (ship): replace with
;       $2C (frigate tile) for visual distinction between allied and
;       enemy ships.
;
;   The creature entry is then cleared ($4F00,X = 0) to prevent
;   double-rendering on the next frame.
;
; ---------------------------------------------------------------------------
input_combat_render_unit  txa                  ; Save creature index
            pha                  ; Push X to stack
            jsr  $0230           ; ProDOS MLI call (sync display)
            pla                  ; Restore creature index
            tax
            lda  $4F40,X         ; Load creature X position
            sta  $02             ; → combat_cursor_x
            lda  $4F60,X         ; Load creature Y position
            sta  $03             ; → combat_cursor_y
            jsr  $46FF           ; Compute map tile pointer
            lda  $4F20,X         ; Load terrain-under-creature
            beq  input_store_tile      ; Zero = no terrain → use as-is
            lsr  a               ; Extract animation frame:
            lsr  a               ;   (terrain >> 2) & 3
            and  #$03
            clc
            adc  #$24            ; + $24 = creature tile ($24-$27)
input_store_tile  sta  ($FE),Y         ; Write creature tile to map
            lda  $4F00,X         ; Load creature type
            lsr  a               ; Shift right (bit 0 → carry)
            sta  $CE             ; Store shifted type in current_tile
            pha                  ; Save for later comparison
            lda  #$00
            sta  $4F00,X         ; Clear creature entry (consumed)
            pla                  ; Restore shifted type
            cmp  #$1E            ; Is this a ship? ($3C >> 1 = $1E)
            bne  input_jump_render      ; No → render normally
            lda  $0E             ; Check current transport mode
            cmp  #$16            ; Already on a ship?
            beq  input_jump_render      ; Yes → render as normal ship
            lda  #$2C            ; No → use frigate tile for enemy ships
            sta  ($FE),Y         ; Override tile display
input_jump_render  jmp  render_combat_update     ; Trigger display refresh

; --- Data region (356 bytes, text data) ---
            DB      $A3,$03,$A5,$0E,$C9,$7E,$F0,$0C,$20,$BA,$46,$C2,$EF,$E1,$F2,$E4
            DB      $00,$4C,$79,$52,$20,$FC,$46,$C9,$28,$F0,$10,$C9,$2C,$F0,$2A,$20
            DB      $BA,$46,$C2,$EF,$E1,$F2,$E4,$00,$4C,$79,$52,$A9,$04,$91,$FE,$A9
            DB      $14,$85,$0E,$85,$E0,$20,$BA,$46,$CD,$EF,$F5,$EE,$F4,$A0,$E8,$EF
            DB      $F2,$F3,$E5,$A1,$FF,$00,$4C,$35,$6E,$A9,$00,$91,$FE,$A9,$16,$85
            DB      $0E,$85,$E0,$20,$BA,$46,$C2,$EF,$E1,$F2,$E4,$A0,$E6,$F2,$E9,$E7
            DB      $E1,$F4,$E5,$A1,$FF,$00,$4C,$35,$6E,$A9,$03,$A2,$A3,$A0,$33,$20
            DB      $A3,$03,$C9,$1A,$D0,$FC,$A9,$78,$85,$1F,$A5,$D5,$85,$D6,$20,$BA
            DB      $46,$C3,$E1,$F3,$F4,$A0,$E2,$F9,$A0,$F7,$E8,$EF,$ED,$BF,$AD,$00
            DB      $20,$24,$70,$D0,$19,$4C,$35,$6E,$20,$BA,$46,$C9,$CE,$C3,$C1,$D0
            DB      $C1,$C3,$C9,$D4,$C1,$D4,$C5,$C4,$A1,$FF,$00,$4C,$68,$52,$A5,$D5
            DB      $85,$D6,$20,$BA,$75,$D0,$E1,$A0,$17,$B1,$FE,$C9,$C3,$F0,$4F,$C9
            DB      $D0,$F0,$4B,$C9,$C9,$F0,$47,$C9,$D7,$F0,$67,$C9,$CC,$F0,$63,$C9
            DB      $C1,$F0,$5F,$C9,$C4,$F0,$17,$C9,$D2,$F0,$13,$20,$BA,$46,$CE,$CF
            DB      $D4,$A0,$C1,$A0,$CD,$C1,$C7,$C5,$A1,$FF,$00,$4C,$68,$52,$20,$BA
            DB      $46
            ASC     "SPELL TYPE W/C-"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$D7,$F0,$2A,$C9,$C3,$F0,$02,$D0,$E0,$20,$BA,$46
            ASC     "CLERIC SPELL-"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$C1,$90,$E8,$C9,$D1,$B0,$E4,$38,$E9,$B1,$85,$D7
            DB      $4C,$59,$54,$20,$BA,$46,$D7,$C9,$DA,$C1,$D2,$C4,$A0,$D3,$D0,$C5,$CC,$CC,$AD
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$C1,$90,$E8,$C9,$D1,$B0,$E4,$38,$E9,$C1,$85,$D7
            DB      $4C,$59,$54,$20,$46,$74,$48,$29,$7F,$20,$CC,$46,$20,$BA,$46,$FF
            DB      $00
; --- End data region (356 bytes) ---


; ---------------------------------------------------------------------------
; input_spell_check_done — Verify spell was successfully cast
; ---------------------------------------------------------------------------
;
;   PURPOSE: After a spell casting attempt, checks whether the spell
;            resolved or was cancelled. The sentinel at $5362 is set
;            to $20 (space) when a spell completes successfully.
;            If not $20, the cast was interrupted or failed — pop
;            the return address and exit early.
;
;   After a successful cast, sets up the character pointer ($46F6)
;   and loads the spell index ($D7) for the effect resolver.
;
; ---------------------------------------------------------------------------
input_spell_pop_rts  pla                  ; Discard return address
            rts                  ; Early exit — spell cancelled/failed
input_spell_check_done  lda  $5362           ; Check spell completion sentinel
            cmp  #$20            ; $20 = space = spell resolved
            bne  input_spell_pop_rts      ; Not resolved → abort

            jsr  $46F6           ; Setup character pointer for caster
            lda  $D7             ; Load spell index for effect dispatch
            and  #$0F            ; A=A&$0F X=[stk] Y=A ; [SP-131]
            tax                  ; A=A&$0F X=A Y=A ; [SP-131]
            lda  #$05            ; A=$0005 X=A Y=A ; [SP-131]
            jsr  combat_bcd_multiply      ; A=$0005 X=A Y=A ; [SP-133]
            ldy  #$19            ; A=$0005 X=A Y=$0019 ; [SP-133]
; LUMA: data_ptr_offset
            lda  ($FE),Y         ; A=$0005 X=A Y=$0019 ; [SP-133]
            cmp  $D0             ; A=$0005 X=A Y=$0019 ; [SP-133]
            bcs  input_cmd_table     ; A=$0005 X=A Y=$0019 ; [SP-133]
            jsr  $46BA           ; Call $0046BA(A, Y)
            cmp  $D0AE           ; A=$0005 X=A Y=$0019 ; [SP-135]
            ldx  $D4A0           ; A=$0005 X=A Y=$0019 ; [SP-135]
            DB      $CF
            DB      $CF
            ldy  #$CC            ; [SP-135]

; ---
            DB      $CF,$D7,$A1,$FF,$00,$4C,$68,$52
input_cmd_table
            DB      $F8,$38,$B1,$FE,$E5,$D0,$91,$FE,$D8,$20,$BA,$46,$FF
; ---

; LUMA: int_brk
            brk  #$A5            ; A=$0005 X=A Y=$0019 ; [SP-139]

; --- Data region (259 bytes, text data) ---
            DB      $D7
            DB      $18,$69,$59,$20,$32,$89,$20,$BA,$46,$FF,$FF,$00,$A5,$D7,$0A,$A8
            DB      $B9,$B7,$54,$85,$FE,$B9,$B8,$54,$85,$FF,$6C,$FE,$00,$F7,$54,$22
            DB      $55,$66,$55,$70,$55,$8A,$55,$A2,$55,$A9,$55,$DC,$55,$EC,$55,$F6
            DB      $55,$FC,$55,$4D,$56,$54,$56,$5E,$56,$6E,$56,$B6,$56,$BD,$56,$7E
            DB      $57,$E8,$56,$66,$55,$8A,$55,$70,$55,$1F,$57,$49,$57,$90,$57,$EC
            DB      $55,$9F,$57,$AE,$57,$4D,$56,$BD,$57,$B6,$56,$11,$58,$A5,$E2,$C9
            DB      $80,$F0,$03,$4C,$6E,$58,$A5,$CE,$C9,$30,$F0,$03,$4C,$6E,$58,$AD
            DB      $21,$55,$F0,$03,$4C,$6E,$58,$A9,$FF,$8D,$21,$55,$20,$E7,$46,$30
            DB      $03,$4C,$6E,$58,$4C,$B6,$56,$00,$A9,$28,$20,$E4,$46,$09,$10,$85
            DB      $D0,$A5,$E2,$C9,$80,$F0,$03,$4C,$6E,$58,$20,$BA,$46
            ASC     "DIRECT-"
            DB      $00 ; null terminator
            DB      $20,$73,$7D,$20,$85,$58,$A4,$D5,$B9,$A0,$99,$85,$02,$B9,$A4,$99
            DB      $85,$03,$20,$41,$7D,$10,$03,$4C,$6E,$58,$85,$FB,$A9,$F7,$20,$05
            DB      $47,$20,$C7,$84,$4C,$82,$58,$A9,$0A,$85,$CC,$20,$85,$58,$4C,$82
            DB      $58,$A5,$E2,$C9,$01,$F0,$03,$4C,$6E,$58,$20,$85,$58,$A5,$13,$C9
            DB      $07,$90,$03,$4C,$6E,$58,$E6,$13,$4C,$2B,$57,$A5,$E2,$C9,$01,$F0
            DB      $03,$4C,$6E,$58,$20,$85,$58,$A5,$13,$D0,$03,$4C,$6B
; --- End data region (259 bytes) ---

input_dungeon_random_pos  ror  $13C6           ; A=$0005 X=A Y=$0019 ; [SP-168]
            jmp  input_dungeon_gen_pos      ; A=$0005 X=A Y=$0019 ; [SP-168]

; --- Data region (393 bytes) ---
            DB      $A9,$4B,$85,$D0,$4C,$2B,$55,$20,$85,$58,$A5,$E2,$F0,$03,$4C,$6E
            DB      $58,$A5,$0E,$C9,$16,$D0,$03,$4C,$6E,$58,$A9,$40,$20,$E4,$46,$85
            DB      $02,$A9,$40,$20,$E4,$46,$85,$03,$20,$FF,$46,$C9,$04,$D0,$EB,$A5
            DB      $02,$85,$00,$A5,$03,$85,$01,$4C,$82,$58,$20,$F6,$46,$A0,$14,$B1
            DB      $FE,$20,$5F,$71,$0A,$85,$D0,$4C,$2B,$55,$A9,$FA,$85,$CC,$20,$85
            DB      $58,$4C,$82,$58,$20,$85,$58,$4C,$01,$54,$A9,$4B,$85,$D0,$A5,$E2
            DB      $C9,$80,$F0,$03,$4C,$6E,$58,$20,$85,$58,$A9,$08,$85,$FB,$C6,$FB
            DB      $10,$03,$4C,$35,$6E,$20,$E7,$46,$29,$03,$F0,$F2,$A6,$FB,$BD,$98
            DB      $99,$F0,$EB,$BD,$80,$99,$85,$02,$BD,$88,$99,$85,$03,$20,$18,$7E
            DB      $A9,$78,$91,$FE,$20,$28,$03,$A9,$F7,$20,$05,$47,$A5,$CE,$A0,$00
            DB      $91,$FE,$20,$28,$03,$20,$C7,$84,$4C,$10,$56,$A9,$FF,$85,$D0,$4C
            DB      $2B,$55,$20,$85,$58,$A9,$14,$85,$CB,$4C,$82,$58,$20,$F6,$46,$A0
            DB      $14,$B1,$FE,$20,$5F,$71,$0A,$85,$D0,$4C,$00,$56,$A5,$E2,$C9,$80
            DB      $F0,$03,$4C,$6E,$58,$20,$85,$58,$A9,$08,$85,$FB,$C6,$FB,$10,$03
            DB      $4C,$35,$6E,$A6,$FB,$BD,$98,$99,$F0,$F2,$A9,$05,$9D,$98,$99,$BD
            DB      $80,$99,$85,$02,$BD,$88,$99,$85,$03,$20,$18,$7E,$A9,$78,$91,$FE
            DB      $20,$28,$03,$A9,$F7,$20,$05,$47,$A5,$CE,$A0,$00,$91,$FE,$20,$28
            DB      $03,$4C,$7E,$56,$A9,$FF,$85,$D0,$4C,$00,$56,$A5,$E2,$C9,$80,$F0
            DB      $03,$4C,$6E,$58,$A5,$CE,$C9,$32,$F0,$03,$4C,$6E,$58,$AD,$E7,$56
            DB      $F0,$03,$4C,$6E,$58,$A9,$FF,$8D,$E7,$56,$20,$E7,$46,$30,$03,$4C
            DB      $6E,$58,$4C,$B6,$56,$00,$A9,$14,$20,$E4,$46,$69,$0A,$20,$6F,$71
            DB      $85,$D0,$4C,$F7,$56,$20,$BA,$46
            ASC     "HEAL WHOM?-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$6E,$58,$A5,$D0,$20,$07,$71,$20,$E4,$88
            DB      $20,$85,$58,$20,$E4,$88,$4C,$82,$58,$20,$85,$58,$A5,$E2,$C9,$01
            DB      $F0,$03,$4C,$6E,$58
; --- End data region (393 bytes) ---


; ---------------------------------------------------------------------------
; input_dungeon_gen_pos — Generate random valid dungeon position
; ---------------------------------------------------------------------------
;
;   PURPOSE: Places the party at a random empty tile in the current
;            dungeon level. Used for teleportation effects and some
;            trap outcomes.
;
;   ALGORITHM (rejection sampling):
;   1. Generate random X in range 0-15 ($46E4 = random mod A)
;   2. Generate random Y in range 0-15
;   3. Look up tile at (X,Y) on current dungeon level (calc_hgr_scanline)
;   4. If tile is non-zero (wall/obstacle) → retry from step 1
;   5. If tile is zero (empty floor) → place party there
;
;   This is a classic rejection sampling loop — simple but potentially
;   slow if the dungeon is very dense. In practice, Ultima III dungeon
;   levels always have enough open space to converge quickly.
;
; ---------------------------------------------------------------------------
input_dungeon_gen_pos  lda  #$10            ; Range: 0-15 (dungeon is 16×16)
            jsr  $46E4           ; Random X = rand() mod 16
            sta  $02             ; → trial X position
            lda  #$10
            jsr  $46E4           ; Random Y = rand() mod 16
            sta  $03             ; → trial Y position
            jsr  calc_hgr_scanline      ; Look up tile at (X,Y)
            bne  input_dungeon_gen_pos      ; Non-empty → reject, try again
            lda  $02             ; Accept: copy trial position
            sta  $00             ; → map_cursor_x
            lda  $03
            sta  $01             ; → map_cursor_y
            jmp  input_return_to_loop      ; Return to game loop

; --- Data region (276 bytes, text data) ---
            DB      $20,$BA,$46
            ASC     "CURE WHOM?-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$6E,$58,$20,$E4,$88,$20,$85,$58,$20,$E4
            DB      $88,$20,$F6,$46,$A0,$11,$B1,$FE,$C9,$D0,$F0,$03,$4C,$6E,$58,$A9
            DB      $C7,$91,$FE,$4C,$82,$58,$20,$85,$58,$20,$E7,$46,$29,$03,$F0,$EC
            DB      $A9,$00,$8D,$DC,$5B,$4C,$9B,$5B,$A5,$E2,$C9,$01,$F0,$03,$4C,$6E
            DB      $58,$20,$85,$58,$4C,$6B,$6E,$A9,$50,$20,$E4,$46,$69,$14,$20,$6F
            DB      $71,$85,$D0,$4C,$F7,$56,$20,$85,$58,$A5,$E2,$C9,$01,$F0,$03,$4C
            DB      $D5,$64,$4C,$9A,$8F,$A5,$E2,$C9,$80,$D0,$03,$4C,$6E,$58,$20,$BA
            DB      $46
            ASC     "RESURECT WHOM?-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$6E,$58,$20,$E4,$88,$20,$85,$58,$20,$E4
            DB      $88,$20,$F6,$46,$A0,$11,$B1,$FE,$C9,$C4,$F0,$03,$4C,$6E,$58,$20
            DB      $E7,$46,$29,$03,$D0,$09,$A0,$11,$A9,$C1,$91,$FE,$4C,$6E,$58,$A9
            DB      $C7,$A0,$11,$91,$FE,$4C,$82,$58,$A5,$E2,$C9,$80,$D0,$03,$4C,$6E
            DB      $58,$20,$BA,$46
            ASC     "RECALL WHOM?-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$6E,$58,$20,$E4,$88,$20,$85,$58,$20,$E4
            DB      $88,$20,$F6,$46,$A0,$11,$B1,$FE,$C9,$C1,$F0,$03,$4C,$6E,$58,$A5
            DB      $D5,$48,$A5,$D6,$85,$D5,$20,$F6,$46,$A0,$15,$F8,$B1,$FE,$38,$E9
            DB      $05,$91
; --- End data region (276 bytes) ---


; === while loop starts here (counter: Y 'iter_y') [nest:7] ===
; XREF: 1 ref (1 branch) from input_spell_setup_slot
input_recall_set_status  inc  $68D8,X         ; A=[$0003] X=A Y=$0019 ; [SP-298]
            sta  $D5             ; A=[$0003] X=A Y=$0019 ; [SP-297]
            jsr  $46F6           ; A=[$0003] X=A Y=$0019 ; [SP-299]
            lda  #$C7            ; A=$00C7 X=A Y=$0019 ; [SP-299]
            ldy  #$11            ; A=$00C7 X=A Y=$0011 ; [SP-299]
            sta  ($FE),Y         ; A=$00C7 X=A Y=$0011 ; [SP-299]
            jmp  input_return_to_loop      ; A=$00C7 X=A Y=$0011 ; [SP-299]

; ---
            DB      $20,$BA,$46,$C6,$C1,$C9,$CC,$C5,$C4,$A1,$FF,$00,$A9,$FA,$20,$05
            DB      $47,$4C,$35,$6E
; ---

; XREF: 10 refs (10 jumps) from input_recall_set_status, $005563, $00556D, $00580E, $00571C, ...
input_return_to_loop  jmp  game_loop_end_turn   ; A=$00C7 X=A Y=$0011 ; [SP-305]

; ---
            DB      $20,$C8,$58,$20,$E9,$58,$C9,$D1,$F0,$03
; ---


; === while loop starts here [nest:8] ===
; XREF: 1 ref (1 branch) from input_spell_setup_slot
input_spell_check_class  pla                  ; A=[stk] X=A Y=$0011 ; [SP-308]
            bne  input_spell_done      ; A=[stk] X=A Y=$0011 ; [SP-308]
            lda  $D7             ; A=[$00D7] X=A Y=$0011 ; [SP-308]
            and  #$0F            ; A=A&$0F X=A Y=$0011 ; [SP-308]
            asl  a               ; A=A&$0F X=A Y=$0011 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-308]
            asl  a               ; A=A&$0F X=A Y=$0011 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-308]
            asl  a               ; A=A&$0F X=A Y=$0011 ; [SP-308]
            clc                  ; A=A&$0F X=A Y=$0011 ; [SP-308]
            adc  #$60            ; A=A+$60 X=A Y=$0011 ; [SP-308]
input_spell_setup_slot  tax                  ; A=A+$60 X=A Y=$0011 ; [SP-308]
            lda  #$FD            ; A=$00FD X=A Y=$0011 ; [SP-308]
            ldy  #$30            ; A=$00FD X=A Y=$0030 ; [SP-308]
            jsr  $4705           ; A=$00FD X=A Y=$0030 ; [SP-310]
            jsr  char_decrypt_records       ; A=$00FD X=A Y=$0030 ; [SP-312]
            cmp  #$D1            ; A=$00FD X=A Y=$0030 ; [SP-312]
            bne  input_spell_check_class      ; A=$00FD X=A Y=$0030 ; [SP-312]
; === End of while loop ===

            lda  #$03            ; A=$0003 X=A Y=$0030 ; [SP-312]
            asl  $58B7           ; A=$0003 X=A Y=$0030 ; [SP-312]
            ldx  #$A3            ; A=$0003 X=$00A3 Y=$0030 ; [SP-312]
            dec  $58B8           ; A=$0003 X=$00A3 Y=$0030 ; [SP-312]
            ldy  #$33            ; A=$0003 X=$00A3 Y=$0033 ; [SP-312]
            bpl  input_recall_set_status      ; A=$0003 X=$00A3 Y=$0033 ; [SP-312]
; === End of while loop (counter: Y) ===

            DB      $03
            lsr  $58B7           ; A=$0003 X=$00A3 Y=$0033 ; [SP-312]

; ---
            DB      $EE,$B8,$58,$C9,$1A,$F0,$03,$6C,$F0,$03
; ---

; XREF: 2 refs (2 branches) from input_spell_setup_slot, input_spell_check_class
input_spell_done  rts                  ; A=$0003 X=$00A3 Y=$0033 ; [SP-310]

; --- Data region (33 bytes, text data) ---
            DB      $A5,$10,$30,$1C,$A5,$D7,$29,$0F,$0A,$69,$08,$85,$FB,$20,$E7,$46
            DB      $A2,$28,$A8,$88,$D0,$FD,$2C,$30,$C0,$CA,$D0,$F6,$C6,$FB,$D0,$ED
            DB      $60
; --- End data region (33 bytes) ---


; ###########################################################################
; ###                                                                     ###
; ###             CHARACTER MANAGEMENT ($5506-$6457)                      ###
; ###                                                                     ###
; ###########################################################################
;
;   Character records are 64-byte structures stored at $4000+ (PLRS).
;   The engine encrypts them on disk using XOR $FF to prevent casual
;   hex editing — a simple but effective anti-cheat measure for 1983.
;
;   The decrypt/encrypt functions are the most-called routines in the
;   engine (14+ callers each), invoked before any character field access
;   and after any modification. This XOR toggle pattern means the same
;   function both encrypts and decrypts (XOR is its own inverse).
;

; ---------------------------------------------------------------------------
; char_decrypt_records — XOR-toggle character record encryption
; ---------------------------------------------------------------------------
;
;   PURPOSE: Toggles encryption on all character records. XOR $FF is
;            applied to bytes 1-22 of each record (skipping byte 0,
;            the first character of the name). Since XOR is self-inverse,
;            calling this function twice restores the original data.
;
;   PARAMS:  None (operates on PLRS area via lookup tables)
;   RETURNS: A = last decrypted byte, X = $10, Y = $80
;            Then jumps to indirect dispatch at ($52F3)
;
;   ANTI-CHEAT CONTEXT:
;   Richard Garriott was famously concerned about players cheating with
;   sector editors. The XOR $FF encryption makes character stats unreadable
;   in a hex dump — instead of seeing "99" for max HP, you'd see "66".
;   This was sufficient to deter casual cheating in the pre-Internet era.
;   The encryption only covers bytes 1-22 (stats and flags), leaving byte 0
;   (first name character) in cleartext for the character select screen.
;
;   MEMORY LAYOUT:
;   The lookup tables at $4300/$43C0 contain lo/hi bytes of base addresses
;   for character record pages. X indexes into these tables (starting at 8,
;   running to $B7 = 183) to iterate over all active record pages.
;
; ---------------------------------------------------------------------------
char_decrypt_records   ldx  #$08            ; Start at table index 8

char_decrypt_outer lda  $4300,X         ; Load record page base address (lo)
            sta  $FC             ; → $FC/$FD = record pointer
            lda  $43C0,X         ; Load record page base address (hi)
            sta  $FD
            ldy  #$16            ; 22 bytes to XOR (bytes 1-22)

; --- XOR each byte with $FF (toggle encryption) ---
char_decrypt_inner lda  ($FC),Y         ; Load encrypted/decrypted byte
            eor  #$FF            ; Toggle all bits (XOR $FF)
            sta  ($FC),Y         ; Store result
            dey                  ; Next byte (counting down)
            bne  char_decrypt_inner ; Continue until Y=0 (skip byte 0)

            inx                  ; Next record page
            cpx  #$B8            ; End of table?
            bcc  char_decrypt_outer ; No → continue to next page

            ldy  #$80            ; Y = $80 for caller context
            txa                  ; A = final table index
            sec
            sbc  #$02            ; A = table index - 2
            ldx  #$10            ; X = $10 for caller context
            jmp  ($52F3)         ; Indirect dispatch to caller

; --- Data region (851 bytes) ---
            DB      $20,$BA,$46,$C4,$E5,$F3,$E3,$E5,$EE,$E4,$00,$4C,$79,$52,$20,$BA
            DB      $46,$C5,$EE,$F4,$E5,$F2,$A0,$00,$A5,$E2,$F0,$0A,$C9,$FF,$D0,$03
            DB      $4C,$36,$5A,$4C,$35,$51,$A2,$13,$CA,$10,$03,$4C,$C6,$59,$BD,$B7
            DB      $79,$C5,$00,$D0,$F3,$BD,$CA,$79,$C5,$01,$D0,$EC,$86,$FB,$A5,$0E
            DB      $85,$E0,$A5,$00,$85,$E3,$A5,$01,$85,$E4,$A5,$09,$C9,$0A,$D0,$1F
            DB      $20,$BA,$46,$E4,$F5,$EE,$E7,$E5,$EF,$EE,$A1,$FF,$00,$A9,$01,$48
            DB      $A9,$00,$85,$13,$A9,$01,$85,$00,$85,$01,$85,$14,$4C,$C9,$59,$C9
            DB      $0C,$D0,$1C,$20,$BA,$46,$F4,$EF,$F7,$EE,$A1,$FF,$00,$A9,$02,$48
            DB      $A9,$20,$85,$01,$A9,$01,$85,$00,$A9,$02,$85,$0F,$4C,$C9,$59,$C9
            DB      $0E,$D0,$23,$A9,$1E,$8D,$78,$63,$20,$BA,$46,$E3,$E1,$F3,$F4,$EC
            DB      $E5,$A1,$FF,$00,$A9,$03,$48,$A9,$20,$85,$00,$A9,$3E,$85,$01,$A9
            DB      $02,$85,$0F,$4C,$C9,$59,$4C,$79,$52,$A9,$00,$85,$B1,$85,$B0,$20
            DB      $6A,$65,$18,$A5,$FB,$69,$C1,$8D,$ED,$59,$8D,$F9,$59,$8D,$10,$5A
            DB      $20,$B7,$46,$04,$C2,$CC,$CF,$C1,$C4,$A0,$CD,$C1,$D0,$C1,$8D,$04
            ASC     "BLOAD TLKA"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $68,$85,$E2,$C9,$01,$F0,$30,$20,$B7,$46,$04
            ASC     "BLOAD MONA"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $A5,$E2,$C9,$02,$D0,$05,$85,$B1,$4C,$35,$6E,$A5,$E3,$CD,$B8,$79
            DB      $D0,$07,$A9,$07,$85,$B1,$4C,$35,$6E,$A9,$03,$85,$B1,$4C,$35,$6E
            DB      $4C,$E9,$8C,$A5,$00,$85,$02,$A5,$01,$85,$03,$20,$FF,$46,$C9,$F8
            DB      $F0,$03,$4C,$33,$59,$20,$BA,$46,$F3,$E8,$F2,$E9,$EE,$E5,$A1,$FF
            ASC     "WHO ENTERS?-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$68,$52,$20,$BA,$75,$F0,$03,$4C,$8B,$53
            DB      $A9,$00,$85,$B1,$85,$B0,$A5,$B2,$D0,$FC,$20,$B7,$46,$04
            ASC     "BLOAD SHNE"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $A9,$0A,$85,$B1,$85,$B0,$20,$00,$94,$A9,$0B,$85,$B1,$4C,$35,$6E
            DB      $20,$BA,$46,$C6,$E9,$F2,$E5,$00,$A5,$0E,$C9,$16,$F0,$03,$4C,$79
            DB      $52,$20,$BA,$46,$FF
            ASC     "DIRECT-"
            DB      $00 ; null terminator
            DB      $20,$73,$7D,$A9,$FB,$20,$05,$47,$A5,$00,$85,$02,$A5,$01,$85,$03
            DB      $A9,$04,$85,$D4,$C6,$D4,$F0,$2B,$18,$A5,$02,$65,$04,$29,$3F,$85
            DB      $02,$18,$A5,$03,$65,$05,$29,$3F,$85,$03,$20,$A4,$7C,$10,$1A,$20
            DB      $FF,$46,$48,$A9,$F4,$91,$FE,$20,$30,$02,$20,$FF,$46,$68,$91,$FE
            DB      $4C,$CB,$5A,$20,$30,$02,$4C,$35,$6E,$85,$CE,$20,$FF,$46,$48,$A9
            DB      $F4,$91,$FE,$20,$30,$02,$A9,$F7,$20,$05,$47,$20,$FF,$46,$A6,$CE
            DB      $BD,$00,$4F,$C9,$3C,$D0,$08,$20,$E7,$46,$30,$03,$4C,$5D,$5B,$20
            DB      $E7,$46,$30,$03,$4C,$5D,$5B,$BD,$00,$4F,$4A,$4A,$18,$69,$01,$20
            DB      $32,$89,$20,$BA,$46,$D3,$FF,$C4,$C5,$D3,$D4,$D2,$CF,$D9,$C5,$C4
            DB      $A1,$FF,$00,$68,$20,$FF,$46,$A6,$CE,$BD,$20,$4F,$91,$FE,$A9,$00
            DB      $9D,$00,$4F,$4C,$35,$6E,$20,$FF,$46,$68,$91,$FE,$20,$28,$03,$4C
            DB      $35,$6E,$A9,$FF,$8D,$DC,$5B,$20,$BA,$46,$C7,$C5,$D4,$A0,$C3,$C8
            DB      $C5,$D3,$D4,$A1,$FF
            ASC     "PLR TO SEARCH-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$35,$6E,$20,$BA,$75,$F0,$03,$4C,$8B,$53
            DB      $A5,$00,$85,$02,$A5,$01,$85,$03,$A5,$E2,$C9,$01,$F0,$1B,$20,$FF
            DB      $46,$C9,$24,$90,$11,$C9,$28,$B0,$0D,$29,$03,$0A,$0A,$D0,$02,$A9
            DB      $20,$91,$FE,$4C,$CF,$5B,$4C,$88,$52,$20,$DE,$93,$C9,$40,$D0,$F6
            DB      $A9,$00,$91,$FE,$AD,$DC,$5B,$F0,$05,$20,$E7,$46,$30,$04,$4C,$F4
            DB      $5C,$FF,$20,$E7,$46,$85,$FB,$20,$E7,$46,$25,$FB,$29,$03,$C9,$00
            DB      $F0,$0B,$C9,$01,$F0,$2F,$C9,$02,$F0,$56,$4C,$94,$5C,$20,$BA,$46
            ASC     "ACID TRAP!"
            DB      $FF,$00,$20,$D3,$5C,$20,$E4,$88,$A9,$F7,$20,$05,$47,$20,$E4,$88
            DB      $20,$E7,$46,$29,$37,$20,$81,$71,$4C,$F4,$5C,$20,$BA,$46,$D0,$CF
            DB      $C9,$D3,$CF,$CE,$A0,$D4,$D2,$C1,$D0,$A1,$FF,$00,$20,$D3,$5C,$20
            DB      $E4,$88,$A9,$F7,$20,$05,$47,$20,$E4,$88,$20,$F6,$46,$A0,$11,$A9
            DB      $D0,$91,$FE,$4C,$F4,$5C,$20,$BA,$46,$C2,$CF,$CD,$C2,$A0,$D4,$D2
            DB      $C1,$D0,$A1,$FF,$00,$20,$D3,$5C,$20,$63,$5C,$4C,$35,$6E
; --- End data region (851 bytes) ---


; ---------------------------------------------------------------------------
; char_combat_turn — Process environmental damage for each party member
; ---------------------------------------------------------------------------
;
;   PURPOSE: Applies per-turn environmental effects to all party members.
;            Called when the party is affected by area hazards (poison gas,
;            dungeon traps, lava tiles, etc.).
;
;   ALGORITHM:
;   For each party member ($D5 counting down from party_size-1 to 0):
;     1. Check if character can act (magic_resolve_effect → status check)
;     2. If alive: decrypt stats, generate random damage (AND #$77 caps
;        at 119 BCD), apply damage via combat_apply_damage
;     3. Scale additional damage by dungeon level: (level+1) × 8
;        This makes deeper dungeon levels progressively more lethal
;     4. Re-encrypt stats after modification
;   Finally refresh the status display.
;
;   DUNGEON LEVEL SCALING:
;   The formula (dungeon_level + 1) << 3 means:
;     Level 1: (1+1)×8 = 16 bonus damage
;     Level 4: (4+1)×8 = 40 bonus damage
;     Level 8: (8+1)×8 = 72 bonus damage
;   This steep scaling makes deep dungeons extremely dangerous without
;   proper preparation — a core design choice encouraging gradual
;   progression.
;
;   PARAMS:  None (reads $E1 = party_size, $13 = dungeon_level)
;   RETURNS: After updating all party members and refreshing display
;
; ---------------------------------------------------------------------------
char_combat_turn   lda  $E1             ; Load party_size from PRTY
            sta  $D5             ; → loop counter
            dec  $D5             ; Start at party_size - 1 (0-indexed)

char_turn_loop jsr  magic_resolve_effect       ; Check if this member can act
            bne  char_turn_next    ; Dead/incapacitated → skip
            jsr  render_encrypt_records        ; Decrypt character records
            lda  #$F7            ; Display code for damage flash
            jsr  $4705           ; Flash damage indicator
            jsr  render_encrypt_records        ; Re-encrypt after display access
            jsr  $46E7           ; Generate random byte
            and  #$77            ; Cap at 0-119 BCD (mask off high bits)
            jsr  combat_apply_damage       ; Apply random base damage
            lda  $13             ; Load dungeon_level (0-7)
            clc
            adc  #$01            ; level + 1
            asl  a               ; ×2  — three shifts = ×8
            asl  a               ; ×4
            asl  a               ; ×8 = (level+1) × 8
            jsr  combat_apply_damage       ; Apply level-scaled bonus damage
char_turn_next dec  $D5             ; Next party member (counting down)
            bpl  char_turn_loop    ; Continue until all processed

            jsr  move_display_party_status       ; Refresh party status sidebar
            rts

; --- Data region (469 bytes, text data) ---
            DB      $A5,$D5,$85,$D6,$20,$BA,$46,$C7,$C1,$D3,$A0,$D4,$D2,$C1,$D0,$A1
            DB      $FF,$00,$20,$D3,$5C,$A5,$E1,$85,$D5,$C6,$D5,$20,$BA,$75,$D0,$14
            DB      $20,$E4,$88,$A9,$F7,$20,$05,$47,$20,$E4,$88,$20,$F6,$46,$A0,$11
            DB      $A9,$D0,$91,$FE,$C6,$D5,$10,$E3,$A5,$D6,$85,$D5,$4C,$F4,$5C,$20
            DB      $CF,$75,$F0,$01,$60,$20,$BA,$46,$D4,$D2,$C1,$D0,$A0,$C5,$D6,$C1
            DB      $C4,$C5,$C4,$A1,$FF,$00,$68,$68,$A9,$FA,$20,$05,$47,$4C,$F4,$5C
            DB      $20,$BA,$46,$C7,$CF,$CC,$C4,$AB,$00,$A9,$64,$20,$E4,$46,$09,$30
            DB      $20,$6F,$71,$85,$FB,$20,$D5,$46,$20,$BA,$46,$FF,$00,$A5,$FB,$20
            DB      $BB,$70,$20,$E7,$46,$C9,$40,$90,$03,$4C,$35,$6E,$20,$E7,$46,$30
            DB      $32,$85,$FB,$20,$E7,$46,$25,$FB,$29,$07,$F0,$27,$85,$FB,$20,$BA
            DB      $46
            ASC     "AND A "
            DB      $00 ; null terminator
            DB      $18,$A5,$FB,$69,$41,$20,$32,$89,$20,$BA,$46,$FF,$00,$A5,$FB,$18
            DB      $69,$30,$A8,$A9,$01,$20,$45,$71,$4C,$35,$6E,$20,$E7,$46,$30,$30
            DB      $85,$FB,$20,$E7,$46,$25,$FB,$29,$03,$F0,$25,$85,$FB,$20,$BA,$46
            DB      $C1,$CE,$C4,$A0,$00,$18,$A5,$FB,$69,$51,$20,$32,$89,$20,$BA,$46
            DB      $FF,$00,$A5,$FB,$18,$69,$28,$A8,$A9,$01,$20,$45,$71,$4C,$35,$6E
            DB      $4C,$35,$6E,$20,$BA,$46,$C8,$E1,$EE,$E4,$A0,$E5,$F1,$F5,$E9,$F0
            DB      $ED,$E5,$EE,$F4,$A1,$FF
            ASC     "FROM PLR-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$17,$66,$20,$F6,$46,$A0,$11,$B1,$FE,$D0
            DB      $03,$4C,$17,$66,$A5,$D5,$85,$D6,$20,$BA,$46
            ASC     "  TO PLR-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$17,$66,$20,$F6,$46,$A0,$11,$B1,$FE,$D0
            DB      $03,$4C,$17,$66,$A6,$D5,$A4,$D6,$84,$D5,$86,$D6,$20,$BA,$46
            ASC     "F,G,E,W,A:"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$C6,$F0,$1C,$C9,$C7,$F0,$67,$C9,$C5,$D0,$03,$4C
            DB      $9D,$5E,$C9,$D7,$D0,$03,$4C,$0A,$5F,$C9,$C1,$D0,$03,$4C,$63,$5F
            DB      $4C,$56,$5F,$20,$BA,$46,$C1,$CD,$CF,$D5,$CE,$D4,$AD
            DB      $00 ; null terminator
            DB      $20,$E1,$46,$2C,$10,$C0,$20,$BA,$46,$FF,$00,$A0,$20,$A5,$D0,$20
            DB      $BE,$5F,$F0,$18,$20,$BA,$46,$CE,$CF,$D4,$A0,$C5,$CE,$CF,$D5,$C7
            DB      $C8,$A1,$FF,$00,$A9,$FF,$20,$05,$47,$4C,$35,$6E,$A5,$D6,$85,$D5
            DB      $A5,$D0,$A0,$20,$20,$20,$74
char_turn_done_msg
            DB      $20,$BA,$46,$C4,$CF,$CE,$C5,$A1,$FF
; --- End data region (469 bytes) ---

            brk  #$4C            ; A=A+$01 X=$0010 Y=$0080 ; [SP-576]
            and  $6E,X           ; -> $007E ; A=A+$01 X=$0010 Y=$0080 ; [SP-576]

; --- Data region (179 bytes, text data) ---
            DB      $20,$BA,$46
            ASC     "AMOUNT-"
            DB      $00 ; null terminator
            DB      $20,$E1,$46,$2C,$10,$C0,$20,$BA,$46,$FF,$00,$A0,$23,$A5,$D0,$20
            DB      $BE,$5F,$F0,$03,$4C,$3D,$5E,$A5,$D6,$85,$D5,$A5,$D0,$A0,$23,$20
            DB      $BB,$70,$4C,$60,$5E,$20,$BA,$46
            ASC     "G,K,P,T:"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$C7,$D0,$05,$A0,$25,$4C,$D3,$5E,$C9,$CB,$D0,$05
            DB      $A0,$26,$4C,$D3,$5E,$C9,$D0,$D0,$05,$A0,$27,$4C,$D3,$5E,$C9,$D4
            DB      $D0,$05,$A0,$0F,$4C,$D3,$5E,$4C,$56,$5F,$84,$FB,$20,$BA,$46,$FF
            ASC     "HOW MANY-"
            DB      $00 ; null terminator
            DB      $20,$E1,$46,$20,$BA,$46,$FF,$00,$20,$F6,$46,$A4,$FB,$B1,$FE,$38
            DB      $E5,$D0,$B0,$03,$4C,$3D,$5E,$91,$FE,$A5,$D6,$85,$D5,$A4,$FB,$A5
            DB      $D0,$20,$45,$71,$4C,$60,$5E,$20,$BA,$46
            ASC     "WHICH WEAPON:"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$C2
; --- End data region (179 bytes) ---

; ---------------------------------------------------------------------------
; char_equip_check_weapon — Validate and equip a weapon from inventory
; ---------------------------------------------------------------------------
;
;   PURPOSE: Handles the "Ready weapon" command. Validates the player's
;            weapon choice (A-P, mapped from high-ASCII $C1-$D0), checks
;            whether the character owns it, and equips it.
;
;   CHARACTER RECORD WEAPON LAYOUT (offsets from $FE/$FF pointer):
;     $30 = readied weapon index (0 = Hands, 1-15 = weapon type)
;     $31-$3F = weapon inventory counts (BCD, one per weapon type)
;
;   ALGORITHM:
;   1. Range-check input: must be $C1-$D0 (A-P in high-ASCII)
;   2. Convert to weapon index: subtract $C1 → 0-15
;   3. If index matches currently readied weapon ($30) → already equipped
;   4. Otherwise, check inventory slot ($30 + index) for quantity > 0
;   5. If owned: BCD-decrement inventory, equip the weapon, add 1 to
;      the previous weapon's inventory via combat_add_bcd_field
;   6. If not owned: print "NONE!" error message
;
; ---------------------------------------------------------------------------
char_equip_check_weapon bcc  char_equip_none_msg    ; Below 'A' → invalid
            cmp  #$D1            ; Above 'P'?
            bcs  char_equip_none_msg    ; Yes → invalid (only 16 weapons)
            sec
            sbc  #$C1            ; Convert high-ASCII → weapon index 0-15
            sta  $F0             ; Save weapon index
            jsr  $46F6           ; Setup character pointer ($FE/$FF)
            ldy  #$30            ; Offset $30 = readied weapon
            lda  ($FE),Y         ; Load currently equipped weapon
            cmp  $F0             ; Same as requested?
            bne  char_equip_not_owned    ; No → check inventory
            jmp  char_equip_add_weapon    ; Yes → re-equip (swap logic)
char_equip_not_owned clc
            lda  #$30            ; Base of weapon inventory ($31-$3F)
            adc  $F0             ; + weapon index = inventory slot offset
            tay
            lda  ($FE),Y         ; Load inventory count for this weapon
            beq  char_equip_none_msg    ; Zero → don't own it
            sed                  ; BCD decrement inventory
            sec
            sbc  #$01            ; Count -= 1
            cld
            sta  ($FE),Y         ; Store updated count
            lda  $D6             ; Restore active slot
            sta  $D5
            lda  #$01            ; Return 1 weapon to previous slot
            jsr  combat_add_bcd_field         ; Add to previous weapon's inventory
            jmp  char_turn_done_msg    ; Print "DONE!" and end
; XREF: 8 refs (3 jumps) (5 branches) from char_equip_check_weapon, $005E1B, char_equip_not_owned, char_equip_none_msg, char_equip_check_weapon, ...
char_equip_none_msg jsr  $46BA           ; A=$0001 X=$0010 Y=$0030 ; [SP-610]
            dec  $CECF           ; SLOTEXP_x6CF - Slot expansion ROM offset $6CF {Slot}
            cmp  $A1             ; A=$0001 X=$0010 Y=$0030 ; [SP-610]
            DB      $FF
            brk  #$4C            ; A=$0001 X=$0010 Y=$0030 ; [SP-610]
            pla                  ; A=[stk] X=$0010 Y=$0030 ; [SP-610]

; --- Data region (77 bytes, text data) ---
            DB      $52,$20,$BA,$46
            ASC     "WHICH ARMOUR:"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$C2,$90,$DB,$C9,$C9,$B0,$D7,$38,$E9,$C1,$85,$F0
            DB      $20,$F6,$46,$A0,$28,$B1,$FE,$C5,$F0,$F0,$20,$18,$A9,$28,$65,$F0
            DB      $A8,$B1,$FE,$D0,$03,$4C,$56,$5F,$F8,$38,$E9,$01,$D8,$91,$FE,$A5
            DB      $D6,$85,$D5,$A9,$01,$20,$45,$71,$4C,$60,$5E
; --- End data region (77 bytes) ---

; XREF: 2 refs (1 jump) (1 branch) from char_equip_check_weapon, char_equip_none_msg
char_equip_add_weapon jsr  $46BA           ; A=[stk] X=$0010 Y=$0030 ; [SP-619]
            cmp  #$CE            ; A=[stk] X=$0010 Y=$0030 ; [SP-619]
            ldy  #$D5            ; A=[stk] X=$0010 Y=$00D5 ; [SP-619]
            DB      $D3
            cmp  $A1             ; A=[stk] X=$0010 Y=$00D5 ; [SP-619]

; --- Data region (36 bytes) ---
            DB      $FF,$00,$4C,$68,$52,$85,$F0,$84,$F2,$20,$F6,$46,$A4,$F2,$F8,$38
            DB      $C8,$B1,$FE,$E5,$F0,$91,$FE,$88,$B1,$FE,$E9,$00,$91,$FE,$D8,$90
            DB      $03,$A9,$00,$60
; --- End data region (36 bytes) ---

; XREF: 1 ref (1 branch) from char_equip_add_weapon
char_equip_bcd_add sed                  ; A=[stk] X=$0010 Y=$00D5 ; [SP-619]
            clc                  ; A=[stk] X=$0010 Y=$00D5 ; [SP-619]
            iny                  ; A=[stk] X=$0010 Y=$00D6 ; [SP-619]
            lda  ($FE),Y         ; A=[stk] X=$0010 Y=$00D6 ; [SP-619]
            adc  $F0             ; A=[stk] X=$0010 Y=$00D6 ; [SP-619]
            sta  ($FE),Y         ; A=[stk] X=$0010 Y=$00D6 ; [SP-619]
            dey                  ; A=[stk] X=$0010 Y=$00D5 ; [SP-619]
            lda  ($FE),Y         ; A=[stk] X=$0010 Y=$00D5 ; [SP-619]
            adc  #$00            ; A=A X=$0010 Y=$00D5 ; [SP-619]
            sta  ($FE),Y         ; A=A X=$0010 Y=$00D5 ; [SP-619]
            cld                  ; A=A X=$0010 Y=$00D5 ; [SP-619]
            lda  #$FF            ; A=$00FF X=$0010 Y=$00D5 ; [SP-619]
            rts                  ; A=$00FF X=$0010 Y=$00D5 ; [SP-617]

; --- Data region (481 bytes, text data) ---
            DB      $20,$BA,$46,$C9,$E7,$EE,$E9,$F4,$E5,$A0,$E1,$A0,$F4,$EF,$F2,$E3
            DB      $E8,$FF,$00,$A5,$E2,$C9,$01,$F0,$03,$4C,$88,$52,$20,$BA,$46
            ASC     "WHOSE TORCH-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$35,$6E,$20,$F6,$46,$A0,$0F,$B1,$FE,$D0
            DB      $12,$20,$BA,$46,$CE,$CF,$CE,$C5,$A0,$CC,$C5,$C6,$D4,$A1,$FF,$00
            DB      $4C,$35,$6E,$F8,$38,$E9,$01,$91,$FE,$D8,$A9,$FF,$85,$CC,$4C,$35
            DB      $6E,$20,$BA,$46,$CA,$EF,$E9,$EE,$A0,$E7,$EF,$EC,$E4,$A0,$F4,$EF
            DB      $AD,$00,$20,$24,$70,$D0,$03,$4C,$35,$6E,$C5,$E1,$90,$05,$F0,$03
            DB      $4C,$17,$66,$85,$FB,$A2,$00,$86,$D1,$86,$D2,$F8,$86,$D5,$20,$F6
            DB      $46,$A0,$24,$18,$B1,$FE,$65,$D2,$85,$D2,$8A,$91,$FE,$88,$B1,$FE
            DB      $65,$D1,$85,$D1,$8A,$91,$FE,$90,$06,$A9,$99,$85,$D1,$85,$D2,$E6
            DB      $D5,$A5,$D5,$C5,$E1,$90,$D7,$D8,$A5,$FB,$85,$D5,$C6,$D5,$20,$F6
            DB      $46,$A0,$23,$A5,$D1,$91,$FE,$C8,$A5,$D2,$91,$FE,$4C,$35,$6E,$20
            DB      $BA,$46,$CB,$EC,$E9,$ED,$E2,$A0,$BC,$AD,$D7,$C8,$C1,$D4,$BF,$FF
            DB      $00,$4C,$68,$52,$20,$BA,$46,$CC,$EF,$EF,$EB,$AD,$00,$20,$73,$7D
            DB      $20,$BA,$46,$AD,$BE,$00,$20,$FF,$46,$4A,$4A,$18,$69,$01,$20,$32
            DB      $89,$20,$BA,$46,$FF,$00,$4C,$35,$6E,$20,$BA,$46,$CD,$EF,$E4,$E9
            DB      $E6,$F9,$A0,$EF,$F2,$E4,$E5,$F2,$A1,$FF,$D0,$CC,$D2,$BA,$AD,$00
            DB      $20,$24,$70,$D0,$03,$4C,$91,$61,$38,$E9,$01,$85,$D1,$C5,$E1,$B0
            DB      $73,$20,$BA,$46,$D0,$CC,$D2,$BA,$AD
            DB      $00 ; null terminator
            DB      $20,$24,$70,$F0,$65,$38,$E9,$01,$85,$D2,$C5,$E1,$B0,$5C,$C5,$D1
            DB      $F0,$58,$A5,$D1,$85,$D5,$20,$F6,$46,$A5,$FE,$85,$FC,$A5,$FF,$85
            DB      $FD,$A5,$D2,$85,$D5,$20,$F6,$46,$A4,$D1,$A6,$D2,$B9,$E6,$00,$48
            DB      $B5,$E6,$99,$E6,$00,$68,$95,$E6,$A0,$3F,$B1,$FE,$48,$B1,$FC,$91
            DB      $FE,$68,$91,$FC,$88,$10,$F3,$20,$C0,$46,$20,$62,$6F,$20,$4A,$50
            DB      $A9,$17,$85,$FA,$A9,$18,$85,$F9,$20,$BA,$46,$C5,$D8,$C3,$C8,$C1
            DB      $CE,$C7,$C5,$C4,$A1,$FF,$00,$4C,$35,$6E,$20,$BA,$46,$C1,$C2,$CF
            DB      $D2,$D4,$C5,$C4,$A1,$FF,$00,$4C,$35,$6E,$20,$BA,$46,$CE,$E5,$E7
            DB      $E1,$F4,$E5,$A0,$F4,$E9,$ED,$E5,$A1,$FF
            ASC     "WHOSE POWD?-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$35,$6E,$20,$F6,$46,$A0,$27,$B1,$FE,$D0
            DB      $03,$4C,$2E,$60
; --- End data region (481 bytes) ---

; ---------------------------------------------------------------------------
; char_use_powder — Consume one powder and light the dungeon
; ---------------------------------------------------------------------------
;
;   PURPOSE: Decrements the character's powder count (BCD at offset $27
;            in the character record) and sets the light timer to 10 turns.
;
;   THE SED/CLD BRACKET:
;   The 6502's decimal mode flag (D) makes ADC/SBC operate in BCD instead
;   of binary. All Ultima III inventory counts are stored as BCD, so
;   decrementing a powder count requires SED before the SBC and CLD after.
;   Forgetting the CLD would corrupt all subsequent arithmetic — a bug
;   that plagued many early 6502 programs.
;
;   $CB is the light/torch timer — counts down each turn. Setting it to
;   $0A (10 decimal in BCD) gives 10 turns of illumination.
;
; ---------------------------------------------------------------------------
char_use_powder sed                  ; Enter BCD mode for inventory math
            lda  ($FE),Y         ; Load current powder count
            sec
            sbc  #$01            ; Decrement by 1 (BCD)
            sta  ($FE),Y         ; Store updated count
            cld                  ; Exit BCD mode (CRITICAL)
            lda  #$0A            ; 10 turns of light
            sta  $CB             ; Set torch/light timer
            jmp  game_loop_end_turn   ; End this turn

; --- Data region (166 bytes, text data) ---
            DB      $A9,$FF,$8D,$B9,$6A,$20,$BA,$46,$CF,$F4,$E8,$E5,$F2,$A0,$E3,$EF
            DB      $ED,$ED,$E1,$EE,$E4,$A1,$FF
            ASC     "WHOSE ACTION-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$35,$6E,$20,$BA,$75,$F0,$03,$4C,$8B,$53
            DB      $20,$BA,$46,$C3,$CD,$C4,$BA,$AD,$00,$2C,$10,$C0,$A9,$08,$8D,$A6
            DB      $62,$20,$08,$47,$C9,$8D,$F0,$17,$C9,$C0,$90,$F5,$C9,$DB,$B0,$F1
            DB      $8D,$A7,$62,$29,$7F,$20,$CC,$46,$E6,$F9,$CE,$A6,$62,$D0,$E2,$20
            DB      $BA,$46,$FF,$00,$AD,$A7,$62,$AE,$A6,$62,$C9,$D4,$D0,$07,$E0,$02
            DB      $D0,$03,$4C,$A8,$62,$C9,$C7,$D0,$07,$E0,$05,$D0,$03,$4C,$BA,$63
            DB      $C9,$C8,$D0,$07,$E0,$02,$D0,$03,$4C,$79,$63,$C9,$C5,$D0,$07,$E0
            DB      $03,$D0,$03,$4C,$08,$64,$C9,$D9,$D0,$07,$E0,$04,$D0,$03,$4C,$6B
file_cmd_data_1
            DB      $64
; --- End data region (166 bytes) ---

            cmp  #$C5            ; A=$000A X=$0010 Y=$00D5 ; [SP-695]

; --- Data region (119 bytes, text data) ---
            DB      $D0,$07,$E0,$01,$D0,$03,$4C,$75,$6A,$20,$BA,$46,$CE,$CF,$A0,$C5
            DB      $C6,$C6,$C5,$C3,$D4,$A1,$FF,$00,$4C,$35,$6E,$AA,$00
file_cmd_data_2
            DB      $00,$20,$BA,$46,$C4,$C9,$D2,$AD,$00,$20,$73,$7D,$20,$FF,$46,$C9
            DB      $7C,$F0,$03,$4C,$88,$52,$20,$BA,$46
            ASC     "D, S, L, M-"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$A2,$1E,$C9,$CC,$F0,$12,$E8,$C9,$D3,$F0,$0D,$E8,$C9
            DB      $CD,$F0,$08,$E8,$C9,$C4,$F0,$03,$4C,$79,$52,$86,$F1,$8A,$38,$E9
            DB      $1E,$A8,$20,$D3,$93,$85,$F0,$20,$F6,$46,$A0,$0E,$B1,$FE,$25,$F0
            DB      $D0,$03,$4C,$2E,$60
; --- End data region (119 bytes) ---

; ---------------------------------------------------------------------------
; file_mark_check_slot — Endgame mark/card insertion and Exodus encounter
; ---------------------------------------------------------------------------
;
;   PURPOSE: Handles the "insert card into slot" mechanic at the Exodus
;            encounter. The player must insert 4 cards into 4 slots in
;            a specific sequence. Wrong card → instant death (HP zeroed,
;            $FF damage = 255 BCD, effectively fatal).
;
;   ENDGAME SEQUENCE:
;   Ultima III's endgame is unique in RPG history — you don't fight
;   Exodus with weapons. Instead, you insert the 4 cards (Sol, Moon,
;   Love, Death) into slots on the Exodus machine. Insert them in the
;   wrong order and your characters die. Get all 4 right and you
;   trigger the END sequence.
;
;   file_max_slots ($6378) tracks how many correct insertions have been
;   made. When it reaches $22 (decimal 34 — the completion sentinel),
;   the game BRUNs the END binary to play the victory sequence.
;
;   ENDGAME SETUP LOOP:
;   Once all cards are correctly inserted, the loop prepares each party
;   member's display state ($F0 = flash effect, $7C = special tile)
;   for the victory animation before transitioning to BRUN END.
;
; ---------------------------------------------------------------------------
file_mark_check_slot  ldx  $F1             ; Load mark/card slot index
            cpx  $02             ; Compare against expected slot
            beq  file_mark_check_done      ; Correct slot → continue

; --- Wrong card/slot → kill the character ---
file_mark_apply_loop  jsr  render_encrypt_records        ; Decrypt for stat modification
            lda  #$F7
            jsr  $4705           ; Flash damage effect
            jsr  render_encrypt_records        ; Re-encrypt after display
            jsr  $46F6           ; Setup character pointer
            lda  #$00
            ldy  #$1A            ; Offset $1A = HP (high byte)
            sta  ($FE),Y         ; Zero HP → death
            lda  #$FF            ; 255 damage (fatal)
            jsr  combat_apply_damage       ; Apply lethal damage
            jmp  game_loop_end_turn   ; End turn (character dies)

; --- Correct card inserted → advance toward victory ---
file_mark_check_done  cpx  file_max_slots     ; Check against current progress
            bne  file_mark_apply_loop      ; Mismatch → lethal punishment

            inc  file_max_slots     ; Advance the progress counter
            lda  #$04
            sta  $D0             ; 5 iterations (4 party members + 1)

; --- Prepare victory animation for each party member ---
file_endgame_setup_loop  jsr  $46FF           ; Setup pointer for member
            lda  #$F0            ; Flash effect tile
            sta  ($FE),Y         ; Set display to flash
            jsr  $0230           ; Commit to display
            lda  #$F7
            jsr  $4705           ; Visual effect
            jsr  $46FF           ; Re-setup pointer
            lda  #$7C            ; Victory tile (special graphic)
            sta  ($FE),Y         ; Set display to victory tile
            jsr  $0230           ; Commit to display
            lda  #$F7
            jsr  $4705           ; Visual effect
            dec  $D0             ; Next member
            bpl  file_endgame_setup_loop      ; Continue for all members

; --- Check if all 4 cards have been inserted ---
            lda  #$20            ; Clear display
            ldy  #$00
            sta  ($FE),Y         ; Reset tile at (0,0)
            jsr  $0230           ; Commit
            lda  file_max_slots     ; Load progress counter
            cmp  #$22            ; All cards inserted? ($22 = completion)
            beq  file_endgame_start      ; Yes → trigger endgame!
            jmp  game_loop_end_turn   ; No → wait for next insertion

; --- VICTORY: Load and run the END binary ---
file_endgame_start  lda  #$0A            ; Disk request code for END
            sta  $B1
            sta  $B0
            jsr  $46B7           ; Execute inline command:

; --- Data region (236 bytes, text data) ---
            DB      $04 ; string length
            ASC     "BRUN"
            ASC     " END"
            DB      $8D
            DB      $00 ; null terminator
file_max_slots
            DB      $1E,$A5,$09,$C9,$7C,$F0,$03,$4C,$88,$52,$A5,$00,$29,$03,$A8,$20
            DB      $D3,$93,$85,$F0,$20,$F6,$46,$A0,$0E,$B1,$FE,$05,$F0,$91,$FE,$20
            DB      $BA,$46,$C1,$A0,$C3,$C1,$D2,$C4,$AC,$A0,$D7,$C9,$D4,$C8,$FF,$D3
            DB      $D4,$D2,$C1,$CE,$C7,$C5,$A0,$CD,$C1,$D2,$CB,$D3,$A1,$FF,$00,$4C
            DB      $35,$6E,$A5,$E2,$F0,$03,$4C,$88,$52,$A5,$00,$C9,$21,$F0,$03,$4C
            DB      $DF,$63,$A5,$01,$C9,$03,$F0,$03,$4C,$88,$52,$20,$F6,$46,$A0,$3F
            DB      $A9,$01,$91,$FE,$4C,$F8,$63,$C9,$13,$F0,$03,$4C,$88,$52,$A5,$01
            DB      $C9,$2C,$F0,$03,$4C,$88,$52,$20,$F6,$46,$A0,$2F,$A9,$01,$91,$FE
            DB      $20,$BA,$46,$C5,$D8,$CF,$D4,$C9,$C3,$D3,$A1,$FF,$00,$4C,$35,$6E
            DB      $20,$BA,$46,$C4,$C9,$D2,$AD,$00,$20,$73,$7D,$20,$A4,$7C,$10,$03
            DB      $4C,$88,$52,$85,$CE,$20,$F6,$46,$A0,$23,$B1,$FE,$D0,$18,$20,$BA
            DB      $46,$CE,$CF,$D4,$A0,$C5,$CE,$CF,$D5,$C7,$C8,$A0,$C7,$CF,$CC,$C4
            DB      $A1,$FF,$00,$4C,$68,$52,$F8,$38,$E9,$01,$D8,$91,$FE,$A6,$CE,$BD
            DB      $00,$4F,$C9,$48,$F0,$03,$4C,$93,$62,$BD,$40,$4F,$85,$02,$BD,$60
file_overlay_data
            DB      $4F
; --- End data region (236 bytes) ---

            sta  $03             ; A=$000A X=$0010 Y=$0000 ; [SP-763]
            jsr  $46FF           ; A=$000A X=$0010 Y=$0000 ; [SP-765]

; --- Data region (110 bytes, text data) ---
            DB      $BD,$20,$4F,$91,$FE,$A9,$00,$9D,$00,$4F,$4C,$35,$6E,$A5,$E2,$C9
            DB      $02,$D0,$29,$A5,$E3,$CD,$BB,$79,$D0,$22,$A9,$30,$C5,$00,$D0,$1C
            DB      $C5,$01,$D0,$18,$20,$BA,$46,$FF,$D9,$C5,$CC,$CC,$A0,$A7,$C5,$D6
            DB      $CF,$C3,$C1,$D2,$C5,$A7,$FF,$FF,$00,$4C,$35,$6E,$4C,$93,$62,$20
            DB      $BA,$46,$D0,$E5,$E5,$F2,$A0,$E1,$F4,$A0,$E7,$E5,$ED,$A1,$FF
            ASC     "WHOSE GEM-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$35,$6E,$20,$F6,$46,$A0,$25,$B1,$FE,$D0
            DB      $03,$4C,$2E,$60
; --- End data region (110 bytes) ---

; ---------------------------------------------------------------------------
; file_use_gem_bcd — Use a gem to see a world overview map
; ---------------------------------------------------------------------------
;
;   PURPOSE: Consumes one gem from the character's inventory, then loads
;            the OUTM (outdoor map overview) overlay from disk to display
;            a zoomed-out view of the surrounding area.
;
;   IMPLEMENTATION:
;   1. BCD-decrement gem count at offset $25 in character record
;   2. Reset map cursor to (0,0) for the overview renderer
;   3. Save current $B0 (disk I/O request) state
;   4. Wait for any pending disk I/O to complete
;   5. BLOAD OUTM overlay file from disk
;   6. Restore $B0 and trigger display update
;
;   GEMS AND EXPLORATION:
;   In Ultima III, gems are a limited consumable that reveals the local
;   map — essential for navigating dungeons and finding hidden locations.
;   This creates an economy around exploration: gems are expensive, so
;   players must choose carefully when to use them.
;
; ---------------------------------------------------------------------------
file_use_gem_bcd  sed                  ; Enter BCD mode
            lda  ($FE),Y         ; Load gem count (offset $25)
            sec
            sbc  #$01            ; Decrement by 1 (BCD)
            sta  ($FE),Y         ; Store updated count
            cld                  ; Exit BCD mode
            lda  #$00
            sta  $02             ; Reset overview cursor X = 0
            sta  $03             ; Reset overview cursor Y = 0
            lda  $B0             ; Save current disk I/O request state
            pha
            lda  #$00
            sta  $B1             ; Clear display update flag
            sta  $B0             ; Clear disk I/O request

; --- Spin-wait for disk, then BLOAD OUTM overlay ---
file_wait_vblank  lda  $B2             ; Check disk busy flag
            bne  file_wait_vblank      ; Still busy → wait
            jsr  $46B7           ; Execute inline BLOAD command:

; --- Data region (197 bytes, text data) ---
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D OUTM"
            DB      $8D
            DB      $00 ; null terminator
            DB      $A9,$0A,$85,$B0,$68,$85,$B1,$20,$00,$94,$4C,$35,$6E,$20,$BA,$46
            DB      $D1,$F5,$E9,$F4,$A0,$A6,$A0,$F3,$E1,$F6,$E5,$AE,$AE,$AE,$FF,$00
            DB      $A5,$E2,$F0,$1D,$20,$BA,$46,$CF,$CE,$CC,$D9,$A0,$CF,$CE,$A0,$D3
            DB      $D5,$D2,$C6,$C1,$C3,$C5,$A1,$FF,$00,$A9,$FF,$20,$05,$47,$4C,$35
            DB      $6E,$20,$3F,$65,$4C,$35,$6E,$A5,$0E,$85,$E0,$A5,$00,$85,$E3,$A5
            DB      $01,$85,$E4,$A5,$EA,$20,$D5,$46,$A5,$EB,$20,$D5,$46,$A5,$EC,$20
            DB      $D5,$46,$A5,$ED,$20,$D5,$46,$20,$BA,$46,$A0,$CD,$CF,$D6,$C5,$D3
            DB      $FF,$00,$20,$BA,$46,$D0,$CC,$C5,$C1,$D3,$C5,$A0,$D7,$C1,$C9,$D4
            DB      $AE,$AE,$AE,$FF,$00
file_save_game
            DB      $AD,$F1,$03,$C9,$B7,$EA,$EA,$A5,$B0,$48,$A9,$00,$85,$B1,$85,$B0
game_loop_vblank
            DB      $A5,$B2,$D0,$FC,$20,$B7,$46,$04
            DB      $C2
            DB      $D3,$C1,$D6,$C5,$A0,$D3,$CF,$D3,$C1,$8D,$04
            ASC     "BSAVE SOSM"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $4C,$BD,$65,$A5,$B0,$48,$A9
            DB      $00 ; null terminator
; --- End data region (202 bytes) ---

; ###########################################################################
; ###                                                                     ###
; ###              GAME MAIN LOOP ($65B0-$6F42)                           ###
; ###                                                                     ###
; ###########################################################################
;
;   The central state machine of Ultima III. This is the heartbeat of the
;   entire game. Each iteration:
;
;   1. Wait for disk I/O completion (VBlank sync)
;   2. Save party state (BSAVE PLRS, BSAVE PRTY)
;   3. Poll keyboard for input
;   4. Dispatch to command handler (move, attack, cast, get, etc.)
;   5. Process turn effects (poison, food depletion, MP regen)
;   6. Check for random encounters
;   7. Update display
;   8. Loop back to step 1
;
;   GAME DESIGN — THE TURN STRUCTURE:
;   Ultima III uses a hybrid turn system. In the overworld, time advances
;   with each player action (move, search, etc.). In combat, it's strictly
;   turn-based with a round-robin among party members and monsters. The
;   game_main_loop handles the overworld turn; combat has its own loop
;   (render_combat_loop_start) that temporarily takes over.
;
;   FILE I/O — CONTINUOUS AUTOSAVE:
;   The game saves PLRS and PRTY to disk EVERY TURN. This is both a
;   feature (no lost progress on power failure — critical for 1983 when
;   the Apple II had no battery backup) and an anti-cheat measure (you
;   can't reload an old save to undo bad outcomes). The $B0/$B1/$B2 flags
;   coordinate asynchronous disk I/O with the ProDOS MLI.
;
; ---------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; file_save_and_dispatch — Save party state to disk, then dispatch command
; ---------------------------------------------------------------------------
;
;   CONTINUOUS AUTOSAVE MECHANISM:
;   Every single turn, the game saves both PLRS (character records at
;   $4000, 4×64 bytes) and PRTY (party state at $E0, 16 bytes) to disk.
;   This happens BEFORE the next command is processed, ensuring that no
;   game state is ever lost — even if the player turns off the Apple II
;   mid-game.
;
;   The $B0/$B1/$B2 flags coordinate disk I/O:
;     $B0 = save request pending (set to 1 to request save)
;     $B1 = display update pending
;     $B2 = disk busy flag (non-zero while ProDOS is writing)
;
;   The game spins on $B2 before issuing new BSAVE commands to avoid
;   corrupting the disk if a previous write is still in progress.
;   This busy-wait pattern is the only synchronization mechanism — there
;   are no interrupts or DMA on the Apple II.
;
;   DESIGN RATIONALE:
;   Richard Garriott insisted on persistent save state to prevent "save
;   scumming" — reloading saves to undo bad outcomes. Combined with the
;   XOR encryption, this was Ultima's answer to cheating. Death is real:
;   if your party dies, the save file already reflects it.
;
; ---------------------------------------------------------------------------
            sta  $B1             ; Clear save request flags
            sta  $B0

; --- Spin-wait for any pending disk I/O to complete ---
game_loop_wait_vblank lda  $B2             ; Check disk busy flag
            bne  game_loop_wait_vblank ; Still busy → keep waiting
            jsr  $46B7           ; Execute inline BSAVE commands via BASIC:

; --- Data region (54 bytes, text data) ---
            DB      $04 ; string length
            ASC     "BSAV"
            ASC     "E PLRS"
            DB      $8D
            DB      $04 ; string length
            ASC     "BSAV"
            ASC     "E PRTY"
            DB      $8D
            DB      $00 ; null terminator
            DB      $68,$85,$B1,$85,$B0,$A9,$65,$48,$A9,$F7,$48,$A9,$A3,$85,$FE,$A9
            DB      $03,$85,$FF,$EE,$F5,$65,$A9,$03,$A2,$A3,$A0,$33,$6B
; --- End data region (54 bytes) ---

; ---------------------------------------------------------------------------
; game_loop_dispatch_entry — Secondary command dispatch after file save
; ---------------------------------------------------------------------------
;
;   This is the second half of the command dispatch mechanism. After the
;   autosave completes, execution falls through here. Like input_dispatch_entry,
;   the leading bytes (CE 00 CE / F5 65) are actually the tail end of inline
;   data — CIDAR sees INC $CE00,X / SBC $65,X but they're data.
;
;   The actual dispatch uses the same $FE/$FF indirect jump mechanism
;   established by input_dispatch_entry above.
;
; ---------------------------------------------------------------------------
game_loop_dispatch_entry inc  $CE00,X         ; (data flow — not a real instruction)
            sbc  $65,X           ; (continuation of data flow)

game_loop_check_key cmp  #$1A            ; Range check for dispatch
            bne  game_loop_check_key    ; Not ready → wait
            rts                  ; Return to caller

; --- Data region (413 bytes, text data) ---
            DB      $20,$BA,$46,$D2,$E5,$E1,$E4,$F9,$A0,$E6,$EF,$F2,$A0,$A3,$A0,$AD
            DB      $A0,$00,$20,$02,$70,$D0,$17,$20,$BA,$46,$CE,$CF,$A0,$D3,$D5,$C3
            DB      $C8,$A0,$D0,$CC,$C1,$D9,$C5,$D2,$A1,$FF,$00,$4C,$68,$52,$C9,$05
            DB      $B0,$E5,$85,$D5,$C6,$D5,$20,$BA,$46
            ASC     "WEAPON-"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$C1,$90,$EE,$C9,$D1,$B0,$EA,$85,$F0,$20,$F6,$46
            DB      $A0,$17,$B1,$FE,$A2,$00,$DD,$07,$6A,$F0,$05,$E8,$E0,$0B,$90,$F6
            DB      $A5,$F0,$C9,$D0,$F0,$19,$DD,$12,$6A,$90,$14,$20,$BA,$46,$CE,$CF
            DB      $D4,$A0,$C1,$CC,$CC,$CF,$D7,$C5,$C4,$A1,$FF,$00,$4C,$68,$52,$38
            DB      $E9,$C1,$85,$D7,$F0,$1F,$20,$F6,$46,$18,$A9,$30,$65,$D7,$A8,$B1
            DB      $FE,$D0,$12,$20,$BA,$46,$CE,$CF,$D4,$A0,$CF,$D7,$CE,$C5,$C4,$A1
            DB      $FF,$00,$4C,$68,$52,$18,$A5,$D7,$69,$41,$20,$32,$89,$20,$BA,$46
            ASC     " READY"
            DB      $FF,$00,$20,$F6,$46,$A0,$30,$A5,$D7,$91,$FE,$4C,$35,$6E,$20,$BA
            DB      $46,$D0,$EC,$F2,$A0,$F4,$EF,$A0,$F3,$F4,$E5,$E1,$EC,$AD,$00,$20
            DB      $24,$70,$D0,$03,$4C,$35,$6E,$20,$BA,$75,$F0,$03,$4C,$8B,$53,$20
            DB      $BA,$46
            ASC     "DIRECT-"
            DB      $00 ; null terminator
            DB      $20,$73,$7D,$20,$CF,$75,$F0,$3E,$20,$E7,$46,$29,$03,$F0,$0F,$20
            DB      $BA,$46,$C6,$C1,$C9,$CC,$C5,$C4,$A1,$FF,$00,$4C,$35,$6E,$A2,$3F
            DB      $BD,$00,$4F,$C9,$48,$D0,$05,$A9,$C0,$9D,$80,$4F,$CA,$10,$F1,$20
            DB      $BA,$46,$D7,$C1,$D4,$C3,$C8,$A0,$CF,$D5,$D4,$A1,$FF,$00,$A9,$FA
            DB      $20,$05,$47,$4C,$35,$6E,$20,$FF,$46,$C9,$94,$90,$BB,$C9,$E8,$B0
            DB      $B7,$18,$A5,$02,$65,$04,$18,$65,$04,$85,$02,$18,$A5,$03,$65,$05
            DB      $18,$65,$05,$85,$03,$20,$FF,$46,$C9,$24,$D0,$9C,$A9,$20,$91,$FE
            DB      $4C,$F4,$5C,$20,$BA,$46,$D7,$E8,$EF,$A0,$F7,$E9,$EC,$EC,$FF,$D4
            DB      $F2,$E1,$EE,$F3,$E1,$E3,$F4,$AD,$00,$20,$24,$70,$D0,$03,$4C,$35
            DB      $6E,$20,$BA,$75,$F0,$03,$4C,$8B,$53,$20,$BA,$46
            ASC     "DIRECT-"
            DB      $00 ; null terminator
            DB      $20,$73,$7D,$20,$A4,$7C,$10,$6B
; --- End data region (413 bytes) ---

game_loop_setup_ptr jsr  $46FF           ; A=[$00B2] X=$0010 Y=$0000 ; [SP-873]
            cmp  #$94            ; A=[$00B2] X=$0010 Y=$0000 ; [SP-873]
            bcs  game_loop_check_encounter    ; A=[$00B2] X=$0010 Y=$0000 ; [SP-873]
            jmp  input_not_here_msg      ; A=[$00B2] X=$0010 Y=$0000 ; [SP-873]
; XREF: 1 ref (1 branch) from game_loop_setup_ptr
game_loop_check_encounter cmp  #$E8            ; A=[$00B2] X=$0010 Y=$0000 ; [SP-873]
            bcc  game_loop_no_encounter    ; A=[$00B2] X=$0010 Y=$0000 ; [SP-873]
            jmp  input_not_here_msg      ; A=[$00B2] X=$0010 Y=$0000 ; [SP-873]
; XREF: 1 ref (1 branch) from game_loop_check_encounter
game_loop_no_encounter clc                  ; A=[$00B2] X=$0010 Y=$0000 ; [SP-873]
            lda  $02             ; A=[$0002] X=$0010 Y=$0000 ; [SP-873]
            adc  $04             ; A=[$0002] X=$0010 Y=$0000 ; [SP-873]
            sta  $02             ; A=[$0002] X=$0010 Y=$0000 ; [SP-873]
            clc                  ; A=[$0002] X=$0010 Y=$0000 ; [SP-873]
            lda  $03             ; A=[$0003] X=$0010 Y=$0000 ; [SP-873]
            adc  $05             ; A=[$0003] X=$0010 Y=$0000 ; [SP-873]
            sta  $03             ; A=[$0003] X=$0010 Y=$0000 ; [SP-873]
            jsr  $46FF           ; A=[$0003] X=$0010 Y=$0000 ; [SP-875]
            cmp  #$40            ; A=[$0003] X=$0010 Y=$0000 ; [SP-875]
            beq  game_loop_check_y    ; A=[$0003] X=$0010 Y=$0000 ; [SP-875]
            jmp  input_not_here_msg      ; A=[$0003] X=$0010 Y=$0000 ; [SP-875]
; XREF: 1 ref (1 branch) from game_loop_no_encounter
game_loop_check_y lda  $01             ; A=[$0001] X=$0010 Y=$0000 ; [SP-875]
            and  #$07            ; A=A&$07 X=$0010 Y=$0000 ; [SP-875]
            clc                  ; A=A&$07 X=$0010 Y=$0000 ; [SP-875]
            adc  #$B0            ; A=A+$B0 X=$0010 Y=$0000 ; [SP-875]
            sta  $67E7           ; A=A+$B0 X=$0010 Y=$0000 ; [SP-875]
            lda  #$00            ; A=$0000 X=$0010 Y=$0000 ; [SP-875]
            sta  $B1             ; A=$0000 X=$0010 Y=$0000 ; [SP-875]
            sta  $B0             ; A=$0000 X=$0010 Y=$0000 ; [SP-875]

; === while loop starts here [nest:14] ===
; XREF: 1 ref (1 branch) from game_loop_get_viewport
game_loop_get_viewport lda  $B2             ; A=[$00B2] X=$0010 Y=$0000 ; [SP-875]
            bne  game_loop_get_viewport    ; A=[$00B2] X=$0010 Y=$0000 ; [SP-875]
            jsr  $46B7           ; A=[$00B2] X=$0010 Y=$0000 ; [SP-877]

; --- Data region (347 bytes, text data) ---
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D SHP@"
            DB      $8D
            DB      $00 ; null terminator
            DB      $A5,$D5,$85,$D6,$20,$BD,$88,$A9,$06,$85,$B1,$85,$B0,$20,$00,$94
            DB      $A5,$E2,$85,$B1,$A5,$D6,$85,$D5,$20,$BD,$88,$4C,$35,$6E,$BD,$00
            DB      $4F,$C9,$4C,$D0,$03,$4C,$32,$68,$BD,$80,$4F,$29,$0F,$F0,$06,$20
            DB      $24,$89,$4C,$35,$6E,$20,$BA,$46,$FF,$C7,$CF,$CF,$C4,$A0,$C4,$C1
            DB      $D9,$A1,$FF,$FF,$00,$4C,$35,$6E,$A9,$08,$85,$B0,$20,$BA,$46,$FF
            ASC     "WELCOME MY CHILD"
            DB      $FF,$00,$20,$F6,$46,$A0,$1C,$B1,$FE,$A0,$1E,$D1,$FE,$90,$05,$F0
            DB      $03,$4C,$DA,$68,$C9,$25,$90,$10,$20,$BA,$46,$CE,$CF,$A0,$CD,$CF
            DB      $D2,$C5,$A1,$FF,$00,$4C,$F1,$68,$C9,$05,$90,$2B,$A0,$0E,$B1,$FE
            DB      $29,$80,$D0,$23,$20,$BA,$46,$D3,$C5,$C5,$CB,$A0,$D9,$C5,$AC,$A0
            DB      $D4,$C8,$C5,$FF,$CD,$C1,$D2,$CB,$A0,$CF,$C6,$A0,$CB,$C9,$CE,$C7
            DB      $D3,$A1,$FF,$00,$4C,$F1,$68,$A0,$1C,$B1,$FE,$F8,$18,$69,$01,$D8
            DB      $C9,$25,$90,$02,$A9,$25,$91,$FE,$20,$BA,$46,$D4,$C8,$CF,$D5,$A0
            DB      $C1,$D2,$D4,$A0,$C7,$D2,$C5,$C1,$D4,$C5,$D2,$FF,$FF,$00,$20,$E9
            DB      $58,$A9,$FD,$A2,$80,$A0,$40,$20,$05,$47,$20,$E9,$58,$4C,$F1,$68
            DB      $20,$BA,$46,$C5,$D8,$D0,$C5,$D2,$C9,$C5,$CE,$C3,$C5,$A0,$CD,$CF
            DB      $D2,$C5,$A1,$A1,$FF,$FF,$00,$4C,$35,$6E,$A5,$E2,$C9,$01,$D0,$03
            DB      $4C,$88,$52,$20,$BA,$46,$D5,$EE,$EC,$EF,$E3,$EB,$AD,$00,$20,$73
            DB      $7D,$A5,$05,$D0,$EB,$20,$FF,$46,$C9,$B8,$D0,$E4,$20,$BA,$46
            ASC     "WHOSE KEY-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$35,$6E,$20,$F6,$46,$A0,$26,$B1,$FE,$D0
            DB      $03,$4C,$2E,$60
; --- End data region (347 bytes) ---

; ---------------------------------------------------------------------------
; game_loop_food_deduct — Consume food and update NPC tile animation
; ---------------------------------------------------------------------------
;
;   PURPOSE: Decrements the active character's food supply (BCD) and
;            updates the NPC/creature tile appearance based on the
;            current tile type ($09).
;
;   FOOD AS TIME:
;   In Ultima III, food serves as the game's time currency. Every
;   action (move, search, attack) costs food. When food reaches zero,
;   the party begins taking starvation damage. This creates urgency —
;   the player can't wander indefinitely and must plan routes to
;   provisions. The food depletion rate is configurable (default 4,
;   stored at $772C in ULT3), controlling game difficulty.
;
;   ASL of $09 (tile type) doubles it to get the animated tile index —
;   the engine uses even/odd tile pairs for animation frames.
;
; ---------------------------------------------------------------------------
game_loop_food_deduct sed                  ; Enter BCD mode for food math
            sec
            sbc  #$01            ; Decrement food by 1 (BCD)
            sta  ($FE),Y         ; Store updated food count
            cld                  ; Exit BCD mode
            jsr  $46FF           ; Re-setup character pointer
            lda  $09             ; Load current tile type
            asl  a               ; ×2 for animation tile pair index
            sta  ($FE),Y         ; Store animated tile appearance
            jsr  $0230           ; ProDOS MLI call (commit state)
            jmp  game_loop_end_turn   ; End this turn

; --- Data region (1256 bytes, text data) ---
            DB      $20,$BA,$46,$D6,$EF,$EC,$F5,$ED,$E5,$A0,$00,$A5,$10,$49,$FF,$85
            DB      $10,$30,$0B,$20,$BA,$46,$CF,$CE,$A1,$FF,$00,$4C,$35,$6E,$20,$BA
            DB      $46,$CF,$C6,$C6,$A1,$FF,$00,$4C,$35,$6E,$20,$BA,$46,$D7,$E5,$E1
            DB      $F2,$A0,$E6,$EF,$F2,$A0,$A3,$A0,$AD,$A0,$00,$20,$02,$70,$D0,$03
            DB      $4C,$17,$66,$C9,$05,$B0,$F9,$85,$D5,$C6,$D5,$20,$BA,$46
            ASC     "ARMOUR-"
            DB      $00 ; null terminator
            DB      $20,$49,$54,$C9,$C1,$90,$EE,$C9,$C9,$B0,$EA,$85,$F0,$20,$F6,$46
            DB      $A0,$17,$B1,$FE,$A2,$00,$DD,$07,$6A,$F0,$05,$E8,$E0,$0B,$90,$F6
            DB      $A5,$F0,$C9,$C8,$F0,$08,$DD,$1D,$6A,$90,$03,$4C,$6C,$66,$38,$E9
            DB      $C1,$85,$D7,$F0,$10,$20,$F6,$46,$18,$A9,$28,$65,$D7,$A8,$B1,$FE
            DB      $D0,$03,$4C,$94,$66,$18,$A5,$D7,$69,$51,$20,$32,$89,$20,$BA,$46
            ASC     " READY"
            DB      $FF,$00,$20,$F6,$46,$A0,$28,$A5,$D7,$91,$FE,$4C,$35,$6E,$C6,$C3
            DB      $D7,$D4,$D0,$C2,$CC,$C9,$C4,$C1,$D2,$D1,$C4,$C3,$C8,$D1,$D1,$D1
            DB      $C4,$C4,$C3,$CC,$C9,$C5,$C3,$C4,$C6,$C4,$C3,$C4,$C3,$C3,$C8,$20
            DB      $BA,$46,$D8,$AD,$E9,$F4,$A0,$00,$A5,$0E,$C9,$7E,$D0,$03,$4C,$79
            DB      $52,$20,$FC,$46,$C9,$05,$90,$03,$4C,$88,$52,$A5,$0E,$0A,$91,$FE
            DB      $A9,$7E,$85,$0E,$20,$BA,$46,$E3,$F2,$E1,$E6,$F4,$FF,$00,$4C,$35
            DB      $6E,$A9,$00,$8D,$B9,$6A,$20,$BA,$46,$D9,$E5,$EC,$EC,$AC,$A0,$F7
            DB      $E8,$EF,$ED,$BF,$AD,$00,$4C,$07,$62,$4C,$93,$62,$AD,$B9,$6A,$D0
            DB      $F8,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$40,$F0,$ED,$A5,$E2,$D0,$E9
            DB      $A5,$00,$C9,$0A,$D0,$E3,$A5,$01,$C9,$3B,$F0,$07,$C9,$38,$F0,$0A
            DB      $4C,$72,$6A,$A9,$38,$85,$01,$4C,$A7,$6A,$A9,$3B,$85,$01,$20,$C3
            DB      $46,$A9,$FD,$A2,$C0,$A0,$40,$20,$05,$47,$20,$30,$02,$4C,$35,$6E
            DB      $00,$AD,$4A,$B4,$C9,$08,$F0,$03,$4C,$1D,$6A,$20,$BA,$46,$DA,$F4
            DB      $E1,$F4,$F3,$A0,$E6,$EF,$F2,$A0,$A3,$A0,$AD,$A0,$00,$20,$24,$70
            DB      $D0,$03,$4C,$35,$6E,$20,$F6,$46,$A0,$00,$84,$D7,$B1,$FE,$D0,$03
            DB      $4C,$35,$6E,$29,$7F,$20,$CC,$46,$E6,$F9,$E6,$D7,$20,$F6,$46,$A4
            DB      $D7,$B1,$FE,$D0,$EE,$20,$BA,$46,$FF
            ASC     "STR..."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$12,$B1,$FE,$20,$D5,$46,$20,$BA,$46,$FF
            ASC     "DEX..."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$13,$B1,$FE,$20,$D5,$46,$20,$BA,$46,$FF
            ASC     "INT..."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$14,$B1,$FE,$20,$D5,$46,$20,$BA,$46,$FF
            ASC     "WIS..."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$15,$B1,$FE,$20,$D5,$46,$20,$4A,$70,$20,$BA,$46
            DB      $FF
            ASC     "H.P..."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$1A,$B1,$FE,$20,$D5,$46,$20,$F6,$46,$A0,$1B,$B1
            DB      $FE,$20,$D5,$46,$20,$4A,$70,$20,$BA,$46,$FF
            ASC     "H.M..."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$1C,$B1,$FE,$20,$D5,$46,$20,$F6,$46,$A0,$1D,$B1
            DB      $FE,$20,$D5,$46,$20,$4A,$70,$20,$BA,$46,$FF
            ASC     "GOLD: "
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$23,$B1,$FE,$20,$D5,$46,$20,$F6,$46,$A0,$24,$B1
            DB      $FE,$20,$D5,$46,$20,$4A,$70,$20,$BA,$46,$FF
            ASC     "EXP..."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$1E,$B1,$FE,$20,$D5,$46,$20,$F6,$46,$A0,$1F,$B1
            DB      $FE,$20,$D5,$46,$20,$4A,$70,$20,$BA,$46,$FF
            ASC     "GEMS.."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$25,$B1,$FE,$20,$D5,$46,$20,$4A,$70,$20,$BA,$46
            DB      $FF
            ASC     "KEYS.."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$26,$B1,$FE,$20,$D5,$46,$20,$4A,$70,$20,$BA,$46
            DB      $FF
            ASC     "POWD.."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$27,$B1,$FE,$20,$D5,$46,$20,$4A,$70,$20,$BA,$46
            DB      $FF
            ASC     "TRCH.."
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$0F,$B1,$FE,$20,$D5,$46,$20,$4A,$70,$20,$F6,$46
            DB      $A0,$0E,$B1,$FE,$29,$08,$F0,$15,$20,$BA,$46,$FF
            ASC     "CARD OF DEATH"
            DB      $00 ; null terminator
            DB      $20,$4A,$70,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$02,$F0,$13,$20,$BA
            DB      $46,$FF
            ASC     "CARD OF SOL"
            DB      $00 ; null terminator
            DB      $20,$4A,$70,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$01,$F0,$14,$20,$BA
            DB      $46,$FF
            ASC     "CARD OF LOVE"
            DB      $00 ; null terminator
            DB      $20,$4A,$70,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$04,$F0,$15,$20,$BA
            DB      $46,$FF
            ASC     "CARD OF MOONS"
            DB      $00 ; null terminator
            DB      $20,$4A,$70,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$10,$F0,$15,$20,$BA
            DB      $46,$FF
            ASC     "MARK OF FORCE"
            DB      $00 ; null terminator
            DB      $20,$4A,$70,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$20,$F0,$14,$20,$BA
            DB      $46,$FF
            ASC     "MARK OF FIRE"
            DB      $00 ; null terminator
            DB      $20,$4A,$70,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$40,$F0,$15,$20,$BA
            DB      $46,$FF
            ASC     "MARK OF SNAKE"
            DB      $00 ; null terminator
            DB      $20,$4A,$70,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$80,$F0,$15,$20,$BA
            DB      $46,$FF
            ASC     "MARK OF KINGS"
            DB      $00 ; null terminator
            DB      $20,$4A,$70,$20,$BA,$46,$FF
            ASC     "WEAPON:"
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$30,$B1,$FE,$18,$69,$41,$20,$32,$89,$20,$4A,$70
            DB      $20,$BA,$46,$FF
            ASC     "ARMOUR:"
            DB      $00 ; null terminator
            DB      $20,$F6,$46,$A0,$28,$B1,$FE,$18,$69,$51,$20,$32,$89,$20,$4A,$70
            DB      $20,$BA,$46,$FF
            ASC     "**WEAPONS**"
            DB      $00 ; null terminator
            DB      $A9,$10,$85,$D7,$C6,$D7,$F0,$3A,$20,$F6,$46,$18,$A9,$30,$65,$D7
            DB      $A8,$B1,$FE,$F0,$EF,$48,$20,$BA,$46,$FF,$00,$68,$20,$D5,$46,$20
            DB      $BA,$46,$AD,$00,$18,$A5,$D7,$69,$41,$20,$32,$89,$18,$A5,$D7,$69
            DB      $C1,$8D,$BA,$6D,$20,$BA,$46,$AD,$A8,$00,$A9,$00,$20,$4A,$70,$4C
            DB      $85,$6D,$20,$BA,$46,$FF,$B0,$B2,$AD,$C8,$C1,$CE,$C4,$D3,$AD,$A8
            DB      $C1,$A9,$FF
            ASC     "**ARMOUR**"
            DB      $00 ; null terminator
            DB      $A9,$08,$85,$D7,$C6,$D7,$F0,$3A,$20,$F6,$46,$18,$A9,$28,$65,$D7
            DB      $A8,$B1,$FE,$F0,$EF,$48,$20,$BA,$46,$FF,$00,$68,$20,$D5,$46,$20
            DB      $BA,$46,$AD,$00,$18,$A5,$D7,$69,$51,$20,$32,$89,$18,$A5,$D7,$69
            DB      $C1,$8D,$18,$6E,$20,$BA,$46,$AD,$A8,$00,$A9,$00,$20,$4A,$70,$4C
            DB      $E3,$6D,$20,$BA,$46,$FF,$B0,$B1,$AD,$D3,$CB,$C9,$CE,$AD,$A8,$C1
            DB      $A9,$FF,$00,$4C,$35,$6E
; --- End data region (1256 bytes) ---


; ---------------------------------------------------------------------------
; game_loop_end_turn — Central turn dispatcher (52 callers!)
; ---------------------------------------------------------------------------
;
;   PURPOSE: The single convergence point for ALL command handlers. Every
;            action in the game (move, attack, cast, get, etc.) eventually
;            JMPs here when done. This function processes end-of-turn
;            effects and dispatches to the appropriate location handler.
;
;   LOCATION TYPE DISPATCH ($E2):
;   The party's current location type determines which subsystem runs:
;     $00 = Sosaria overworld → check_surface_only (day/night, encounters)
;     $01 = Dungeon → $1800 dungeon renderer + dungeon_turn_process
;     $02 = Town/Castle → standard turn processing
;     $80 = Combat → render_combat_loop_start (tactical grid)
;
;   TOWN EXIT DETECTION:
;   When location_type ≥ 2 (town) and map position (0,0) or (X,0), the
;   party has walked off the map edge. The engine restores saved overworld
;   coordinates ($E3/$E4 = saved_x/saved_y from PRTY) and transitions
;   back to the surface, loading overworld sound data.
;
;   52 CALLERS:
;   Every command handler, every combat resolution, every spell effect
;   ends by jumping here. This is the narrowest bottleneck in the entire
;   engine — all game flow passes through this single point.
;
; ---------------------------------------------------------------------------
game_loop_end_turn jsr  $03AF           ; ProDOS event handler (inter-turn)
            lda  #$03
            ldx  #$A3
            ldy  #$33
            jsr  $03A3           ; ProDOS MLI setup for display refresh
            cmp  #$1A            ; Ready for next turn?
            bne  game_loop_end_turn   ; Not yet → retry (wait for I/O)
            lda  $E2             ; Load location_type from PRTY
            bne  game_loop_check_dungeon   ; Non-zero → not overworld
            pha                  ; Save location_type
            jsr  check_surface_only     ; Overworld turn processing
            pla                  ; Restore location_type

; --- Dispatch by location type ---
game_loop_check_dungeon cmp  #$01            ; Dungeon?
            bne  game_loop_check_surface
            jsr  $1800           ; Render 3D dungeon view
            jmp  dungeon_turn_process      ; Process dungeon turn
game_loop_check_surface cmp  #$80            ; Combat?
            bne  game_loop_check_town
            jmp  render_combat_loop_start      ; Enter combat subsystem
game_loop_check_town cmp  #$02            ; Town or castle?
            bcc  game_loop_call_terrain   ; Below 2 → surface movement
            lda  $00             ; Check map X position
            beq  game_loop_load_saved_x   ; X=0 → at map edge, exit town
            lda  $01             ; Check map Y position
            bne  game_loop_call_terrain   ; Y≠0 → still in town

; --- Exit town/castle: restore overworld position ---
game_loop_load_saved_x lda  $E3             ; Restore saved_x from PRTY
            sta  $00             ; → map_cursor_x
            lda  $E4             ; Restore saved_y from PRTY
            sta  $01             ; → map_cursor_y
            lda  #$FF
            sta  $0F             ; Force map reload flag
            lda  #$00
            sta  $E2             ; Set location_type = overworld
            sta  $B1             ; Clear display update
            sta  $B0             ; Clear disk I/O request

; === while loop starts here [nest:15] ===
; XREF: 1 ref (1 branch) from game_loop_get_music
game_loop_get_music lda  $B2             ; A=[$00B2] X=$00A3 Y=$0033 ; [SP-1200]
            bne  game_loop_get_music   ; A=[$00B2] X=$00A3 Y=$0033 ; [SP-1200]
            jsr  $46BA           ; Call $0046BA(A)
            cmp  $D8             ; A=[$00B2] X=$00A3 Y=$0033 ; [SP-1202]
            cmp  #$D4            ; A=[$00B2] X=$00A3 Y=$0033 ; [SP-1202]
            ldy  #$D4            ; A=[$00B2] X=$00A3 Y=$00D4 ; [SP-1202]
            DB      $CF
            ldy  #$D3            ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1202]

; --- Data region (67 bytes, text data) ---
            DB      $CF
            DB      $D3,$C1,$D2,$C9,$C1,$A1,$FF,$00,$20,$BA,$46,$D0,$CC,$C5,$C1,$D3
            DB      $C5,$A0,$D7,$C1,$C9,$D4,$AE,$AE,$AE,$FF,$00,$20,$B7,$46,$04,$C2
            DB      $CC,$CF,$C1,$C4,$A0,$D3,$CF,$D3,$C1,$8D,$04
            ASC     "BLOAD SOSM"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $A5,$0E,$85,$E0,$20,$7D,$65,$A9,$01,$85,$B1
; --- End data region (67 bytes) ---

; ---------------------------------------------------------------------------
; game_loop_call_terrain — Overworld turn: process movement + check tiles
; ---------------------------------------------------------------------------
;
;   PURPOSE: The overworld (non-dungeon, non-combat) turn handler.
;            Runs after every player action on the surface or in towns.
;
;   TURN SEQUENCE:
;   1. move_process_turn: Apply poison, food depletion, MP regen
;   2. Refresh party status display
;   3. Check tile $88 = sign/message → show sign text
;   4. Check tile $30 = shop → enter shop interface
;   5. Check if at a special location (shrine, fountain, etc.)
;   6. If at special location: generate random combat position
;      on the 11×11 grid, check for occupied tile ($10 = impassable),
;      and either place the encounter or skip
;
;   RANDOM ENCOUNTER PLACEMENT:
;   The encounter spawner generates random (X,Y) on the 11×11 grid
;   ($46E4 with range 11). Position (5,5) is special — it's the center
;   where the party stands, so a hit there triggers char_combat_turn
;   (environmental damage) instead of normal placement.
;
;   For non-center positions, if combat_tile_at_xy returns $10 (wall),
;   the encounter is placed with tile $7A (encounter marker) and the
;   display is flashed. Otherwise, the turn ends normally.
;
; ---------------------------------------------------------------------------
game_loop_call_terrain jsr  move_process_turn        ; Per-turn maintenance
            jsr  move_display_party_status       ; Refresh HP/status sidebar
            jsr  $46FC           ; Get tile at current position
            cmp  #$88            ; Sign/message tile?
            bne  game_loop_check_tile
            jsr  world_move_handler      ; Yes → display sign text
game_loop_check_tile jsr  $46FC           ; Re-check current tile
            cmp  #$30            ; Shop tile?
            bne  game_loop_check_location
            jsr  shop_handle      ; Yes → enter shop transaction
game_loop_check_location jsr  check_location        ; At a special location?
            beq  game_loop_clear_flag   ; Yes → process special encounter
            jmp  game_loop_check_special   ; No → check remaining specials

; --- At special location: generate random encounter position ---
game_loop_clear_flag lda  #$00
            sta  $CB             ; Clear light timer
            lda  #$0B            ; Range: 0-10 (11×11 combat grid)
            jsr  $46E4           ; Random encounter X
            sta  $02
            lda  #$0B
            jsr  $46E4           ; Random encounter Y
            sta  $03
            cmp  #$05            ; Y = center (5)?
            bne  game_loop_combat_lookup
            lda  $02
            cmp  #$05            ; X = center (5)?
            beq  game_loop_combat_lookup2   ; Both center → party position

; --- Place encounter at random grid position ---
game_loop_combat_lookup jsr  combat_tile_at_xy      ; Look up tile at (X,Y)
            cmp  #$10            ; Impassable tile?
            bne  game_loop_jmp_input   ; No → can't place here, skip
            lda  #$7A            ; Encounter marker tile
            sta  ($FE),Y         ; Place on combat grid
            jsr  $0328           ; Commit to display
            lda  #$F7            ; Flash effect
            jsr  $4705
            jsr  $0230           ; Sync display
game_loop_jmp_input jmp  world_move_start   ; Return to overworld input

; --- Encounter at party center → environmental damage ---
game_loop_combat_lookup2 jsr  combat_tile_at_xy      ; Look up center tile
            lda  #$7A            ; Encounter marker
            sta  ($FE),Y         ; Place at center
            jsr  $0328           ; Commit
            jsr  char_combat_turn       ; Apply environmental damage to party
            jsr  $0230           ; Sync display
; XREF: 1 ref (1 jump) from game_loop_check_location
game_loop_check_special lda  $6E3E           ; A=[$6E3E] X=$00A3 Y=$00D3 ; [SP-1243]
            cmp  #$20            ; A=[$6E3E] X=$00A3 Y=$00D3 ; [SP-1243]
            bne  check_surface_only     ; A=[$6E3E] X=$00A3 Y=$00D3 ; [SP-1243]
            jmp  world_move_start   ; A=[$6E3E] X=$00A3 Y=$00D3 ; [SP-1243]

; ---------------------------------------------------------------------------
; check_location — Test if party is at a special coordinate
; ---------------------------------------------------------------------------
;
;   PURPOSE: Checks whether the party's current position matches a
;            predefined special location coordinate. Used by the game
;            loop to trigger location-specific events (shrines, fountains,
;            the Time Lord, etc.).
;
;   ALGORITHM:
;   - If in combat ($E2 = $80): use combat map identifier ($835E)
;   - Otherwise: check if $E2 = 3 (Ambrosia) AND saved_x matches
;     the expected coordinate at $79B8
;   - Returns A=0 (ZF set) if at the special location
;   - Returns A=$FF (ZF clear) if not
;
;   This is called 3 times from different contexts — the game loop,
;   combat rendering, and dungeon processing all need to know if the
;   party is at a quest-critical location.
;
; ---------------------------------------------------------------------------
check_location    lda  $E2             ; Load location_type
            cmp  #$80            ; In combat?
            bne  check_location_compare     ; No → use location_type directly
            lda  $835E           ; Yes → use combat map ID instead
check_location_compare cmp  #$03            ; Location type 3 (Ambrosia)?
            bne  check_location_not_found     ; No → not at special location
            lda  $E3             ; Check saved_x coordinate
            cmp  $79B8           ; Match expected X?
            bne  check_location_not_found     ; No → not at special location
            lda  #$00            ; Found! Return 0 (ZF set)
            rts
check_location_not_found lda  #$FF            ; Not found. Return $FF (ZF clear)
            rts

; ---------------------------------------------------------------------------
; check_surface_only — Gate for overworld-only processing
; ---------------------------------------------------------------------------
;
;   PURPOSE: Quick filter that only runs overworld logic when the party
;            is on the Sosaria surface ($E2 = 0). If in any other
;            location type (dungeon, town, combat), returns immediately.
;
; ---------------------------------------------------------------------------
check_surface_only lda  $E2             ; Load location_type
            beq  toggle_music     ; Zero = overworld → process
            rts                  ; Non-zero → skip (not on surface)

; ---------------------------------------------------------------------------
; toggle_music — Overworld day/night cycle and moongate phase tracking
; ---------------------------------------------------------------------------
;
;   PURPOSE: Manages two periodic counters that drive the overworld's
;            time-based events:
;
;   COUNTER 1 (turn_counter_1, period = 12 turns):
;   Controls moongate phase cycling. Every 12 overworld moves, the
;   moongate phase ($6FA1) advances by 1, wrapping at $B8 back to $B0.
;   This gives 8 phases ($B0-$B7) matching Ultima III's 8 moongate
;   positions. The moongates physically move around the map on each
;   phase change — a landmark game mechanic that required players to
;   track lunar cycles to use the fast-travel system.
;
;   COUNTER 2 (turn_counter_2, period = 4 turns):
;   Controls NPC animation cycling ($6FA4). Every 4 moves, NPC
;   appearance tiles advance, creating the illusion of movement
;   even when NPCs are standing still.
;
;   SELF-MODIFYING CODE:
;   The phase values are stored back into the instruction stream
;   (STA $6FA1 / STA $6FA4) — the operand bytes serve double duty
;   as both code and data. This saves 2 bytes of ZP allocation.
;
; ---------------------------------------------------------------------------
toggle_music dec  turn_counter_1     ; Decrement moongate phase timer
            bne  toggle_music_phase2  ; Not zero → skip phase advance
            lda  #$0C            ; Reset counter to 12 turns
            sta  turn_counter_1
            lda  $6FA1           ; Load current moongate phase
            jsr  advance_turn        ; Advance: phase + 1, wrap at $B8
            sta  $6FA1           ; Store back (self-modifying code)
toggle_music_phase2 dec  turn_counter_2     ; Decrement NPC animation timer
            bne  toggle_music_update  ; Not zero → skip
            lda  #$04            ; Reset counter to 4 turns
            sta  turn_counter_2
            lda  $6FA4           ; Load current NPC animation phase
            jsr  advance_turn        ; Advance + wrap
            sta  $6FA4           ; Store back (self-modifying code)
toggle_music_update jmp  advance_turn_update     ; Continue to overworld update

; ---------------------------------------------------------------------------
; advance_turn — Increment phase counter with wrap-around
; ---------------------------------------------------------------------------
;
;   PURPOSE: Adds 1 to A, wrapping from $B7 back to $B0. This gives
;            8 states ($B0-$B7) — matching the 8 moongate phases
;            (one per lunar position) and 8 NPC animation frames.
;
;   The range $B0-$B7 maps to page $00B0+ in the tile table,
;   where the engine stores the 8 moongate appearance tiles.
;
; ---------------------------------------------------------------------------
advance_turn    clc
            adc  #$01            ; Phase + 1
            cmp  #$B8            ; Past maximum ($B7)?
            bcc  advance_turn_done     ; No → return as-is
            lda  #$B0            ; Yes → wrap to $B0
advance_turn_done rts
; XREF: 1 ref (1 jump) from toggle_music_update
advance_turn_update jsr  move_save_cursor_pos     ; A=$00B0 X=$00A3 Y=$00D3 ; [SP-1241]
            ldy  #$00            ; A=$00B0 X=$00A3 Y=$0000 ; [SP-1241]
            ldx  #$08            ; A=$00B0 X=$0008 Y=$0000 ; [SP-1241]
            jsr  $46F3           ; Call $0046F3(X, Y)
            ora  $B4A8,X         ; -> $B4B0 ; A=$00B0 X=$0008 Y=$0000 ; [SP-1243]
            lda  #$A8            ; A=$00A8 X=$0008 Y=$0000 ; [SP-1243]
; *** MODIFIED AT RUNTIME by $6F85 ***
            ldy  $A9,X           ; -> $00B1 ; A=$00A8 X=$0008 Y=$0000 ; [SP-1243]
            DB      $1F
            brk  #$20            ; A=$00A8 X=$0008 Y=$0000 ; [SP-1243]
            and  $4C73           ; A=$00A8 X=$0008 Y=$0000 ; [SP-1243]

; --- Data region (86 bytes) ---
            DB      $B0,$6F
turn_counter_1
            DB      $0C
turn_counter_2
            DB      $04,$A5,$E2,$F0,$01,$60,$AD,$A1,$6F,$C9,$B0,$D0,$0F,$AD,$A4,$6F
            DB      $C9,$B0,$D0,$08,$A9,$18,$8D,$65,$1D,$4C,$D3,$6F,$A9,$0C,$8D,$65
            DB      $1D,$4C,$D3,$6F,$A2,$07,$BD,$97,$79,$85,$02,$BD,$9F,$79,$85,$03
            DB      $20,$FF,$46,$A9,$04,$91,$FE,$CA,$10,$EC,$AD,$A1,$6F,$38,$E9,$B0
            DB      $AA,$BD,$97,$79,$85,$02,$BD,$9F,$79,$85,$03,$20,$FF,$46,$A9,$88
            DB      $91,$FE,$60
; --- End data region (86 bytes) ---


; ###########################################################################
; ###                                                                     ###
; ###              COMBAT SYSTEM ($7087-$75AD)                            ###
; ###                                                                     ###
; ###########################################################################
;
;   Ultima III's tactical combat system operates on an 11×11 tile grid
;   (CON files at $9900). Up to 4 party members and 8 monsters are
;   placed on the grid. Combat is turn-based: each party member selects
;   an action (Attack, Cast, Retreat, etc.), then monsters act via
;   simple AI. Combat ends when all monsters are defeated or all party
;   members die.
;
;   COMBAT INNOVATIONS (1983):
;   Ultima III was the FIRST CRPG to feature a separate tactical combat
;   screen. Prior CRPGs (including Ultima I and II, Wizardry, and
;   Bard's Tale predecessors) used either menu-based combat or the
;   overworld map. The 11×11 grid with positioned combatants, terrain
;   effects, and movement was revolutionary — it became the template
;   for every tactical RPG that followed.
;
;   BCD ARITHMETIC:
;   All combat math (HP, damage, gold, XP) uses BCD (Binary Coded
;   Decimal) via the 6502's SED/CLD decimal mode. This simplifies
;   display (each nibble IS a digit) at the cost of more complex
;   arithmetic. The combat_bcd_multiply function implements BCD
;   multiplication via repeated addition.
;
; ---------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; combat_init — Wait for player number input to start combat round
; ---------------------------------------------------------------------------
;
;   PURPOSE: Waits for the player to press a digit key (0-9) to select
;            which party member acts next. Keys outside $B0-$B9
;            (high-ASCII '0'-'9') are rejected and the loop retries.
;
; ---------------------------------------------------------------------------
combat_init      jsr  input_wait_key     ; Wait for keypress
            cmp  #$B0            ; Key < '0'?
            bcc  combat_init     ; Yes → reject, try again

            cmp  #$BA            ; Key > '9'?
            bcs  combat_init     ; Yes → reject, try again

            pha                  ; Save key for later
            and  #$7F            ; Strip high bit for display
            jsr  $46CC           ; Echo character to screen
            jsr  $46BA           ; Print inline string:
            DB      $FF
            brk  #$AD            ; A=A&$7F X=$0008 Y=$0000 ; [SP-1252]

; ---
            DB      $6F
            DB      $B7,$C9,$AA,$F0,$04,$68,$38,$E9,$B0,$60
; ---


; ---------------------------------------------------------------------------
; combat_setup — Prompt player to select a party member (1-4)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Displays the character selection prompt and waits for a valid
;            keypress ($B1-$B4 = high-ASCII '1'-'4'). Used whenever the
;            game needs the player to choose which party member should
;            act — combat, spellcasting, equipping, etc. Loops until a
;            valid digit is entered, rejecting keys outside the range.
;
;   INPUT: Waits for keypress via input_wait_key (animating while waiting)
;   VALIDATION: Only accepts $B0-$B4 (high-ASCII '0'-'4')
;   OUTPUT: Falls through to combat_parse_input to store slot index
;
;   WHY $AA: The $AA sentinel stored at $62A5 marks the "waiting for
;   player input" state — checked elsewhere to detect if the game is
;   mid-prompt (prevents re-entrant animation callbacks).
;
; XREF: 7 refs (5 calls) (2 branches) from char_use_powder, $0066D6, $008F7D, file_overlay_data, combat_setup, ...
combat_setup    lda  #$AA            ; Set "awaiting input" sentinel
            sta  $62A5           ; Store sentinel at input state flag
            jsr  input_wait_key     ; Wait for key (animating world)
            cmp  #$B0            ; Key < '0'? (high-ASCII)
            bcc  combat_setup        ; Too low → retry
; === End of while loop ===

            cmp  #$B5            ; Key >= '5'?
            bcs  combat_setup        ; Too high → retry (only 1-4 valid)
; === End of while loop ===

            pha                  ; Save keypress
            and  #$7F            ; Strip high bit for display
            jsr  $46CC           ; Print the digit character
            jsr  $46BA           ; Print inline string (prompt suffix)
            DB      $FF
            brk  #$68            ; (inline string data bytes)
            sec                  ; Set carry for subtraction below

; ---------------------------------------------------------------------------
; combat_parse_input — Convert '1'-'4' keypress to slot index
; ---------------------------------------------------------------------------
;
;   PURPOSE: Converts the raw keypress ($B1-$B4) to a 0-based slot index
;            by subtracting $B0 then decrementing. Stores in $D5, which
;            is the standard party member index used throughout the engine.
;
;   PARAMS:  A = keypress from stack ($B1-$B4)
;   RETURNS: $D5 = 0-based slot index (0-3)
;            Z flag set if slot 0 selected
;
combat_parse_input  sbc  #$B0            ; Convert high-ASCII '1'-'4' → 1-4
            sta  $D5             ; Store as slot index
            dec  $D5             ; Adjust to 0-based (1→0, 2→1, etc.)
            cmp  #$00            ; Set Z flag for caller
            rts

; ---------------------------------------------------------------------------
; combat_read_key — Read keyboard input during combat (with timeout)
; ---------------------------------------------------------------------------
;
;   PURPOSE: The combat-specific keyboard reader. Unlike input_wait_key
;            (which animates the world while waiting), this routine polls
;            $C000 directly — combat has its own display update cadence
;            controlled by the combat loop, not the generic animation tick.
;
;   SELF-MODIFYING CODE: Writes $B7 to $705C on entry (marks "in combat
;   input" state), then restores $50 on keypress. This modifies a byte
;   in the combat data blob — a flag that other routines check to
;   determine if the player is currently being prompted.
;
;   KEY HANDLING:
;     $8D = Return → accept (return to caller)
;     $9B = Escape → cancel entire action (pops stack, prints inline msg)
;     Other → reject, loop back for another keypress
;
;   PARAMS:  None
;   RETURNS: A = key code (high-ASCII, with bit 7 set)
;            Only Return ($8D) exits normally; Escape aborts the caller
;
; XREF: 17 refs (16 calls) from $006C0A, $006DBD, $006D6E, $006D52, $006D16, ...
combat_read_key     lda  #$B7            ; "In combat input" sentinel
            sta  $705C           ; SMC: set combat input flag
            ldx  #$50            ; Restore value for when key received

; --- Poll keyboard hardware until key pressed ---
; XREF: 1 ref (1 branch) from combat_key_wait
combat_key_wait  lda  $C000           ; Read keyboard data register (bit 7 = key ready)
            bpl  combat_key_wait      ; No key → keep polling
; === End of while loop ===

            bit  $C010           ; Clear keyboard strobe (acknowledge key)
            pha                  ; Save keypress on stack
            lda  boot_init_data_2     ; Load game state byte
            stx  $705C           ; SMC: restore $50 (clear combat input flag)
            cmp  $62A5           ; Check if game state matches sentinel
            bne  combat_key_check_enter ; Mismatch → process key normally
            rts                  ; Match → abort (special state)
; --- Check for Return key ($8D) ---
; XREF: 1 ref (1 branch) from combat_key_wait
combat_key_check_enter  pla                  ; Restore keypress
            cmp  #$8D            ; Return key? (high-ASCII CR)
            bne  combat_key_check_esc ; No → check Escape
            rts                  ; Yes → accept input, return to caller
; --- Check for Escape key ($9B) → abort the entire action ---
; XREF: 1 ref (1 branch) from combat_key_check_enter
combat_key_check_esc  cmp  #$9B            ; Escape key?
            bne  combat_read_key         ; No → reject, wait for another key
; === End of while loop ===

; --- Escape pressed: unwind stack and print cancel message ---
            pla                  ; Discard saved return address (lo)
            pla                  ; Discard saved return address (hi)
            jsr  $46BA           ; Print inline cancel message
            DB      $FF
            brk  #$4C            ; (inline string data continuation)
            and  $6E,X           ; -> $00BE (inline data bytes)

; ---------------------------------------------------------------------------
; combat_bcd_multiply — BCD multiplication via repeated addition
; ---------------------------------------------------------------------------
;
;   PURPOSE: Multiplies A × X in BCD mode. Result stored in $D0.
;            Used to compute spell costs, damage, and experience.
;
;   PARAMS:  A = multiplicand (BCD value)
;            X = multiplier (binary count of additions)
;   RETURNS: A = $D0 = A × X (BCD product)
;
;   ALGORITHM:
;   Since the 6502's decimal mode (SED) only provides BCD addition and
;   subtraction — NOT multiplication — this implements multiply as
;   repeated BCD addition: result += multiplicand, X times. This is
;   O(X) which could be slow for large multipliers, but game values
;   rarely exceed 99 (2-digit BCD), so X is always small.
;
;   WHY BCD?
;   In 1983, BCD simplified display: each nibble IS a decimal digit.
;   Converting binary to decimal for screen output on a 1 MHz 6502
;   requires expensive division loops. With BCD, display is trivial
;   (just extract nibbles), but arithmetic is slightly more complex.
;   Garriott's team chose BCD for ALL game math — a pragmatic tradeoff
;   that pervades the entire codebase.
;
; ---------------------------------------------------------------------------
combat_bcd_multiply  sed                  ; Enter BCD mode
            sta  $F0             ; Save multiplicand
            clc
            lda  #$00            ; Accumulator = 0
            cpx  #$00            ; Multiplier = 0?
            bne  combat_bcd_mul_loop ; No → start adding
            sta  $D0             ; Yes → result is 0
            rts

; --- Repeated addition loop: add $F0 to A, X times ---
combat_bcd_mul_loop  clc
            adc  $F0             ; Accumulator += multiplicand (BCD)
            dex                  ; Decrement counter
            bne  combat_bcd_mul_loop ; Continue until X = 0

            sta  $D0             ; Store BCD product
            cld                  ; Exit BCD mode
            rts

; ---
            DB      $85,$F0,$20,$F6,$46,$F8,$18,$A0,$1F,$B1,$FE,$65,$F0,$91,$FE,$A0
            DB      $1E,$B1,$FE,$69,$00,$91,$FE,$D8,$C9,$99,$B0,$01,$60
; ---

; XREF: 1 ref (1 branch) from combat_bcd_mul_loop
combat_hp_overflow  lda  #$99            ; A=$0099 X=$004F Y=$0000 ; [SP-1246]
            ldy  #$1F            ; A=$0099 X=$004F Y=$001F ; [SP-1246]
            sta  ($FE),Y         ; A=$0099 X=$004F Y=$001F ; [SP-1246]
            lda  #$98            ; A=$0098 X=$004F Y=$001F ; [SP-1246]
combat_hp_store_max  ldy  #$1E            ; A=$0098 X=$004F Y=$001E ; [SP-1246]
            sta  ($FE),Y         ; A=$0098 X=$004F Y=$001E ; [SP-1246]
            rts                  ; A=$0098 X=$004F Y=$001E ; [SP-1244]

; ---
            DB      $85,$F0,$20,$F6,$46,$F8,$18,$A0,$24,$B1,$FE,$65,$F0,$91,$FE,$A0
            DB      $23,$B1,$FE,$69
            DB      $00 ; null terminator
            DB      $91,$FE,$D8,$B0,$01,$60
; ---

; XREF: 1 ref (1 branch) from combat_hp_store_max
combat_gold_overflow  lda  #$99            ; A=$0099 X=$004F Y=$001E ; [SP-1244]
            ldy  #$24            ; A=$0099 X=$004F Y=$0024 ; [SP-1244]
            sta  ($FE),Y         ; A=$0099 X=$004F Y=$0024 ; [SP-1244]
            ldy  #$23            ; A=$0099 X=$004F Y=$0023 ; [SP-1244]
            sta  ($FE),Y         ; A=$0099 X=$004F Y=$0023 ; [SP-1244]
            rts                  ; A=$0099 X=$004F Y=$0023 ; [SP-1242]

; ---
            DB      $85,$F0,$20,$F6,$46,$F8,$18,$A0,$1D,$B1,$FE,$65,$F0,$91,$FE,$A0
            DB      $1C,$B1,$FE,$69,$00,$91,$FE,$D8,$B0,$01,$60
; ---

; XREF: 1 ref (1 branch) from combat_gold_overflow
combat_exp_overflow  lda  #$99            ; A=$0099 X=$004F Y=$0023 ; [SP-1242]
            ldy  $1D             ; A=$0099 X=$004F Y=$0023 ; [SP-1242]
            sta  ($FE),Y         ; A=$0099 X=$004F Y=$0023 ; [SP-1242]
            ldy  $1C             ; A=$0099 X=$004F Y=$0023 ; [SP-1242]
            sta  ($FE),Y         ; A=$0099 X=$004F Y=$0023 ; [SP-1242]
            rts                  ; A=$0099 X=$004F Y=$0023 ; [SP-1240]

; ---------------------------------------------------------------------------
; combat_add_hp — Add HP to a character with max HP clamping
; ---------------------------------------------------------------------------
;
;   PURPOSE: Adds a BCD healing amount to a character's current HP,
;            clamping at their maximum HP to prevent overhealing.
;
;   CHARACTER RECORD HP LAYOUT (BCD16, big-endian):
;     $1A/$1B = current HP (high/low bytes)
;     $1C/$1D = max HP (high/low bytes)
;
;   ALGORITHM:
;   1. BCD-add healing amount ($F0) to HP low byte ($1B)
;   2. Propagate carry to HP high byte ($1A)
;   3. If overflow (carry set) → clamp to max HP
;   4. Otherwise compare: if HP > max_HP → clamp to max HP
;
;   The comparison is 16-bit BCD: subtract current from max. If borrow
;   occurs (carry clear after SBC), current exceeds max → cap it.
;
;   PARAMS:  A = healing amount (BCD)
;   RETURNS: HP clamped to max_HP
;
; ---------------------------------------------------------------------------
combat_add_hp  sta  $F0             ; Save healing amount
            jsr  $46F6           ; Setup character pointer ($FE/$FF)
            sed                  ; Enter BCD mode for HP math
            clc
            ldy  #$1B            ; HP low byte offset
            lda  ($FE),Y         ; Load current HP (low)
            adc  $F0             ; Add healing amount (BCD)
            sta  ($FE),Y         ; Store updated HP (low)
            ldy  #$1A            ; HP high byte offset
            lda  ($FE),Y         ; Load current HP (high)
            adc  #$00            ; Propagate carry from low byte
            sta  ($FE),Y         ; Store updated HP (high)
            bcs  combat_hp_cap_at_max      ; Carry = BCD overflow → clamp
; --- Compare HP against max_HP (16-bit BCD) ---
            sec
            ldy  #$1D            ; max_HP low byte
            lda  ($FE),Y
            ldy  #$1B            ; current HP low byte
            sbc  ($FE),Y         ; max_HP_lo - HP_lo
            ldy  #$1C            ; max_HP high byte
            lda  ($FE),Y
            ldy  #$1A            ; current HP high byte
            sbc  ($FE),Y         ; max_HP_hi - HP_hi (with borrow)
            bcs  combat_hp_add_done      ; No borrow → HP ≤ max → OK
; --- HP exceeds max: clamp to max_HP ---
combat_hp_cap_at_max  ldy  #$1C            ; Copy max_HP → current HP
            lda  ($FE),Y         ; max_HP high byte
            ldy  #$1A
            sta  ($FE),Y         ; → HP high byte
            ldy  #$1D
            lda  ($FE),Y         ; max_HP low byte
            ldy  #$1B
            sta  ($FE),Y         ; → HP low byte
combat_hp_add_done  cld                  ; Exit BCD mode
            rts

; ---------------------------------------------------------------------------
; combat_add_bcd_field — Add a BCD value to a character record field
; ---------------------------------------------------------------------------
;
;   PURPOSE: General-purpose BCD field incrementer. Adds the value in A
;            to the character record byte at offset Y, for the character
;            in slot X ($D5). Used for adding gold, food, experience,
;            and other BCD-encoded quantities.
;
;   ALGORITHM:
;   1. Saves addend in $F0, field offset in $F2
;   2. Sets up character pointer via $46F6 (slot $D5 → $FE/$FF)
;   3. Performs BCD addition in SED mode
;   4. On overflow (carry set): clamps field to $99 (max 1-byte BCD)
;
;   PARAMS:  A = amount to add (BCD)
;            Y = character record field offset
;            X = character slot index (passed via $D5 to $46F6)
;   RETURNS: Updated field value stored in character record
;
;   OVERFLOW: If the BCD addition overflows (e.g., $80 + $30 = $110,
;   which doesn't fit in one byte), the value is clamped to $99 —
;   the maximum single-byte BCD value (decimal 99). This prevents
;   stat corruption while allowing gold/food to cap naturally.
;
; XREF: 5 refs (5 calls) from $005F04, $005D51, $005D86, char_equip_none_msg, char_equip_not_owned
combat_add_bcd_field     sta  $F0             ; Save addend
            sty  $F2             ; Save field offset
            jsr  $46F6           ; Setup $FE/$FF → character record
            ldy  $F2             ; Restore field offset
            sed                  ; Enter BCD mode
            clc
            lda  ($FE),Y         ; Load current field value (BCD)
            adc  $F0             ; Add the amount (BCD)
            sta  ($FE),Y         ; Store result
            cld                  ; Exit BCD mode
            bcs  combat_bcd_overflow ; Carry set = overflow → clamp to $99
            rts                  ; Normal return
; --- BCD overflow: clamp to maximum single-byte value ---
; XREF: 1 ref (1 branch) from combat_add_bcd_field
combat_bcd_overflow  lda  #$99            ; $99 = max BCD byte (decimal 99)
            sta  ($FE),Y         ; Clamp the field
            rts

; ---------------------------------------------------------------------------
; combat_bcd_to_binary — Convert BCD byte to binary
; ---------------------------------------------------------------------------
;
;   PURPOSE: Converts a BCD-encoded value in A to its binary equivalent.
;            E.g., BCD $42 (representing 42 decimal) → binary $2A (42).
;
;   ALGORITHM: Repeated BCD subtraction — subtract BCD 1 in a loop,
;              counting iterations in X. The count (binary) = the value.
;              This is O(N) where N is the decimal value. For game stats
;              (max 99), this takes at most 99 iterations (~500 cycles).
;
;   PARAMS:  A = BCD value (0-99)
;   RETURNS: A = binary equivalent
;
; ---------------------------------------------------------------------------
combat_bcd_to_binary   cmp  #$00            ; Zero?
            beq  combat_bcd_conv_done ; Yes → return 0
            ldx  #$00            ; Binary counter
            sed                  ; BCD mode for subtraction

combat_bcd_sub_loop inx                  ; Count one BCD unit
            sec
            sbc  #$01            ; Subtract BCD 1
            bne  combat_bcd_sub_loop ; Continue until BCD value = 0

            cld                  ; Exit BCD mode
            txa                  ; A = binary count
combat_bcd_conv_done rts

; ---------------------------------------------------------------------------
; combat_binary_to_bcd — Convert binary byte to BCD
; ---------------------------------------------------------------------------
;
;   PURPOSE: Converts a binary value in A to BCD. The inverse of
;            combat_bcd_to_binary. E.g., binary $2A (42) → BCD $42.
;
;   ALGORITHM: Repeated BCD addition — add BCD 1 in a loop, counting
;              down the binary value in $F3.
;
;   PARAMS:  A = binary value
;   RETURNS: A = BCD equivalent
;
; ---------------------------------------------------------------------------
combat_binary_to_bcd   sta  $F3             ; Save binary count
            cmp  #$00            ; Zero?
            beq  combat_bcd_conv_ret ; Yes → return 0
            lda  #$00            ; BCD accumulator
            sed                  ; BCD mode for addition

combat_bcd_add_loop clc
            adc  #$01            ; Add BCD 1
            dec  $F3             ; Decrement binary counter
            bne  combat_bcd_add_loop ; Continue until counter = 0

            cld                  ; Exit BCD mode
combat_bcd_conv_ret rts

; ---------------------------------------------------------------------------
; combat_apply_damage  [12 calls]
;   Called by: render_combat_resolve, combat_end_flag, char_turn_loop, equip_handle, file_mark_apply_loop, move_turn_poison_damage
; ---------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; combat_apply_damage — Subtract HP from a character (BCD)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Applies damage to a character's HP field. If HP drops below
;            zero (carry clear after BCD subtraction), the character is
;            killed — status set to 'D' (Dead) and HP zeroed.
;
;   PARAMS:  A = damage amount (BCD)
;            $D5 = character slot ID (used by $46F6 to set $FE/$FF)
;   RETURNS: A = 0 if character survived, $FF if killed
;
;   CHARACTER RECORD HP LAYOUT:
;   Offset $1A = HP high byte (BCD hundreds)
;   Offset $1B = HP low byte (BCD tens/units)
;   HP is a 16-bit BCD value: $1A:$1B = 0000-9999
;
;   DEATH HANDLING:
;   When HP underflows (carry clear after SBC), the character's status
;   byte (offset $11) is set to $C4 = high-ASCII 'D' (Dead), and HP
;   is zeroed. The combat_end_check function is then called to see if
;   the entire party has been wiped out.
;
; ---------------------------------------------------------------------------
combat_apply_damage   sta  $F3             ; Save damage amount
            jsr  $46F6           ; Setup $FE/$FF → character record
            sed                  ; BCD mode for HP subtraction
            ldy  #$1B            ; HP low byte offset
            lda  ($FE),Y         ; Load current HP low
            sec
            sbc  $F3             ; Subtract damage (BCD)
            sta  ($FE),Y         ; Store result
            ldy  #$1A            ; HP high byte offset
            lda  ($FE),Y         ; Load HP high
            sbc  #$00            ; Propagate borrow
            sta  ($FE),Y         ; Store result
            cld                  ; Exit BCD mode
            bcc  combat_unit_killed ; Carry clear = HP underflowed → dead
            lda  #$00            ; Survived: return 0
            rts

; --- Character killed: set status to Dead, zero HP ---
combat_unit_killed lda  #$C4            ; $C4 = high-ASCII 'D' (Dead)
            ldy  #$11            ; Offset $11 = status byte
            sta  ($FE),Y         ; Set status to Dead
            lda  #$00
            ldy  #$1A            ; Zero HP high byte
            sta  ($FE),Y
            ldy  #$1B            ; Zero HP low byte
            sta  ($FE),Y
            jsr  combat_end_check ; Check if all party members dead
            lda  #$FF            ; Killed: return $FF
            rts

; ---------------------------------------------------------------------------
; combat_check_party_alive — Check if any party member is still alive
; ---------------------------------------------------------------------------
;
;   PURPOSE: Scans all party slots (3 down to 0) looking for at least one
;            member with status 'G' (Good, $C7) or 'P' (Poisoned, $D0).
;            If ANY alive member is found, jumps to combat_checksum_xor
;            (the anti-cheat routine, which returns to the combat loop).
;
;            If ALL members are dead/ashed (no 'G' or 'P' found after
;            scanning all 4 slots), prints "ALL PLAYERS OUT!" and triggers
;            the game-over sequence via combat_end_check → file_save_game.
;
;   CALLERS: Combat damage resolution, encounter handlers
;   PARAMS:  None (scans all 4 party slots)
;
; XREF: 3 refs (3 calls) from $008808, boot_clear_floor, render_return_to_game
combat_check_party_alive lda  #$03            ; Start scanning from slot 3
            sta  $D5             ; $D5 = current slot being checked

; --- Loop through all party slots, checking status ---
; XREF: 1 ref (1 branch) from combat_alive_check_loop
combat_alive_check_loop jsr  $46F6           ; Set $FE/$FF → character record for slot $D5
            ldy  #$11            ; Offset $11 = status byte
            lda  ($FE),Y         ; Load status
            cmp  #$C7            ; 'G' (Good)? → still alive
            beq  combat_checksum_xor ; Found alive member → return to game
            cmp  #$D0            ; 'P' (Poisoned)? → still conscious
            beq  combat_checksum_xor ; Found alive member → return to game
            dec  $D5             ; Try next slot down
            bpl  combat_alive_check_loop ; More slots to check → continue
; === End of while loop ===

; --- All party members dead: print game-over message ---
            jsr  move_display_party_status ; Display final party status
            jsr  $46BA           ; Print inline: "ALL PLAYERS OUT!"
            DB      $FF
            DB      $FF
            cmp  ($CC,X)         ; (inline string data continuation)

; ---
            DB      $CC,$A0,$D0,$CC,$C1,$D9,$C5,$D2,$D3,$A0,$CF,$D5,$D4,$A1,$FF,$00
            DB      $20,$00,$72,$4C,$16,$BA
; ---


; ---------------------------------------------------------------------------
; combat_checksum_xor — Anti-cheat XOR checksum over engine code
; ---------------------------------------------------------------------------
;
;   PURPOSE: Computes an XOR checksum over 128 bytes of engine code
;            ($50A8-$5127) and stores it at $36/$37. This detects
;            memory tampering — if a player uses a sector editor or
;            memory poke to modify game values, the checksum will fail
;            and boot_check_quit will terminate the game.
;
;   SELF-MODIFYING CODE:
;   The EOR instruction's high address byte at combat_dead_xor_addr
;   is patched from $50 to $B5 during the computation, then restored.
;   This changes the XOR source from $50A8+ to $B5A8+ — computing
;   the checksum over TWO different memory regions in sequence.
;   This is a classic 6502 anti-tamper trick: the checksum routine
;   itself is part of what's being checksummed.
;
; ---------------------------------------------------------------------------
combat_checksum_xor    lda  #$B5            ; Patch EOR to read from $B5xx
            sta  combat_dead_xor_addr ; SMC: change high byte of EOR operand
            ldy  #$80            ; 128 bytes to checksum
            lda  #$00            ; Clear accumulator

; --- XOR 128 bytes from $50A8 (or $B5A8 after SMC) ---
combat_xor_loop eor  $50A8,Y         ; XOR next byte into accumulator
            dey                  ; Count down
            bpl  combat_xor_loop ; Continue through all 128 bytes

            ldx  #$50            ; Restore original high byte
            stx  combat_dead_xor_addr ; Unpatch the SMC
            rts

; ---------------------------------------------------------------------------
; combat_end_check — Handle combat exit after a character is killed
; ---------------------------------------------------------------------------
;
;   PURPOSE: Called after a character dies in combat. Temporarily sets
;            $E2 (location type) to $00 to enable overworld save logic,
;            then determines whether to save state and return to the game
;            loop. This is the critical transition point between combat
;            and the main game state.
;
;   SAVE STATE LOGIC:
;   - If location was $00 (overworld): save current position ($00/$01)
;     back to PRTY ($E3/$E4), save transport ($0E → $E0), then call
;     file_save_game to write PLRS+PRTY to disk immediately.
;   - If location was $80 (combat): check $835E for sub-location state.
;     If zero (overworld combat), save position. If non-zero (location
;     combat), return to the game loop to handle post-combat.
;   - Otherwise: return to game_main_loop for location-specific handling.
;
;   The saved location type is pushed on stack and restored on exit,
;   so $E2 returns to its pre-call value.
;
; XREF: 1 ref (1 call) from combat_unit_killed
combat_end_check   ldx  #$00
            lda  $E2             ; Save current location type
            stx  $E2             ; Temporarily set to $00 (overworld mode)
            pha                  ; Push saved location type for later restore
            bne  combat_end_check_surface ; Was in a location → check type

; --- Was on overworld ($E2=0): save coordinates and transport ---
; XREF: 1 ref (1 branch) from combat_end_check_surface
combat_end_save_pos lda  $00             ; Current X position
            sta  $E3             ; → PRTY saved_x
            lda  $01             ; Current Y position
            sta  $E4             ; → PRTY saved_y
            lda  $0E             ; Current transport mode
            sta  $E0             ; → PRTY transport
            jsr  file_save_game          ; Save PLRS+PRTY to disk
            jmp  combat_end_restore    ; Restore $E2 and return
; --- Check if we were in combat ($80) or a sub-location ---
; XREF: 1 ref (1 branch) from combat_end_check
combat_end_check_surface cmp  #$80            ; Were we in combat?
            bne  combat_end_return_game ; No → return to game loop
            lda  $835E           ; Check saved sub-location state
            cmp  #$00            ; Zero = overworld combat
            beq  combat_end_save_pos ; Yes → save overworld position
; === End of while loop ===

; XREF: 1 ref (1 branch) from combat_end_check_surface
combat_end_return_game jsr  game_main_loop       ; Re-enter main game loop

; --- Restore original location type and return ---
; XREF: 3 refs (2 jumps) (1 branch) from combat_end_save_pos, move_display_party_status, combat_end_restore
combat_end_restore pla                  ; Restore saved location type
            sta  $E2             ; Put it back in $E2
            rts

; --- Data region (102 bytes, text data) ---
            DB      $85,$F3,$A0,$00,$A9,$B7,$85,$FD,$A9,$6C,$85,$FC,$B1,$FC,$CD,$A5
            DB      $62,$F0,$E9,$A5,$0E,$C9,$16,$D0,$03,$4C,$12,$73,$A5,$F3,$C9,$40
            DB      $F0,$4A,$C9,$42,$F0,$43,$C9,$44,$F0,$10,$C9,$7C,$F0,$0C,$C9,$18
            DB      $B0,$34,$C9,$00,$F0,$30,$C9,$08,$F0,$2C,$A9,$F6,$20,$05,$47,$A2
            DB      $FF,$A0,$20,$CA,$D0,$FD,$88,$D0,$FA,$A9,$F6,$20,$05,$47,$A5,$0E
            DB      $C9,$14,$D0,$0F,$A2,$FF,$A0,$20,$CA,$D0,$FD,$88,$D0,$FA,$A9,$F6
            DB      $20,$05,$47,$A9,$00,$60
; --- End data region (102 bytes) ---

; --- Return $FF flag (signals "combat ended" to callers) ---
; XREF: 5 refs (1 jump) (4 branches) from $00731A, combat_end_restore, combat_end_flag, combat_end_restore, combat_end_restore
combat_end_flag lda  #$FF            ; $FF = "combat ended" flag
            rts

; --- Data region (138 bytes, text data) ---
            DB      $4C,$DE,$72,$20,$E9,$58,$A9,$FC,$A2,$10,$20,$05,$47,$A9,$00,$85
            DB      $D5,$20,$F6,$46,$A0,$0E,$B1,$FE,$29,$10,$F0,$12,$E6,$D5,$A5,$D5
            DB      $C5,$E1,$90,$ED,$20,$E9,$58,$C9,$D1,$F0,$A6,$6C,$F0,$03,$A9,$99
            DB      $20,$81,$71,$20,$E4,$88,$A9,$F7,$20,$05,$47,$20,$E4,$88,$20,$E9
            DB      $58,$C9,$D1,$F0,$B8,$6C,$F0,$03,$A9,$F8,$20,$05,$47,$A9,$00,$85
            DB      $D5,$20,$BA,$75,$D0,$08,$A0,$0E,$B1,$FE,$29,$20,$F0,$0B,$E6,$D5
            DB      $A5,$D5,$C5,$E1,$90,$EB,$4C,$67,$72,$A9,$50,$20,$81,$71,$20,$E4
            DB      $88,$A9,$F7,$20,$05,$47,$20,$E4,$88,$4C,$F4,$72,$A5,$F3,$F0,$07
            DB      $C9,$18,$F0,$03,$4C,$93,$72,$A9,$00,$60
; --- End data region (138 bytes) ---


; ---------------------------------------------------------------------------
; move_save_cursor_pos / move_restore_cursor_pos — Text cursor save/restore
; ---------------------------------------------------------------------------
;
;   PURPOSE: Saves and restores the text cursor position ($F9=X, $FA=Y)
;            across status display rendering. The party status sidebar
;            moves the cursor to render each character's stats; these
;            functions bracket that rendering to preserve the cursor for
;            the caller's ongoing text output.
;
;   SELF-MODIFYING STORAGE: The saved cursor bytes are stored directly
;   into the instruction operand bytes at $732B and move_saved_cursor_y
;   ($732C). This is a textbook 6502 pattern: using code bytes as data
;   storage avoids allocating precious zero-page space. The "DB $00"
;   after the RTS is the SMC storage byte for cursor X.
;
;   CALLERS: move_display_party_status (every status refresh),
;            advance_turn_update (turn counter display)
;
; XREF: 2 refs (2 calls) from move_display_party_status, advance_turn_update
move_save_cursor_pos lda  $F9             ; Load text cursor X
            sta  $732B           ; SMC: save into operand byte below
            lda  $FA             ; Load text cursor Y
            sta  move_saved_cursor_y ; SMC: save into operand byte below
            rts
            DB      $00              ; SMC storage for saved cursor X
move_saved_cursor_y
            DB      $00              ; SMC storage for saved cursor Y

; XREF: 1 ref (1 jump) from move_status_restore
move_restore_cursor_pos  lda  move_saved_cursor_y ; Restore saved cursor Y
            sta  $FA
            lda  $732B           ; Restore saved cursor X
            sta  $F9
            rts

; ---------------------------------------------------------------------------
; move_display_party_status — Render the party status sidebar
; ---------------------------------------------------------------------------
;
;   PURPOSE: Draws the right-side status display showing each party member's
;            name, status, class, race, HP, MaxHP, MP, EXP, and level.
;            This is the persistent UI element visible at all times — the
;            "party roster at a glance" that defined the CRPG visual style.
;
;            The function saves the cursor position, iterates up to 4 party
;            members, prints each character's stats using the inline string
;            printer and BCD display routines, then restores the cursor.
;
;   NOTABLE: BCD level display at line ~3832 adds 1 to the raw EXP
;            high-nibble to show levels starting at 1, not 0. This is
;            why the engine stores "level - 1" in the EXP field.
;
;   CALLERS: 13 — called from virtually every game state transition
;
; XREF: 13 refs (13 calls)
move_display_party_status   jsr  move_save_cursor_pos
            lda  #$03            ; A=$0003 X=$0000 Y=$007F ; [SP-1271]
            sta  $D5             ; A=$0003 X=$0000 Y=$007F ; [SP-1271]
            ldx  #$10            ; A=$0003 X=$0010 Y=$007F ; [SP-1271]
            clc                  ; A=$0003 X=$0010 Y=$007F ; [SP-1271]
            adc  #$B3            ; A=A+$B3 X=$0010 Y=$007F ; [SP-1271]
            ldy  #$80            ; A=A+$B3 X=$0010 Y=$0080 ; [SP-1271]
            jsr  $03A3           ; Call $0003A3(A, X, Y)
            cmp  #$D1            ; A=A+$B3 X=$0010 Y=$0080 ; [SP-1273]
            beq  move_status_char_loop    ; A=A+$B3 X=$0010 Y=$0080 ; [SP-1273]
            jmp  combat_end_restore    ; A=A+$B3 X=$0010 Y=$0080 ; [SP-1273]
; === End of while loop ===


; === while loop starts here (counter: Y 'j') [nest:33] ===
; XREF: 2 refs (1 jump) (1 branch) from move_status_next_char, move_display_party_status
move_status_char_loop jsr  $46F6           ; A=A+$B3 X=$0010 Y=$0080 ; [SP-1275]
            ldy  #$00            ; A=A+$B3 X=$0010 Y=$0000 ; [SP-1275]
            lda  ($FE),Y         ; A=A+$B3 X=$0010 Y=$0000 ; [SP-1275]
            bne  move_status_print_name    ; A=A+$B3 X=$0010 Y=$0000 ; [SP-1275]
            jmp  move_status_end    ; A=A+$B3 X=$0010 Y=$0000 ; [SP-1275]
; XREF: 1 ref (1 branch) from move_status_char_loop
move_status_print_name jsr  $46F9           ; A=A+$B3 X=$0010 Y=$0000 ; [SP-1277]
            lda  #$26            ; A=$0026 X=$0010 Y=$0000 ; [SP-1277]
            sta  $F9             ; A=$0026 X=$0010 Y=$0000 ; [SP-1277]
            jsr  $46F6           ; Call $0046F6(A)
            ldy  #$11            ; A=$0026 X=$0010 Y=$0011 ; [SP-1279]
            lda  ($FE),Y         ; A=$0026 X=$0010 Y=$0011 ; [SP-1279]
            and  #$7F            ; A=A&$7F X=$0010 Y=$0011 ; [SP-1279]
            jsr  $46CC           ; Call $0046CC(A, Y)
            inc  $FA             ; A=A&$7F X=$0010 Y=$0011 ; [SP-1281]
            lda  #$19            ; A=$0019 X=$0010 Y=$0011 ; [SP-1281]
            sta  $F9             ; A=$0019 X=$0010 Y=$0011 ; [SP-1281]
            jsr  $46F6           ; Call $0046F6(A)
            ldy  #$18            ; A=$0019 X=$0010 Y=$0018 ; [SP-1283]
            lda  ($FE),Y         ; A=$0019 X=$0010 Y=$0018 ; [SP-1283]
            and  #$7F            ; A=A&$7F X=$0010 Y=$0018 ; [SP-1283]
            jsr  $46CC           ; Call $0046CC(A, Y)
            inc  $F9             ; A=A&$7F X=$0010 Y=$0018 ; [SP-1285]
            jsr  $46F6           ; A=A&$7F X=$0010 Y=$0018 ; [SP-1287]
            ldy  #$16            ; A=A&$7F X=$0010 Y=$0016 ; [SP-1287]
            lda  ($FE),Y         ; A=A&$7F X=$0010 Y=$0016 ; [SP-1287]
            and  #$7F            ; A=A&$7F X=$0010 Y=$0016 ; [SP-1287]
            jsr  $46CC           ; Call $0046CC(A, Y)
            inc  $F9             ; A=A&$7F X=$0010 Y=$0016 ; [SP-1289]
            jsr  $46F6           ; A=A&$7F X=$0010 Y=$0016 ; [SP-1291]
            ldy  #$17            ; A=A&$7F X=$0010 Y=$0017 ; [SP-1291]
            lda  ($FE),Y         ; A=A&$7F X=$0010 Y=$0017 ; [SP-1291]
            and  #$7F            ; A=A&$7F X=$0010 Y=$0017 ; [SP-1291]
            jsr  $46CC           ; Call $0046CC(A, Y)
            inc  $F9             ; A=A&$7F X=$0010 Y=$0017 ; [SP-1293]
            inc  $F9             ; A=A&$7F X=$0010 Y=$0017 ; [SP-1293]
            jsr  $46BA           ; A=A&$7F X=$0010 Y=$0017 ; [SP-1295]
            cmp  !$00BA          ; A=A&$7F X=$0010 Y=$0017 ; [SP-1295]
            jsr  $46F6           ; A=A&$7F X=$0010 Y=$0017 ; [SP-1297]
            ldy  #$19            ; A=A&$7F X=$0010 Y=$0019 ; [SP-1297]
            lda  ($FE),Y         ; A=A&$7F X=$0010 Y=$0019 ; [SP-1297]
            jsr  $46D5           ; Call $0046D5(A, Y)
            inc  $F9             ; A=A&$7F X=$0010 Y=$0019 ; [SP-1299]
            jsr  $46BA           ; A=A&$7F X=$0010 Y=$0019 ; [SP-1301]
            cpy  !$00BA          ; A=A&$7F X=$0010 Y=$0019 ; [SP-1301]
            jsr  $46F6           ; A=A&$7F X=$0010 Y=$0019 ; [SP-1303]
            ldy  #$1E            ; A=A&$7F X=$0010 Y=$001E ; [SP-1303]
            lda  ($FE),Y         ; A=A&$7F X=$0010 Y=$001E ; [SP-1303]
            sed                  ; A=A&$7F X=$0010 Y=$001E ; [SP-1303]
            clc                  ; A=A&$7F X=$0010 Y=$001E ; [SP-1303]
            adc  #$01            ; A=A+$01 X=$0010 Y=$001E ; [SP-1303]
            cld                  ; A=A+$01 X=$0010 Y=$001E ; [SP-1303]
            jsr  $46D5           ; Call $0046D5(A, Y)
            inc  $FA             ; A=A+$01 X=$0010 Y=$001E ; [SP-1305]
            lda  #$19            ; A=$0019 X=$0010 Y=$001E ; [SP-1305]
            sta  $F9             ; A=$0019 X=$0010 Y=$001E ; [SP-1305]
            jsr  $46BA           ; Call $0046BA(A)
            iny                  ; A=$0019 X=$0010 Y=$001F ; [SP-1307]
            tsx                  ; A=$0019 X=$0010 Y=$001F ; [SP-1307]
            brk  #$20            ; A=$0019 X=$0010 Y=$001F ; [SP-1310]

; --- Data region (49 bytes, text data) ---
            DB      $F6,$46,$A0,$1A,$B1,$FE,$20,$D5,$46,$20,$F6,$46,$A0,$1A,$C8,$B1
            DB      $FE,$20,$D5,$46,$E6,$F9,$20,$BA,$46,$C6,$BA,$00,$20,$F6,$46,$A0
            DB      $20,$B1,$FE,$20,$D5,$46,$20,$F6,$46,$A0,$20,$C8,$B1,$FE,$20,$D5
            DB      $46
; --- End data region (49 bytes) ---

; XREF: 1 ref (1 jump) from move_status_char_loop
move_status_end lda  #$B7            ; A=$00B7 X=$0010 Y=$001F ; [SP-1327]
            sta  $FF             ; A=$00B7 X=$0010 Y=$001F ; [SP-1327]
            lda  #$6C            ; A=$006C X=$0010 Y=$001F ; [SP-1327]
            sta  $FE             ; A=$006C X=$0010 Y=$001F ; [SP-1327]
            ldy  #$00            ; A=$006C X=$0010 Y=$0000 ; [SP-1327]
            lda  ($FE),Y         ; A=$006C X=$0010 Y=$0000 ; [SP-1327]
            cmp  #$AA            ; A=$006C X=$0010 Y=$0000 ; [SP-1327]
            beq  move_status_next_char    ; A=$006C X=$0010 Y=$0000 ; [SP-1327]
            dec  $D5             ; A=$006C X=$0010 Y=$0000 ; [SP-1327]
            bmi  move_status_restore    ; A=$006C X=$0010 Y=$0000 ; [SP-1327]
; XREF: 1 ref (1 branch) from move_status_end
move_status_next_char jmp  move_status_char_loop    ; " vF "
; === End of while loop (counter: Y) ===

; XREF: 1 ref (1 branch) from move_status_end
move_status_restore jmp  move_restore_cursor_pos      ; A=$006C X=$0010 Y=$0000 ; [SP-1327]

; ---
            DB      $85,$F0,$20,$F6,$46,$F8,$18,$A0,$21,$B1,$FE,$65,$F0,$91,$FE,$A0
            DB      $20,$B1,$FE,$69
            DB      $00 ; null terminator
            DB      $91,$FE,$D8,$B0,$01,$60
; ---

; XREF: 1 ref (1 branch) from move_status_restore
move_status_gold_overflow lda  #$99            ; A=$0099 X=$0010 Y=$0000 ; [SP-1327]
            ldy  $21             ; A=$0099 X=$0010 Y=$0000 ; [SP-1327]
            sta  ($FE),Y         ; A=$0099 X=$0010 Y=$0000 ; [SP-1327]
            ldy  $20             ; A=$0099 X=$0010 Y=$0000 ; [SP-1327]
            sta  ($FE),Y         ; A=$0099 X=$0010 Y=$0000 ; [SP-1327]
            rts                  ; A=$0099 X=$0010 Y=$0000 ; [SP-1325]

; ---------------------------------------------------------------------------
; input_wait_key — Wait for keyboard input with animation updates
; ---------------------------------------------------------------------------
;
;   PURPOSE: The primary keyboard polling loop. While waiting for a keypress,
;            continuously updates the display (viewport animation, creature
;            movement) to keep the world alive. This is how Ultima III
;            achieves its characteristic "living world" feel — monsters
;            visibly move while the player decides their action.
;
;   SELF-MODIFYING CODE: The function saves X and Y registers into SMC
;   operand bytes at input_wait_selfmod and input_wait_restore_y, then
;   restores them after the keypress. This preserves caller state across
;   the animation subroutine calls that clobber X/Y. SMC was a standard
;   6502 technique for saving registers without burning stack space.
;
;   APPLE II KEYBOARD: $C000 reads the keyboard data register. Bit 7
;   (high bit) is set when a key is pressed. BIT $C010 clears the
;   keyboard strobe so the next key can be detected. This hardware
;   latch design means you MUST clear the strobe or the same key
;   will be "read" forever.
;
;   PARAMS:  X, Y = caller's values (preserved via SMC)
;   RETURNS: A = key code (with bit 7 set, high-ASCII)
;            X, Y = restored to caller's values
;
; XREF: 4 refs (4 calls) from render_combat_wait_key, combat_setup, combat_init, $005449
input_wait_key stx  input_wait_selfmod  ; Save X via SMC (writes into operand byte below)
            sty  input_wait_restore_y  ; Save Y via SMC

; --- Animation loop: update display while polling keyboard ---
input_wait_animate lda  $E2             ; Check location type
            cmp  #$01            ; In dungeon? ($E2=1)
            beq  input_wait_poll  ; Yes → skip overworld animation
            jsr  $46ED           ; Update viewport animation frame
            jsr  $46F0           ; Advance creature positions
            jsr  $470E           ; Redraw viewport
            jsr  $0328           ; Screen refresh (VTAB/HTAB reset)
input_wait_poll lda  $C000           ; Read keyboard data register
            bpl  input_wait_animate ; Bit 7 clear = no key → keep animating

            bit  $C010           ; Key pressed! Clear keyboard strobe
            ldx  input_wait_selfmod  ; Restore caller's X from SMC byte
            ldy  input_wait_restore_y  ; Restore caller's Y from SMC byte
            rts                  ; Return with key code in A

; --- SMC storage: these bytes are overwritten by input_wait_key ---
; *** MODIFIED AT RUNTIME by input_wait_key ($7446) ***
input_wait_selfmod brk  #$00            ; Holds saved X register value
            DB      $20

; ###########################################################################
; ###                                                                     ###
; ###          TURN PROCESSING ($7470-$75AD)                              ###
; ###                                                                     ###
; ###########################################################################
;
;   Per-turn party maintenance: MP regeneration, poison damage, food
;   consumption, HP regeneration, encounter rolling, and the anti-cheat
;   checksum verification. Called every turn from the main game loop,
;   combat loop, and dungeon loop.
;

; ---------------------------------------------------------------------------
; move_process_turn — Execute one turn of party maintenance
; ---------------------------------------------------------------------------
;
;   PURPOSE: The "heartbeat" of the game. Every turn (movement, combat
;            round, dungeon step), this function:
;            1. Checks if the game state is valid ($B769 OR $55 == $FF)
;            2. On surface ($E2=0): process party status immediately
;            3. In locations ($E2!=0): decrement encounter counter, roll
;               for random encounters every 4th turn
;            4. For each party member: check class, regenerate MP based
;               on stat/2 caps, apply poison damage, regen 1 HP per
;               10 steps, verify anti-cheat XOR checksum
;
;   ENCOUNTER SYSTEM: The encounter counter (move_encounter_counter)
;   starts at $0A (10) and decrements each turn in a location. Every
;   4 turns (move_turn_encounter_roll resets to 4), it rolls for a
;   random monster encounter.
;
; XREF: 3 refs (3 calls) from dungeon_turn_process, game_loop_call_terrain, render_call_turn
move_process_turn    lda  $B769           ; Game state validation byte
            ora  #$55            ; OR with $55 pattern
            cmp  #$FF            ; Should equal $FF if valid
            beq  input_wait_selfmod ; Invalid → skip processing (abort)

            lda  $E2             ; Location type
            beq  move_turn_party_loop   ; $E2=0 → Sosaria surface, skip encounter
            dec  move_encounter_counter ; Decrement encounter countdown
            beq  move_turn_encounter_roll ; Hit zero → roll for encounter
            rts                  ; Not yet → return

; --- Encounter countdown hit zero: reset and trigger encounter ---
; XREF: 1 ref (1 branch) from move_turn_encounter_roll
move_turn_encounter_roll lda  #$04            ; Reset encounter timer to 4 turns
            sta  move_encounter_counter
            ldx  #$31            ; Set up encounter parameters
            clc
            adc  #$B3            ; Compute encounter type
            ldy  #$1B
            jsr  $03A3           ; Call Applesoft RNG/encounter handler
            cmp  #$32            ; Check encounter result
            bne  move_turn_encounter_roll ; No encounter → try again
; === End of while loop ===

; --- Per-turn party maintenance: MP regen, poison, HP regen, checksum ---
move_turn_party_loop lda  #$04            ; Process up to 4 party members
            sta  $D5             ; $D5 = member counter (4 down to 0)
            dec  move_regen_counter ; Decrement HP regen timer (10-turn cycle)
            bpl  move_turn_check_next ; Not yet → skip regen flag
            lda  #$09            ; Timer expired → reset to 9 (10-turn period)
            sta  move_regen_counter ; Regen 1 HP per 10 steps walked

; --- Loop through each party member for turn processing ---
; XREF: 2 refs (1 jump) (1 branch) from move_turn_party_loop, move_turn_checksum
move_turn_check_next dec  $D5             ; Next party member (4→3→2→1→0)
            bpl  move_turn_check_class ; More members → process this one
            lda  $B769           ; All done — check game state flag
            cmp  #$AA            ; $AA = game terminated
            bne  move_turn_display_status ; Still running → refresh display
            pla                  ; Game over → unwind stack
; XREF: 1 ref (1 branch) from move_turn_check_next
move_turn_display_status jsr  move_display_party_status ; Refresh party stats sidebar
            rts
; --- CLASS-SPECIFIC MP REGENERATION ---
;   Each class that can cast spells regenerates 1 MP per turn, up to
;   a cap of (governing_stat / 2). The stat is BCD, so the halving
;   requires BCD→binary→LSR→binary→BCD conversion (O(N) loops).
;
;   Wizard ($D7):       cap = STR/2 (offset $14)
;   Cleric ($C3):       cap = WIS/2 (offset $15)
;   Lark/Druid/Alch:    cap = STR/2 (offset $14)
;   Paladin/Illus/Druid: cap = WIS/2 (offset $15)
;   Ranger ($D2):       cap = max(STR/2, WIS/2)
;
; XREF: 1 ref (1 branch) from move_turn_check_next
move_turn_check_class jsr  $46F6           ; Set $FE/$FF → character record
            ldy  #$17            ; Offset $17 = class byte
            lda  ($FE),Y         ; Load class
            cmp  #$D7            ; Wizard? ('W' high-ASCII)
            bne  move_turn_check_cleric ; No → try Cleric
            ldy  #$19            ; Wizard: check MP (offset $19)
            lda  ($FE),Y         ; Load current MP
            ldy  #$14            ; Compare against STR (offset $14)
            cmp  ($FE),Y         ; MP >= STR?
            bcs  move_turn_check_cleric ; Already at cap → skip
            jsr  magic_cast_spell ; Below cap → add 1 MP
; XREF: 2 refs (2 branches) from move_turn_check_class, move_turn_check_class
move_turn_check_cleric ldy  #$17            ; Reload class byte
            lda  ($FE),Y
            cmp  #$C3            ; Cleric? ('C')
            bne  move_turn_check_lark ; No → try hybrid classes
            ldy  #$19            ; Check MP
            lda  ($FE),Y
            ldy  #$15            ; Compare against WIS (offset $15)
            cmp  ($FE),Y         ; MP >= WIS?
            bcs  move_turn_check_lark ; At cap → skip
            jsr  magic_cast_spell ; Below cap → add 1 MP
; --- STR-based regen: Lark ($CC), Druid ($C4), Alchemist ($C1) ---
; XREF: 2 refs (2 branches) from move_turn_check_cleric, move_turn_check_cleric
move_turn_check_lark ldy  #$17            ; Reload class byte
            lda  ($FE),Y
            cmp  #$CC            ; Lark? ('L')
            beq  move_turn_regen_mp_str ; Yes → regen to STR/2
            cmp  #$C4            ; Druid? ('D')
            beq  move_turn_regen_mp_str ; Yes → regen to STR/2
            cmp  #$C1            ; Alchemist? ('A')
            beq  move_turn_regen_mp_str ; Yes → regen to STR/2
            jmp  move_turn_check_wizard ; None matched → check WIS-based
; --- Compute STR/2 cap and regen if MP < cap ---
; XREF: 3 refs (3 branches) from move_turn_check_lark, move_turn_check_lark, move_turn_check_lark
move_turn_regen_mp_str ldy  #$14            ; Offset $14 = STR (BCD)
            lda  ($FE),Y         ; Load STR
            jsr  combat_bcd_to_binary ; BCD→binary (O(N) loop)
            lsr  a               ; Binary divide by 2
            jsr  combat_binary_to_bcd ; Binary→BCD (O(N) loop)
            ldy  #$19            ; A = STR/2 as BCD; compare to MP
            cmp  ($FE),Y         ; STR/2 vs current MP
            bcc  move_turn_check_wizard ; MP >= cap → no regen
            beq  move_turn_check_wizard ; MP == cap → no regen
            jsr  magic_cast_spell ; MP < cap → add 1 MP
; --- WIS-based regen: Paladin ($D0), Illusionist ($C9), Druid ($C4) ---
; XREF: 3 refs (1 jump) (2 branches) from move_turn_check_lark, move_turn_regen_mp_str, move_turn_regen_mp_str
move_turn_check_wizard ldy  #$17            ; Reload class byte
            lda  ($FE),Y
            cmp  #$D0            ; Paladin? ('P')
            beq  move_turn_regen_mp_wis ; Yes → regen to WIS/2
            cmp  #$C9            ; Illusionist? ('I')
            beq  move_turn_regen_mp_wis ; Yes → regen to WIS/2
            cmp  #$C4            ; Druid? ('D') — gets BOTH STR and WIS regen
            beq  move_turn_regen_mp_wis ; Yes → also regen to WIS/2
            jmp  move_turn_regen_mp_int ; None → check Ranger
; --- Compute WIS/2 cap and regen if MP < cap ---
; XREF: 3 refs (3 branches) from move_turn_check_wizard, move_turn_check_wizard, move_turn_check_wizard
move_turn_regen_mp_wis ldy  #$15            ; Offset $15 = WIS (BCD)
            lda  ($FE),Y         ; Load WIS
            jsr  combat_bcd_to_binary ; BCD→binary
            lsr  a               ; /2
            jsr  combat_binary_to_bcd ; →BCD
            ldy  #$19            ; Compare WIS/2 to MP
            cmp  ($FE),Y
            bcc  move_turn_regen_mp_int ; MP >= cap → no regen
            beq  move_turn_regen_mp_int ; MP == cap → no regen
            jsr  magic_cast_spell ; Below cap → add 1 MP
; --- Ranger ($D2): dual regen — both WIS/2 AND STR/2 caps ---
;   Rangers are the only class that regenerates MP against TWO stat
;   caps. First checks WIS/2, then STR/2 — each can independently
;   grant +1 MP per turn if below its respective cap. This makes
;   Rangers the best MP regenerators in the game.
;
; XREF: 3 refs (1 jump) (2 branches) from move_turn_regen_mp_wis, move_turn_check_wizard, move_turn_regen_mp_wis
move_turn_regen_mp_int ldy  #$17            ; Reload class byte
            lda  ($FE),Y
            cmp  #$D2            ; Ranger? ('R')
            bne  move_turn_poison_damage ; Not Ranger → skip to poison check
            ldy  #$15            ; First: check WIS/2 cap
            lda  ($FE),Y         ; Load WIS
            jsr  combat_bcd_to_binary ; BCD→binary
            lsr  a               ; /2
            jsr  combat_binary_to_bcd ; →BCD
            ldy  #$19            ; Compare WIS/2 to MP
            cmp  ($FE),Y
            bcc  move_turn_poison_damage ; MP >= WIS/2 cap → skip first regen
            beq  move_turn_poison_damage ; MP == WIS/2 cap → skip first regen
            ldy  #$14            ; Second: also check STR/2 cap
            lda  ($FE),Y         ; Load STR
            jsr  combat_bcd_to_binary
            lsr  a               ; /2
            jsr  combat_binary_to_bcd
            ldy  #$19            ; Compare STR/2 to MP
            cmp  ($FE),Y

; --- Final MP regen check (shared by Ranger second cap) ---
; XREF: 1 ref (1 branch) from move_turn_add_exp
move_turn_poison_check bcc  move_turn_poison_damage ; MP >= cap → no regen
            beq  move_turn_poison_damage ; MP == cap → no regen
            jsr  magic_cast_spell ; Below cap → add 1 MP

; --- POISON DAMAGE & FOOD DEDUCTION ---
;   After MP regen, check if the character is alive and process:
;   1. Deduct $10 (BCD 16) food per turn for living characters
;   2. If status is 'P' (Poisoned, $D0): apply 1 HP damage
;   3. If regen counter hit zero: heal 1 HP (natural regeneration)
;   4. Run anti-cheat checksum on every character every turn
;
; XREF: 5 refs (5 branches)
move_turn_poison_damage ldy  #$11            ; Offset $11 = status byte
            lda  ($FE),Y         ; Load status
            cmp  #$C4            ; Dead ('D')? → skip all processing
            beq  move_turn_checksum
            cmp  #$C1            ; Ashes ('A')? → skip
            beq  move_turn_checksum
            cmp  #$00            ; Empty slot? → skip
            beq  move_turn_checksum
            lda  #$10            ; Deduct $10 food (BCD 16) per turn
            jsr  magic_check_mp  ; (deducts food via BCD16 subtraction)
            ldy  #$11            ; Re-check status after food deduction
            lda  ($FE),Y
            cmp  #$D0            ; Poisoned ('P')?
            bne  move_turn_add_hp ; No → skip poison damage
            lda  #$01            ; Yes → apply 1 HP damage
            jsr  combat_apply_damage ; Poison tick

; --- Encrypt records and print status inline ---
; XREF: 1 ref (1 branch) from move_turn_checksum
move_turn_add_exp jsr  render_encrypt_records ; Re-encrypt character records
            jsr  $46BA           ; Print inline status message
            bne  move_turn_poison_check ; (inline data flow)
            cmp  #$D3            ; (inline data bytes)
            DB      $CF
            dec  $FFA1           ; (inline data bytes)
            DB      $00,$20,$E4,$88
; --- Natural HP regeneration: +1 HP every 10 turns ---
; XREF: 1 ref (1 branch) from move_turn_poison_damage
move_turn_add_hp lda  move_regen_counter ; Check HP regen timer
            bne  move_turn_checksum ; Not zero → no regen this turn
            lda  #$01            ; Timer expired → heal 1 HP
            jsr  combat_add_hp   ; Add 1 HP (with max HP clamping)
; --- Anti-cheat checksum: run on every character every turn ---
; XREF: 4 refs (4 branches)
move_turn_checksum jsr  combat_checksum_xor ; XOR checksum over engine code
            cmp  #$0F            ; Expected checksum value
            bne  move_turn_add_exp ; Mismatch → tamper detected path
            jmp  move_turn_check_next ; OK → process next party member

; --- Embedded counter data (inline with code) ---
move_encounter_counter
            DB      $0A              ; Encounter countdown (starts at 10)
move_regen_counter
            DB      $09              ; HP regen countdown (10-turn cycle)

; ###########################################################################
; ###                                                                     ###
; ###              MAGIC SYSTEM ($75AE-$761C)                             ###
; ###                                                                     ###
; ###########################################################################
;
;   Ultima III's magic system was revolutionary for 1983 CRPGs: separate
;   Wizard and Cleric spell lists, MP regeneration tied to attributes,
;   and class-specific spell access. The system below handles MP
;   regeneration during overworld turns — not combat spell resolution,
;   which lives in the data blob above (the inline-string-heavy combat
;   spell handler at $72xx-$73xx).
;
;   MP REGENERATION RULES (per turn, every 10th step):
;   - Wizards (class $D7): regen if MP < STR/2  (INT-based cap)
;   - Clerics (class $C3): regen if MP < INT/2  (WIS-based cap)
;   - Larks ($CC), Druids ($C4), Alchemists ($C1): regen to STR/2 cap
;   - Paladins ($D0), Illusionists ($C9), Druids ($C4): regen to WIS/2 cap
;   - Rangers ($D2): regen to both STR/2 AND WIS/2 caps
;   The halving is done by BCD→binary conversion, LSR, then back to BCD.
;   This means a stat of 50 gives a regen cap of 25 MP.
;

; ---------------------------------------------------------------------------
; magic_cast_spell — Increment a character's MP by 1 (BCD)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Adds 1 MP to the current character pointed to by $FE/$FF.
;            Uses BCD mode so the increment is decimal (09→10, not 09→0A).
;            Called during turn processing for each eligible spell-casting
;            class, after checking that their MP is below the regen cap.
;
;   PARAMS:  $FE/$FF = pointer to 64-byte character record
;   RETURNS: A = new MP value
;   MODIFIES: Character record byte $19 (MP)
;
; XREF: 5 refs (5 calls) from move_turn_check_class, move_turn_poison_check, move_turn_regen_mp_str, move_turn_check_cleric, move_turn_regen_mp_wis
magic_cast_spell   sed                  ; Enter BCD mode for decimal increment
            ldy  #$19            ; Y = offset to MP field in character record
            lda  ($FE),Y         ; Load current MP (BCD)
            clc
            adc  #$01            ; MP += 1 (decimal: 09 becomes 10, not 0A)
            sta  ($FE),Y         ; Store updated MP
            cld                  ; Exit BCD mode — CRITICAL: forgetting CLD
            rts                  ; corrupts all subsequent arithmetic

; ---------------------------------------------------------------------------
; magic_resolve_effect — Check if a character can act (not incapacitated)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Checks character status byte ($11) for incapacitating conditions.
;            Status $C7 = 'G' (Good) and $D0 = 'P' (Poisoned) are the only
;            conditions that allow action — the character is conscious.
;            Status $C4 = 'D' (Dead) or $C1 = 'A' (Ashes) prevent action.
;
;   PARAMS:  $D5 = character slot index (passed to $46F6 to set $FE/$FF)
;   RETURNS: A = 0 if character can act, $FF if incapacitated
;   CALLERS: Combat turn loop, party status display, dungeon traps
;
; XREF: 11 refs (11 calls) from render_party_status_disp, char_turn_loop, char_turn_next, char_use_powder, loc_00917A, ...
magic_resolve_effect   jsr  $46F6           ; Set $FE/$FF → character record for slot $D5
            ldy  #$11            ; Offset $11 = status byte
            lda  ($FE),Y         ; Load status
            cmp  #$C7            ; 'G' = Good? (high-bit ASCII)
            beq  magic_effect_zero   ; Yes → can act (return 0)
            cmp  #$D0            ; 'P' = Poisoned?
            beq  magic_effect_zero   ; Yes → can act (return 0)
            lda  #$FF            ; Incapacitated (Dead/Ashes/other)
            rts
; XREF: 2 refs (2 branches) from magic_resolve_effect, magic_resolve_effect
magic_effect_zero lda  #$00            ; Can act
            rts

; --- Data region (75 bytes, text data) ---
            DB      $20,$F6,$46,$A0,$13,$B1,$FE,$20,$5F,$71,$85,$D3,$A0,$17,$B1,$FE
            DB      $C9,$D4,$F0,$0E,$C9,$C2,$F0,$13,$C9,$C9,$F0,$0F,$C9,$D2,$F0,$0B
            DB      $D0,$0F,$A5,$D3,$69,$80,$85,$D3,$4C,$00,$76,$A5,$D3,$69,$40,$85
            DB      $D3,$20,$E7,$46,$C5,$D3,$B0,$13,$A9,$B7,$8D,$0E,$76,$AD,$6C,$50
            DB      $8C,$0E,$76,$CD,$A5,$62,$F0,$F5,$A9,$00,$60
; --- End data region (75 bytes) ---

; XREF: 1 ref (1 branch) from magic_effect_zero
magic_effect_miss lda  #$FF            ; A=$00FF X=$0031 Y=$0011 ; [SP-1380]
            rts                  ; A=$00FF X=$0031 Y=$0011 ; [SP-1378]

; ---------------------------------------------------------------------------
; magic_check_mp — Deduct food from a character (BCD16 subtraction)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Subtracts A units of food from the character at $FE/$FF.
;            Food is stored as a 3-byte BCD16 value at offsets $20-$22
;            (sub-morsels at $20, food_hi at $21, food_lo at $22).
;            If food underflows (carry clear after BCD subtraction),
;            falls through to equip_handle which zeroes food and prints
;            "STARVING!" — a death sentence if not remedied quickly.
;
;   BCD16 SUBTRACTION: The 6502's SED mode only works on single bytes,
;   so multi-byte BCD subtraction must be done byte-by-byte with carry
;   propagation, just like binary multi-byte subtraction but in decimal
;   mode. The bytes are processed from low ($22) to high ($20).
;
;   PARAMS:  A = amount to deduct (BCD)
;            $FE/$FF = character record pointer
;   RETURNS: Falls through to equip_handle on underflow
;
; XREF: 1 ref (1 call) from move_turn_poison_damage
magic_check_mp   sta  $D0             ; Save deduction amount
            sed                  ; Enter BCD mode
            sec                  ; Set carry for subtraction
            ldy  #$22            ; Start with food_lo byte
            lda  ($FE),Y         ; Load food_lo
            sbc  $D0             ; Subtract deduction amount
            sta  ($FE),Y         ; Store result
            dey                  ; Y=$21 → food_hi
            lda  ($FE),Y         ; Load food_hi
            sbc  #$00            ; Propagate borrow
            sta  ($FE),Y
            dey                  ; Y=$20 → sub-morsels
            lda  ($FE),Y         ; Load sub-morsels
            sbc  #$00            ; Propagate borrow
            sta  ($FE),Y
            cld                  ; Exit BCD mode
            bcc  equip_handle   ; Borrow set? → food underflowed → STARVING!
            rts                  ; Food OK, return normally

; ###########################################################################
; ###                                                                     ###
; ###          EQUIPMENT & ECONOMY ($763B-$7960)                          ###
; ###                                                                     ###
; ###########################################################################
;
;   Food depletion, starvation handling, moongate/whirlpool ship mechanics,
;   and the "enter town/dungeon" transition logic. Also contains the food
;   depletion rate constant at $772C (default 04 = deduct food every 4th
;   step on the overworld). This section is heavily interleaved with
;   inline strings for narrative messages ("STARVING!", "A HUGE SWIRLING
;   WHIRLPOOL ENGULFS YOU AND YOUR SHIP...").
;

; ---------------------------------------------------------------------------
; equip_handle — Handle food starvation (zero food, print warning)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Called when food underflows past zero. Zeros both food bytes
;            in the character record, then prints "STARVING!" inline and
;            applies 5 damage. In 1983, food management was a core survival
;            mechanic — running out on the overworld was a genuine threat.
;
;   PARAMS:  $FE/$FF = character record pointer
;   RETURNS: After damage application
;
; XREF: 3 refs (1 call) (2 branches) from magic_check_mp, equip_load_state, dungeon_trap_setup
equip_handle    lda  #$00            ; Zero the food field
            ldy  #$20            ; Offset $20 = sub-morsels
            sta  ($FE),Y
            ldy  #$21            ; Offset $21 = food_hi
            sta  ($FE),Y
            jsr  $46BA           ; Print inline: (next bytes are "STARVING!")
            DB      $FF
            ASC     "STARVING!"
            DB      $FF,$00,$20,$E4,$88,$A9,$F7,$20,$05,$47,$20,$E4,$88,$A9,$05,$20
            DB      $81,$71,$60
equip_check_location lda  $E2             ; A=[$00E2] X=$0031 Y=$0021 ; [SP-1382]
            beq  equip_food_deduct     ; A=[$00E2] X=$0031 Y=$0021 ; [SP-1382]
            rts                  ; A=[$00E2] X=$0031 Y=$0021 ; [SP-1380]
; XREF: 1 ref (1 branch) from equip_check_location
equip_food_deduct dec  $772C           ; A=[$00E2] X=$0031 Y=$0021 ; [SP-1380]
            beq  equip_load_state     ; A=[$00E2] X=$0031 Y=$0021 ; [SP-1380]
            rts                  ; A=[$00E2] X=$0031 Y=$0021 ; [SP-1378]
; XREF: 1 ref (1 branch) from equip_food_deduct
equip_load_state lda  $62A5           ; A=[$62A5] X=$0031 Y=$0021 ; [SP-1378]
            cmp  $B76F           ; A=[$62A5] X=$0031 Y=$0021 ; [SP-1378]
            beq  equip_handle        ; A=[$62A5] X=$0031 Y=$0021 ; [SP-1378]
; === End of while loop ===

            lda  #$04            ; A=$0004 X=$0031 Y=$0021 ; [SP-1378]
            sta  $772C           ; A=$0004 X=$0031 Y=$0021 ; [SP-1378]
            lda  #$08            ; A=$0008 X=$0031 Y=$0021 ; [SP-1378]
            jsr  $46E4           ; A=$0008 X=$0031 Y=$0021 ; [SP-1380]
            beq  equip_setup_monster     ; A=$0008 X=$0031 Y=$0021 ; [SP-1380]
            clc                  ; A=$0008 X=$0031 Y=$0021 ; [SP-1380]
            lda  $4FFC           ; A=[$4FFC] X=$0031 Y=$0021 ; [SP-1380]
            adc  $4FFE           ; A=[$4FFC] X=$0031 Y=$0021 ; [SP-1380]
            and  #$3F            ; A=A&$3F X=$0031 Y=$0021 ; [SP-1380]
            sta  $02             ; A=A&$3F X=$0031 Y=$0021 ; [SP-1380]
            clc                  ; A=A&$3F X=$0031 Y=$0021 ; [SP-1380]
            lda  $4FFD           ; A=[$4FFD] X=$0031 Y=$0021 ; [SP-1380]
            adc  $4FFF           ; A=[$4FFD] X=$0031 Y=$0021 ; [SP-1380]
            and  #$3F            ; A=A&$3F X=$0031 Y=$0021 ; [SP-1380]
            sta  $03             ; A=A&$3F X=$0031 Y=$0021 ; [SP-1380]
            jsr  $46FF           ; A=A&$3F X=$0031 Y=$0021 ; [SP-1382]
            beq  equip_write_tile     ; A=A&$3F X=$0031 Y=$0021 ; [SP-1382]
            cmp  #$2C            ; A=A&$3F X=$0031 Y=$0021 ; [SP-1382]
            bne  equip_setup_monster     ; A=A&$3F X=$0031 Y=$0021 ; [SP-1382]
            lda  #$30            ; A=$0030 X=$0031 Y=$0021 ; [SP-1382]
            sta  ($FE),Y         ; A=$0030 X=$0031 Y=$0021 ; [SP-1382]
            ldx  $4FFC           ; A=$0030 X=$0031 Y=$0021 ; [SP-1382]
            lda  $02             ; A=[$0002] X=$0031 Y=$0021 ; [SP-1382]
            sta  $4FFC           ; A=[$0002] X=$0031 Y=$0021 ; [SP-1382]
            stx  $02             ; A=[$0002] X=$0031 Y=$0021 ; [SP-1382]
            ldx  $4FFD           ; A=[$0002] X=$0031 Y=$0021 ; [SP-1382]
            lda  $03             ; A=[$0003] X=$0031 Y=$0021 ; [SP-1382]
            sta  $4FFD           ; A=[$0003] X=$0031 Y=$0021 ; [SP-1382]
            stx  $03             ; A=[$0003] X=$0031 Y=$0021 ; [SP-1382]
            jsr  $46FF           ; A=[$0003] X=$0031 Y=$0021 ; [SP-1384]
            lda  #$00            ; A=$0000 X=$0031 Y=$0021 ; [SP-1384]
            sta  ($FE),Y         ; A=$0000 X=$0031 Y=$0021 ; [SP-1384]
            jsr  $0230           ; A=$0000 X=$0031 Y=$0021 ; [SP-1386]
            jsr  equip_check_class        ; A=$0000 X=$0031 Y=$0021 ; [SP-1388]
            jsr  $46BA           ; A=$0000 X=$0031 Y=$0021 ; [SP-1390]
            cmp  ($A0,X)         ; A=$0000 X=$0031 Y=$0021 ; [SP-1390]
            DB      $D3
            iny                  ; A=$0000 X=$0031 Y=$0022 ; [SP-1390]

; ---
            DB      $C9,$D0,$A0,$D7,$C1,$D3,$FF,$C4,$C5,$D3,$D4,$D2,$CF,$D9,$C5,$C4
            DB      $A1,$FF,$1D,$00,$4C,$2B,$77
; ---

; XREF: 2 refs (2 branches) from equip_load_state, equip_load_state
equip_setup_monster lda  #$08            ; A=$0008 X=$0031 Y=$0022 ; [SP-1391]
            jsr  $46E4           ; A=$0008 X=$0031 Y=$0022 ; [SP-1394]
            tax                  ; A=$0008 X=$0008 Y=$0022 ; [SP-1394]
            lda  $79A7,X         ; -> $79AF ; A=$0008 X=$0008 Y=$0022 ; [SP-1394]
            sta  $4FFE           ; A=$0008 X=$0008 Y=$0022 ; [SP-1394]
            lda  $79AF,X         ; -> $79B7 ; A=$0008 X=$0008 Y=$0022 ; [SP-1394]
            sta  $4FFF           ; A=$0008 X=$0008 Y=$0022 ; [SP-1394]
            jmp  equip_ship_pos     ; A=$0008 X=$0008 Y=$0022 ; [SP-1394]
; XREF: 1 ref (1 branch) from equip_load_state
equip_write_tile lda  #$30            ; A=$0030 X=$0008 Y=$0022 ; [SP-1394]
            sta  ($FE),Y         ; A=$0030 X=$0008 Y=$0022 ; [SP-1394]
            ldx  $4FFC           ; A=$0030 X=$0008 Y=$0022 ; [SP-1394]
            lda  $02             ; A=[$0002] X=$0008 Y=$0022 ; [SP-1394]
            sta  $4FFC           ; A=[$0002] X=$0008 Y=$0022 ; [SP-1394]
            stx  $02             ; A=[$0002] X=$0008 Y=$0022 ; [SP-1394]
            ldx  $4FFD           ; A=[$0002] X=$0008 Y=$0022 ; [SP-1394]
            lda  $03             ; A=[$0003] X=$0008 Y=$0022 ; [SP-1394]
            sta  $4FFD           ; A=[$0003] X=$0008 Y=$0022 ; [SP-1394]
            stx  $03             ; A=[$0003] X=$0008 Y=$0022 ; [SP-1394]
            jsr  $46FF           ; A=[$0003] X=$0008 Y=$0022 ; [SP-1396]
            lda  #$00            ; A=$0000 X=$0008 Y=$0022 ; [SP-1396]
            sta  ($FE),Y         ; A=$0000 X=$0008 Y=$0022 ; [SP-1396]
; XREF: 1 ref (1 jump) from equip_setup_monster
equip_ship_pos lda  $4FFC           ; A=[$4FFC] X=$0008 Y=$0022 ; [SP-1396]
            cmp  $00             ; A=[$4FFC] X=$0008 Y=$0022 ; [SP-1396]
            bne  equip_done     ; A=[$4FFC] X=$0008 Y=$0022 ; [SP-1396]
            lda  $4FFD           ; A=[$4FFD] X=$0008 Y=$0022 ; [SP-1396]
            cmp  $01             ; A=[$4FFD] X=$0008 Y=$0022 ; [SP-1396]
            bne  equip_done     ; A=[$4FFD] X=$0008 Y=$0022 ; [SP-1396]
            jsr  shop_handle      ; A=[$4FFD] X=$0008 Y=$0022 ; [OPT] TAIL_CALL: Tail call: JSR/JSL at $007728 followed by RTS ; [SP-1398]
; XREF: 2 refs (2 branches) from equip_ship_pos, equip_ship_pos
equip_done rts                  ; A=[$4FFD] X=$0008 Y=$0022 ; [SP-1396]
            DB      $00

; ---------------------------------------------------------------------------
; shop_handle  [2 calls]
;   Called by: equip_ship_pos, game_loop_check_tile
; ---------------------------------------------------------------------------

; FUNC $00772D: register -> A:X []
; Proto: uint32_t func_00772D(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [8 dead stores]
; XREF: 2 refs (2 calls) from equip_ship_pos, game_loop_check_tile
shop_handle  lda  #$18            ; A=$0018 X=$0008 Y=$0022 ; [SP-1399]
            sta  $0E             ; A=$0018 X=$0008 Y=$0022 ; [SP-1399]
            jsr  $0230           ; A=$0018 X=$0008 Y=$0022 ; [SP-1401]
            jsr  $46BA           ; Call $0046BA(A)
            DB      $FF
            cmp  ($A0,X)         ; A=$0018 X=$0008 Y=$0022 ; [SP-1403]
            iny                  ; A=$0018 X=$0008 Y=$0023 ; [SP-1403]

; --- Data region (103 bytes, text data) ---
            DB      $D5,$C7,$C5,$A0,$D3,$D7,$C9,$D2,$CC,$C9,$CE,$C7,$FF,$A0,$AD,$AD
            DB      $D7,$C8,$C9,$D2,$CC,$D0,$CF,$CF,$CC,$AD,$AD,$FF,$A0,$A0,$C5,$CE
            DB      $C7,$D5,$CC,$C6,$D3,$A0,$D9,$CF,$D5,$FF,$A0,$C1,$CE,$C4,$A0,$D9
            DB      $CF,$D5,$D2,$A0,$D3,$C8,$C9,$D0,$FF,$A0,$C4,$D2,$C1,$C7,$C7,$C9
            DB      $CE,$C7,$A0,$C2,$CF,$D4,$C8,$FF,$A0,$A0,$A0,$A0,$A0,$D4,$CF,$A0
            DB      $C1,$FF
            ASC     " WATERY GRAVE!"
            DB      $00 ; null terminator
            DB      $20,$A2,$77,$4C,$C2,$77
; --- End data region (103 bytes) ---


; ===========================================================================
; DISPLAY (8 functions)
; ===========================================================================

; ---------------------------------------------------------------------------
; equip_check_class — Play "sinking ship" sound effect
; ---------------------------------------------------------------------------
;
;   PURPOSE: Despite the CIDAR-generated name, this is a descending-pitch
;            sound effect played when the player's ship sinks (whirlpool
;            encounter). It's a classic Apple II 1-bit speaker synthesis:
;            an outer loop sweeps the period from $40→$C0, producing a
;            descending tone that evokes the gurgling of a sinking vessel.
;
;   ALGORITHM:
;   - $F3 = period counter, starts at $40 (high pitch)
;   - Inner X loop: PHA/PLA pairs burn 7 cycles each for timing delay
;   - Inner Y loop (20 iterations): repeats the delay for each half-wave
;   - BIT $C030: toggles speaker once per Y iteration
;   - Period increments ($40→$C0): pitch drops as period lengthens
;   - $10 (in-party flag) check: skip sound if character not active
;
;   WHY PHA/PLA: Same idiom as SUBS sound effects — burns exactly
;   7 cycles per pair (PHA=3, PLA=4) for cycle-precise speaker timing.
;   NOT redundant code despite CIDAR's "PEEPHOLE: Redundant PHA/PLA"
;   warning. Without these delay cycles, the pitch would be too high
;   and the waveform would alias against the CPU's instruction timing.
;
; XREF: 2 refs (2 calls) from shop_handle, equip_load_state
equip_check_class    lda  $10             ; Check in-party flag
            bmi  equip_class_done   ; If $FF (in party) → skip? Actually: $10 bit 7
            lda  #$40            ; Starting period (high pitch)
            sta  $F3

equip_class_check_offset ldy  #$14            ; 20 half-wave cycles per pitch step

equip_class_load_ptr ldx  $F3             ; X = current period (delay count)

; --- Cycle-burn delay loop: X * 7 cycles per iteration ---
equip_class_push_state pha                  ; } 7 cycles: PHA(3) + PLA(4)
            pla                  ; } This is a TIMING IDIOM, not dead code
            dex                  ; Decrement delay counter
            bne  equip_class_push_state   ; Repeat for X iterations

            bit  $C030           ; Toggle speaker — produces one half-wave
            dey                  ; Next half-wave cycle
            bne  equip_class_load_ptr   ; 20 toggles per pitch step

            inc  $F3             ; Increase period → lower pitch
            lda  $F3
            cmp  #$C0            ; Reached lowest pitch ($C0)?
            bcc  equip_class_check_offset   ; No → continue descending
equip_class_done rts

; --- Data region (415 bytes, text data) ---
            DB      $A5,$E2,$F0,$1B,$10,$03,$4C,$E6,$78,$A9,$40,$20,$E4,$46,$85,$00
            DB      $A9,$40,$20,$E4,$46,$85,$01,$20,$FC,$46,$D0,$ED,$4C,$54,$79,$A5
            DB      $00,$85,$E3,$85,$02,$A5,$01,$85,$E4,$85,$03,$20,$FF,$46,$A9,$00
            DB      $91,$FE,$A9,$02,$8D,$FC,$4F,$A9,$3E,$8D,$FD,$4F,$A9,$16,$85,$0E
            DB      $85,$E0,$A9,$00,$85,$B1,$85,$B0,$A5,$B2,$D0,$FC,$20,$7D,$65,$20
            DB      $C3,$46,$20,$BA,$46,$FF,$FF,$A0,$C1,$D3,$A0,$D4,$C8,$C5,$A0,$D7
            DB      $C1,$D4,$C5,$D2,$FF,$A0,$C5,$CE,$D4,$C5,$D2,$D3,$A0,$A0,$D9,$CF
            DB      $D5,$D2,$FF,$CC,$D5,$CE,$C7,$D3,$A0,$D9,$CF,$D5,$A0,$D0,$C1,$D3
            DB      $D3,$FF,$C9,$CE,$D4,$CF,$A0,$C4,$C1,$D2,$CB,$CE,$C5,$D3,$D3,$A1
            DB      $FF,$FF,$00,$20,$B7,$46,$04,$C2,$CC,$CF,$C1,$C4,$A0,$CD,$C1,$D0
            DB      $DA,$8D,$04
            ASC     "BLOAD MONZ"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $A9,$0B,$85,$B1,$A9,$7E,$85,$E0,$A9,$20,$85,$00,$A9,$36,$85,$01
            DB      $A9,$FF,$85,$E2,$20,$BA,$46,$FF,$A0,$D9,$CF,$D5,$A0,$C1,$D7,$C1
            DB      $CB,$C5,$CE,$A0,$CF,$CE,$FF,$A0,$D4,$C8,$C5,$A0,$D3,$C8,$CF,$D2
            DB      $C5,$D3,$A0,$CF,$C6,$FF,$A0,$A0,$C1,$A0,$C6,$CF,$D2,$C7,$CF,$D4
            DB      $D4,$C5,$CE,$FF,$CC,$C1,$CE,$C4,$AE,$A0,$D9,$CF,$D5,$D2,$A0,$D3
            DB      $C8,$C9,$D0,$FF,$A0,$C1,$CE,$C4,$A0,$C3,$D2,$C5,$D7,$A0,$CC,$CF
            DB      $D3,$D4,$FF,$A0,$A0,$D4,$CF,$A0,$D4,$C8,$C5,$A0,$D3,$C5,$C1,$A1
            DB      $FF,$00,$4C,$54,$79,$A9,$00,$85,$B1,$85,$B0,$A5,$B2,$D0,$FC,$20
            DB      $B7,$46,$04
            ASC     "BLOAD SOSA"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $20,$BA,$46,$FF,$FF,$FF,$FF,$FF,$A0,$C1,$CC,$CC,$A0,$C9,$D3,$A0
            DB      $C4,$C1,$D2,$CB,$A1,$FF,$FF,$00,$20,$C3,$46,$20,$B7,$46,$04
            ASC     "BLOAD SOSM"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $20,$BA,$46,$A0,$D9,$CF,$D5,$A0,$CD,$C1,$C4,$C5,$A0,$C9,$D4,$A1
            DB      $FF,$00,$A5,$E3,$85,$00,$A5,$E4,$85,$01,$A9,$00,$85,$E2,$A9,$16
            DB      $85,$E0,$20,$B0,$65,$A9,$01,$85,$B1,$A5,$E0,$85,$0E,$20,$30,$02
            DB      $20,$BA,$46,$1D,$00,$60
; --- End data region (415 bytes) ---


; ###########################################################################
; ###                                                                     ###
; ###          WORLD MOVEMENT ($7961-$7A0B)                               ###
; ###                                                                     ###
; ###########################################################################
;
;   Overworld location entry handler. When the player steps onto a town,
;   castle, or dungeon entrance tile, this code loads the appropriate map
;   from disk and transitions to the location. The decrypt/encrypt calls
;   bracket disk I/O because character records are XOR-encrypted in memory
;   and must be decrypted before BLOAD overwrites PLRS, then re-encrypted.
;
;   LOCATION TABLE ($7997/$799F): Two parallel 8-byte arrays mapping
;   location codes to starting X,Y coordinates within the location map.
;   The location code comes from the tile type, offset by $B0 to index
;   into the table.
;

; ---------------------------------------------------------------------------
; world_move_handler — Enter a town, castle, or dungeon from overworld
; ---------------------------------------------------------------------------
;
;   PURPOSE: Transition from the Sosaria overworld into a sub-location.
;            Decrypts character records, loads the destination map via
;            the ProDOS BLOAD dispatcher at $0230, then re-encrypts.
;            The double decrypt-load-encrypt pattern is needed because
;            the BLOAD may overwrite the PLRS memory area at $4000.
;
;   PARAMS:  $6FA4 = location code from tile interaction
;   RETURNS: After location load and encryption restore
;
; XREF: 1 ref (1 call) from game_loop_call_terrain
world_move_handler  jsr  $0230           ; Execute ProDOS command (BLOAD map)
            jsr  char_decrypt_records   ; Decrypt char records for disk I/O
            lda  #$FD            ; A=$00FD X=$0007 Y=$0013 ; [SP-1457]
            ldx  #$C0            ; A=$00FD X=$00C0 Y=$0013 ; [SP-1457]
            ldy  #$20            ; A=$00FD X=$00C0 Y=$0020 ; [SP-1457]
            jsr  $4705           ; A=$00FD X=$00C0 Y=$0020 ; [SP-1459]
            jsr  char_decrypt_records       ; A=$00FD X=$00C0 Y=$0020 ; [SP-1461]
            lda  $6FA4           ; A=[$6FA4] X=$00C0 Y=$0020 ; [SP-1461]
            sec                  ; A=[$6FA4] X=$00C0 Y=$0020 ; [SP-1461]
            sbc  #$B0            ; A=A-$B0 X=$00C0 Y=$0020 ; [SP-1461]
            tax                  ; A=A-$B0 X=A Y=$0020 ; [SP-1461]
            lda  $7997,X         ; A=A-$B0 X=A Y=$0020 ; [SP-1461]
            sta  $00             ; A=A-$B0 X=A Y=$0020 ; [SP-1461]
            lda  $799F,X         ; A=A-$B0 X=A Y=$0020 ; [SP-1461]
            sta  $01             ; A=A-$B0 X=A Y=$0020 ; [SP-1461]
            jsr  $0230           ; Call $000230(Y)
            jsr  char_decrypt_records       ; A=A-$B0 X=A Y=$0020 ; [SP-1465]
            lda  #$FD            ; A=$00FD X=A Y=$0020 ; [SP-1465]
            ldx  #$C0            ; A=$00FD X=$00C0 Y=$0020 ; [SP-1465]
            ldy  #$20            ; A=$00FD X=$00C0 Y=$0020 ; [SP-1465]
            jsr  $4705           ; A=$00FD X=$00C0 Y=$0020 ; [SP-1467]
            jsr  char_decrypt_records       ; A=$00FD X=$00C0 Y=$0020 ; [OPT] TAIL_CALL: Tail call: JSR/JSL at $007993 followed by RTS ; [SP-1469]
            rts                  ; A=$00FD X=$00C0 Y=$0020 ; [SP-1467]

; --- Data region (70 bytes) ---
            DB      $08,$39,$0F,$24,$0F,$0C,$1F,$3A,$08,$2E,$1B,$3A,$1D,$37,$1F,$1F
            DB      $00,$01,$01,$01,$00,$FF,$FF,$FF,$01,$01,$00,$FF,$FF,$FF,$00,$01
            DB      $2D,$0A,$2E,$06,$22,$31,$2F,$07,$25,$12,$1E,$38,$13,$31,$3A,$3A
            DB      $38,$09,$2E,$12,$35,$13,$0D,$10,$3A,$3A,$2C,$35,$1F,$02,$1F,$39
            DB      $22,$1E,$2C,$06,$1C,$07
; --- End data region (70 bytes) ---

; XREF: 2 refs (2 jumps) from game_loop_jmp_input, game_loop_check_special
world_move_start lda  #$18            ; A=$0018 X=$00C0 Y=$0020 ; [SP-1472]
            sta  $F9             ; A=$0018 X=$00C0 Y=$0020 ; [SP-1472]
            lda  #$17            ; A=$0017 X=$00C0 Y=$0020 ; [SP-1472]
            sta  $FA             ; A=$0017 X=$00C0 Y=$0020 ; [SP-1472]
            lda  $0E             ; A=[$000E] X=$00C0 Y=$0020 ; [SP-1472]
            cmp  #$14            ; A=[$000E] X=$00C0 Y=$0020 ; [SP-1472]
            bcc  world_move_check_torch   ; A=[$000E] X=$00C0 Y=$0020 ; [SP-1472]
            cmp  #$18            ; A=[$000E] X=$00C0 Y=$0020 ; [SP-1472]
            bcs  world_move_check_torch   ; A=[$000E] X=$00C0 Y=$0020 ; [SP-1472]
            lda  $CD             ; A=[$00CD] X=$00C0 Y=$0020 ; [SP-1472]
            eor  #$FF            ; A=A^$FF X=$00C0 Y=$0020 ; [SP-1472]
            sta  $CD             ; A=A^$FF X=$00C0 Y=$0020 ; [SP-1472]
            bmi  world_move_check_torch   ; A=A^$FF X=$00C0 Y=$0020 ; [SP-1472]
            jmp  boot_check_quit      ; A=A^$FF X=$00C0 Y=$0020 ; [SP-1472]
; === End of while loop (counter: Y) ===

; XREF: 3 refs (3 branches) from world_move_start, world_move_start, world_move_start
world_move_check_torch lda  $CB             ; A=[$00CB] X=$00C0 Y=$0020 ; [SP-1472]
            beq  world_move_dungeon   ; A=[$00CB] X=$00C0 Y=$0020 ; [SP-1472]
            dec  $CB             ; A=[$00CB] X=$00C0 Y=$0020 ; [SP-1472]
            jmp  boot_check_quit      ; A=[$00CB] X=$00C0 Y=$0020 ; [SP-1472]
; === End of while loop (counter: Y) ===

; XREF: 1 ref (1 branch) from world_move_check_torch
world_move_dungeon jsr  dungeon_handle     ; A=[$00CB] X=$00C0 Y=$0020 ; [SP-1474]
            jsr  tile_update     ; A=[$00CB] X=$00C0 Y=$0020 ; [SP-1476]
            jmp  boot_check_quit      ; A=[$00CB] X=$00C0 Y=$0020 ; [SP-1476]

; ###########################################################################
; ###                                                                     ###
; ###          DUNGEON & CREATURE AI ($7A0C-$7C0B)                        ###
; ###                                                                     ###
; ###########################################################################
;
;   Monster spawning and movement AI for the overworld. The game maintains
;   a creature tracking system at $4F00-$4F9F with 5 parallel 32-entry
;   arrays (columnar layout, same principle as MON files):
;
;     $4F00-$4F1F: creature type/tile (0 = empty slot)
;     $4F20-$4F3F: terrain-under-creature (restored when creature moves)
;     $4F40-$4F5F: creature X position
;     $4F60-$4F7F: creature Y position
;     $4F80-$4F9F: creature behavior flags ($C0=aggressive, $40=wander, $80=track)
;
;   Spawning is probabilistic: `dungeon_handle` rolls dice based on a
;   13-entry type table ($7BAC) and a 13-entry terrain preference table
;   ($7BB9). Creatures spawned at random positions within map range.
;
;   Movement AI (`tile_update`) iterates all 32 creature slots per turn:
;   - $C0 (aggressive): pathfind toward player using Manhattan distance
;   - $80 (tracking): move toward player with direction preference
;   - $40 (wandering): random movement with direction jitter
;   - Collision: if destination tile is impassable, try adjacent tiles
;   - Player contact: triggers combat encounter
;

; ---------------------------------------------------------------------------
; dungeon_handle — Spawn new overworld creatures
; ---------------------------------------------------------------------------
;
;   PURPOSE: Per-turn creature spawner. Only runs on Sosaria surface
;            ($E2=0); in towns/dungeons creature spawning is handled
;            differently. Searches for an empty slot ($4F00,X == 0),
;            then rolls creature type and position, placing it if the
;            terrain matches the creature's preferred type.
;
;   PARAMS:  $00/$01 = player X,Y position
;   RETURNS: May populate a creature slot in $4F00-$4F9F arrays
;
; XREF: 1 ref (1 call) from world_move_dungeon
dungeon_handle lda  $E2             ; Check location type
            beq  dungeon_check_light ; $E2=0 → Sosaria surface, proceed
            rts                  ; In town/dungeon → no overworld spawning
; XREF: 1 ref (1 branch) from dungeon_handle
dungeon_check_light lda  #$86            ; A=$0086 X=$00C0 Y=$0020 ; [SP-1474]
            jsr  $46E4           ; A=$0086 X=$00C0 Y=$0020 ; [SP-1476]
            bmi  dungeon_set_floor  ; A=$0086 X=$00C0 Y=$0020 ; [SP-1476]
            rts                  ; A=$0086 X=$00C0 Y=$0020 ; [SP-1474]
; XREF: 1 ref (1 branch) from dungeon_check_light
dungeon_set_floor lda  #$20            ; A=$0020 X=$00C0 Y=$0020 ; [SP-1474]
            sta  $D0             ; A=$0020 X=$00C0 Y=$0020 ; [SP-1474]

; === while loop starts here [nest:18] ===
; XREF: 2 refs (1 jump) (1 branch) from dungeon_init_vars, dungeon_load_counter
dungeon_dec_counter dec  $D0             ; A=$0020 X=$00C0 Y=$0020 ; [SP-1474]
            bpl  dungeon_load_counter  ; A=$0020 X=$00C0 Y=$0020 ; [SP-1474]
            rts                  ; A=$0020 X=$00C0 Y=$0020 ; [SP-1472]
; XREF: 1 ref (1 branch) from dungeon_dec_counter
dungeon_load_counter ldx  $D0             ; A=$0020 X=$00C0 Y=$0020 ; [SP-1472]
            lda  $4F00,X         ; -> $4FC0 ; A=$0020 X=$00C0 Y=$0020 ; [SP-1472]
            bne  dungeon_dec_counter  ; A=$0020 X=$00C0 Y=$0020 ; [SP-1472]
; === End of while loop ===

            lda  #$0D            ; A=$000D X=$00C0 Y=$0020 ; [SP-1472]
            jsr  $46E4           ; A=$000D X=$00C0 Y=$0020 ; [SP-1474]
            sta  $FB             ; A=$000D X=$00C0 Y=$0020 ; [SP-1474]
            lda  #$0D            ; A=$000D X=$00C0 Y=$0020 ; [SP-1474]
            jsr  $46E4           ; A=$000D X=$00C0 Y=$0020 ; [SP-1476]
            and  $FB             ; A=$000D X=$00C0 Y=$0020 ; [SP-1476]
            tay                  ; A=$000D X=$00C0 Y=$000D ; [SP-1476]
            lda  $7BAC,Y         ; -> $7BB9 ; A=$000D X=$00C0 Y=$000D ; [SP-1476]
            asl  a               ; A=$000D X=$00C0 Y=$000D ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1476]
            asl  a               ; A=$000D X=$00C0 Y=$000D ; [SP-1476]
            sta  $4F00,X         ; -> $4FC0 ; A=$000D X=$00C0 Y=$000D ; [SP-1476]
            lda  $7BB9,Y         ; -> $7BC6 ; A=$000D X=$00C0 Y=$000D ; [SP-1476]
            sta  $4F20,X         ; -> $4FE0 ; A=$000D X=$00C0 Y=$000D ; [SP-1476]
            lda  #$40            ; A=$0040 X=$00C0 Y=$000D ; [SP-1476]
            jsr  $46E4           ; A=$0040 X=$00C0 Y=$000D ; [SP-1478]
            cmp  $00             ; A=$0040 X=$00C0 Y=$000D ; [SP-1478]
            beq  dungeon_init_vars  ; A=$0040 X=$00C0 Y=$000D ; [SP-1478]
            sta  $02             ; A=$0040 X=$00C0 Y=$000D ; [SP-1478]
            lda  #$40            ; A=$0040 X=$00C0 Y=$000D ; [SP-1478]
            jsr  $46E4           ; A=$0040 X=$00C0 Y=$000D ; [SP-1480]
            cmp  $01             ; A=$0040 X=$00C0 Y=$000D ; [SP-1480]
            beq  dungeon_init_vars  ; A=$0040 X=$00C0 Y=$000D ; [SP-1480]
            sta  $03             ; A=$0040 X=$00C0 Y=$000D ; [SP-1480]
            jsr  $46FF           ; A=$0040 X=$00C0 Y=$000D ; [SP-1482]
            cmp  $4F20,X         ; -> $4FE0 ; A=$0040 X=$00C0 Y=$000D ; [SP-1482]
            bne  dungeon_init_vars  ; A=$0040 X=$00C0 Y=$000D ; [SP-1482]
            lda  $02             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1482]
            sta  $4F40,X         ; -> $5000 ; A=[$0002] X=$00C0 Y=$000D ; [SP-1482]
            lda  $03             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1482]
            sta  $4F60,X         ; -> $5020 ; A=[$0003] X=$00C0 Y=$000D ; [SP-1482]
            lda  #$C0            ; A=$00C0 X=$00C0 Y=$000D ; [SP-1482]
            sta  $4F80,X         ; -> $5040 ; A=$00C0 X=$00C0 Y=$000D ; [SP-1482]
            lda  $4F00,X         ; -> $4FC0 ; A=$00C0 X=$00C0 Y=$000D ; [SP-1482]
            sta  ($FE),Y         ; A=$00C0 X=$00C0 Y=$000D ; [SP-1482]
            rts                  ; A=$00C0 X=$00C0 Y=$000D ; [SP-1480]
; XREF: 3 refs (3 branches) from dungeon_load_counter, dungeon_load_counter, dungeon_load_counter
dungeon_init_vars lda  #$00            ; A=$0000 X=$00C0 Y=$000D ; [SP-1480]
            sta  $4F00,X         ; -> $4FC0 ; A=$0000 X=$00C0 Y=$000D ; [SP-1480]
            jmp  dungeon_dec_counter  ; A=$0000 X=$00C0 Y=$000D ; [SP-1480]
; === End of while loop ===


; ---------------------------------------------------------------------------
; tile_update — Move all overworld creatures one step (AI tick)
; ---------------------------------------------------------------------------
;
;   PURPOSE: Per-turn creature movement. Iterates all 32 creature slots
;            (index $20 down to $00). For each active creature, determines
;            its behavior type from $4F80 flags and applies movement:
;
;            Behavior types (upper 2 bits of $4F80,X):
;              $00 = dormant (no movement)
;              $40 = wandering (random direction)
;              $80 = tracking (pathfind toward player)
;              $C0 = aggressive (direct pursuit + combat on contact)
;
;            Movement algorithm:
;            1. Calculate direction toward player ($02/$03 = target X/Y)
;            2. Check if target tile is passable (tile_check_passable)
;            3. If blocked, try perpendicular directions
;            4. If destination == player position → trigger combat
;            5. Otherwise: save terrain under creature, move creature tile
;
;            The "save terrain under creature" mechanism ($4F20 array)
;            means creatures visually replace their underlying tile and
;            restore it when they move — a technique also used in the
;            combat maps (CON files) for monster/PC positions.
;
;   PARAMS:  $00/$01 = player X,Y
;   RETURNS: May trigger combat encounter (via char_combat_turn)
;
; XREF: 1 ref (1 call) from world_move_dungeon
tile_update lda  #$20            ; Start at creature slot 32 (count down)
            sta  $D0             ; $D0 = loop counter

; === while loop starts here [nest:18] ===
; XREF: 8 refs (7 jumps) (1 branch) from tile_update_dec_range, tile_update_restart, tile_update_load_pos2, tile_update_read_type, tile_update_load_counter, ...
tile_update_dec_counter dec  $D0             ; A=$0020 X=$00C0 Y=$000D ; [SP-1480]
            bpl  tile_update_load_counter  ; A=$0020 X=$00C0 Y=$000D ; [SP-1480]
            rts                  ; A=$0020 X=$00C0 Y=$000D ; [SP-1478]
; XREF: 1 ref (1 branch) from tile_update_dec_counter
tile_update_load_counter ldx  $D0             ; A=$0020 X=$00C0 Y=$000D ; [SP-1478]
            lda  $4F00,X         ; -> $4FC0 ; A=$0020 X=$00C0 Y=$000D ; [SP-1478]
            beq  tile_update_dec_counter  ; A=$0020 X=$00C0 Y=$000D ; [SP-1478]
; === End of while loop ===

            lda  $E2             ; A=[$00E2] X=$00C0 Y=$000D ; [SP-1478]
            beq  tile_update_check_special  ; A=[$00E2] X=$00C0 Y=$000D ; [SP-1478]
            jmp  tile_update_read_type ; A=[$00E2] X=$00C0 Y=$000D ; [SP-1478]

; === while loop starts here [nest:17] ===
; XREF: 2 refs (1 jump) (1 branch) from tile_update_load_counter, tile_update_check_type
tile_update_check_special jsr  tile_check_special     ; A=[$00E2] X=$00C0 Y=$000D ; [SP-1480]
            lda  $02             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1480]
            cmp  $00             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1480]
            bne  tile_update_char_ptr  ; A=[$0002] X=$00C0 Y=$000D ; [SP-1480]
            lda  $03             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1480]
            cmp  $01             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1480]
            bne  tile_update_char_ptr  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1480]
            jmp  input_combat_render_unit      ; A=[$0003] X=$00C0 Y=$000D ; [SP-1480]
; === End of while loop (counter: Y) ===


; === while loop starts here [nest:16] ===
; XREF: 4 refs (2 jumps) (2 branches) from tile_update_check_special, tile_update_wait_anim3, tile_update_find_target, tile_update_check_special
tile_update_char_ptr jsr  $46FF           ; A=[$0003] X=$00C0 Y=$000D ; [SP-1482]
            jsr  tile_check_passable     ; A=[$0003] X=$00C0 Y=$000D ; [SP-1484]
            beq  tile_update_load_pos  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1484]
            lda  $4F40,X         ; -> $5000 ; A=[$0003] X=$00C0 Y=$000D ; [SP-1484]
            sta  $02             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1484]
            jsr  $46FF           ; A=[$0003] X=$00C0 Y=$000D ; [SP-1486]
            jsr  tile_check_passable     ; A=[$0003] X=$00C0 Y=$000D ; [SP-1488]
            beq  tile_update_load_pos  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1488]
            lda  $4F40,X         ; -> $5000 ; A=[$0003] X=$00C0 Y=$000D ; [SP-1488]
            clc                  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1488]
            adc  $04             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1488]
            and  #$3F            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1488]
            sta  $02             ; A=A&$3F X=$00C0 Y=$000D ; [SP-1488]
            lda  $4F60,X         ; -> $5020 ; A=A&$3F X=$00C0 Y=$000D ; [SP-1488]
            sta  $03             ; A=A&$3F X=$00C0 Y=$000D ; [SP-1488]
            jsr  $46FF           ; A=A&$3F X=$00C0 Y=$000D ; [SP-1490]
            jsr  tile_check_passable     ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
            beq  tile_update_load_pos  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
            lda  $4F00,X         ; -> $4FC0 ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
            cmp  #$3C            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
            beq  tile_update_jump_display  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
            cmp  #$74            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
            beq  tile_update_jump_display  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
            jmp  tile_update_dec_counter  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
; XREF: 2 refs (2 branches) from tile_update_char_ptr, tile_update_char_ptr
tile_update_jump_display jmp  tile_update_wait_anim  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1492]
; XREF: 3 refs (3 branches) from tile_update_char_ptr, tile_update_char_ptr, tile_update_char_ptr
tile_update_load_pos lda  $02             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1492]
            cmp  $00             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1492]
            bne  tile_update_load_pos2  ; A=[$0002] X=$00C0 Y=$000D ; [SP-1492]
            lda  $03             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            cmp  $01             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            bne  tile_update_load_pos2  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            jmp  tile_update_dec_counter  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
; XREF: 2 refs (2 branches) from tile_update_load_pos, tile_update_load_pos
tile_update_load_pos2 lda  $02             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1492]
            sta  $F1             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1492]
            lda  $03             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            sta  $F2             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            lda  $4F40,X         ; -> $5000 ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            sta  $02             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            lda  $4F60,X         ; -> $5020 ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            sta  $03             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1492]
            jsr  $46FF           ; A=[$0003] X=$00C0 Y=$000D ; [SP-1494]
            lda  $4F20,X         ; -> $4FE0 ; A=[$0003] X=$00C0 Y=$000D ; [SP-1494]
            sta  ($FE),Y         ; A=[$0003] X=$00C0 Y=$000D ; [SP-1494]
            lda  $F1             ; A=[$00F1] X=$00C0 Y=$000D ; [SP-1494]
            sta  $02             ; A=[$00F1] X=$00C0 Y=$000D ; [SP-1494]
            sta  $4F40,X         ; -> $5000 ; A=[$00F1] X=$00C0 Y=$000D ; [SP-1494]
            lda  $F2             ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1494]
            sta  $03             ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1494]
            sta  $4F60,X         ; -> $5020 ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1494]
            jsr  $46FF           ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            lda  ($FE),Y         ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            sta  $4F20,X         ; -> $4FE0 ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            lda  $4F00,X         ; -> $4FC0 ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            sta  ($FE),Y         ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            cmp  #$3C            ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            beq  tile_update_wait_anim  ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            cmp  #$74            ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            beq  tile_update_wait_anim  ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
            jmp  tile_update_dec_counter  ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1496]
; XREF: 3 refs (1 jump) (2 branches) from tile_update_load_pos2, tile_update_load_pos2, tile_update_jump_display
tile_update_wait_anim jsr  $46E7           ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1498]
            bmi  tile_update_restart ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1498]
            jsr  tile_check_special     ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1500]
            sec                  ; A=[$00F2] X=$00C0 Y=$000D ; [SP-1500]
            lda  #$05            ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            sbc  $F5             ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            sta  $02             ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            cmp  #$0B            ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            bcs  tile_update_restart ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            sec                  ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            lda  #$05            ; A=$0005 X=$00C0 Y=$000D ; [OPT] REDUNDANT_LOAD: Redundant LDA: same value loaded at $007B3F ; [SP-1500]
            sbc  $F6             ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            sta  $03             ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            cmp  #$0B            ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            bcs  tile_update_restart ; A=$0005 X=$00C0 Y=$000D ; [SP-1500]
            jsr  $0230           ; A=$0005 X=$00C0 Y=$000D ; [SP-1502]
            lda  #$FB            ; A=$00FB X=$00C0 Y=$000D ; [SP-1502]
            jsr  $4705           ; A=$00FB X=$00C0 Y=$000D ; [SP-1504]
            lda  #$03            ; A=$0003 X=$00C0 Y=$000D ; [SP-1504]
            sta  $FB             ; A=$0003 X=$00C0 Y=$000D ; [SP-1504]

; === while loop starts here [nest:22] ===
; XREF: 1 ref (1 branch) from tile_update_dec_range
tile_update_bcd_food clc                  ; A=$0003 X=$00C0 Y=$000D ; [SP-1504]
            lda  $02             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1504]
            adc  $04             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1504]
            sta  $02             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1504]
            cmp  #$0B            ; A=[$0002] X=$00C0 Y=$000D ; [SP-1504]
            bcs  tile_update_restart ; A=[$0002] X=$00C0 Y=$000D ; [SP-1504]
            clc                  ; A=[$0002] X=$00C0 Y=$000D ; [SP-1504]
            lda  $03             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1504]
            adc  $05             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1504]
            sta  $03             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1504]
            cmp  #$0B            ; A=[$0003] X=$00C0 Y=$000D ; [SP-1504]
            bcs  tile_update_restart ; A=[$0003] X=$00C0 Y=$000D ; [SP-1504]
            jsr  combat_tile_at_xy      ; A=[$0003] X=$00C0 Y=$000D ; [SP-1506]
            cmp  #$08            ; A=[$0003] X=$00C0 Y=$000D ; [SP-1506]
            beq  tile_update_restart ; A=[$0003] X=$00C0 Y=$000D ; [SP-1506]
            cmp  #$46            ; A=[$0003] X=$00C0 Y=$000D ; [SP-1506]
            beq  tile_update_restart ; A=[$0003] X=$00C0 Y=$000D ; [SP-1506]
            cmp  #$48            ; A=[$0003] X=$00C0 Y=$000D ; [SP-1506]
            beq  tile_update_restart ; A=[$0003] X=$00C0 Y=$000D ; [SP-1506]
            pha                  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1507]
            lda  #$7A            ; A=$007A X=$00C0 Y=$000D ; [SP-1507]
            sta  ($FE),Y         ; A=$007A X=$00C0 Y=$000D ; [SP-1507]
            jsr  $0328           ; A=$007A X=$00C0 Y=$000D ; [SP-1509]
            jsr  combat_tile_at_xy      ; A=$007A X=$00C0 Y=$000D ; [SP-1511]
            pla                  ; A=[stk] X=$00C0 Y=$000D ; [SP-1510]
            sta  ($FE),Y         ; A=[stk] X=$00C0 Y=$000D ; [SP-1510]
            lda  $02             ; A=[$0002] X=$00C0 Y=$000D ; [SP-1510]
            cmp  #$05            ; A=[$0002] X=$00C0 Y=$000D ; [SP-1510]
            bne  tile_update_dec_range ; A=[$0002] X=$00C0 Y=$000D ; [SP-1510]
            lda  $03             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1510]
            cmp  #$05            ; A=[$0003] X=$00C0 Y=$000D ; [SP-1510]
            bne  tile_update_dec_range ; A=[$0003] X=$00C0 Y=$000D ; [SP-1510]
            jsr  char_combat_turn       ; A=[$0003] X=$00C0 Y=$000D ; [SP-1512]
; XREF: 8 refs (8 branches) from tile_update_wait_anim, tile_update_wait_anim, tile_update_wait_anim, tile_update_bcd_food, tile_update_bcd_food, ...
tile_update_restart jmp  tile_update_dec_counter  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1512]
; XREF: 2 refs (2 branches) from tile_update_bcd_food, tile_update_bcd_food
tile_update_dec_range dec  $FB             ; A=[$0003] X=$00C0 Y=$000D ; [SP-1512]
            bne  tile_update_bcd_food  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1512]
            jmp  tile_update_dec_counter  ; A=[$0003] X=$00C0 Y=$000D ; [SP-1512]

; ---
            DB      $18,$17,$19,$14,$1A,$1B,$0D,$1C,$16,$0E,$0F,$1D,$1E,$04,$04,$04
            DB      $04,$04,$04,$00,$04,$04,$00,$00,$04,$04
; ---

; XREF: 1 ref (1 jump) from tile_update_load_counter
tile_update_read_type lda  $4F80,X         ; -> $5040 ; A=[$0003] X=$00C0 Y=$000D ; [SP-1518]
            and  #$C0            ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1518]
            bne  tile_update_check_type ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1518]
            jmp  tile_update_dec_counter  ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1518]
; XREF: 1 ref (1 branch) from tile_update_read_type
tile_update_check_type cmp  #$40            ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1518]
            beq  tile_update_wait_anim2 ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1518]
            cmp  #$80            ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1518]
            beq  tile_update_find_target ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1518]
            jmp  tile_update_check_special  ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1518]
; XREF: 1 ref (1 branch) from tile_update_check_type
tile_update_wait_anim2 jsr  $46E7           ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1520]
            bmi  tile_update_wait_anim3 ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1520]

; === while loop starts here [nest:18] ===
; XREF: 2 refs (2 branches) from tile_update_wait_anim3, tile_update_wait_anim3
tile_update_restart2 jmp  tile_update_dec_counter  ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1520]
; XREF: 1 ref (1 branch) from tile_update_wait_anim2
tile_update_wait_anim3 jsr  $46E7           ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1522]
            jsr  render_sign_extend       ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1524]
            clc                  ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1524]
            adc  $4F40,X         ; -> $5000 ; A=A&$C0 X=$00C0 Y=$000D ; [SP-1524]
            and  #$3F            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1524]
            sta  $02             ; A=A&$3F X=$00C0 Y=$000D ; [SP-1524]
            beq  tile_update_restart2 ; A=A&$3F X=$00C0 Y=$000D ; [SP-1524]
            jsr  $46E7           ; A=A&$3F X=$00C0 Y=$000D ; [SP-1526]
            jsr  render_sign_extend       ; A=A&$3F X=$00C0 Y=$000D ; [SP-1528]
            clc                  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1528]
            adc  $4F60,X         ; -> $5020 ; A=A&$3F X=$00C0 Y=$000D ; [SP-1528]
            and  #$3F            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1528]
            sta  $03             ; A=A&$3F X=$00C0 Y=$000D ; [SP-1528]
            beq  tile_update_restart2 ; A=A&$3F X=$00C0 Y=$000D ; [SP-1528]
            jmp  tile_update_char_ptr  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1528]
; XREF: 1 ref (1 branch) from tile_update_check_type
tile_update_find_target jsr  tile_check_special     ; A=A&$3F X=$00C0 Y=$000D ; [SP-1530]
            jmp  tile_update_char_ptr  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1530]

; ###########################################################################
; ###                                                                     ###
; ###              TILE & MAP LOGIC ($7C0C-$7DFF)                         ###
; ###                                                                     ###
; ###########################################################################
;
;   Tile passability and special tile handling. The game world is built
;   from tile types, each with properties: passable/impassable, terrain
;   type (water, forest, mountain), special behavior (towns, dungeons,
;   shrines), and transport requirements (ship for water, etc.).
;

; ---------------------------------------------------------------------------
; tile_check_passable — Determine if a creature can move onto a tile
; ---------------------------------------------------------------------------
;
;   PURPOSE: Checks whether the creature at index X in the combat/world
;            tracking arrays can move onto the tile type in A. Returns
;            A=0 if passable, A=$FF if blocked.
;
;   TILE PASSABILITY RULES:
;   - Creature type $2C-$3F (special range): only passable if tile = $00
;   - Tile $04 (grass), $08 (forest), $0C (open), $20 (floor): always passable
;   - All other tiles: impassable (walls, mountains, deep water, etc.)
;
;   PARAMS:  A = tile type to check
;            X = creature index in $4F00 tracking array
;   RETURNS: A = 0 (passable) or $FF (blocked)
;
; ---------------------------------------------------------------------------
tile_check_passable pha                  ; Save tile type
            lda  $4F00,X         ; Load creature's type/flags
            cmp  #$40            ; Type >= $40?
            bcs  tile_passable_check_type ; Yes → check tile normally
            cmp  #$2C            ; Type in $2C-$3F range?
            bcc  tile_passable_check_type ; No → check tile normally
; --- Special creature type ($2C-$3F): only passable on empty tiles ---
            pla                  ; Restore tile type
            cmp  #$00            ; Is it empty?
            bne  tile_not_passable ; No → blocked
            jmp  tile_is_passable ; Yes → passable
; --- Normal passability: check against allowed tile types ---
tile_passable_check_type pla                  ; Restore tile type
            cmp  #$04            ; Grass?
            beq  tile_is_passable
            cmp  #$08            ; Forest?
            beq  tile_is_passable
            cmp  #$0C            ; Open terrain?
            beq  tile_is_passable
            cmp  #$20            ; Floor?
            beq  tile_is_passable
tile_not_passable lda  #$FF            ; Blocked
            rts
tile_is_passable lda  #$00            ; Passable
            rts

; ---------------------------------------------------------------------------
; tile_check_special  [3 calls]
;   Called by: tile_update_find_target, tile_update_check_special, tile_update_wait_anim
;   Calls: render_sign_extend, render_tile_scale, render_abs_value
; ---------------------------------------------------------------------------

; FUNC $007C37: register -> A:X [I]
; Proto: uint32_t func_007C37(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [10 dead stores]
; XREF: 3 refs (3 calls) from tile_update_find_target, tile_update_check_special, tile_update_wait_anim
tile_check_special lda  $E2             ; A=[$00E2] X=$00C0 Y=$000D ; [SP-1525]
            beq  tile_special_surface  ; A=[$00E2] X=$00C0 Y=$000D ; [SP-1525]
            sec                  ; A=[$00E2] X=$00C0 Y=$000D ; [SP-1525]
            lda  $00             ; A=[$0000] X=$00C0 Y=$000D ; [SP-1525]
            sbc  $4F40,X         ; -> $5000 ; A=[$0000] X=$00C0 Y=$000D ; [SP-1525]
            sta  $F5             ; A=[$0000] X=$00C0 Y=$000D ; [SP-1525]
            jsr  render_sign_extend       ; A=[$0000] X=$00C0 Y=$000D ; [SP-1527]
            sta  $04             ; A=[$0000] X=$00C0 Y=$000D ; [SP-1527]
            clc                  ; A=[$0000] X=$00C0 Y=$000D ; [SP-1527]
            adc  $4F40,X         ; -> $5000 ; A=[$0000] X=$00C0 Y=$000D ; [SP-1527]
            and  #$3F            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1527]
            sta  $02             ; A=A&$3F X=$00C0 Y=$000D ; [SP-1527]
            sec                  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1527]
            lda  $01             ; A=[$0001] X=$00C0 Y=$000D ; [SP-1527]
            sbc  $4F60,X         ; -> $5020 ; A=[$0001] X=$00C0 Y=$000D ; [SP-1527]
            sta  $F6             ; A=[$0001] X=$00C0 Y=$000D ; [SP-1527]
            jsr  render_sign_extend       ; A=[$0001] X=$00C0 Y=$000D ; [SP-1529]
            sta  $05             ; A=[$0001] X=$00C0 Y=$000D ; [SP-1529]
            clc                  ; A=[$0001] X=$00C0 Y=$000D ; [SP-1529]
            adc  $4F60,X         ; -> $5020 ; A=[$0001] X=$00C0 Y=$000D ; [SP-1529]
            and  #$3F            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1529]
            sta  $03             ; A=A&$3F X=$00C0 Y=$000D ; [SP-1529]
            jmp  tile_special_calc_dist  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1529]
; XREF: 1 ref (1 branch) from tile_check_special
tile_special_surface sec                  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1529]
            lda  $00             ; A=[$0000] X=$00C0 Y=$000D ; [SP-1529]
            sbc  $4F40,X         ; -> $5000 ; A=[$0000] X=$00C0 Y=$000D ; [SP-1529]
            sta  $F5             ; A=[$0000] X=$00C0 Y=$000D ; [SP-1529]
            jsr  render_tile_scale      ; A=[$0000] X=$00C0 Y=$000D ; [SP-1531]
            sta  $04             ; A=[$0000] X=$00C0 Y=$000D ; [SP-1531]
            clc                  ; A=[$0000] X=$00C0 Y=$000D ; [SP-1531]
            adc  $4F40,X         ; -> $5000 ; A=[$0000] X=$00C0 Y=$000D ; [SP-1531]
            and  #$3F            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            sta  $02             ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            sec                  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            lda  $01             ; A=[$0001] X=$00C0 Y=$000D ; [SP-1531]
            sbc  $4F60,X         ; -> $5020 ; A=[$0001] X=$00C0 Y=$000D ; [SP-1531]
            sta  $F6             ; A=[$0001] X=$00C0 Y=$000D ; [SP-1531]
            jsr  render_tile_scale      ; A=[$0001] X=$00C0 Y=$000D ; [SP-1533]
            sta  $05             ; A=[$0001] X=$00C0 Y=$000D ; [SP-1533]
            clc                  ; A=[$0001] X=$00C0 Y=$000D ; [SP-1533]
            adc  $4F60,X         ; -> $5020 ; A=[$0001] X=$00C0 Y=$000D ; [SP-1533]
            and  #$3F            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1533]
            sta  $03             ; A=A&$3F X=$00C0 Y=$000D ; [SP-1533]
; XREF: 1 ref (1 jump) from tile_check_special
tile_special_calc_dist lda  $F5             ; A=[$00F5] X=$00C0 Y=$000D ; [SP-1533]
            jsr  render_abs_value        ; A=[$00F5] X=$00C0 Y=$000D ; [SP-1535]
            sta  $FB             ; A=[$00F5] X=$00C0 Y=$000D ; [SP-1535]
            lda  $F6             ; A=[$00F6] X=$00C0 Y=$000D ; [SP-1535]
            jsr  render_abs_value        ; A=[$00F6] X=$00C0 Y=$000D ; [SP-1537]
            clc                  ; A=[$00F6] X=$00C0 Y=$000D ; [SP-1537]
            adc  $FB             ; A=[$00F6] X=$00C0 Y=$000D ; [SP-1537]
            sta  $FB             ; A=[$00F6] X=$00C0 Y=$000D ; [SP-1537]
            rts                  ; A=[$00F6] X=$00C0 Y=$000D ; [SP-1535]
            DB      $A9,$20,$85,$D0

; === while loop starts here [nest:16] ===
; XREF: 3 refs (3 branches) from tile_special_check_pos, tile_special_check_pos, tile_special_check_pos
tile_special_find_loop dec  $D0             ; A=[$00F6] X=$00C0 Y=$000D ; [SP-1535]
            bpl  tile_special_check_pos  ; A=[$00F6] X=$00C0 Y=$000D ; [SP-1535]
            lda  #$FF            ; A=$00FF X=$00C0 Y=$000D ; [SP-1535]
            rts                  ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
; XREF: 1 ref (1 branch) from tile_special_find_loop
tile_special_check_pos ldx  $D0             ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
            lda  $4F00,X         ; -> $4FC0 ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
            beq  tile_special_find_loop  ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
; === End of while loop ===

            lda  $4F40,X         ; -> $5000 ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
            cmp  $02             ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
            bne  tile_special_find_loop  ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
; === End of while loop ===

            lda  $4F60,X         ; -> $5020 ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
            cmp  $03             ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
            bne  tile_special_find_loop  ; A=$00FF X=$00C0 Y=$000D ; [SP-1533]
            txa                  ; A=$00C0 X=$00C0 Y=$000D ; [SP-1533]
            rts                  ; A=$00C0 X=$00C0 Y=$000D ; [SP-1531]

; ---------------------------------------------------------------------------
; tile_read_map  [1 call]
;   Called by: render_return_to_game
; ---------------------------------------------------------------------------

; FUNC $007CC6: register -> A:X []
; Liveness: returns(A,X,Y) [7 dead stores]
; XREF: 1 ref (1 call) from render_return_to_game
tile_read_map  ldy  #$00            ; A=$00C0 X=$00C0 Y=$0000 ; [SP-1531]
            ldx  #$08            ; A=$00C0 X=$0008 Y=$0000 ; [SP-1531]
            lda  $13             ; A=[$0013] X=$0008 Y=$0000 ; [SP-1531]
            clc                  ; A=[$0013] X=$0008 Y=$0000 ; [SP-1531]
            adc  #$B1            ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1531]
            sta  $7CDB           ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1531] ; WARNING: Self-modifying code -> $7CDB
            jsr  $46F3           ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1533]
            ora  $D6CC,X         ; -> $D6D4 ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1533]
            cpy  $B0BA           ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1533]
; *** MODIFIED AT RUNTIME by $7CCF ***
            bcs  tile_lookup_data     ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1533]
            brk  #$A0            ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1536]

; ---
            DB      $17,$A2,$06,$20,$F3,$46,$1D,$C8,$C5,$C1,$C4,$AD,$00,$A5,$14,$F0
            DB      $13,$C9,$01,$F0,$1A,$C9,$02,$F0,$21,$20,$BA,$46,$AD
tile_lookup_data
            DB      $D7
; ---

            cmp  $D3             ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1538]
            DB      $D4,$1F,$00,$60
render_print_dir_north  jsr  $46BA           ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1538]
            dec  $D2CF           ; A=A+$B1 X=$0008 Y=$0000 ; [SP-1538]
            DB      $D4
            iny                  ; A=A+$B1 X=$0008 Y=$0001 ; [SP-1538]
            DB      $1F,$00,$60
render_print_dir_east  jsr  $46BA           ; A=A+$B1 X=$0008 Y=$0001 ; [SP-1538]
            lda  $C1C5           ; S1_xC5 - Slot 1 ROM offset $C5 {Slot}

; ---
            DB      $D3
            DB      $D4
            DB      $1F,$00,$60
; ---

; XREF: 1 ref (1 branch) from tile_read_map
render_print_dir_south  jsr  $46BA           ; A=[$C1C5] X=$0008 Y=$0001 ; [SP-1538]

; ---
            ASC     "SOUTH"
            DB      $1F,$00,$60
; ---


; ---------------------------------------------------------------------------
; render_combat_map  [2 calls]
;   Called by: render_combat_check_mon
; ---------------------------------------------------------------------------
; Loop counter: X=#$08
; XREF: 2 refs (2 calls) from render_combat_check_mon, $0083EE
render_combat_map ldx  #$08            ; A=[$C1C5] X=$0008 Y=$0001 ; [SP-1538]

; === while loop starts here [nest:17] ===
; XREF: 3 refs (3 branches) from render_combat_check_mon, render_combat_check_mon, render_combat_check_mon
render_combat_next_mon dex                  ; A=[$C1C5] X=$0007 Y=$0001 ; [SP-1539]
            bpl  render_combat_check_mon  ; A=[$C1C5] X=$0007 Y=$0001 ; [SP-1539]
            lda  #$FF            ; A=$00FF X=$0007 Y=$0001 ; [SP-1539]
            rts                  ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
; XREF: 1 ref (1 branch) from render_combat_next_mon
render_combat_check_mon lda  $9998,X         ; -> $999F ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
            beq  render_combat_next_mon  ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
; === End of while loop ===

            lda  $9980,X         ; -> $9987 ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
            cmp  $02             ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
            bne  render_combat_next_mon  ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
; === End of while loop ===

            lda  $9988,X         ; -> $998F ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
            cmp  $03             ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
            bne  render_combat_next_mon  ; A=$00FF X=$0007 Y=$0001 ; [SP-1537]
            txa                  ; A=$0007 X=$0007 Y=$0001 ; [SP-1537]
            rts                  ; A=$0007 X=$0007 Y=$0001 ; [SP-1535]

; --- Data region (44 bytes) ---
            DB      $18,$A5,$02,$65,$04,$85,$02,$C9,$0B,$B0,$21,$18,$A5,$03,$65,$05
            DB      $85,$03,$C9,$0B,$B0,$16,$20,$18,$7E,$48,$A5,$1F,$91,$FE,$20,$28
            DB      $03,$A0,$00,$68,$91,$FE,$20,$24,$7D,$30,$D5,$60
; --- End data region (44 bytes) ---

; XREF: 2 refs (2 branches) from render_combat_check_mon, render_combat_check_mon
render_combat_wait_key jsr  $0328           ; A=$0007 X=$0007 Y=$0001 ; [SP-1541]
            lda  #$FF            ; A=$00FF X=$0007 Y=$0001 ; [SP-1541]
            rts                  ; A=$00FF X=$0007 Y=$0001 ; [SP-1539]

; --- Data region (137 bytes) ---
            DB      $A9,$B7,$A2,$31,$A0,$1B,$20,$A3,$03,$C9,$32,$D0,$FC,$20,$46,$74
            DB      $C9,$8D,$F0,$17,$C9,$8B,$F0,$13,$C9,$AF,$F0,$24,$C9,$8A,$F0,$20
            DB      $C9,$88,$F0,$31,$C9,$95,$F0,$41,$4C,$73,$7D,$20,$BA,$46,$CE,$EF
            DB      $F2,$F4,$E8,$FF,$00,$A9,$00,$85,$04,$A9,$FF,$85,$05,$4C,$ED,$7D
            DB      $20,$BA,$46,$D3,$EF,$F5,$F4,$E8,$FF,$00,$A9,$00,$85,$04,$A9,$01
            DB      $85,$05,$4C,$ED,$7D,$20,$BA,$46,$D7,$E5,$F3,$F4,$FF,$00,$A9,$FF
            DB      $85,$04,$A9,$00,$85,$05,$4C,$ED,$7D,$20,$BA,$46,$C5,$E1,$F3,$F4
            DB      $FF,$00,$A9,$01,$85,$04,$A9,$00,$85,$05,$18,$A5,$00,$65,$04,$85
            DB      $02,$18,$A5,$01,$65,$05,$85,$03,$60
; --- End data region (137 bytes) ---


; ###########################################################################
; ###                                                                     ###
; ###          MATH UTILITIES ($7DFC-$7E84)                               ###
; ###                                                                     ###
; ###########################################################################
;
;   Small utility functions for signed arithmetic, distance calculation,
;   and coordinate math. The 6502 has no native signed operations, so
;   sign extension, absolute value, and comparison must be synthesized
;   from unsigned instructions — a common pattern in 80s game engines.
;

; ---------------------------------------------------------------------------
; render_sign_extend — Clamp a signed value to {-1, 0, +1}
; ---------------------------------------------------------------------------
;
;   PURPOSE: Converts a signed difference into a direction step.
;            Used by creature AI to determine which direction to move
;            toward or away from the player. The result is:
;              A > 0 (positive) → return +1
;              A = 0            → return 0
;              A < 0 (bit 7 set) → return $FF (-1)
;
;   PARAMS:  A = signed 8-bit value
;   RETURNS: A = direction step (-1, 0, or +1)
;
; XREF: 7 refs (6 calls) (1 jump)
render_sign_extend   cmp  #$00            ; Test value
            beq  render_sign_done   ; Zero → return 0
            bmi  render_sign_negative ; Negative (bit 7) → return -1
            lda  #$01            ; Positive → return +1
render_sign_done rts
render_sign_negative lda  #$FF            ; Negative → return -1 (two's complement)
            rts

; ---------------------------------------------------------------------------
; render_tile_scale — Scale a difference by 4x and clamp to direction
; ---------------------------------------------------------------------------
;
;   PURPOSE: Multiplies A by 4 (two ASL shifts) then clamps to {-1,0,+1}.
;            Used for surface-map creature movement where distances are
;            scaled by the viewport tile size before extracting direction.
;
; XREF: 2 refs (2 calls) from tile_special_surface
render_tile_scale  asl  a               ; A *= 2
            asl  a               ; A *= 2 (total: A *= 4)
            jmp  render_sign_extend ; Clamp to direction step


; ---------------------------------------------------------------------------
; render_abs_value — Absolute value of a signed 8-bit number
; ---------------------------------------------------------------------------
;
;   PURPOSE: Returns |A| using two's complement negation. If bit 7 is set
;            (negative), negate via EOR #$FF + 1 (standard 6502 idiom for
;            negation since the 6502 has no NEG instruction). Used for
;            Manhattan distance calculation in targeting/pathfinding.
;
;   PARAMS:  A = signed 8-bit value
;   RETURNS: A = |A| (unsigned)
;
; XREF: 4 refs (4 calls) from render_target_check_alive, tile_special_calc_dist
render_abs_value    cmp  #$80            ; Negative? (bit 7 set means $80-$FF)
            bcs  render_negate    ; Yes → negate it
            rts                  ; Already positive, return as-is
render_negate eor  #$FF            ; Two's complement negation: ~A
            clc
            adc  #$01            ; ~A + 1 = -A (as unsigned magnitude)
            rts

; ---------------------------------------------------------------------------
; combat_tile_at_xy — Read a tile from the 11x11 combat grid
; ---------------------------------------------------------------------------
;
;   PURPOSE: Computes the byte address within the CON file's 11x11 tile
;            grid and returns the tile value. The grid starts at $9900
;            (CON file load address). Uses the formula:
;              offset = Y*11 + X  =  Y*8 + Y + Y + Y + X
;            The Y*11 is computed without multiplication hardware:
;              Y << 3 = Y*8, then add Y three more times = Y*11.
;
;   WHY $9900: CON files are BLOADed at $9900. The 11x11 grid occupies
;   bytes $9900-$9978 (121 bytes). The remaining bytes in the 192-byte
;   CON file hold monster/PC positions and runtime workspace.
;
;   PARAMS:  $02 = X coordinate (0-10)
;            $03 = Y coordinate (0-10)
;   RETURNS: A = tile value at (X,Y)
;            $FE/$FF = pointer to the tile (for in-place modification)
;   CALLERS: 25 references — combat, creature movement, rendering
;
; XREF: 25 refs (16 calls)
combat_tile_at_xy  clc                  ; Clear carry for addition chain
            lda  $03             ; A = Y coordinate
            asl  a               ; Y*2
            asl  a               ; Y*4
            asl  a               ; Y*8
            adc  $03             ; Y*9
            adc  $03             ; Y*10
            adc  $03             ; Y*11
            adc  $02             ; Y*11 + X = linear offset
            sta  $FE             ; Low byte of pointer
            lda  #$99            ; High byte = $99 (CON grid at $9900)
            sta  $FF
            ldy  #$00
            lda  ($FE),Y         ; Load tile value
            rts

; ---------------------------------------------------------------------------
; render_check_solid  [3 calls]
;   Called by: render_target_calc_dist
;   Preserves: A
; ---------------------------------------------------------------------------

; FUNC $007E31: register -> A:X []
; Proto: uint32_t func_007E31(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Frame: push_only, 2 bytes params [saves: A]
; Liveness: params(A,X,Y) returns(A,X,Y) [3 dead stores]
; XREF: 3 refs (3 calls) from render_target_calc_dist, render_target_calc_dist, render_target_calc_dist
render_check_solid pha                  ; A=$0099 X=$0007 Y=$0000 ; [SP-1546]
            lda  $CE             ; A=[$00CE] X=$0007 Y=$0000 ; [SP-1546]
            cmp  #$20            ; A=[$00CE] X=$0007 Y=$0000 ; [SP-1546]
            bcs  render_solid_check_type ; A=[$00CE] X=$0007 Y=$0000 ; [SP-1546]
            cmp  #$16            ; A=[$00CE] X=$0007 Y=$0000 ; [SP-1546]
            bcc  render_solid_check_type ; A=[$00CE] X=$0007 Y=$0000 ; [SP-1546]
            pla                  ; A=[stk] X=$0007 Y=$0000 ; [SP-1545]
            cmp  #$00            ; A=[stk] X=$0007 Y=$0000 ; [SP-1545]
            bne  render_is_solid ; A=[stk] X=$0007 Y=$0000 ; [SP-1545]
            jmp  render_not_solid ; A=[stk] X=$0007 Y=$0000 ; [SP-1545]
; XREF: 2 refs (2 branches) from render_check_solid, render_check_solid
render_solid_check_type pla                  ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
            cmp  #$02            ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
            beq  render_not_solid ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
            cmp  #$04            ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
            beq  render_not_solid ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
            cmp  #$06            ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
            beq  render_not_solid ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
            cmp  #$10            ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
            beq  render_not_solid ; A=[stk] X=$0007 Y=$0000 ; [SP-1544]
; XREF: 1 ref (1 branch) from render_check_solid
render_is_solid lda  #$FF            ; A=$00FF X=$0007 Y=$0000 ; [SP-1544]
            rts                  ; A=$00FF X=$0007 Y=$0000 ; [SP-1542]
; XREF: 5 refs (1 jump) (4 branches) from render_solid_check_type, render_solid_check_type, render_solid_check_type, render_solid_check_type, render_check_solid
render_not_solid lda  #$00            ; A=$0000 X=$0007 Y=$0000 ; [SP-1542]
            rts                  ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]

; ---------------------------------------------------------------------------
; render_viewport_flash — Screen flash effect for magical/special events
; ---------------------------------------------------------------------------
;
;   PURPOSE: Produces a visual flash by toggling HGR page display twice
;            with a timed delay between. The Apple II's soft switches at
;            $C050-$C057 control which HGR page is visible; JSR $4705
;            with A=$F6 toggles the page. The double toggle creates a
;            "flash" effect visible for ~8000 cycles (X*Y delay loop =
;            255*32 = 8160 iterations of DEX/BNE = ~40,800 cycles ≈ 40ms).
;
;   TILE CHECK: Only fires on certain tile types ($02=water, $04=grass,
;   $06=brush, $10=floor) — other tiles block the flash. Returns $FF
;   if blocked, $00 if flash fired.
;
; XREF: 1 ref (1 call) from $0082B2
render_viewport_flash cmp  #$02            ; Water tile?
            beq  render_flash_activate
            cmp  #$04            ; Grass?
            beq  render_flash_activate
            cmp  #$06            ; Brush?
            beq  render_flash_activate
            cmp  #$10            ; Floor?
            beq  render_flash_activate
            lda  #$FF            ; Blocked — no flash
            rts
render_flash_activate lda  #$F6            ; Toggle HGR page (flash ON)
            jsr  $4705
            ldx  #$FF            ; Delay: X=255, Y=32
            ldy  #$20

; --- Nested delay loop: ~40,800 cycles ≈ 40ms visible flash ---
render_flash_delay_loop dex
            bne  render_flash_delay_loop

            dey
            bne  render_flash_delay_loop

            lda  #$F6            ; Toggle HGR page back (flash OFF)
            jsr  $4705
            lda  #$00            ; Success — flash occurred
            rts

; ###########################################################################
; ###                                                                     ###
; ###          COMBAT AI & RENDERING ($7E85-$88FF)                        ###
; ###                                                                     ###
; ###########################################################################
;
;   The combat rendering system and monster AI. Ultima III's tactical
;   combat screen was unprecedented for 1983 — an 11x11 grid where
;   monsters and party members move independently, with ranged attacks,
;   spell areas of effect, and terrain obstacles. This was years ahead
;   of most CRPGs, which used abstract "lines" of combatants.
;
;   MONSTER TARGETING: render_find_target implements nearest-enemy
;   selection using Manhattan distance (|dx| + |dy|), checking
;   line-of-sight through solid tiles. Monsters target the closest
;   alive party member they can reach.
;
;   COMBAT RESOLUTION: The combat loop alternates between player turns
;   (render_party_status_disp) and monster turns (render_combat_monster_ai),
;   with the "VICTORY!" screen triggered when all monster slots are empty.
;

; ---------------------------------------------------------------------------
; render_find_target — Select nearest alive party member for monster AI
; ---------------------------------------------------------------------------
;
;   PURPOSE: Scans all party members, computes Manhattan distance from
;            the current monster, and selects the closest alive target.
;            Used by monster AI to decide which PC to attack or pursue.
;
;   ALGORITHM:
;   - $D0 = best distance so far (starts at $FF = max)
;   - $D5 = party member index being checked (0 to party_size-1)
;   - $D6 = index of best target found (starts at $FF = none)
;   - For each alive member: compute |monster_x - pc_x| + |monster_y - pc_y|
;   - If distance < best_distance: update best target
;
;   PARAMS:  Monster position in $4F40,X / $4F60,X
;   RETURNS: $D6 = target slot index, $D0 = distance ($FF if no target)
;
; XREF: 1 ref (1 call) from render_combat_mon_check
render_find_target lda  #$FF            ; Initialize: no target found
            sta  $D6             ; Best target index = $FF (none)
            sta  $D5             ; Current check index (will increment to 0)
            sta  $D0             ; Best distance = $FF (maximum)

; === while loop starts here [nest:32] ===
; XREF: 6 refs (3 jumps) (3 branches) from render_target_check_alive, render_target_calc_dist, render_target_check_alive, render_target_update_best, render_target_adjacent, ...
render_target_next inc  $D5             ; A=$00FF X=$00FE Y=$001F ; [SP-1540]
            lda  $D5             ; A=[$00D5] X=$00FE Y=$001F ; [SP-1540]
            cmp  $E1             ; A=[$00D5] X=$00FE Y=$001F ; [SP-1540]
            bcc  render_target_check_alive ; A=[$00D5] X=$00FE Y=$001F ; [SP-1540]
            jmp  render_target_selected ; "&M$V"
; XREF: 1 ref (1 branch) from render_target_next
render_target_check_alive jsr  $46F6           ; A=[$00D5] X=$00FE Y=$001F ; [SP-1542]
            ldy  #$11            ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            lda  ($FE),Y         ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            cmp  #$C4            ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            beq  render_target_next ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
; === End of while loop ===

            cmp  #$C1            ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            beq  render_target_next ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
; === End of while loop ===

            ldx  $CD             ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            ldy  $D5             ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            sec                  ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            lda  $99A0,Y         ; -> $99B1 ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            sbc  $9980,X         ; -> $9A7E ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            sta  $04             ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1542]
            jsr  render_abs_value        ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1544]
            sta  $D1             ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1544]
            sec                  ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1544]
            lda  $99A4,Y         ; -> $99B5 ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1544]
            sbc  $9988,X         ; -> $9A86 ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1544]
            sta  $05             ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1544]
            jsr  render_abs_value        ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1546]
            sta  $D2             ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1546]
            ora  $D1             ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1546]
            cmp  #$02            ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1546]
            bcc  render_target_adjacent ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1546]
            clc                  ; A=[$00D5] X=$00FE Y=$0011 ; [SP-1546]
            lda  $D1             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1546]
            adc  $D2             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1546]
            cmp  $D0             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1546]
            beq  render_target_calc_dist ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1546]
            bcs  render_target_next ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1546]
; XREF: 1 ref (1 branch) from render_target_check_alive
render_target_calc_dist sta  $D1             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1546]
            lda  $04             ; A=[$0004] X=$00FE Y=$0011 ; [SP-1546]
            jsr  render_sign_extend       ; A=[$0004] X=$00FE Y=$0011 ; [SP-1548]
            sta  $04             ; A=[$0004] X=$00FE Y=$0011 ; [SP-1548]
            clc                  ; A=[$0004] X=$00FE Y=$0011 ; [SP-1548]
            adc  $9980,X         ; -> $9A7E ; A=[$0004] X=$00FE Y=$0011 ; [SP-1548]
            sta  $02             ; A=[$0004] X=$00FE Y=$0011 ; [SP-1548]
            lda  $05             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1548]
            jsr  render_sign_extend       ; A=[$0005] X=$00FE Y=$0011 ; [SP-1550]
            sta  $05             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1550]
            clc                  ; A=[$0005] X=$00FE Y=$0011 ; [SP-1550]
            adc  $9988,X         ; -> $9A86 ; A=[$0005] X=$00FE Y=$0011 ; [SP-1550]
            sta  $03             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1550]
            jsr  combat_tile_at_xy      ; A=[$0005] X=$00FE Y=$0011 ; [SP-1552]
            jsr  render_check_solid   ; A=[$0005] X=$00FE Y=$0011 ; [SP-1554]
            bpl  render_target_update_best ; A=[$0005] X=$00FE Y=$0011 ; [SP-1554]
            clc                  ; A=[$0005] X=$00FE Y=$0011 ; [SP-1554]
            lda  $9988,X         ; -> $9A86 ; A=[$0005] X=$00FE Y=$0011 ; [SP-1554]
            adc  $05             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1554]
            sta  $03             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1554]
            lda  $9980,X         ; -> $9A7E ; A=[$0005] X=$00FE Y=$0011 ; [SP-1554]
            sta  $02             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1554]
            jsr  combat_tile_at_xy      ; A=[$0005] X=$00FE Y=$0011 ; [SP-1556]
            jsr  render_check_solid   ; A=[$0005] X=$00FE Y=$0011 ; [SP-1558]
            bpl  render_target_update_best ; A=[$0005] X=$00FE Y=$0011 ; [SP-1558]
            clc                  ; A=[$0005] X=$00FE Y=$0011 ; [SP-1558]
            lda  $9980,X         ; -> $9A7E ; A=[$0005] X=$00FE Y=$0011 ; [SP-1558]
            adc  $04             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1558]
            sta  $02             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1558]
            lda  $9988,X         ; -> $9A86 ; A=[$0005] X=$00FE Y=$0011 ; [SP-1558]
            sta  $03             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1558]
            jsr  combat_tile_at_xy      ; A=[$0005] X=$00FE Y=$0011 ; [SP-1560]
            jsr  render_check_solid   ; A=[$0005] X=$00FE Y=$0011 ; [SP-1562]
            bpl  render_target_update_best ; A=[$0005] X=$00FE Y=$0011 ; [SP-1562]
            jmp  render_target_next ; A=[$0005] X=$00FE Y=$0011 ; [SP-1562]
; XREF: 3 refs (3 branches) from render_target_calc_dist, render_target_calc_dist, render_target_calc_dist
render_target_update_best ldy  $D5             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1562]
            sty  $D6             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1562]
            lda  $D1             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            sta  $D0             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            lda  $02             ; A=[$0002] X=$00FE Y=$0011 ; [SP-1562]
            sta  $F7             ; A=[$0002] X=$00FE Y=$0011 ; [SP-1562]
            lda  $03             ; A=[$0003] X=$00FE Y=$0011 ; [SP-1562]
            sta  $F8             ; A=[$0003] X=$00FE Y=$0011 ; [SP-1562]
            lda  $04             ; A=[$0004] X=$00FE Y=$0011 ; [SP-1562]
            sta  $F5             ; A=[$0004] X=$00FE Y=$0011 ; [SP-1562]
            lda  $05             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1562]
            sta  $F6             ; A=[$0005] X=$00FE Y=$0011 ; [SP-1562]
            jmp  render_target_next ; A=[$0005] X=$00FE Y=$0011 ; [SP-1562]
; XREF: 1 ref (1 branch) from render_target_check_alive
render_target_adjacent lda  #$00            ; A=$0000 X=$00FE Y=$0011 ; [SP-1562]
            sta  $D0             ; A=$0000 X=$00FE Y=$0011 ; [SP-1562]
            sty  $D6             ; A=$0000 X=$00FE Y=$0011 ; [SP-1562]
            clc                  ; A=$0000 X=$00FE Y=$0011 ; [SP-1562]
            lda  $D1             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            adc  $D2             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            cmp  #$02            ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            bcc  render_target_selected ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            jmp  render_target_next ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
; XREF: 2 refs (1 jump) (1 branch) from render_target_next, render_target_adjacent
render_target_selected ldx  $CD             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            ldy  $D6             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            sty  $D5             ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1562]
            rts                  ; A=[$00D1] X=$00FE Y=$0011 ; [SP-1560]

; --- Data region (50 bytes, text data) ---
            DB      $20,$F6,$46,$A0,$17,$B1,$FE,$C9,$C6,$F0,$27,$C9,$C3,$F0,$26,$C9
            DB      $D7,$F0,$25,$C9,$D4,$F0,$24,$C9,$D0,$F0,$17,$C9,$C2,$F0,$13,$C9
            DB      $CC,$F0,$1B,$C9,$C9,$F0,$11,$C9,$C4,$F0,$0A,$C9,$C1,$F0,$09,$A9
            DB      $7E,$60
; --- End data region (50 bytes) ---

; XREF: 3 refs (3 branches) from render_target_selected, render_target_selected, render_target_selected
render_appearance_melee lda  #$28            ; A=$0028 X=$00FE Y=$0011 ; [SP-1560]
            rts                  ; A=$0028 X=$00FE Y=$0011 ; [SP-1558]
; XREF: 2 refs (2 branches) from render_target_selected, render_target_selected
render_show_weapon lda  #$2A            ; A=$002A X=$00FE Y=$0011 ; [SP-1558]
            rts                  ; A=$002A X=$00FE Y=$0011 ; [SP-1556]
; XREF: 3 refs (3 branches) from render_target_selected, render_target_selected, render_target_selected
render_appearance_ranged lda  #$2C            ; A=$002C X=$00FE Y=$0011 ; [SP-1556]
            rts                  ; A=$002C X=$00FE Y=$0011 ; [SP-1554]
; XREF: 1 ref (1 branch) from render_target_selected
render_show_armor lda  #$2E            ; A=$002E X=$00FE Y=$0011 ; [SP-1554]
            rts                  ; A=$002E X=$00FE Y=$0011 ; [SP-1552]
; XREF: 1 ref (1 branch) from render_target_selected
render_appearance_wizard lda  #$22            ; A=$0022 X=$00FE Y=$0011 ; [SP-1552]
            rts                  ; A=$0022 X=$00FE Y=$0011 ; [SP-1550]

; ===========================================================================
; DISPLAY (8 functions)
; ===========================================================================

; ---------------------------------------------------------------------------
; render_monster_sprite  [3 calls]
; ---------------------------------------------------------------------------
; XREF: 3 refs (3 calls) from $008140, $008143, $00814F
render_monster_sprite    lda  #$FD            ; A=$00FD X=$00FE Y=$0011 ; [SP-1550]
            ldx  #$F0            ; A=$00FD X=$00F0 Y=$0011 ; [SP-1550]
            ldy  #$10            ; A=$00FD X=$00F0 Y=$0010 ; [SP-1550]
            jmp  $4705           ; A=$00FD X=$00F0 Y=$0010 ; [SP-1550]
            lda  #$FD            ; A=$00FD X=$00F0 Y=$0010 ; [SP-1550]
            ldx  #$80            ; A=$00FD X=$0080 Y=$0010 ; [SP-1550]
            ldy  #$10            ; A=$00FD X=$0080 Y=$0010 ; [SP-1550]
            jmp  $4705           ; A=$00FD X=$0080 Y=$0010 ; [SP-1550]

; === while loop starts here (counter: Y 'j') [nest:2] ===
; XREF: 2 refs (2 jumps) from input_jump_render, dungeon_set_encounter
render_combat_update lda  $B0             ; A=[$00B0] X=$0080 Y=$0010 ; [SP-1550]
            sta  $835F           ; A=[$00B0] X=$0080 Y=$0010 ; [SP-1550]
            lda  #$00            ; A=$0000 X=$0080 Y=$0010 ; [SP-1550]
            sta  $5521           ; A=$0000 X=$0080 Y=$0010 ; [SP-1550]
            sta  $56E7           ; A=$0000 X=$0080 Y=$0010 ; [SP-1550]
            sta  $B1             ; A=$0000 X=$0080 Y=$0010 ; [SP-1550]
            sta  $B0             ; A=$0000 X=$0080 Y=$0010 ; [SP-1550]

; === while loop starts here [nest:23] ===
; XREF: 1 ref (1 branch) from render_check_music
render_check_music lda  $B2             ; A=[$00B2] X=$0080 Y=$0010 ; [SP-1550]
            bne  render_check_music     ; A=[$00B2] X=$0080 Y=$0010 ; [SP-1550]
; === End of while loop ===

; Loop counter: X=#$20
            ldx  #$20            ; A=[$00B2] X=$0020 Y=$0010 ; [SP-1550]

; === while loop starts here [nest:23] ===
; XREF: 2 refs (1 jump) (1 branch) from render_dec_cursor, render_set_window
render_dec_cursor dex                  ; A=[$00B2] X=$001F Y=$0010 ; [SP-1550]
            bmi  render_print_status_hdr     ; A=[$00B2] X=$001F Y=$0010 ; [SP-1550]
            lda  $4F00,X         ; -> $4F1F ; A=[$00B2] X=$001F Y=$0010 ; [SP-1550]
            cmp  #$4C            ; A=[$00B2] X=$001F Y=$0010 ; [SP-1550]
            beq  render_set_window     ; A=[$00B2] X=$001F Y=$0010 ; [SP-1550]
            cmp  #$48            ; A=[$00B2] X=$001F Y=$0010 ; [SP-1550]
            bne  render_dec_cursor     ; A=[$00B2] X=$001F Y=$0010 ; [SP-1550]
; === End of while loop ===

; XREF: 1 ref (1 branch) from render_dec_cursor
render_set_window lda  #$C0            ; A=$00C0 X=$001F Y=$0010 ; [SP-1550]
            sta  $4F80,X         ; -> $4F9F ; A=$00C0 X=$001F Y=$0010 ; [SP-1550]
            jmp  render_dec_cursor     ; A=$00C0 X=$001F Y=$0010 ; [SP-1550]
; XREF: 1 ref (1 branch) from render_dec_cursor
render_print_status_hdr jsr  $46BA           ; A=$00C0 X=$001F Y=$0010 ; [SP-1552]
            DB      $FF
            lda  $ADAD           ; A=[$ADAD] X=$001F Y=$0010 ; [SP-1552]

; --- Data region (373 bytes) ---
            DB      $C3,$CF,$CE,$C6,$CC,$C9,$C3,$D4,$A1,$A1,$AD,$AD,$AD,$FF,$AD,$BE
            DB      $00,$20,$57,$84,$20,$BA,$46,$D3,$FF,$FF,$00,$A5,$E2,$C9,$01,$D0
            DB      $05,$A9,$C3,$4C,$79,$80,$A5,$CE,$C9,$1E,$D0,$14,$A9,$2E,$85,$CE
            DB      $A5,$0E,$C9,$16,$D0,$05,$A9,$D3,$4C,$79,$80,$A9,$C1,$4C,$79,$80
            DB      $A5,$0E,$C9,$16,$D0,$10,$A5,$CE,$C9,$20,$B0,$05,$A9,$D1,$4C,$79
            DB      $80,$A9,$D2,$4C,$79,$80,$A5,$CE,$C9,$20,$B0,$09,$C9,$16,$90,$05
            DB      $A9,$CD,$4C,$79,$80,$A5,$09,$C9,$02,$D0,$05,$A9,$C7,$4C,$79,$80
            DB      $C9,$04,$D0,$05,$A9,$C2,$4C,$79,$80,$C9,$06,$D0,$05,$A9,$C6,$4C
            DB      $79,$80,$C9,$10,$D0,$05,$A9,$C3,$4C,$79,$80,$C9,$40,$F0,$F5,$C9
            DB      $42,$F0,$F1,$A9,$C7,$8D,$89,$80,$20,$B7,$46,$04
            ASC     "BLOAD CON@"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $A5,$E2,$8D,$5E,$83,$A9,$80,$85,$E2,$A6,$E1,$CA,$30,$3A,$86,$D5
            DB      $20,$F6,$46,$A0,$11,$B1,$FE,$C9,$C7,$F0,$0F,$C9,$D0,$F0,$0B,$A9
            DB      $FF,$9D,$A0,$99,$9D,$A4,$99,$4C,$97,$80,$BD,$A0,$99,$85,$02,$BD
            DB      $A4,$99,$85,$03,$20,$5D,$7F,$9D,$AC,$99,$20,$18,$7E,$9D,$A8,$99
            DB      $BD,$AC,$99,$91,$FE,$4C,$97,$80,$A2,$07,$A9,$00,$9D,$98,$99,$CA
            DB      $10,$FA,$20,$43,$6F,$F0,$18,$AD,$5E,$83,$C9,$02,$90,$18,$C9,$04
            DB      $B0,$14,$A5,$CE,$C9,$24,$F0,$07,$A9,$00,$85,$FB,$4C,$09,$81,$A9
            DB      $07,$85,$FB,$4C,$09,$81,$20,$E7,$46,$29,$07,$85,$FB,$20,$E7,$46
            DB      $29,$07,$AA,$BD,$98,$99,$D0,$F5,$A5,$CE,$4A,$29,$0F,$A8,$B9,$14
            DB      $89,$20,$E4,$46,$09,$0F,$9D,$98,$99,$BD,$80,$99,$85,$02,$BD,$88
            DB      $99,$85,$03,$20,$18,$7E,$9D,$90,$99,$A5,$CE,$91,$FE,$C6,$FB,$10
            DB      $CC,$20,$28,$03,$20,$9E,$7F,$20,$9E,$7F,$A9,$FD,$A2,$F0,$A0,$04
            DB      $20,$05,$47,$20,$9E,$7F,$A9,$05,$85,$B1,$2C,$10,$C0
; --- End data region (373 bytes) ---


; === while loop starts here (counter: Y 'iter_y') [nest:18] ===
; XREF: 2 refs (2 jumps) from render_combat_monster_ai, render_combat_check_cb
render_call_turn jsr  move_process_turn        ; A=[$ADAD] X=$001F Y=$0010 ; [SP-1591]
            jsr  move_display_party_status       ; A=[$ADAD] X=$001F Y=$0010 ; [SP-1593]
            ldx  #$00            ; A=[$ADAD] X=$0000 Y=$0010 ; [SP-1593]
            stx  $835D           ; A=[$ADAD] X=$0000 Y=$0010 ; [SP-1593]

; === while loop starts here (counter: Y 'iter_y') [nest:20] ===
; XREF: 1 ref (1 jump) from render_combat_mon_status
render_party_status_disp lda  $835D           ; A=[$835D] X=$0000 Y=$0010 ; [SP-1593]
            sta  $D5             ; A=[$835D] X=$0000 Y=$0010 ; [SP-1593]
            jsr  render_calc_offset     ; A=[$835D] X=$0000 Y=$0010 ; [SP-1595]
            jsr  magic_resolve_effect       ; A=[$835D] X=$0000 Y=$0010 ; [SP-1597]
            beq  render_party_final     ; A=[$835D] X=$0000 Y=$0010 ; [SP-1597]
            jmp  render_combat_loop_start      ; A=[$835D] X=$0000 Y=$0010 ; [SP-1597]
; XREF: 1 ref (1 branch) from render_party_status_disp
render_party_final lda  #$2F            ; A=$002F X=$0000 Y=$0010 ; [SP-1597]
            sta  $12             ; A=$002F X=$0000 Y=$0010 ; [SP-1597]
            jsr  $46BA           ; Call $0046BA(A, X)
            lda  $ADAD           ; A=[$ADAD] X=$0000 Y=$0010 ; [SP-1599]
            lda  $CCD0           ; SLOTEXP_x4D0 - Slot expansion ROM offset $4D0 {Slot}
            cmp  ($D9,X)         ; A=[$CCD0] X=$0000 Y=$0010 ; [SP-1599]
            cmp  $D2             ; A=[$CCD0] X=$0000 Y=$0010 ; [SP-1599]
            lda  $A500           ; A=[$A500] X=$0000 Y=$0010 ; [SP-1599]
            cmp  $18,X           ; A=[$A500] X=$0000 Y=$0010 ; [SP-1599]
            adc  #$01            ; A=A+$01 X=$0000 Y=$0010 ; [SP-1599]
            jsr  $46D2           ; A=A+$01 X=$0000 Y=$0010 ; [SP-1601]
            jsr  $46BA           ; A=A+$01 X=$0000 Y=$0010 ; [SP-1603]
            lda  $ADAD           ; A=[$ADAD] X=$0000 Y=$0010 ; [SP-1603]
            lda  $1DFF           ; A=[$1DFF] X=$0000 Y=$0010 ; [SP-1603]
            brk  #$A9            ; A=[$1DFF] X=$0000 Y=$0010 ; [SP-1606]

; --- Data region (340 bytes) ---
            DB      $00,$85,$04,$85,$05,$A6,$D5,$BD,$A0,$99,$85,$02,$BD,$A4,$99,$85
            DB      $03,$20,$18,$7E,$A9,$C0,$85,$CD,$18,$A5,$CD,$69,$40,$85,$CD,$D0
            DB      $0D,$20,$18,$7E,$A6,$D5,$BD,$A8,$99,$91,$FE,$4C,$D2,$81,$20,$18
            DB      $7E,$A6,$D5,$BD,$AC,$99,$91,$FE,$20,$ED,$46,$20,$F0,$46,$20,$28
            DB      $03,$C6,$12,$D0,$05,$A9,$A0,$4C,$EC,$81,$20,$1F,$BA,$10,$C9,$2C
            DB      $10,$C0,$48,$20,$18,$7E,$A6,$D5,$BD,$AC,$99,$91,$FE,$20,$28,$03
            DB      $68,$C9,$C1,$90,$07,$C9,$DB,$B0,$03,$4C,$E7,$82,$C9,$8D,$F0,$1B
            DB      $C9,$8B,$F0,$17,$C9,$AF,$F0,$24,$C9,$8A,$F0,$20,$C9,$95,$F0,$2D
            DB      $C9,$88,$F0,$39,$C9,$A0,$F0,$45,$4C,$35,$51,$20,$BA,$46,$CE,$EF
            DB      $F2,$F4,$E8,$FF,$00,$A9,$FF,$85,$05,$4C,$8D,$82,$20,$BA,$46,$D3
            DB      $EF,$F5,$F4,$E8,$FF,$00,$A9,$01,$85,$05,$4C,$8D,$82,$20,$BA,$46
            DB      $C5,$E1,$F3,$F4,$FF,$00,$A9,$01,$85,$04,$4C,$8D,$82,$20,$BA,$46
            DB      $D7,$E5,$F3,$F4,$FF,$00,$A9,$FF,$85,$04,$4C,$8D,$82,$20,$BA,$46
            DB      $D0,$E1,$F3,$F3,$FF,$00,$4C,$A6,$85,$20,$BA,$46,$C9,$CE,$D6,$C1
            DB      $CC,$C9,$C4,$A0,$CD,$CF,$D6,$C5,$A1,$FF,$00,$A9,$FF,$20,$05,$47
            DB      $4C,$A6,$85,$A6,$D5,$18,$BD,$A0,$99,$65,$04,$85,$02,$85,$F1,$30
            DB      $D8,$C9,$0B,$B0,$D4,$18,$BD,$A4,$99,$65,$05,$85,$03,$85,$F2,$30
            DB      $C8,$C9,$0B,$B0,$C4,$20,$18,$7E,$20,$5B,$7E,$D0,$BC,$A6,$D5,$BD
            DB      $A0,$99,$85,$02,$BD,$A4,$99,$85,$03,$20,$18,$7E,$BD,$A8,$99,$91
            DB      $FE,$A5,$F1,$85,$02,$9D,$A0,$99,$A5,$F2,$85,$03,$9D,$A4,$99,$20
            DB      $18,$7E,$9D,$A8,$99,$BD,$AC,$99,$91,$FE,$4C,$A6,$85,$C9,$C1,$D0
            DB      $03,$4C,$60
render_combat_cmd_data
            DB      $83
; --- End data region (340 bytes) ---

            cmp  #$C3            ; A=[$1DFF] X=$0000 Y=$0010 ; [SP-1650]

; --- Data region (384 bytes) ---
            DB      $D0,$03,$4C,$8C,$85,$C9,$CE,$D0,$14,$20,$BA,$46,$CE,$C5,$C7,$C1
            DB      $D4,$C5,$A0,$D4,$C9,$CD,$C5,$A1,$FF,$00,$4C,$C6,$61,$C9,$D2,$D0
            DB      $17,$20,$BA,$46,$D2,$C5,$C1,$C4,$D9,$A0,$C1,$A0,$D7,$C5,$C1,$D0
            DB      $CF,$CE,$A1,$FF,$00,$4C,$36,$66,$C9,$D6,$D0,$03,$4C,$4D,$69,$C9
            DB      $DA,$D0,$0D,$20,$BA,$46,$DA,$D4,$C1,$D4,$D3,$FF,$00,$4C,$DE,$6A
            DB      $20,$BA,$46,$CE,$CF,$D4,$A0,$D5,$D3,$C1,$C2,$CC,$C5,$A0,$C3,$CD
            DB      $C4,$A1,$FF,$1D,$00,$A9,$FE,$20,$05,$47,$4C,$B2,$81,$00,$00,$00
            DB      $A9,$7A,$85,$1F,$20,$F6,$46,$A0,$30,$B1,$FE,$18,$69,$41,$20,$32
            DB      $89,$20,$BA,$46,$A0,$C1,$D4,$D4,$C1,$C3,$CB,$FF,$C4,$C9,$D2,$AD
            DB      $00,$AD,$00,$C0,$10,$FB,$C9,$A0,$D0,$0F,$20,$BA,$46,$CE,$CF,$CE
            DB      $C5,$FF,$00,$2C,$10,$C0,$4C,$A6,$85,$20,$73,$7D,$A5,$D5,$0A,$0A
            DB      $0A,$18,$69,$E0,$AA,$A0,$06,$A9,$FD,$20,$05,$47,$20,$F6,$46,$A0
            DB      $30,$B1,$FE,$C9,$03,$F0,$0F,$C9,$05,$F0,$0B,$C9,$09,$F0,$07,$C9
            DB      $0D,$F0,$03,$4C,$DC,$83,$A6,$D5,$BD,$A0,$99,$85,$02,$BD,$A4,$99
            DB      $85,$03,$20,$41,$7D,$30,$3D,$85,$FB,$4C,$26,$84,$A6,$D5,$18,$BD
            DB      $A0,$99,$65,$04,$85,$02,$18,$BD,$A4,$99,$65,$05,$85,$03,$20,$24
            DB      $7D,$10,$33,$20,$F6,$46,$A0,$30,$B1,$FE,$C9,$01,$D0,$16,$A0,$31
            DB      $F8,$38,$B1,$FE,$E9,$01,$91,$FE,$D8,$D0,$BB,$A0,$30,$A9,$00,$91
            DB      $FE,$4C,$C6,$83,$20,$BA,$46,$CD,$C9,$D3,$D3,$C5,$C4,$A1,$FF,$00
            DB      $20,$28,$03,$4C,$A6,$85,$85,$FB,$20,$43,$6F,$D0,$0E,$20,$F6,$46
            DB      $A0,$30,$B1,$FE,$C9,$0F,$F0,$03,$4C,$14,$84,$20,$E7,$46,$30,$11
            DB      $A9,$63,$20,$E4,$46,$20,$6F,$71,$20,$F6,$46,$A0,$13,$D1,$FE,$B0
            DB      $C3,$20,$57,$84,$4C,$7A,$84,$A5,$01,$4A,$90,$14,$A5,$CE,$38,$E9
            DB      $2E,$90,$0D,$4A,$48,$A5,$00,$4A,$68,$2A,$69,$79,$20,$32,$89,$60
; --- End data region (384 bytes) ---

; XREF: 2 refs (2 branches) from $00845A, $008461
render_monster_attack  lda  $CE             ; A=[$00CE] X=$0000 Y=$0010 ; [SP-1715]
            lsr  a               ; A=[$00CE] X=$0000 Y=$0010 ; [SP-1715]
            clc                  ; A=[$00CE] X=$0000 Y=$0010 ; [SP-1715]
            adc  #$01            ; A=A+$01 X=$0000 Y=$0010 ; [SP-1715]
            jsr  render_draw_text_row     ; A=A+$01 X=$0000 Y=$0010 ; [OPT] TAIL_CALL: Tail call: JSR/JSL at $008476 followed by RTS ; [SP-1717]
            rts                  ; A=A+$01 X=$0000 Y=$0010 ; [SP-1715]

; --- Data region (171 bytes) ---
            DB      $20,$BA,$46,$FF,$C8,$C9,$D4,$A1,$FF,$00,$20,$18,$7E,$A5,$1F,$91
            DB      $FE,$20,$28,$03,$A9,$F7,$20,$05,$47,$A5,$CE,$A0,$00,$91,$FE,$20
            DB      $F6,$46,$A0,$12,$B1,$FE,$20,$5F,$71,$09,$01,$20,$E4,$46,$85,$D0
            DB      $A0,$12,$B1,$FE,$4A,$65,$D0,$85,$D0,$A0,$30,$B1,$FE,$0A,$71,$FE
            DB      $65,$D0,$69,$04,$20,$C7,$84,$20,$28,$03,$4C,$A6,$85,$A5,$CE,$C9
            DB      $26,$F0,$0F,$A6,$FB,$BD,$98,$99,$38,$E5,$D0,$9D,$98,$99,$90,$03
            DB      $F0,$01,$60,$20,$BA,$46
            ASC     "KILLED! EXP.-"
            DB      $00 ; null terminator
            DB      $A5,$CE,$4A,$29,$0F,$AA,$BD,$25,$85,$85,$D4,$20,$D5,$46,$20,$BA
            DB      $46,$FF,$00,$A5,$D4,$20,$91,$70,$A6,$FB,$BD,$80,$99,$85,$02,$BD
            DB      $88,$99,$85,$03,$20,$18,$7E,$A0,$00,$BD,$90,$99,$91,$FE,$A9,$00
            DB      $9D,$98,$99,$20,$28,$03,$60
; --- End data region (171 bytes) ---

render_exp_table  ora  ($02,X)         ; A=A+$01 X=$0000 Y=$0010 ; [SP-1742]
            ora  $20,X           ; A=A+$01 X=$0000 Y=$0010 ; [SP-1742]
            php                  ; A=A+$01 X=$0000 Y=$0010 ; [SP-1743]
            asl  $10             ; A=A+$01 X=$0000 Y=$0010 ; [SP-1743]
            ora  $03             ; A=A+$01 X=$0000 Y=$0010 ; [SP-1743]
            DB      $04
            asl  $08             ; A=A+$01 X=$0000 Y=$0010 ; [SP-1743]
            DB      $10,$15,$20,$05

; === while loop starts here [nest:22] ===
; XREF: 1 ref (1 jump) from render_combat_find_mon
render_victory  lda  #$00            ; A=$0000 X=$0000 Y=$0010 ; [SP-1746]
            sta  $CB             ; A=$0000 X=$0000 Y=$0010 ; [SP-1749]
            sta  $B1             ; A=$0000 X=$0000 Y=$0010 ; [SP-1749]
            sta  $B0             ; A=$0000 X=$0000 Y=$0010 ; [SP-1749]

; === while loop starts here [nest:24] ===
; XREF: 1 ref (1 branch) from render_victory_wait_vbl
render_victory_wait_vbl  lda  $B2             ; A=[$00B2] X=$0000 Y=$0010 ; [SP-1749]
            bne  render_victory_wait_vbl      ; A=[$00B2] X=$0000 Y=$0010 ; [SP-1749]
            jsr  $46BA           ; A=[$00B2] X=$0000 Y=$0010 ; [SP-1751]
            DB      $FF
            tax                  ; A=[$00B2] X=[$00B2] Y=$0010 ; [SP-1751]
            tax                  ; A=[$00B2] X=[$00B2] Y=$0010 ; [SP-1751]
            tax                  ; A=[$00B2] X=[$00B2] Y=$0010 ; [SP-1751]

; --- Data region (35 bytes, text data) ---
            DB      $AA,$D6,$C9,$C3,$D4,$CF,$D2,$D9,$A1,$AA,$AA,$AA,$AA,$FF,$FF,$00
            DB      $A9,$FD,$A2,$80,$A0,$10,$20,$05,$47,$20,$A7,$7F,$20,$A7,$7F,$A9
            DB      $FD,$A2,$60
; --- End data region (35 bytes) ---

render_victory_music  ldy  #$40            ; A=[$00B2] X=[$00B2] Y=$0040 ; [SP-1757]
            jsr  $4705           ; A=[$00B2] X=[$00B2] Y=$0040 ; [SP-1759]
            lda  $835F           ; A=[$835F] X=[$00B2] Y=$0040 ; [SP-1759]
            sta  $B1             ; A=[$835F] X=[$00B2] Y=$0040 ; [SP-1759]
            sta  $B0             ; A=[$835F] X=[$00B2] Y=$0040 ; [SP-1759]
            lda  $835E           ; A=[$835E] X=[$00B2] Y=$0040 ; [SP-1759]
            sta  $E2             ; A=[$835E] X=[$00B2] Y=$0040 ; [SP-1759]
            cmp  #$01            ; A=[$835E] X=[$00B2] Y=$0040 ; [SP-1759]
            bne  render_victory_cleanup      ; A=[$835E] X=[$00B2] Y=$0040 ; [SP-1759]
            jsr  $1800           ; Call $001800(A)
            jmp  render_return_to_game     ; A=[$835E] X=[$00B2] Y=$0040 ; [SP-1761]
; XREF: 1 ref (1 branch) from render_victory_music
render_victory_cleanup  jsr  $0230           ; A=[$835E] X=[$00B2] Y=$0040 ; [SP-1763]
            jmp  game_loop_end_turn   ; A=[$835E] X=[$00B2] Y=$0040 ; [SP-1763]

; ---
            DB      $A9,$78,$85,$1F,$20,$BA,$46,$C3,$C1,$D3,$D4,$A0,$D3,$D0,$C5,$CC
            DB      $CC,$A1,$FF,$00,$20,$F6,$46,$4C,$AA,$53
; ---

; XREF: 6 refs (6 jumps) from $00828A, render_party_status_disp, $008396, $0082E4, render_monster_attack, ...
render_combat_loop_start  lda  $835F           ; A=[$835F] X=[$00B2] Y=$0040 ; [SP-1765]
            cmp  #$07            ; A=[$835F] X=[$00B2] Y=$0040 ; [SP-1765]
            bne  render_combat_load_turn      ; A=[$835F] X=[$00B2] Y=$0040 ; [SP-1765]
            lda  #$00            ; A=$0000 X=[$00B2] Y=$0040 ; [SP-1765]
            sta  $CB             ; A=$0000 X=[$00B2] Y=$0040 ; [SP-1765]
; XREF: 1 ref (1 branch) from render_combat_loop_start
render_combat_load_turn  lda  $835D           ; A=[$835D] X=[$00B2] Y=$0040 ; [SP-1765]
            sta  $D5             ; A=[$835D] X=[$00B2] Y=$0040 ; [SP-1765]
            jsr  $0328           ; A=[$835D] X=[$00B2] Y=$0040 ; [SP-1767]
            jsr  render_calc_offset     ; A=[$835D] X=[$00B2] Y=$0040 ; [SP-1769]
            ldx  #$07            ; A=[$835D] X=$0007 Y=$0040 ; [SP-1769]

; === while loop starts here [nest:23] ===
; XREF: 1 ref (1 branch) from render_combat_find_mon
render_combat_find_mon  lda  $9998,X         ; -> $999F ; A=[$835D] X=$0007 Y=$0040 ; [SP-1769]
            bne  render_combat_mon_status      ; A=[$835D] X=$0007 Y=$0040 ; [SP-1769]
            dex                  ; A=[$835D] X=$0006 Y=$0040 ; [SP-1769]
            bpl  render_combat_find_mon      ; A=[$835D] X=$0006 Y=$0040 ; [SP-1769]
            jmp  render_victory      ; A=[$835D] X=$0006 Y=$0040 ; [SP-1769]
; XREF: 1 ref (1 branch) from render_combat_find_mon
render_combat_mon_status  jsr  move_display_party_status       ; A=[$835D] X=$0006 Y=$0040 ; [SP-1771]
            lda  #$17            ; A=$0017 X=$0006 Y=$0040 ; [SP-1771]
            sta  $FA             ; A=$0017 X=$0006 Y=$0040 ; [SP-1771]
            lda  #$18            ; A=$0018 X=$0006 Y=$0040 ; [SP-1771]
            sta  $F9             ; A=$0018 X=$0006 Y=$0040 ; [SP-1771]
            inc  $835D           ; A=$0018 X=$0006 Y=$0040 ; [SP-1771]
            lda  $835D           ; A=[$835D] X=$0006 Y=$0040 ; [SP-1771]
            cmp  $E1             ; A=[$835D] X=$0006 Y=$0040 ; [SP-1771]
            bcs  render_combat_check_cb      ; A=[$835D] X=$0006 Y=$0040 ; [SP-1771]
            jmp  render_party_status_disp     ; A=[$835D] X=$0006 Y=$0040 ; [SP-1771]
; XREF: 1 ref (1 branch) from render_combat_mon_status
render_combat_check_cb  lda  $CB             ; A=[$00CB] X=$0006 Y=$0040 ; [SP-1771]
            beq  render_combat_init_cd      ; A=[$00CB] X=$0006 Y=$0040 ; [SP-1771]
            dec  $CB             ; A=[$00CB] X=$0006 Y=$0040 ; [SP-1771]
            jmp  render_call_turn     ; " pt 8s\x22"
; XREF: 1 ref (1 branch) from render_combat_check_cb
render_combat_init_cd  ldx  #$FF            ; A=[$00CB] X=$00FF Y=$0040 ; [SP-1771]
            stx  $CD             ; A=[$00CB] X=$00FF Y=$0040 ; [SP-1771]

; === while loop starts here [nest:18] ===
; XREF: 5 refs (4 jumps) (1 branch) from render_combat_mon_check, render_combat_draw_2, render_combat_mon_special, render_combat_status_upd, render_combat_mon_action
render_combat_monster_ai  inc  $CD             ; A=[$00CB] X=$00FF Y=$0040 ; [SP-1771]
            ldx  $CD             ; A=[$00CB] X=$00FF Y=$0040 ; [SP-1771]
            cpx  #$08            ; A=[$00CB] X=$00FF Y=$0040 ; [SP-1771]
            bcc  render_combat_mon_check      ; A=[$00CB] X=$00FF Y=$0040 ; [SP-1771]
            jmp  render_call_turn     ; " pt 8s\x22"
; XREF: 1 ref (1 branch) from render_combat_monster_ai
render_combat_mon_check  lda  $9998,X         ; -> $9A97 ; A=[$00CB] X=$00FF Y=$0040 ; [SP-1771]
            beq  render_combat_monster_ai      ; A=[$00CB] X=$00FF Y=$0040 ; [SP-1771]
            jsr  render_find_target    ; Call $007E85(A, X)
            lda  #$7A            ; A=$007A X=$00FF Y=$0040 ; [SP-1773]
            sta  $1F             ; A=$007A X=$00FF Y=$0040 ; [SP-1773]
            lda  $D0             ; A=[$00D0] X=$00FF Y=$0040 ; [SP-1773]
            bne  render_combat_mon_target      ; A=[$00D0] X=$00FF Y=$0040 ; [SP-1773]
            jmp  render_combat_get_tile      ; A=[$00D0] X=$00FF Y=$0040 ; [SP-1773]
; XREF: 1 ref (1 branch) from render_combat_mon_check
render_combat_mon_target  lda  $D5             ; A=[$00D5] X=$00FF Y=$0040 ; [SP-1773]
            bmi  render_combat_mon_move      ; A=[$00D5] X=$00FF Y=$0040 ; [SP-1773]
            jsr  $46E7           ; Call $0046E7(A)
            bmi  render_combat_mon_move      ; A=[$00D5] X=$00FF Y=$0040 ; [SP-1775]
            lda  $CE             ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1775]
            cmp  #$3A            ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1775]
            bne  render_combat_mon_move      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1775]
            jmp  render_combat_mon_flag      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1775]
; XREF: 3 refs (3 branches) from render_combat_mon_target, render_combat_mon_target, render_combat_mon_target
render_combat_mon_move  lda  #$C0            ; A=$00C0 X=$00FF Y=$0040 ; [SP-1775]
            jsr  $46E4           ; Call $0046E4(A, Y)
            bpl  render_combat_mon_action      ; A=$00C0 X=$00FF Y=$0040 ; [SP-1777]
            lda  $CE             ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            cmp  #$1A            ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            beq  render_combat_mon_wait      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            cmp  #$1C            ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            beq  render_combat_mon_wait      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            cmp  #$2C            ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            beq  render_combat_mon_wait      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            cmp  #$36            ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            beq  render_combat_mon_wait      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            cmp  #$3A            ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            beq  render_combat_mon_wait      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            cmp  #$3C            ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            beq  render_combat_mon_wait      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            cmp  #$26            ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]
            beq  render_combat_mon_special      ; A=[$00CE] X=$00FF Y=$0040 ; [SP-1777]

; === while loop starts here [nest:20] ===
; XREF: 2 refs (2 branches) from render_combat_mon_move, render_combat_mon_wait
render_combat_mon_action  lda  $D0             ; A=[$00D0] X=$00FF Y=$0040 ; [SP-1777]
            bpl  render_combat_mon_special      ; A=[$00D0] X=$00FF Y=$0040 ; [SP-1777]
            jmp  render_combat_monster_ai      ; A=[$00D0] X=$00FF Y=$0040 ; [SP-1777]
; XREF: 6 refs (6 branches) from render_combat_mon_move, render_combat_mon_move, render_combat_mon_move, render_combat_mon_move, render_combat_mon_move, ...
render_combat_mon_wait  jsr  $46E7           ; A=[$00D0] X=$00FF Y=$0040 ; [SP-1779]
            and  #$03            ; A=A&$03 X=$00FF Y=$0040 ; [SP-1779]
            sta  $D5             ; A=A&$03 X=$00FF Y=$0040 ; [SP-1779]
            jsr  $46F6           ; A=A&$03 X=$00FF Y=$0040 ; [SP-1781]
            ldy  #$11            ; A=A&$03 X=$00FF Y=$0011 ; [SP-1781]
            lda  ($FE),Y         ; A=A&$03 X=$00FF Y=$0011 ; [SP-1781]
            cmp  #$C7            ; A=A&$03 X=$00FF Y=$0011 ; [SP-1781]
            bne  render_combat_mon_action      ; A=A&$03 X=$00FF Y=$0011 ; [SP-1781]
            jsr  char_decrypt_records       ; Call $0058E9(Y)
            lda  #$FD            ; A=$00FD X=$00FF Y=$0011 ; [SP-1783]
            ldx  #$40            ; A=$00FD X=$0040 Y=$0011 ; [SP-1783]
            ldy  #$40            ; A=$00FD X=$0040 Y=$0040 ; [SP-1783]
            jsr  $4705           ; A=$00FD X=$0040 Y=$0040 ; [SP-1785]
            jsr  char_decrypt_records       ; A=$00FD X=$0040 Y=$0040 ; [SP-1787]
            lda  #$78            ; A=$0078 X=$0040 Y=$0040 ; [SP-1787]
            sta  $1F             ; A=$0078 X=$0040 Y=$0040 ; [SP-1787]
            jmp  render_combat_get_tile      ; A=$0078 X=$0040 Y=$0040 ; [SP-1787]
; XREF: 2 refs (2 branches) from render_combat_mon_action, render_combat_mon_move
render_combat_mon_special  lda  $9980,X         ; -> $99C0 ; A=$0078 X=$0040 Y=$0040 ; [SP-1787]
            sta  $02             ; A=$0078 X=$0040 Y=$0040 ; [SP-1787]
            lda  $9988,X         ; -> $99C8 ; A=$0078 X=$0040 Y=$0040 ; [SP-1787]
            sta  $03             ; A=$0078 X=$0040 Y=$0040 ; [SP-1787]
            jsr  combat_tile_at_xy      ; A=$0078 X=$0040 Y=$0040 ; [SP-1789]
            lda  $9990,X         ; -> $99D0 ; A=$0078 X=$0040 Y=$0040 ; [SP-1789]
            sta  ($FE),Y         ; A=$0078 X=$0040 Y=$0040 ; [SP-1789]
            lda  $F7             ; A=[$00F7] X=$0040 Y=$0040 ; [SP-1789]
            sta  $02             ; A=[$00F7] X=$0040 Y=$0040 ; [SP-1789]
            sta  $9980,X         ; -> $99C0 ; A=[$00F7] X=$0040 Y=$0040 ; [SP-1789]
            lda  $F8             ; A=[$00F8] X=$0040 Y=$0040 ; [SP-1789]
            sta  $03             ; A=[$00F8] X=$0040 Y=$0040 ; [SP-1789]
            sta  $9988,X         ; -> $99C8 ; A=[$00F8] X=$0040 Y=$0040 ; [SP-1789]
            jsr  combat_tile_at_xy      ; A=[$00F8] X=$0040 Y=$0040 ; [SP-1791]
            lda  ($FE),Y         ; A=[$00F8] X=$0040 Y=$0040 ; [SP-1791]
            sta  $9990,X         ; -> $99D0 ; A=[$00F8] X=$0040 Y=$0040 ; [SP-1791]
            lda  $CE             ; A=[$00CE] X=$0040 Y=$0040 ; [SP-1791]
            sta  ($FE),Y         ; A=[$00CE] X=$0040 Y=$0040 ; [SP-1791]
            jsr  $0328           ; Call $000328(A)
            jmp  render_combat_monster_ai      ; A=[$00CE] X=$0040 Y=$0040 ; [SP-1793]
; XREF: 1 ref (1 jump) from render_combat_mon_target
render_combat_mon_flag  lda  #$FB            ; A=$00FB X=$0040 Y=$0040 ; [SP-1793]
            jsr  $4705           ; A=$00FB X=$0040 Y=$0040 ; [SP-1795]
            ldx  $CD             ; A=$00FB X=$0040 Y=$0040 ; [SP-1795]
            lda  $9980,X         ; -> $99C0 ; A=$00FB X=$0040 Y=$0040 ; [SP-1795]
            sta  $02             ; A=$00FB X=$0040 Y=$0040 ; [SP-1795]
            lda  $9988,X         ; -> $99C8 ; A=$00FB X=$0040 Y=$0040 ; [SP-1795]
            sta  $03             ; A=$00FB X=$0040 Y=$0040 ; [SP-1795]

; === while loop starts here [nest:14] ===
; XREF: 1 ref (1 jump) from render_combat_draw_1
render_combat_mon_step  clc                  ; A=$00FB X=$0040 Y=$0040 ; [SP-1795]
            lda  $02             ; A=[$0002] X=$0040 Y=$0040 ; [SP-1795]
            adc  $F5             ; A=[$0002] X=$0040 Y=$0040 ; [SP-1795]
            sta  $02             ; A=[$0002] X=$0040 Y=$0040 ; [SP-1795]
            cmp  #$0B            ; A=[$0002] X=$0040 Y=$0040 ; [SP-1795]
            bcs  render_combat_draw_2      ; A=[$0002] X=$0040 Y=$0040 ; [SP-1795]
            clc                  ; A=[$0002] X=$0040 Y=$0040 ; [SP-1795]
            lda  $03             ; A=[$0003] X=$0040 Y=$0040 ; [SP-1795]
            adc  $F6             ; A=[$0003] X=$0040 Y=$0040 ; [SP-1795]
            sta  $03             ; A=[$0003] X=$0040 Y=$0040 ; [SP-1795]
            cmp  #$0B            ; A=[$0003] X=$0040 Y=$0040 ; [SP-1795]
            bcs  render_combat_draw_2      ; A=[$0003] X=$0040 Y=$0040 ; [SP-1795]
            ldy  $E1             ; A=[$0003] X=$0040 Y=$0040 ; [SP-1795]
            dey                  ; A=[$0003] X=$0040 Y=$003F ; [SP-1795]

; === while loop starts here [nest:16] ===
; XREF: 1 ref (1 branch) from render_combat_dec_range
render_combat_load_dest  lda  $02             ; A=[$0002] X=$0040 Y=$003F ; [SP-1795]
            cmp  $99A0,Y         ; -> $99DF ; A=[$0002] X=$0040 Y=$003F ; [SP-1795]
            bne  render_combat_dec_range      ; A=[$0002] X=$0040 Y=$003F ; [SP-1795]
            lda  $03             ; A=[$0003] X=$0040 Y=$003F ; [SP-1795]
            cmp  $99A4,Y         ; -> $99E3 ; A=[$0003] X=$0040 Y=$003F ; [SP-1795]
            bne  render_combat_dec_range      ; A=[$0003] X=$0040 Y=$003F ; [SP-1795]
            sty  $D5             ; A=[$0003] X=$0040 Y=$003F ; [SP-1795]
            jmp  render_combat_resolve      ; A=[$0003] X=$0040 Y=$003F ; [SP-1795]
; XREF: 2 refs (2 branches) from render_combat_load_dest, render_combat_load_dest
render_combat_dec_range  dey                  ; A=[$0003] X=$0040 Y=$003E ; [SP-1795]
            bpl  render_combat_load_dest      ; A=[$0003] X=$0040 Y=$003E ; [SP-1795]
            jsr  combat_tile_at_xy      ; A=[$0003] X=$0040 Y=$003E ; [SP-1797]
            pha                  ; A=[$0003] X=$0040 Y=$003E ; [SP-1798]
            lda  #$7A            ; A=$007A X=$0040 Y=$003E ; [SP-1798]
            sta  ($FE),Y         ; A=$007A X=$0040 Y=$003E ; [SP-1798]

; === while loop starts here [nest:13] ===
; XREF: 1 ref (1 branch) from render_combat_print_hit
render_combat_draw_1  jsr  $0328           ; A=$007A X=$0040 Y=$003E ; [SP-1800]
            pla                  ; A=[stk] X=$0040 Y=$003E ; [SP-1799]
            ldy  #$00            ; A=[stk] X=$0040 Y=$0000 ; [SP-1799]
            sta  ($FE),Y         ; A=[stk] X=$0040 Y=$0000 ; [SP-1799]
            jmp  render_combat_mon_step      ; A=[stk] X=$0040 Y=$0000 ; [SP-1799]
; XREF: 2 refs (2 branches) from render_combat_mon_step, render_combat_mon_step
render_combat_draw_2  jsr  $0328           ; A=[stk] X=$0040 Y=$0000 ; [SP-1801]
            jmp  render_combat_monster_ai      ; A=[stk] X=$0040 Y=$0000 ; [SP-1801]
; XREF: 2 refs (2 jumps) from render_combat_mon_check, render_combat_mon_wait
render_combat_get_tile  lda  $CE             ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1801]
            cmp  #$1C            ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1801]
            beq  render_combat_tile_check      ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1801]
            cmp  #$3C            ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1801]
            beq  render_combat_tile_check      ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1801]
            cmp  #$38            ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1801]
            beq  render_combat_tile_check      ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1801]
            jmp  render_combat_tile_drop      ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1801]
; XREF: 3 refs (3 branches) from render_combat_get_tile, render_combat_get_tile, render_combat_get_tile
render_combat_tile_check  jsr  render_get_tile_char        ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1803]
            jmp  render_combat_print_hit      ; " :FPLR-"
; XREF: 1 ref (1 jump) from render_combat_get_tile
render_combat_tile_drop  cmp  #$2E            ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1803]
            bne  render_combat_print_hit      ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1803]
            jsr  render_party_member      ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1805]
; XREF: 2 refs (1 jump) (1 branch) from render_combat_tile_check, render_combat_tile_drop
render_combat_print_hit  jsr  $46BA           ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1807]
            bne  render_combat_draw_1      ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1807]
            DB      $D2
            lda  $A500           ; A=[$A500] X=$0040 Y=$0000 ; [SP-1807]

; --- Data region (83 bytes, text data) ---
            DB      $D5,$18,$69,$01,$20,$D2,$46,$A9,$F8,$20,$05,$47,$AD,$5E,$83,$C9
            DB      $03,$D0,$15,$A5,$E3,$CD,$B8,$79,$D0,$0E,$20,$F6,$46,$A0,$28,$B1
            DB      $FE,$C9,$07,$F0,$03,$4C,$6D,$87,$20,$F6,$46,$A0,$28,$B1,$FE,$18
            DB      $69,$10,$20,$E4,$46,$C9,$08,$90,$10,$20,$BA,$46,$AD,$CD,$C9,$D3
            DB      $D3,$C5,$C4,$A1,$FF,$00,$4C,$EE,$85,$20,$BA,$46,$AD,$C8,$C9,$D4
            DB      $A1,$FF,$00
; --- End data region (83 bytes) ---

; XREF: 1 ref (1 jump) from render_combat_load_dest
render_combat_resolve  jsr  $46F6           ; A=[$A500] X=$0040 Y=$0000 ; [SP-1828]
            lda  $CE             ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1828]
            lsr  a               ; A=[$00CE] X=$0040 Y=$0000 ; [SP-1828]
            and  #$0F            ; A=A&$0F X=$0040 Y=$0000 ; [SP-1828]
            tax                  ; A=A&$0F X=A Y=$0000 ; [SP-1828]
            lda  $8914,X         ; A=A&$0F X=A Y=$0000 ; [SP-1828]
            lsr  a               ; A=A&$0F X=A Y=$0000 ; [SP-1828]
            lsr  a               ; A=A&$0F X=A Y=$0000 ; [SP-1828]
            lsr  a               ; A=A&$0F X=A Y=$0000 ; [SP-1828]
            ldy  #$1C            ; A=A&$0F X=A Y=$001C ; [SP-1828]
            adc  ($FE),Y         ; A=A&$0F X=A Y=$001C ; [SP-1828]
            ora  #$01            ; A=A|$01 X=A Y=$001C ; [SP-1828]
            jsr  $46E4           ; Call $0046E4(A, Y)
            adc  #$01            ; A=A+$01 X=A Y=$001C ; [SP-1830]
            jsr  combat_binary_to_bcd       ; A=A+$01 X=A Y=$001C ; [SP-1832]
            jsr  combat_apply_damage       ; A=A+$01 X=A Y=$001C ; [SP-1834]
            lda  $835E           ; A=[$835E] X=A Y=$001C ; [SP-1834]
            and  #$03            ; A=A&$03 X=A Y=$001C ; [SP-1834]
            asl  a               ; A=A&$03 X=A Y=$001C ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1834]
            asl  a               ; A=A&$03 X=A Y=$001C ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1834]
            asl  a               ; A=A&$03 X=A Y=$001C ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1834]
            asl  a               ; A=A&$03 X=A Y=$001C ; [SP-1834]
            jsr  combat_apply_damage       ; A=A&$03 X=A Y=$001C ; [SP-1836]
            jsr  render_encrypt_records        ; A=A&$03 X=A Y=$001C ; [SP-1838]
            ldy  $D5             ; A=A&$03 X=A Y=$001C ; [SP-1838]
            lda  $99A0,Y         ; -> $99BC ; A=A&$03 X=A Y=$001C ; [SP-1838]
            sta  $02             ; A=A&$03 X=A Y=$001C ; [SP-1838]
            lda  $99A4,Y         ; -> $99C0 ; A=A&$03 X=A Y=$001C ; [SP-1838]
            sta  $03             ; A=A&$03 X=A Y=$001C ; [SP-1838]
            jsr  combat_tile_at_xy      ; A=A&$03 X=A Y=$001C ; [SP-1840]
            lda  $1F             ; A=[$001F] X=A Y=$001C ; [SP-1840]
            sta  ($FE),Y         ; A=[$001F] X=A Y=$001C ; [SP-1840]
            jsr  $0328           ; A=[$001F] X=A Y=$001C ; [SP-1842]
            lda  #$F7            ; A=$00F7 X=A Y=$001C ; [SP-1842]
            jsr  $4705           ; Call $004705(A, Y)
            ldy  #$00            ; A=$00F7 X=A Y=$0000 ; [SP-1844]
            ldx  $D5             ; A=$00F7 X=A Y=$0000 ; [SP-1844]
            lda  $99AC,X         ; A=$00F7 X=A Y=$0000 ; [SP-1844]
            sta  ($FE),Y         ; A=$00F7 X=A Y=$0000 ; [SP-1844]
            jsr  $0328           ; A=$00F7 X=A Y=$0000 ; [SP-1846]
            jsr  render_encrypt_records        ; A=$00F7 X=A Y=$0000 ; [SP-1848]
            jsr  $46F6           ; Call $0046F6(Y)
            ldy  #$11            ; A=$00F7 X=A Y=$0011 ; [SP-1850]
            lda  ($FE),Y         ; A=$00F7 X=A Y=$0011 ; [SP-1850]
            cmp  #$C4            ; A=$00F7 X=A Y=$0011 ; [SP-1850]
            bne  render_combat_status_upd      ; A=$00F7 X=A Y=$0011 ; [SP-1850]
            jsr  $46BA           ; A=$00F7 X=A Y=$0011 ; [SP-1852]

; --- Data region (51 bytes) ---
            DB      $CB,$C9,$CC,$CC,$C5,$C4,$A1,$A1,$A1,$FF,$00,$A6,$D5,$BD,$A0,$99
            DB      $85,$02,$BD,$A4,$99,$85,$03,$20,$18,$7E,$BD,$A8,$99,$91,$FE,$A9
            DB      $FF,$9D,$A0,$99,$9D,$A4,$99,$20,$28,$03,$20,$B4,$71,$C9,$0F,$F0
            DB      $02,$68,$60
; --- End data region (51 bytes) ---

; XREF: 2 refs (2 branches) from $00880D, render_combat_resolve
render_combat_status_upd  jsr  move_display_party_status       ; A=$00F7 X=A Y=$0011 ; [SP-1860]
            lda  #$18            ; A=$0018 X=A Y=$0011 ; [SP-1860]
            sta  $F9             ; A=$0018 X=A Y=$0011 ; [SP-1860]
            lda  #$17            ; A=$0017 X=A Y=$0011 ; [SP-1860]
            sta  $FA             ; A=$0017 X=A Y=$0011 ; [SP-1860]
            jmp  render_combat_monster_ai      ; A=$0017 X=A Y=$0011 ; [SP-1860]

; ---------------------------------------------------------------------------
; render_party_member  [1 call]
;   Called by: render_combat_tile_drop
; ---------------------------------------------------------------------------

; FUNC $00881F: register -> A:X []
; Proto: uint32_t func_00881F(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [7 dead stores]
; XREF: 1 ref (1 call) from render_combat_tile_drop
render_party_member  jsr  $46F6           ; A=$0017 X=A Y=$0011 ; [SP-1862]
            jsr  $46E7           ; A=$0017 X=A Y=$0011 ; [SP-1864]
            bmi  render_party_armor_drop   ; A=$0017 X=A Y=$0011 ; [SP-1864]
            jsr  $46E7           ; A=$0017 X=A Y=$0011 ; [SP-1866]
            and  #$0F            ; A=A&$0F X=A Y=$0011 ; [SP-1866]
            beq  render_party_exit      ; A=A&$0F X=A Y=$0011 ; [SP-1866]
            ldy  #$30            ; A=A&$0F X=A Y=$0030 ; [SP-1866]
            cmp  ($FE),Y         ; A=A&$0F X=A Y=$0030 ; [SP-1866]
            beq  render_party_exit      ; A=A&$0F X=A Y=$0030 ; [SP-1866]
            clc                  ; A=A&$0F X=A Y=$0030 ; [SP-1866]
            adc  #$30            ; A=A+$30 X=A Y=$0030 ; [SP-1866]
            tay                  ; A=A+$30 X=A Y=A ; [SP-1866]
            lda  ($FE),Y         ; A=A+$30 X=A Y=A ; [SP-1866]
            beq  render_party_exit      ; A=A+$30 X=A Y=A ; [SP-1866]
            lda  #$00            ; A=$0000 X=A Y=A ; [SP-1866]
            sta  ($FE),Y         ; A=$0000 X=A Y=A ; [SP-1866]
            jmp  $885C           ; " :FPLR-"
; XREF: 1 ref (1 branch) from render_party_member
render_party_armor_drop jsr  $46E7           ; A=$0000 X=A Y=A ; [SP-1868]
            and  #$07            ; A=A&$07 X=A Y=A ; [SP-1868]
            beq  render_party_exit      ; A=A&$07 X=A Y=A ; [SP-1868]
            ldy  #$28            ; A=A&$07 X=A Y=$0028 ; [SP-1868]
            cmp  ($FE),Y         ; A=A&$07 X=A Y=$0028 ; [SP-1868]
            beq  render_party_exit      ; A=A&$07 X=A Y=$0028 ; [SP-1868]
            clc                  ; A=A&$07 X=A Y=$0028 ; [SP-1868]
            adc  #$28            ; A=A+$28 X=A Y=$0028 ; [SP-1868]
            tay                  ; A=A+$28 X=A Y=A ; [SP-1868]
            lda  ($FE),Y         ; A=A+$28 X=A Y=A ; [SP-1868]
            beq  render_party_exit      ; A=A+$28 X=A Y=A ; [SP-1868]
            lda  #$00            ; A=$0000 X=A Y=A ; [SP-1868]
            sta  ($FE),Y         ; A=$0000 X=A Y=A ; [SP-1868]
            jsr  $46BA           ; Call $0046BA(A)
            bne  render_party_drop_jmp   ; A=$0000 X=A Y=A ; [SP-1870]
            DB      $D2
            lda  $A500           ; A=[$A500] X=A Y=A ; [SP-1870]

; ---
            DB      $D5,$18,$69,$01
render_party_data
            DB      $20,$D2,$46,$20,$BA,$46,$AD,$D0,$C9,$CC,$C6,$C5,$D2
; ---

            cmp  $C4             ; A=[$A500] X=A Y=A ; [SP-1877]

; ---
            DB      $A1,$FF,$00,$A9,$FA,$20,$05,$47
; ---

; XREF: 6 refs (6 branches) from render_party_member, render_animate, render_animate, render_party_armor_drop, render_party_armor_drop, ...
render_party_exit  rts                  ; A=[$A500] X=A Y=A ; [SP-1877]

; ---------------------------------------------------------------------------
; render_get_tile_char  [1 call]
;   Called by: render_combat_tile_check
; ---------------------------------------------------------------------------

; FUNC $008881: register -> A:X []
; Proto: uint32_t func_008881(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y)
; XREF: 1 ref (1 call) from render_combat_tile_check
render_get_tile_char    jsr  $46E7           ; A=[$A500] X=A Y=A ; [SP-1879]
            and  #$03            ; A=A&$03 X=A Y=A ; [SP-1879]
            beq  render_tile_check_status     ; A=A&$03 X=A Y=A ; [SP-1879]

; === while loop starts here [nest:8] ===
; XREF: 1 ref (1 branch) from render_tile_check_status
render_tile_char_done rts                  ; A=A&$03 X=A Y=A ; [SP-1877]
; XREF: 1 ref (1 branch) from render_get_tile_char
render_tile_check_status jsr  $46F6           ; A=A&$03 X=A Y=A ; [SP-1879]
            ldy  #$11            ; A=A&$03 X=A Y=$0011 ; [SP-1879]
            lda  ($FE),Y         ; A=A&$03 X=A Y=$0011 ; [SP-1879]
            cmp  #$C7            ; A=A&$03 X=A Y=$0011 ; [SP-1879]
            bne  render_tile_char_done     ; A=A&$03 X=A Y=$0011 ; [SP-1879]
; === End of while loop ===

            lda  #$D0            ; A=$00D0 X=A Y=$0011 ; [SP-1879]
            sta  ($FE),Y         ; A=$00D0 X=A Y=$0011 ; [SP-1879]
            jsr  $46BA           ; A=$00D0 X=A Y=$0011 ; [SP-1881]
            bne  render_party_data     ; A=$00D0 X=A Y=$0011 ; [SP-1881]
            DB      $D2
            lda  $A500           ; A=[$A500] X=A Y=$0011 ; [SP-1881]

; ---
            DB      $D5,$18,$69,$01,$20,$D2,$46,$20,$BA,$46,$AD,$D0,$CF,$C9,$D3,$CF
            DB      $CE,$C5,$C4,$A1,$FF,$00,$A9,$FA,$20,$05,$47,$60
; ---


; ---------------------------------------------------------------------------
; render_calc_offset  [3 calls]
;   Called by: render_party_status_disp, render_combat_load_turn, game_loop_get_viewport
; ---------------------------------------------------------------------------

; FUNC $0088BD: register -> A:X [L]
; Proto: uint32_t func_0088BD(void);
; Liveness: returns(A,X,Y) [3 dead stores]
; XREF: 3 refs (3 calls) from render_party_status_disp, render_combat_load_turn, game_loop_get_viewport
render_calc_offset lda  $D5             ; A=[$00D5] X=A Y=$0011 ; [SP-1890]
            asl  a               ; A=[$00D5] X=A Y=$0011 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1890]

; === while loop starts here [nest:7] ===
; XREF: 1 ref (1 branch) from render_encrypt_vblank
render_offset_shift asl  a               ; A=[$00D5] X=A Y=$0011 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1890]
            asl  a               ; A=[$00D5] X=A Y=$0011 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1890]
            asl  a               ; A=[$00D5] X=A Y=$0011 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1890]
            asl  a               ; A=[$00D5] X=A Y=$0011 ; [SP-1890]
            clc                  ; A=[$00D5] X=A Y=$0011 ; [SP-1890]
            adc  #$07            ; A=A+$07 X=A Y=$0011 ; [SP-1890]
            tax                  ; A=A+$07 X=A Y=$0011 ; [SP-1890]
            ldy  #$1F            ; A=A+$07 X=A Y=$001F ; [SP-1890]
            lda  #$07            ; A=$0007 X=A Y=$001F ; [SP-1890]
            sta  $F3             ; A=$0007 X=A Y=$001F ; [SP-1890]

; === while loop starts here [nest:8] ===
; XREF: 1 ref (1 branch) from render_offset_end
render_offset_xor_loop lda  $4300,X         ; A=$0007 X=A Y=$001F ; [SP-1890]
            sta  $FE             ; A=$0007 X=A Y=$001F ; [SP-1890]
            lda  $43C0,X         ; A=$0007 X=A Y=$001F ; [SP-1890]
            sta  $FF             ; A=$0007 X=A Y=$001F ; [SP-1890]
            lda  ($FE),Y         ; A=$0007 X=A Y=$001F ; [SP-1890]
            eor  #$FF            ; A=A^$FF X=A Y=$001F ; [SP-1890]
            sta  ($FE),Y         ; A=A^$FF X=A Y=$001F ; [SP-1890]
            dex                  ; A=A^$FF X=X-$01 Y=$001F ; [SP-1890]
            dec  $F3             ; A=A^$FF X=X-$01 Y=$001F ; [SP-1890]
            bpl  render_offset_xor_loop  ; A=A^$FF X=X-$01 Y=$001F ; [SP-1890]
; === End of while loop ===

            rts                  ; A=A^$FF X=X-$01 Y=$001F ; [SP-1888]

; ###########################################################################
; ###                                                                     ###
; ###          ANTI-CHEAT ENCRYPTION ($88BD-$8930)                        ###
; ###                                                                     ###
; ###########################################################################
;
;   Ultima III XOR-encrypts character records in RAM as an anti-tampering
;   measure. Since the Apple II had no memory protection, players with
;   tools like The Inspector or Locksmith could freeze the game, edit
;   memory, and give themselves 99 of everything. Richard Garriott's
;   solution: XOR every stat byte with $FF after each access, making
;   raw memory inspection show garbage values.
;
;   Two encryption functions exist:
;   - render_calc_offset: XOR 8 bytes at offsets $18-$1F (via table lookup)
;     These are HP, MaxHP, EXP — the "combat stats" that players would
;     most want to cheat. Only encrypts one character at a time.
;   - render_encrypt_records: XOR bytes $18-$26 across ALL 25 character
;     page entries (PLRS area). This is the bulk encryption called
;     29 times throughout the engine — before/after every disk I/O,
;     combat resolution, turn processing, etc.
;
;   The $4300/$43C0 address tables map character page indices to their
;   base addresses in the PLRS area ($4000-$49FF). Each entry points
;   to one 64-byte character record, giving 25 possible roster slots.
;

; ---------------------------------------------------------------------------
; render_encrypt_records — Bulk XOR-encrypt all character stat fields
; ---------------------------------------------------------------------------
;
;   PURPOSE: Toggles XOR $FF encryption on bytes $18-$26 of all active
;            character records. Since XOR is self-inverse, the same function
;            both encrypts and decrypts. Called before and after any
;            operation that reads or modifies character stats.
;
;   ALGORITHM:
;   - Compute starting page index: $D5 * 32 + $1F (slot offset)
;   - For 24 character pages: XOR bytes Y=$26 down to Y=$18
;   - Address lookup: $4300,X = low byte, $43C0,X = high byte of page
;
;   WHY $18-$26: These offsets cover race ($16/17/18... actually $18+)
;   through gold ($24), encompassing all BCD stat values that a cheater
;   would target. Name bytes ($00-$0D) are left unencrypted.
;
;   PARAMS:  $D5 = current character slot (determines starting offset)
;   RETURNS: All character stats toggled between encrypted/decrypted state
;
; XREF: 29 refs (16 calls)
render_encrypt_records    lda  $D5             ; Current character slot
            asl  a               ; Slot * 2
            asl  a               ; Slot * 4
            asl  a               ; Slot * 8
            asl  a               ; Slot * 16
            asl  a               ; Slot * 32 (each page = 32-byte stride)
            clc                  ; A=[$00D5] X=X-$01 Y=$001F ; [SP-1888]
            adc  #$1F            ; A=A+$1F X=X-$01 Y=$001F ; [SP-1888]
            sta  $FB             ; A=A+$1F X=X-$01 Y=$001F ; [SP-1888]
            lda  #$18            ; A=$0018 X=X-$01 Y=$001F ; [SP-1888]
            sta  $F3             ; A=$0018 X=X-$01 Y=$001F ; [SP-1888]

; === while loop starts here [nest:9] ===
; XREF: 1 ref (1 branch) from render_encrypt_inner
render_encrypt_outer ldx  $FB             ; A=$0018 X=X-$01 Y=$001F ; [SP-1888]
            lda  $4300,X         ; A=$0018 X=X-$01 Y=$001F ; [SP-1888]
            sta  $FE             ; A=$0018 X=X-$01 Y=$001F ; [SP-1888]
            lda  $43C0,X         ; A=$0018 X=X-$01 Y=$001F ; [SP-1888]
            sta  $FF             ; A=$0018 X=X-$01 Y=$001F ; [SP-1888]
            ldy  #$26            ; A=$0018 X=X-$01 Y=$0026 ; [SP-1888]

; === while loop starts here [nest:10] ===
; XREF: 1 ref (1 branch) from render_encrypt_inner
render_encrypt_inner lda  ($FE),Y         ; A=$0018 X=X-$01 Y=$0026 ; [SP-1888]
            eor  #$FF            ; A=A^$FF X=X-$01 Y=$0026 ; [SP-1888]
            sta  ($FE),Y         ; A=A^$FF X=X-$01 Y=$0026 ; [SP-1888]
            dey                  ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1888]
            cpy  #$18            ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1888]
            bcs  render_encrypt_inner     ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1888]
; === End of while loop ===

            dec  $FB             ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1888]
            dec  $F3             ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1888]
            bne  render_encrypt_outer     ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1888]
; === End of while loop ===

            rts                  ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1886]

; === while loop starts here [nest:7] ===
; XREF: 1 ref (1 branch) from render_encrypt_vblank
render_encrypt_prng_call jsr  $F020           ; Call $00F020(A, X, Y)
            beq  render_offset_end  ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1888]
            rts                  ; A=A^$FF X=X-$01 Y=$0025 ; [SP-1886]
render_encrypt_vblank ldy  #$80            ; A=A^$FF X=X-$01 Y=$0080 ; [SP-1886]
            bmi  render_text_set_cursor  ; A=A^$FF X=X-$01 Y=$0080 ; [SP-1886]
            bvs  render_offset_shift  ; A=A^$FF X=X-$01 Y=$0080 ; [SP-1886]
            cpy  #$E0            ; A=A^$FF X=X-$01 Y=$0080 ; [SP-1886]
            beq  render_encrypt_prng_call     ; A=A^$FF X=X-$01 Y=$0080 ; [SP-1886]
            tay                  ; A=A^$FF X=X-$01 Y=A ; [SP-1886]
            lda  #$00            ; A=$0000 X=X-$01 Y=A ; [SP-1886]
            sta  $FE             ; A=$0000 X=X-$01 Y=A ; [SP-1886]
            lda  #$98            ; A=$0098 X=X-$01 Y=A ; [SP-1886]
            sta  $FF             ; A=$0098 X=X-$01 Y=A ; [SP-1886]
            ldx  #$00            ; A=$0098 X=$0000 Y=A ; [SP-1886]
            jmp  render_text_read_char  ; A=$0098 X=$0000 Y=A ; [SP-1886]

; ---------------------------------------------------------------------------
; render_draw_text_row — Look up and print the Nth name from the name table
; ---------------------------------------------------------------------------
;
;   PURPOSE: The name table at $897A contains all entity names in the game
;            as null-terminated strings packed consecutively. This function
;            walks through the table, counting null terminators to find the
;            Nth entry (passed in A), then prints it character by character.
;
;            Name table layout (921 bytes at $897A):
;              0: "(null)"  — empty/ground
;              1: "WATER"   — terrain names (0-13)
;              14: "HORSE"  — transport names
;              17: "MERCHANT" — NPC types
;              21: "FIGHTER" — class names (21-31)
;              32: "ORC"    — monster primary names
;              48-63: single letters — dungeon labels
;              64+: weapons, armor, spells, more monsters
;
;            The $FF delimiter between names doubles as a newline in the
;            rendering logic (render_text_newline). This dual use of $FF
;            is a space-saving trick — one byte serves as both separator
;            and formatting control.
;
;   PARAMS:  A = name index (0-based, up to ~130 entries)
;   RETURNS: Name printed to screen at current cursor position ($F9/$FA)
;
; XREF: 14 refs (14 calls)
render_draw_text_row tay                  ; Y = name index (skip counter)
            lda  #$7A            ; $FE/$FF → $897A (name table start)
            sta  $FE
            lda  #$89
            sta  $FF
            ldx  #$00

; === while loop starts here [nest:7] ===
; XREF: 2 refs (2 jumps) from render_encrypt_vblank, render_text_advance_ptr
render_text_read_char lda  ($FE,X)         ; A=$0089 X=$0000 Y=$0098 ; [SP-1886]
            beq  render_text_dec_row  ; A=$0089 X=$0000 Y=$0098 ; [SP-1886]

; === while loop starts here [nest:7] ===
; XREF: 1 ref (1 jump) from render_text_dec_row
render_text_advance_ptr jsr  render_advance_ptr        ; Call $008973(A)
            jmp  render_text_read_char  ; A=$0089 X=$0000 Y=$0098 ; [SP-1888]
; XREF: 1 ref (1 branch) from render_text_read_char
render_text_dec_row dey                  ; A=$0089 X=$0000 Y=$0097 ; [SP-1888]
            beq  render_text_next_char  ; A=$0089 X=$0000 Y=$0097 ; [SP-1888]
            jmp  render_text_advance_ptr  ; A=$0089 X=$0000 Y=$0097 ; [SP-1888]
; === End of while loop ===


; === while loop starts here [nest:7] ===
; XREF: 3 refs (2 jumps) (1 branch) from render_text_next_char, render_text_dec_row, render_text_set_cursor
render_text_next_char jsr  render_advance_ptr        ; A=$0089 X=$0000 Y=$0097 ; [SP-1890]
            ldx  #$00            ; A=$0089 X=$0000 Y=$0097 ; [SP-1890]
            lda  ($FE,X)         ; A=$0089 X=$0000 Y=$0097 ; [SP-1890]
            beq  render_text_done  ; A=$0089 X=$0000 Y=$0097 ; [SP-1890]
            cmp  #$FF            ; A=$0089 X=$0000 Y=$0097 ; [SP-1890]
            beq  render_text_newline  ; A=$0089 X=$0000 Y=$0097 ; [SP-1890]
            and  #$7F            ; A=A&$7F X=$0000 Y=$0097 ; [SP-1890]
            jsr  $46CC           ; Call $0046CC(X)
            inc  $F9             ; A=A&$7F X=$0000 Y=$0097 ; [SP-1892]
            jmp  render_text_next_char  ; A=A&$7F X=$0000 Y=$0097 ; [SP-1892]
; === End of while loop ===


; === while loop starts here [nest:7] ===
; XREF: 2 refs (2 branches) from render_text_next_char, render_advance_ptr
render_text_done rts                  ; A=A&$7F X=$0000 Y=$0097 ; [SP-1890]
; XREF: 1 ref (1 branch) from render_text_next_char
render_text_newline jsr  $46BD           ; A=A&$7F X=$0000 Y=$0097 ; [SP-1892]
            lda  #$17            ; A=$0017 X=$0000 Y=$0097 ; [SP-1892]
            sta  $FA             ; A=$0017 X=$0000 Y=$0097 ; [SP-1892]
            lda  #$18            ; A=$0018 X=$0000 Y=$0097 ; [SP-1892]
; XREF: 1 ref (1 branch) from render_encrypt_vblank
render_text_set_cursor sta  $F9             ; A=$0018 X=$0000 Y=$0097 ; [SP-1892]
            jmp  render_text_next_char  ; A=$0018 X=$0000 Y=$0097 ; [SP-1892]

; ---------------------------------------------------------------------------
; render_advance_ptr  [2 calls]
;   Called by: render_text_next_char, render_text_advance_ptr
; ---------------------------------------------------------------------------

; FUNC $008973: register -> A:X [IJ]
; Proto: uint32_t func_008973(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Liveness: params(A,X,Y) returns(A,X,Y)
; XREF: 2 refs (2 calls) from render_text_next_char, render_text_advance_ptr
render_advance_ptr    inc  $FE             ; A=$0018 X=$0000 Y=$0097 ; [SP-1892]
            bne  render_text_done  ; A=$0018 X=$0000 Y=$0097 ; [SP-1892]
; === End of while loop ===

            inc  $FF             ; A=$0018 X=$0000 Y=$0097 ; [SP-1892]
            rts                  ; A=$0018 X=$0000 Y=$0097 ; [SP-1890]

; ###########################################################################
; ###                                                                     ###
; ###          NAME TABLE ($897A, 921 bytes)                              ###
; ###                                                                     ###
; ###########################################################################
;
;   The single largest data structure in ULT3 — all entity names in the
;   game packed as null-terminated high-ASCII strings. Every terrain type,
;   NPC, monster, weapon, armor, spell, race, and class name lives here.
;   Total conversion mods replace this entire region via u3edit's
;   `patch compile-names` / `patch import` commands.
;
;   ENCODING: High-bit ASCII ($C1='A' through $DA='Z'). Null bytes ($00)
;   terminate each string. The $FF bytes between some entries serve as
;   line-break markers when rendered by render_draw_text_row.
;
;   BUDGET: 921 bytes total, but the last 30 bytes overlap with the BLOAD
;   tail of the next file load, giving 891 usable bytes for names.
;
;   LAYOUT (by index):
;     0-13:   Terrain names (Ground, Water, Grass, Brush, Forest, Mountains...)
;     14-16:  Transport (Horse, Frigate, Whirlpool)
;     17-20:  NPC types (Serpent, Man-O-War, Pirate, Merchant, Jester, Guard)
;     21-31:  Classes (Fighter, Cleric, Wizard, Thief, Orc...)
;     32-47:  Monster group 1 (Skeleton, Giant, Daemon, Pincher, Dragon...)
;     48-63:  Terrain/location extras (Force Field, Lava, Moon Gate, Wall...)
;     64-79:  Weapons (Hand, Dagger, Mace, Sling, Axe, Bow, Sword...)
;     80-87:  Armor (Skin, Cloth, Leather, Chain, Plate...)
;     88-102: Wizard spells (Repond, Mittar, Lorum, Dor Acron...)
;     103-118: Cleric spells (Pontori, Appar Unem, Sanctu, Luminae...)
;     119+:   Monster group 2 (Brigand, Cutpurse, Goblin, Troll...)
;
; --- Name table data (921 bytes) ---
            DB      $00,$D7,$C1,$D4,$C5,$D2,$00,$C7,$D2,$C1,$D3,$D3,$00,$C2,$D2,$D5
            DB      $D3,$C8,$00
            ASC     "FOREST"
            DB      $00 ; null terminator
            ASC     "MOUNTAINS"
            DB      $00 ; null terminator
            ASC     "DUNGEON"
            DB      $00 ; null terminator
            ASC     "TOWNE"
            DB      $00 ; null terminator
            ASC     "CASTLE"
            DB      $00 ; null terminator
            ASC     "FLOOR"
            DB      $00 ; null terminator
            ASC     "CHEST"
            DB      $00 ; null terminator
            ASC     "HORSE"
            DB      $00 ; null terminator
            ASC     "FRIGATE"
            DB      $00 ; null terminator
            ASC     "WHIRLPOOL"
            DB      $00 ; null terminator
            ASC     "SERPENT"
            DB      $00 ; null terminator
            ASC     "MAN-O-WAR"
            DB      $00 ; null terminator
            ASC     "PIRATE"
            DB      $00 ; null terminator
            ASC     "MERCHANT"
            DB      $00 ; null terminator
            ASC     "JESTER"
            DB      $00 ; null terminator
            ASC     "GUARD"
            DB      $00 ; null terminator
            ASC     "LORD BRITISH"
            DB      $00 ; null terminator
            ASC     "FIGHTER"
            DB      $00 ; null terminator
            ASC     "CLERIC"
            DB      $00 ; null terminator
            ASC     "WIZARD"
            DB      $00 ; null terminator
            ASC     "THIEF"
            DB      $00 ; null terminator
            DB      $CF,$D2,$C3,$00
            ASC     "SKELETON"
            DB      $00 ; null terminator
            ASC     "GIANT"
            DB      $00 ; null terminator
            ASC     "DAEMON"
            DB      $00 ; null terminator
            ASC     "PINCHER"
            DB      $00 ; null terminator
            ASC     "DRAGON"
            DB      $00 ; null terminator
            ASC     "BALRON"
            DB      $00 ; null terminator
            ASC     "EXODUS"
            DB      $00 ; null terminator
            ASC     "FORCE FIELD"
            DB      $00 ; null terminator
            ASC     "LAVA"
            DB      $00 ; null terminator
            ASC     "MOON GATE"
            DB      $00 ; null terminator
            ASC     "WALL"
            DB      $00 ; null terminator
            ASC     "VOID"
            DB      $00 ; null terminator
            ASC     "WALL"
            DB      $00 ; null terminator
            DB      $C1,$00,$C2,$00,$C3,$00,$C4,$00,$C5,$00,$C6,$00,$C7,$00,$C8,$00
            DB      $C9,$00,$D5,$00,$D9,$00,$CC,$00,$CD,$00,$CE,$00,$CF,$00,$D0,$00
            DB      $D7,$00,$D2,$00,$D3,$00,$D4,$00,$D3,$CE,$C1,$CB,$C5,$00,$D3,$CE
            DB      $C1,$CB,$C5,$00,$CD,$C1,$C7,$C9,$C3,$00,$C6,$C9,$D2,$C5,$00
            ASC     "SHRINE"
            DB      $00 ; null terminator
            ASC     "RANGER"
            DB      $00 ; null terminator
            ASC     "HAND"
            DB      $00 ; null terminator
            ASC     "DAGGER"
            DB      $00 ; null terminator
            ASC     "MACE"
            DB      $00 ; null terminator
            ASC     "SLING"
            DB      $00 ; null terminator
            DB      $C1,$D8,$C5,$00,$C2,$CF,$D7,$00,$D3,$D7,$CF,$D2,$C4,$00
            ASC     "2-H-SWD"
            DB      $00 ; null terminator
            ASC     "+2 AXE"
            DB      $00 ; null terminator
            ASC     "+2 BOW"
            DB      $00 ; null terminator
            ASC     "+2 SWD"
            DB      $00 ; null terminator
            ASC     "GLOVES"
            DB      $00 ; null terminator
            ASC     "+4 AXE"
            DB      $00 ; null terminator
            ASC     "+4 BOW"
            DB      $00 ; null terminator
            ASC     "+4 SWD"
            DB      $00 ; null terminator
            ASC     "EXOTIC"
            DB      $00 ; null terminator
            ASC     "SKIN"
            DB      $00 ; null terminator
            ASC     "CLOTH"
            DB      $00 ; null terminator
            ASC     "LEATHER"
            DB      $00 ; null terminator
            ASC     "CHAIN"
            DB      $00 ; null terminator
            ASC     "PLATE"
            DB      $00 ; null terminator
            ASC     "+2 CHAIN"
            DB      $00 ; null terminator
            ASC     "+2 PLATE"
            DB      $00 ; null terminator
            ASC     "EXOTIC"
            DB      $00 ; null terminator
            ASC     "REPOND"
            DB      $00 ; null terminator
            ASC     "MITTAR"
            DB      $00 ; null terminator
            ASC     "LORUM"
            DB      $00 ; null terminator
            ASC     "DOR ACRON"
            DB      $00 ; null terminator
            ASC     "SUR ACRON"
            DB      $00 ; null terminator
            ASC     "FULGAR"
            DB      $00 ; null terminator
            ASC     "DAG ACRON"
            DB      $00 ; null terminator
            ASC     "MENTAR"
            DB      $00 ; null terminator
            ASC     "DAG LORUM"
            DB      $00 ; null terminator
            ASC     "FAL DIVI"
            DB      $00 ; null terminator
            ASC     "NOXUM"
            DB      $00 ; null terminator
            ASC     "DECORP"
            DB      $00 ; null terminator
            ASC     "ALTAIR"
            DB      $00 ; null terminator
            ASC     "DAG MENTAR"
            DB      $00 ; null terminator
            ASC     "NECORP"
            DB      $00 ; null terminator
            DB      $00
            ASC     "PONTORI"
            DB      $00 ; null terminator
            ASC     "APPAR UNEM"
            DB      $00 ; null terminator
            ASC     "SANCTU"
            DB      $00 ; null terminator
            ASC     "LUMINAE"
            DB      $00 ; null terminator
            ASC     "REC SU"
            DB      $00 ; null terminator
            ASC     "REC DU"
            DB      $00 ; null terminator
            ASC     "LIB REC"
            DB      $00 ; null terminator
            ASC     "ALCORT"
            DB      $00 ; null terminator
            ASC     "SEQUITU"
            DB      $00 ; null terminator
            ASC     "SOMINAE"
            DB      $00 ; null terminator
            ASC     "SANCTU MANI"
            DB      $00 ; null terminator
            ASC     "VIEDA"
            DB      $00 ; null terminator
            ASC     "EXCUUN"
            DB      $00 ; null terminator
            ASC     "SURMANDUM"
            DB      $00 ; null terminator
            ASC     "ZXKUQYB"
            DB      $00 ; null terminator
            ASC     "ANJU SERMANI"
            DB      $00 ; null terminator
            ASC     "BRIGAND"
            DB      $00 ; null terminator
            ASC     "CUTPURSE"
            DB      $00 ; null terminator
            ASC     "GOBLIN"
            DB      $00 ; null terminator
            ASC     "TROLL"
            DB      $00 ; null terminator
            ASC     "GHOUL"
            DB      $00 ; null terminator
            ASC     "ZOMBIE"
            DB      $00 ; null terminator
            ASC     "GOLEM"
            DB      $00 ; null terminator
            ASC     "TITAN"
            DB      $00 ; null terminator
            ASC     "GARGOYLE"
            DB      $00 ; null terminator
            ASC     "MANE"
            DB      $00 ; null terminator
            ASC     "SNATCH"
            DB      $00 ; null terminator
            ASC     "BRADLE"
            DB      $00 ; null terminator
            ASC     "GRIFFON"
            DB      $00 ; null terminator
            ASC     "WYVERN"
            DB      $00 ; null terminator
            ASC     "ORCUS"
            DB      $00 ; null terminator
            ASC     "DEVIL"
            DB      $00 ; null terminator
            DB      $A9,$00,$85,$B1,$85,$B0,$A5,$B2,$D0,$FC,$20,$B7,$46,$04
            ASC     "BLOAD DDRW"
            DB      $8D ; CR
            DB      $00 ; null terminator
            DB      $2C,$10,$C0,$A9,$00,$85,$CC,$20,$00,$18,$A9,$04,$85,$B1,$85,$B0
; --- End data region (921 bytes) ---


; === while loop starts here (counter: Y 'iter_y') [nest:3] ===
; XREF: 9 refs (8 jumps) (1 branch) from $009132, render_return_to_game, dungeon_lava, dungeon_fire, render_victory_music, ...
render_return_to_game jsr  combat_check_party_alive     ; A=$0018 X=$0000 Y=$0097 ; [SP-2115]
            cmp  #$0F            ; A=$0018 X=$0000 Y=$0097 ; [SP-2115]
            bne  render_return_to_game     ; A=$0018 X=$0000 Y=$0097 ; [SP-2115]
; === End of while loop ===

            jsr  tile_read_map      ; A=$0018 X=$0000 Y=$0097 ; [SP-2117]
            lda  #$17            ; A=$0017 X=$0000 Y=$0097 ; [SP-2117]
            sta  $FA             ; A=$0017 X=$0000 Y=$0097 ; [SP-2117]
            lda  #$18            ; A=$0018 X=$0000 Y=$0097 ; [SP-2117]
            sta  $F9             ; A=$0018 X=$0000 Y=$0097 ; [SP-2117]
            lda  $CC             ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2117]
            bne  render_dungeon_entry     ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2117]
            jsr  $46BA           ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2119]
            cmp  #$D4            ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2119]

; ---
            DB      $A7
            DB      $D3
            DB      $A0,$C4,$C1,$D2,$CB,$A1,$FF,$00,$20,$C3,$46
; ---

; XREF: 1 ref (1 branch) from render_return_to_game
render_dungeon_entry jsr  $46BA           ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2124]
            ora  $A900,X         ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2124]
            brk  #$85            ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2127]

; --- Data region (137 bytes) ---
            DB      $D1,$85,$D2,$A9,$05,$85,$12,$C6,$D1,$D0,$0B,$C6,$D2,$D0,$07,$C6
            DB      $12,$D0,$03,$4C,$E6,$8D,$20,$1F,$BA,$10,$EC,$2C,$10,$C0,$C9,$8D
            DB      $D0,$03,$4C,$F2,$8D,$C9,$8B,$D0,$03,$4C,$F2,$8D,$C9,$AF,$D0,$03
            DB      $4C,$2C,$8E,$C9,$8A,$D0,$03,$4C,$2C,$8E,$C9,$95,$D0,$03,$4C,$67
            DB      $8E,$C9,$88,$D0,$03,$4C,$93,$8E,$C9,$A0,$D0,$03,$4C,$E6,$8D,$C9
            DB      $C1,$B0,$03,$4C,$35,$51,$C9,$DB,$90,$03,$4C,$35,$51,$38,$E9,$C1
            DB      $0A,$A8,$B9,$B2,$8D,$85,$FE,$B9,$B3,$8D,$85,$FF,$6C,$FE,$00,$F1
            DB      $8E,$F1,$8E,$5C,$53,$0C,$8F,$F1,$8E,$F1,$8E,$69,$5B,$8F,$5D,$F1
            DB      $5F,$4E,$60
dungeon_draw_data
            DB      $37
            DB      $8F
            DB      $F1,$8E,$F6,$60
; --- End data region (137 bytes) ---

dungeon_dispatch  lda  ($61,X)         ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2128]
            DB      $E2
            adc  ($60,X)         ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2128]
dungeon_tile_table
            DB      $8F
            sbc  ($8E),Y         ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2126]
            brk  #$66            ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2126]

; --- Data region (443 bytes) ---
            DB      $F1,$8E,$F1,$8E,$F1,$8E,$4D,$69,$77,$69,$F1,$8E,$5A,$6A,$BA,$6A
            DB      $20,$BA,$46,$D0,$C1,$D3,$D3,$FF,$00,$4C,$C2,$8F,$20,$BA,$46,$C1
            DB      $E4,$F6,$E1,$EE,$E3,$E5,$FF,$00,$A6,$14,$18,$BD,$F5,$93,$65,$00
            DB      $29,$0F,$85,$02,$18,$BD,$F9,$93,$65,$01,$29,$0F,$85,$03,$20,$DE
            DB      $93,$C9,$80,$D0,$03,$4C,$BE,$8E,$A5,$02,$85,$00,$A5,$03,$85,$01
            DB      $20,$00,$18,$4C,$C2,$8F,$20,$BA,$46,$D2,$E5,$F4,$F2,$E5,$E1,$F4
            DB      $FF,$00,$A5,$14,$18,$69,$02,$29,$03,$AA,$18,$BD,$F5,$93,$65,$00
            DB      $29,$0F,$85,$02,$18,$BD,$F9,$93,$65,$01,$29,$0F,$85,$03,$20,$DE
            DB      $93,$30,$65,$A5,$02,$85,$00,$A5,$03,$85,$01,$20,$00,$18,$4C,$C2
            DB      $8F,$20,$BA,$46,$D4,$F5,$F2,$EE,$A0,$F2,$E9,$E7,$E8,$F4,$FF,$00
            DB      $A5,$00,$85,$02,$A5,$01,$85,$03,$20,$DE,$93,$C9,$A0,$B0,$39,$E6
            DB      $14,$A5,$14,$29,$03,$85,$14,$20,$00,$18,$4C,$C2,$8F,$20,$BA,$46
            DB      $D4,$F5,$F2,$EE,$A0,$EC,$E5,$E6,$F4,$FF,$00,$A5,$00,$85,$02,$A5
            DB      $01,$85,$03,$20,$DE,$93,$C9,$A0,$B0,$0E,$C6,$14,$A5,$14,$29,$03
            DB      $85,$14,$20,$00,$18,$4C,$C2,$8F,$20,$BA,$46,$C9,$CE,$D6,$C1,$CC
            DB      $C9,$C4,$A0,$CD,$CF,$D6,$C5,$A1,$FF,$00,$A9,$FF,$20,$05,$47,$4C
            DB      $C2,$8F,$20,$BA,$46,$C9,$CE,$D6,$C1,$CC,$C9,$C4,$A0,$C3,$CD,$C4
            DB      $A1,$FF,$00,$A9,$FF,$20,$05,$47,$4C,$C2,$8F,$20,$BA,$46,$CE,$CF
            DB      $D4,$A0,$C1,$A0,$C4,$CE,$C7,$A0,$C3,$CD,$C4,$A1,$FF,$00,$A9,$FF
            DB      $20,$05,$47,$4C,$C2,$8F,$20,$BA,$46,$C4,$E5,$F3,$E3,$E5,$EE,$E4
            DB      $FF,$00,$A5,$00,$85,$02,$A5,$01,$85,$03,$20,$DE,$93,$10,$03,$4C
            DB      $D8,$8E,$29,$20,$D0,$03,$4C,$D8,$8E,$E6,$13,$20,$00,$18,$4C,$C2
            DB      $8F,$20,$BA,$46,$CB,$EC,$E9,$ED,$E2,$FF,$00,$A5,$00,$85,$02,$A5
            DB      $01,$85,$03,$20,$DE,$93,$29,$10,$D0,$03,$4C,$D8,$8E,$C6,$13,$30
            DB      $06,$20,$00,$18,$4C,$C2,$8F,$4C,$6B,$6E,$20,$BA,$46,$D0,$E5,$E5
            DB      $F2,$A0,$E1,$F4,$A0,$E1,$A0,$E7,$E5,$ED,$A1,$FF
            ASC     "WHO'S GEM-"
            DB      $00 ; null terminator
            DB      $20,$24,$70,$D0,$03,$4C,$35,$6E,$20,$F6,$46,$A0,$25,$B1,$FE,$D0
            DB      $03,$4C,$2E,$60
; --- End data region (443 bytes) ---

; XREF: 1 ref (1 branch) from $008F8C
dungeon_use_gem  sed                  ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2206]
            lda  ($FE),Y         ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2206]
            sec                  ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2206]
            sbc  #$01            ; A=A-$01 X=$0000 Y=$0097 ; [SP-2206]
            sta  ($FE),Y         ; A=A-$01 X=$0000 Y=$0097 ; [SP-2206]
            cld                  ; A=A-$01 X=$0000 Y=$0097 ; [SP-2206]
            lda  #$00            ; A=$0000 X=$0000 Y=$0097 ; [SP-2206]
            sta  $B1             ; A=$0000 X=$0000 Y=$0097 ; [SP-2206]
            sta  $B0             ; A=$0000 X=$0000 Y=$0097 ; [SP-2206]

; === while loop starts here [nest:8] ===
; XREF: 1 ref (1 branch) from dungeon_gem_wait_vbl
dungeon_gem_wait_vbl  lda  $B2             ; A=[$00B2] X=$0000 Y=$0097 ; [SP-2206]
            bne  dungeon_gem_wait_vbl      ; A=[$00B2] X=$0000 Y=$0097 ; [SP-2206]
            jsr  $46B7           ; Call $0046B7(A)

; ---
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D DNGM"
            DB      $8D
            DB      $00 ; null terminator
            DB      $A9,$0A,$85,$B0,$A9,$04,$85,$B1,$20,$00,$94,$4C,$C2,$8F
; ---

; XREF: 11 refs (11 jumps) from $008F34, $008EBB, dungeon_gem_wait_vbl, $008F09, $008ED5, ...
dungeon_turn_process  jsr  $03AF           ; A=[$00B2] X=$0000 Y=$0097 ; [SP-2212]
            jsr  move_process_turn        ; A=[$00B2] X=$0000 Y=$0097 ; [SP-2214]
            jsr  move_display_party_status       ; A=[$00B2] X=$0000 Y=$0097 ; [SP-2216]
            lda  #$17            ; A=$0017 X=$0000 Y=$0097 ; [SP-2216]
            sta  $FA             ; A=$0017 X=$0000 Y=$0097 ; [SP-2216]
            lda  #$18            ; A=$0018 X=$0000 Y=$0097 ; [SP-2216]
            sta  $F9             ; A=$0018 X=$0000 Y=$0097 ; [SP-2216]
            lda  $CC             ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2216]
            beq  dungeon_check_tile      ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2216]
            dec  $CC             ; A=[$00CC] X=$0000 Y=$0097 ; [SP-2216]
; XREF: 1 ref (1 branch) from dungeon_turn_process
dungeon_check_tile  lda  $00             ; A=[$0000] X=$0000 Y=$0097 ; [SP-2216]
            sta  $02             ; A=[$0000] X=$0000 Y=$0097 ; [SP-2216]
            lda  $01             ; A=[$0001] X=$0000 Y=$0097 ; [SP-2216]
            sta  $03             ; A=[$0001] X=$0000 Y=$0097 ; [SP-2216]
            jsr  calc_hgr_scanline      ; A=[$0001] X=$0000 Y=$0097 ; [SP-2218]
            beq  dungeon_random_event      ; A=[$0001] X=$0000 Y=$0097 ; [SP-2218]
            jmp  dungeon_tile_type_1      ; A=[$0001] X=$0000 Y=$0097 ; [SP-2218]
; XREF: 1 ref (1 branch) from dungeon_check_tile
dungeon_random_event  clc                  ; A=[$0001] X=$0000 Y=$0097 ; [SP-2218]
            lda  #$82            ; A=$0082 X=$0000 Y=$0097 ; [SP-2218]
            adc  $13             ; A=$0082 X=$0000 Y=$0097 ; [SP-2218]
            jsr  $46E4           ; Call $0046E4(A)
            bmi  dungeon_calc_encounter      ; A=$0082 X=$0000 Y=$0097 ; [SP-2220]
            jmp  render_return_to_game     ; A=$0082 X=$0000 Y=$0097 ; [SP-2220]
; XREF: 1 ref (1 branch) from dungeon_random_event
dungeon_calc_encounter  lda  $13             ; A=[$0013] X=$0000 Y=$0097 ; [SP-2220]
            clc                  ; A=[$0013] X=$0000 Y=$0097 ; [SP-2220]
            adc  #$02            ; A=A+$02 X=$0000 Y=$0097 ; [SP-2220]
            jsr  $46E4           ; A=A+$02 X=$0000 Y=$0097 ; [SP-2222]
            cmp  #$07            ; A=A+$02 X=$0000 Y=$0097 ; [SP-2222]
            bcc  dungeon_set_encounter      ; A=A+$02 X=$0000 Y=$0097 ; [SP-2222]
            lda  #$06            ; A=$0006 X=$0000 Y=$0097 ; [SP-2222]
; XREF: 1 ref (1 branch) from dungeon_calc_encounter
dungeon_set_encounter  clc                  ; A=$0006 X=$0000 Y=$0097 ; [SP-2222]
            adc  #$18            ; A=A+$18 X=$0000 Y=$0097 ; [SP-2222]
            asl  a               ; A=A+$18 X=$0000 Y=$0097 ; [SP-2222]
            sta  $CE             ; A=A+$18 X=$0000 Y=$0097 ; [SP-2222]
            jsr  calc_hgr_scanline      ; A=A+$18 X=$0000 Y=$0097 ; [SP-2224]
            lda  #$40            ; A=$0040 X=$0000 Y=$0097 ; [SP-2224]
            sta  ($FE),Y         ; A=$0040 X=$0000 Y=$0097 ; [SP-2224]
            jmp  render_combat_update     ; A=$0040 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 jump) from dungeon_check_tile
dungeon_tile_type_1  cmp  #$01            ; A=$0040 X=$0000 Y=$0097 ; [SP-2224]
            bne  dungeon_tile_type_2      ; A=$0040 X=$0000 Y=$0097 ; [SP-2224]
            lda  #$00            ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            sta  ($FE),Y         ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            jmp  dungeon_time_lord      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 branch) from dungeon_tile_type_1
dungeon_tile_type_2  cmp  #$02            ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            bne  dungeon_tile_type_3      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            jmp  dungeon_mark      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 branch) from dungeon_tile_type_2
dungeon_tile_type_3  cmp  #$03            ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            bne  dungeon_tile_type_4      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            jmp  dungeon_fire      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 branch) from dungeon_tile_type_3
dungeon_tile_type_4  cmp  #$04            ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            bne  dungeon_tile_type_5      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            jmp  dungeon_fountain      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 branch) from dungeon_tile_type_4
dungeon_tile_type_5  cmp  #$05            ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            bne  dungeon_tile_type_6      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            jmp  dungeon_chest      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 branch) from dungeon_tile_type_5
dungeon_tile_type_6  cmp  #$06            ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            bne  dungeon_tile_type_8      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            jmp  dungeon_lava      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 branch) from dungeon_tile_type_6
dungeon_tile_type_8  cmp  #$08            ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            bne  dungeon_tile_default      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
            jmp  dungeon_tile_inscription      ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 branch) from dungeon_tile_type_8
dungeon_tile_default  jmp  render_return_to_game     ; A=$0000 X=$0000 Y=$0097 ; [SP-2224]
; XREF: 1 ref (1 jump) from dungeon_tile_type_8
dungeon_tile_inscription  jsr  calc_hgr_scanline      ; Call $0093DE(1 stack)
            lda  #$00            ; A=$0000 X=$0000 Y=$0097 ; [SP-2226]
            sta  ($FE),Y         ; A=$0000 X=$0000 Y=$0097 ; [SP-2226]
            jsr  $46BA           ; A=$0000 X=$0000 Y=$0097 ; [SP-2228]
            cmp  $D3C9           ; A=$0000 X=$0000 Y=$0097 ; [SP-2228]
            DB      $D4
            cmp  $D7A0,Y         ; -> $D837 ; A=$0000 X=$0000 Y=$0097 ; [SP-2230]

; ---
            DB      $D2,$C9,$D4,$C9,$CE,$C7,$BA,$FF,$00,$A5,$13,$18,$69,$01,$20,$24
            DB      $89,$20,$BA,$46,$FF,$00,$4C,$13,$8D
; ---

; XREF: 1 ref (1 jump) from dungeon_tile_type_1
dungeon_time_lord  lda  #$00            ; A=$0000 X=$0000 Y=$0097 ; [SP-2236]
            sta  $B1             ; A=$0000 X=$0000 Y=$0097 ; [SP-2236]
            sta  $B0             ; A=$0000 X=$0000 Y=$0097 ; [SP-2236]

; === while loop starts here [nest:3] ===
; XREF: 1 ref (1 branch) from dungeon_time_wait_vbl
dungeon_time_wait_vbl  lda  $B2             ; A=[$00B2] X=$0000 Y=$0097 ; [SP-2236]
            bne  dungeon_time_wait_vbl      ; A=[$00B2] X=$0000 Y=$0097 ; [SP-2236]
            jsr  $46B7           ; Call $0046B7(A)

; --- Data region (178 bytes, text data) ---
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D TIME"
            DB      $8D
            DB      $00 ; null terminator
            DB      $20,$28,$03,$A9,$0A,$85,$B1,$85,$B0,$20,$BA,$46,$D9,$CF,$D5,$A0
            DB      $D3,$C5,$C5,$A0,$C1,$A0,$D6,$C9,$D3,$C9,$CF,$CE,$FF,$CF,$C6,$A0
            DB      $D4,$C8,$C5,$A0,$D4,$C9,$CD,$C5,$A0,$CC,$CF,$D2,$C4,$FF,$A0,$A0
            DB      $C8,$C5,$A0,$D4,$C5,$CC,$CC,$D3,$A0,$D9,$CF,$D5,$FF,$A0,$D4,$C8
            DB      $C5,$A0,$CF,$CE,$C5,$A0,$D7,$C1,$D9,$A0,$C9,$D3,$FF,$A0,$A0,$A0
            DB      $CC,$CF,$D6,$C5,$AC,$A0,$D3,$CF,$CC,$AC,$FF,$A0,$CD,$CF,$CF,$CE
            DB      $D3,$A0,$A6,$A0,$C4,$C5,$C1,$D4,$C8,$AC,$FF
            ASC     " ALL ELSE FAILS."
            DB      $00 ; null terminator
            DB      $A0,$44,$20,$CF,$46,$A0,$40,$20,$CF,$46,$A0,$40,$20,$CF,$46,$20
            DB      $28,$03,$AD,$00,$C0,$10,$E9,$2C,$10,$C0,$20,$BA,$46,$FF,$00,$20
            DB      $00,$18,$A9,$04,$85,$B1,$4C,$13,$8D
; --- End data region (178 bytes) ---

; XREF: 1 ref (1 jump) from dungeon_tile_type_4
dungeon_fountain  jsr  calc_hgr_scanline      ; A=[$00B2] X=$0000 Y=$0097 ; [SP-2264]
            lda  #$00            ; A=$0000 X=$0000 Y=$0097 ; [SP-2264]
            sta  ($FE),Y         ; A=$0000 X=$0000 Y=$0097 ; [SP-2264]
            jsr  $46BA           ; Call $0046BA(A)
            cmp  ($D2,X)         ; A=$0000 X=$0000 Y=$0097 ; [SP-2266]
            DB      $C7
            iny                  ; A=$0000 X=$0000 Y=$0098 ; [SP-2266]

; --- Data region (49 bytes, text data) ---
            DB      $A1,$A1,$A0,$C1,$A0,$D4,$D2,$C1,$D0,$A1,$A1,$FF,$00,$A9,$F6,$20
            DB      $05,$47,$A9,$00,$85,$D5,$20,$CF,$75,$D0,$10,$20,$BA,$46,$C5,$D6
            DB      $C1,$C4,$C5,$C4,$A1,$A1,$FF,$00,$4C,$13,$8D,$20,$63,$5C,$4C,$13
            DB      $8D
; --- End data region (49 bytes) ---

; XREF: 1 ref (1 jump) from dungeon_tile_type_2
dungeon_mark  lda  #$00            ; A=$0000 X=$0000 Y=$0098 ; [SP-2273]
            sta  $B1             ; A=$0000 X=$0000 Y=$0098 ; [SP-2273]
            sta  $B0             ; A=$0000 X=$0000 Y=$0098 ; [SP-2273]

; === while loop starts here [nest:3] ===
; XREF: 1 ref (1 branch) from dungeon_mark_wait_vbl
dungeon_mark_wait_vbl  lda  $B2             ; A=[$00B2] X=$0000 Y=$0098 ; [SP-2273]
            bne  dungeon_mark_wait_vbl      ; A=[$00B2] X=$0000 Y=$0098 ; [SP-2273]
            jsr  $46B7           ; Call $0046B7(A)

; --- Data region (320 bytes, text data) ---
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D FNTN"
            DB      $8D
            DB      $00 ; null terminator
            DB      $20,$28,$03,$A9,$0A,$85,$B1,$85,$B0,$A9,$17,$85,$FA,$A9,$18,$85
            DB      $F9,$20,$BA,$46,$FF,$C1,$A0,$C6,$CF,$D5,$CE,$D4,$C1,$C9,$CE,$AC
            DB      $A0,$D7,$C8,$CF,$FF
            ASC     "WILL DRINK? - "
            DB      $00 ; null terminator
            DB      $A9,$00,$85,$E2,$20,$24,$70,$48,$A9,$01,$85,$E2,$68,$D0,$0C,$20
            DB      $00,$18,$A9,$04,$85,$B1,$85,$B0,$4C,$13,$8D,$20,$BA,$75,$F0,$13
            DB      $20,$BA,$46,$C3,$C1,$CE,$A7,$D4,$A1,$FF,$00,$A9,$FF,$20,$05,$47
            DB      $4C,$97,$91,$A5,$00,$29,$03,$F0,$38,$C9,$01,$D0,$03,$4C,$61,$92
            DB      $C9,$02,$D0,$03,$4C,$8D,$92,$20,$BA,$46,$C1,$C8,$A1,$A0,$D4,$C8
            DB      $C1,$D4,$A7,$D3,$A0,$CE,$C9,$C3,$C5,$A1,$FF,$00,$20,$F6,$46,$A0
            DB      $11,$B1,$FE,$C9,$D0,$D0,$04,$A9,$C7,$91,$FE,$20,$38,$73,$4C,$97
            DB      $91,$20,$F6,$46,$A0,$11,$A9,$D0,$91,$FE,$20,$BA,$46,$D9,$D5,$C3
            DB      $CB,$A1,$A0,$C8,$CF,$D2,$D2,$C9,$C2,$CC,$C5,$A1,$FF,$00,$20,$E4
            DB      $88,$A9,$F7,$20,$05,$47,$20,$E4,$88,$20,$38,$73,$4C,$97,$91,$20
            DB      $F6,$46,$A0,$1C,$B1,$FE,$A0,$1A,$91,$FE,$A0,$1D,$B1,$FE,$A0,$1B
            DB      $91,$FE,$20,$BA,$46,$C8,$CF,$D7,$A0,$D7,$CF,$CE,$C4,$C5,$D2,$C6
            DB      $D5,$CC,$A1,$FF,$00,$20,$38,$73,$4C,$97,$91,$20,$BA,$46,$C1,$D2
            DB      $C7,$C8,$A1,$A0,$C2,$CC,$C1,$C8,$A1,$A0,$D9,$D5,$CB,$A1,$FF,$00
            DB      $20,$F6,$46,$A9,$25,$20,$81,$71,$20,$E9,$58,$20,$E4,$88,$A9,$F7
            DB      $20,$05,$47,$20,$E4,$88,$20,$E9,$58,$20,$38,$73,$4C,$97,$91
; --- End data region (320 bytes) ---

; XREF: 1 ref (1 jump) from dungeon_tile_type_3
dungeon_fire  jsr  $46BA           ; A=[$00B2] X=$0000 Y=$0098 ; [SP-2337]

; ---
            ASC     "STRANGE WIND!"
            DB      $FF,$00,$A9,$00,$85,$CC,$4C,$13,$8D
; ---

; XREF: 1 ref (1 jump) from dungeon_tile_type_6
dungeon_lava  jsr  calc_hgr_scanline      ; A=[$00B2] X=$0000 Y=$0098 ; [SP-2339]
            lda  #$00            ; A=$0000 X=$0000 Y=$0098 ; [SP-2339]
            sta  ($FE),Y         ; A=$0000 X=$0000 Y=$0098 ; [SP-2339]
            lda  $E1             ; A=[$00E1] X=$0000 Y=$0098 ; [SP-2339]
            jsr  $46E4           ; A=[$00E1] X=$0000 Y=$0098 ; [SP-2341]
            sta  $D5             ; A=[$00E1] X=$0000 Y=$0098 ; [SP-2341]
            jsr  magic_resolve_effect       ; A=[$00E1] X=$0000 Y=$0098 ; [SP-2343]
            beq  dungeon_trap_setup      ; A=[$00E1] X=$0000 Y=$0098 ; [SP-2343]
            jmp  render_return_to_game     ; A=[$00E1] X=$0000 Y=$0098 ; [SP-2343]
; XREF: 1 ref (1 branch) from dungeon_lava
dungeon_trap_setup  ldy  #$20            ; A=[$00E1] X=$0000 Y=$0020 ; [SP-2343]
            lda  ($FE),Y         ; A=[$00E1] X=$0000 Y=$0020 ; [SP-2343]
            bne  dungeon_trap_bcd      ; A=[$00E1] X=$0000 Y=$0020 ; [SP-2343]
            jsr  equip_handle        ; A=[$00E1] X=$0000 Y=$0020 ; [SP-2345]
            jmp  dungeon_trap_damage      ; A=[$00E1] X=$0000 Y=$0020 ; [SP-2345]
; XREF: 1 ref (1 branch) from dungeon_trap_setup
dungeon_trap_bcd  sed                  ; A=[$00E1] X=$0000 Y=$0020 ; [SP-2345]
            sec                  ; A=[$00E1] X=$0000 Y=$0020 ; [SP-2345]
            sbc  #$01            ; A=A-$01 X=$0000 Y=$0020 ; [SP-2345]
            cld                  ; A=A-$01 X=$0000 Y=$0020 ; [SP-2345]
            sta  ($FE),Y         ; A=A-$01 X=$0000 Y=$0020 ; [SP-2345]
; XREF: 1 ref (1 jump) from dungeon_trap_setup
dungeon_trap_damage  lda  #$FA            ; A=$00FA X=$0000 Y=$0020 ; [SP-2345]
            jsr  $4705           ; Call $004705(Y)
            jsr  $46BA           ; A=$00FA X=$0000 Y=$0020 ; [SP-2349]

; ---
            DB      $C7
            ASC     "REMLINS!"
            DB      $FF,$00,$20,$38,$73,$4C,$13,$8D
; ---

; XREF: 1 ref (1 jump) from dungeon_tile_type_5
dungeon_chest  lda  #$00            ; A=$0000 X=$0000 Y=$0020 ; [SP-2349]
            sta  $B1             ; A=$0000 X=$0000 Y=$0020 ; [SP-2349]
            sta  $B0             ; A=$0000 X=$0000 Y=$0020 ; [SP-2349]

; === while loop starts here ===
; XREF: 1 ref (1 branch) from dungeon_chest_status
dungeon_chest_status  lda  $B2             ; A=[$00B2] X=$0000 Y=$0020 ; [SP-2349]
            bne  dungeon_chest_status      ; A=[$00B2] X=$0000 Y=$0020 ; [SP-2349]
            jsr  $46B7           ; A=[$00B2] X=$0000 Y=$0020 ; [SP-2351]

; --- Data region (181 bytes) ---
            DB      $04 ; string length
            ASC     "BLOA"
            ASC     "D BRND"
            DB      $8D
            DB      $00 ; null terminator
            DB      $20,$28,$03,$A9,$0A,$85,$B1,$85,$B0,$A9,$17,$85,$FA,$A9,$18,$85
            DB      $F9,$20,$BA,$46,$C1,$A0,$D2,$C5,$C4,$A0,$C8,$CF,$D4,$A0,$D2,$CF
            DB      $C4,$FF,$C9,$CE,$A0,$D4,$C8,$C5,$A0,$D7,$C1,$CC,$CC,$AC,$A0,$D7
            DB      $C8,$CF,$FF
            ASC     "WILL TOUCH?-"
            DB      $00 ; null terminator
            DB      $A9,$00,$85,$E2,$20,$24,$70,$48,$A9,$01,$85,$E2,$68,$D0,$0F,$20
            DB      $00,$18,$20,$38,$73,$A9,$04,$85,$B1,$85,$B0,$4C,$13,$8D,$A5,$00
            DB      $29,$03,$18,$69,$04,$A8,$20,$D3,$93,$85,$D0,$20,$F6,$46,$A0,$0E
            DB      $B1,$FE,$05,$D0,$91,$FE,$20,$E4,$88,$A9,$F7,$20,$05,$47,$20,$E4
            DB      $88,$A9,$50,$20,$81,$71,$20,$BA,$46,$C9,$D4,$A0,$CC,$C5,$C6,$D4
            DB      $A0,$C1,$A0,$CD,$C1,$D2,$CB,$A1,$FF,$00,$4C,$85,$93,$A9,$01,$C0
            DB      $00,$F0,$04,$0A,$88,$D0,$FC,$60
; --- End data region (181 bytes) ---


; ###########################################################################
; ###                                                                     ###
; ###          DUNGEON MAP LOOKUP ($93DE)                                 ###
; ###                                                                     ###
; ###########################################################################

; ---------------------------------------------------------------------------
; calc_hgr_scanline — Read a tile from the 16x16 dungeon grid
; ---------------------------------------------------------------------------
;
;   PURPOSE: Despite the CIDAR-generated name suggesting HGR graphics math,
;            this function reads a tile from the dungeon map at $1000+.
;            Dungeon maps are 16x16 grids per level, 8 levels per dungeon,
;            loaded at $1000 (level 0) through $1700 (level 7).
;
;   ALGORITHM: offset = Y*16 + X  (Y << 4 + X)
;     $FE = ($03 << 4) + $02    = Y*16 + X (low byte of address)
;     $FF = $10 + $13            = base page + dungeon level
;     Result: tile = [$1000 + level*256 + Y*16 + X]
;
;   WHY $13: Zero-page $13 holds the current dungeon level (0-7).
;   Adding it to $10 offsets into the correct 256-byte level page.
;   Each level is exactly 256 bytes (16x16), so level addressing is
;   simply a page-number addition — elegant memory layout.
;
;   PARAMS:  $02 = X coordinate (0-15)
;            $03 = Y coordinate (0-15)
;            $13 = dungeon level (0-7)
;   RETURNS: A = tile value at (X,Y) on current dungeon level
;            $FE/$FF = pointer to tile (for in-place modification)
;
; XREF: 11 refs (11 calls)
calc_hgr_scanline  clc
            lda  $03             ; Y coordinate
            asl  a               ; Y*2
            asl  a               ; Y*4
            asl  a               ; Y*8
            asl  a               ; Y*16
            adc  $02             ; Y*16 + X = offset within level
            sta  $FE             ; Low byte of address
            clc
            lda  #$10            ; Base page $10 (dungeon maps at $1000)
            adc  $13             ; + dungeon level → page $10-$17
            sta  $FF             ; High byte of address
            ldy  #$00
            lda  ($FE),Y         ; Read tile value
            rts

; --- Direction delta table (used by dungeon movement commands) ---
;   8 entries: N(0,1), NE(0,-1), etc. — direction X/Y deltas
            DB      $00,$01,$00,$FF,$FF,$00,$01,$00,$32,$22,$0D
