; ===========================================================================
; ULT3.s — Ultima III: Exodus Main Game Engine
; ===========================================================================
;
; 17,408 bytes at $5000. Core game logic, combat, magic, equipment, I/O.
; Reassembled byte-identical from CIDAR disassembly via asmiigs.
;
; Subsystems:
;   $5000-$54FF  Boot / Initialization — game setup, data init, quit handler
;   $5506-$58E8  Character Management — record decrypt/encrypt, field access
;   $58E9-$5C62  Character Field Read — char_decrypt_records (14 callers)
;   $5C63-$6457  Character Field Write — char_combat_turn, BCD arithmetic
;   $6458-$65AF  File I/O — save/load PLRS, PRTY, SOSA, overlays
;   $65B0-$6F42  Game Main Loop — central state machine, command dispatch
;   $6F43-$7086  Location & World — check_location, advance_turn
;   $7087-$71FF  Combat HP & Damage — BCD multiply, apply damage, party alive
;   $7200-$731F  Combat End — termination check, XOR checksum
;   $7320-$7445  Movement Display — save cursor, show party status
;   $7446-$746F  Input — input_wait_key, keyboard polling
;   $7470-$75AD  Turn Processing — move_process_turn, turn resolution
;   $75AE-$761C  Magic — cast spell, resolve effect, check MP
;   $761D-$772C  Equipment — equip_handle, class restrictions
;   $772D-$79FF  Shops & Items — shop_handle, transactions
;   $7961-$7A80  World Movement — world_move_handler, overworld dispatch
;   $7A0C-$7C0B  Dungeon — dungeon_handle, level navigation
;   $7C0C-$7DFF  Tile & Map — passability, special tiles, map read
;   $7E00-$88FF  Rendering — viewport, sprites, animation, HGR math
;   $897A-$8CFF  Name Table — 921 bytes, all entity names (high-ASCII)
;   $93DE        calc_hgr_scanline — HGR scanline address computation
;
; Key Forward References (EQU, mid-instruction entry points):
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
; Zero-Page Usage:
;   $00/$01    map_cursor_x/y        Map/overworld position
;   $02/$03    combat_cursor_x/y     Combat grid position
;   $0E        transport_type        Movement mode (SPEEDZ alias)
;   $0F        animation_slot        Tile animation table offset
;   $10        combat_active_flag    Nonzero = in combat
;   $B0-$B2    disk_io_flags         Disk I/O state
;   $CE        current_tile          Tile under player
;   $D0-$D5    display_state         Viewport rendering state
;   $E0        party_transport       PRTY transport byte
;   $E1        party_size            Active party member count
;   $E2        location_type         PRTY location type
;   $E3/$E4    saved_x/saved_y       PRTY overworld coords
;   $E5        party_sentinel        $FF when party active
;   $E6-$E9    party_slots           Roster indices for 4 members
;   $F0-$F3    temp_work             General scratch registers
;   $F9/$FA    text_cursor_x/y       Text output cursor position
;   $FE/$FF    data_pointer          General data pointer
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

            jsr  $B60F           ; [SP-2]
            jsr  $46B7           ; [SP-4]

; --- Data region (129 bytes) ---
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

; XREF: 1 ref (1 jump) from $005047
boot_setup_game  lda  #$58            ; A=$0058 ; [SP-34]
            sta  $B403           ; A=$0058 ; [SP-34]
            lda  #$FF            ; A=$00FF ; [SP-34]
            sta  $B404           ; A=$00FF ; [SP-34]
            lda  #$00            ; A=$0000 ; [SP-34]
            sta  $CB             ; A=$0000 ; [SP-34]
            sta  $10             ; A=$0000 ; [SP-34]
            jsr  $0230           ; A=$0000 ; [SP-36]
            lda  #$00            ; A=$0000 ; [SP-36]
            sta  $B2             ; A=$0000 ; [SP-36]
            lda  #$01            ; A=$0001 ; [SP-36]
            sta  $B0             ; A=$0001 ; [SP-36]
            sta  $B1             ; A=$0001 ; [SP-36]
            bit  $C010           ; KBDSTRB - Clear keyboard strobe {Keyboard} <keyboard_strobe>

; === while loop starts here (counter: Y 'j') ===
; XREF: 3 refs (3 jumps) from world_move_start, world_move_check_torch, world_move_dungeon
boot_check_quit  lda  $36             ; A=[$0036] ; [SP-36]
            cmp  #$4A            ; A=[$0036] ; [SP-36]
            bne  boot_clear_floor      ; A=[$0036] ; [SP-36]
            lda  $37             ; A=[$0037] ; [SP-36]
            cmp  #$B4            ; A=[$0037] ; [SP-36]
            beq  boot_clear_floor      ; A=[$0037] ; [SP-36]

; === while loop starts here [nest:3] ===
; XREF: 1 ref (1 branch) from boot_clear_floor
boot_quit_pop_rts  pla                  ; A=[stk] ; [SP-35]
; LUMA: epilogue_rts
            rts                  ; A=[stk] ; [SP-33]
; XREF: 2 refs (2 branches) from boot_check_quit, boot_check_quit
boot_clear_floor  lda  #$00            ; A=$0000 ; [SP-33]
            sta  $13             ; A=$0000 ; [SP-33]
            jsr  combat_check_party_alive     ; A=$0000 ; [SP-35]
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

input_dispatch_entry  inc  $CE00,X         ; SLOTEXP_x600 - Slot expansion ROM offset $600 {Slot}
            ora  $52             ; A=$0017 ; [SP-71]
            cmp  #$1A            ; A=$0017 ; [SP-71]
            bne  input_dispatch_jump      ; A=$0017 ; [SP-71]
            pla                  ; A=[stk] ; [SP-70]
            sec                  ; A=[stk] ; [SP-70]
            sbc  #$C1            ; A=A-$C1 ; [SP-70]
            asl  a               ; A=A-$C1 ; [SP-70]
            tay                  ; A=A-$C1 Y=A ; [SP-70]
; LUMA: data_array_y
            lda  $5222,Y         ; A=A-$C1 Y=A ; [SP-70]
            sta  $FE             ; A=A-$C1 Y=A ; [SP-70]
; LUMA: data_array_y
            lda  $5223,Y         ; A=A-$C1 Y=A ; [SP-70]
            sta  $FF             ; A=A-$C1 Y=A ; [SP-70]
; XREF: 1 ref (1 branch) from input_dispatch_entry
input_dispatch_jump  jmp  ($00FE)         ; A=A-$C1 Y=A ; [SP-70]

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


; === while loop starts here (counter: Y 'j') ===
; XREF: 1 ref (1 jump) from tile_update_check_special
input_combat_render_unit  txa                  ; Y=A ; [SP-76]
            pha                  ; Y=A ; [SP-77]
            jsr  $0230           ; Y=A ; [SP-79]
            pla                  ; A=[stk] Y=A ; [SP-78]
            tax                  ; A=[stk] X=[stk] Y=A ; [SP-78]
; LUMA: data_array_x
            lda  $4F40,X         ; A=[stk] X=[stk] Y=A ; [SP-78]
            sta  $02             ; A=[stk] X=[stk] Y=A ; [SP-78]
            lda  $4F60,X         ; A=[stk] X=[stk] Y=A ; [SP-78]
            sta  $03             ; A=[stk] X=[stk] Y=A ; [SP-78]
            jsr  $46FF           ; A=[stk] X=[stk] Y=A ; [SP-80]
; LUMA: data_array_x
            lda  $4F20,X         ; A=[stk] X=[stk] Y=A ; [SP-80]
            beq  input_store_tile      ; A=[stk] X=[stk] Y=A ; [SP-80]
            lsr  a               ; A=[stk] X=[stk] Y=A ; [SP-80]
            lsr  a               ; A=[stk] X=[stk] Y=A ; [SP-80]
            and  #$03            ; A=A&$03 X=[stk] Y=A ; [SP-80]
            clc                  ; A=A&$03 X=[stk] Y=A ; [SP-80]
            adc  #$24            ; A=A+$24 X=[stk] Y=A ; [SP-80]
; XREF: 1 ref (1 branch) from input_combat_render_unit
input_store_tile  sta  ($FE),Y         ; A=A+$24 X=[stk] Y=A ; [SP-80]
; LUMA: data_array_x
            lda  $4F00,X         ; A=A+$24 X=[stk] Y=A ; [SP-80]
            lsr  a               ; A=A+$24 X=[stk] Y=A ; [SP-80]
            sta  $CE             ; A=A+$24 X=[stk] Y=A ; [SP-80]
            pha                  ; A=A+$24 X=[stk] Y=A ; [SP-81]
            lda  #$00            ; A=$0000 X=[stk] Y=A ; [SP-81]
            sta  $4F00,X         ; A=$0000 X=[stk] Y=A ; [SP-81]
            pla                  ; A=[stk] X=[stk] Y=A ; [SP-80]
            cmp  #$1E            ; A=[stk] X=[stk] Y=A ; [SP-80]
            bne  input_jump_render      ; A=[stk] X=[stk] Y=A ; [SP-80]
            lda  $0E             ; A=[$000E] X=[stk] Y=A ; [SP-80]
            cmp  #$16            ; A=[$000E] X=[stk] Y=A ; [SP-80]
            beq  input_jump_render      ; A=[$000E] X=[stk] Y=A ; [SP-80]
            lda  #$2C            ; A=$002C X=[stk] Y=A ; [SP-80]
            sta  ($FE),Y         ; A=$002C X=[stk] Y=A ; [SP-80]
; XREF: 2 refs (2 branches) from input_store_tile, input_store_tile
input_jump_render  jmp  render_combat_update     ; A=$002C X=[stk] Y=A ; [SP-80]

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


; === while loop starts here [nest:7] ===
; XREF: 1 ref (1 branch) from input_spell_check_done
input_spell_pop_rts  pla                  ; A=[stk] X=[stk] Y=A ; [SP-129]
; LUMA: epilogue_rts
            rts                  ; A=[stk] X=[stk] Y=A ; [SP-129]
; LUMA: hw_keyboard_read
; XREF: 2 refs (2 jumps) from $005446, $005422
input_spell_check_done  lda  $5362           ; A=[$5362] X=[stk] Y=A ; [SP-129]
            cmp  #$20            ; A=[$5362] X=[stk] Y=A ; [SP-129]
            bne  input_spell_pop_rts      ; A=[$5362] X=[stk] Y=A ; [SP-129]
; === End of while loop ===

            jsr  $46F6           ; A=[$5362] X=[stk] Y=A ; [SP-131]
            lda  $D7             ; A=[$00D7] X=[stk] Y=A ; [SP-131]
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


; === while loop starts here [nest:7] ===
; XREF: 4 refs (2 jumps) (2 branches) from input_dungeon_gen_pos, input_dungeon_random_pos, $005726, $005587
input_dungeon_gen_pos  lda  #$10            ; A=$0010 X=A Y=$0019 ; [SP-236]
            jsr  $46E4           ; Call $0046E4(A)
            sta  $02             ; A=$0010 X=A Y=$0019 ; [SP-238]
            lda  #$10            ; A=$0010 X=A Y=$0019 ; [SP-238]
            jsr  $46E4           ; A=$0010 X=A Y=$0019 ; [SP-240]
            sta  $03             ; A=$0010 X=A Y=$0019 ; [SP-240]
            jsr  calc_hgr_scanline      ; A=$0010 X=A Y=$0019 ; [SP-242]
            bne  input_dungeon_gen_pos      ; A=$0010 X=A Y=$0019 ; [SP-242]
            lda  $02             ; A=[$0002] X=A Y=$0019 ; [SP-242]
            sta  $00             ; A=[$0002] X=A Y=$0019 ; [SP-242]
            lda  $03             ; A=[$0003] X=A Y=$0019 ; [SP-242]
            sta  $01             ; A=[$0003] X=A Y=$0019 ; [SP-242]
            jmp  input_return_to_loop      ; A=[$0003] X=A Y=$0019 ; [SP-242]

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


; ===========================================================================
; SUBROUTINES (29 functions)
; ===========================================================================

; ---------------------------------------------------------------------------
; char_decrypt_records  [14 calls]
;   Called by: combat_end_flag, input_return_to_loop, input_spell_setup_slot, render_combat_mon_wait, world_move_handler
; ---------------------------------------------------------------------------

; FUNC $0058E9: register -> A:X [I]
; Proto: uint32_t func_0058E9(void);
; Liveness: returns(A,X,Y) [24 dead stores]
; XREF: 14 refs (14 calls) from combat_end_flag, combat_end_flag, combat_end_flag, input_return_to_loop, input_spell_setup_slot, ...
char_decrypt_records   ldx  #$08            ; A=$0003 X=$0008 Y=$0033 ; [SP-310]

; === while loop starts here (counter: X 'iter_x', range: 0..184, iters: 184) [nest:13] ===
; XREF: 1 ref (1 branch) from char_decrypt_inner
char_decrypt_outer lda  $4300,X         ; -> $4308 ; A=$0003 X=$0008 Y=$0033 ; [SP-310]
            sta  $FC             ; A=$0003 X=$0008 Y=$0033 ; [SP-310]
            lda  $43C0,X         ; -> $43C8 ; A=$0003 X=$0008 Y=$0033 ; [SP-310]
            sta  $FD             ; A=$0003 X=$0008 Y=$0033 ; [SP-310]
            ldy  #$16            ; A=$0003 X=$0008 Y=$0016 ; [SP-310]

; === loop starts here (counter: Y, range: 22..0, iters: 22) [nest:14] ===
; XREF: 1 ref (1 branch) from char_decrypt_inner
char_decrypt_inner lda  ($FC),Y         ; A=$0003 X=$0008 Y=$0016 ; [SP-310]
            eor  #$FF            ; A=A^$FF X=$0008 Y=$0016 ; [SP-310]
            sta  ($FC),Y         ; A=A^$FF X=$0008 Y=$0016 ; [SP-310]
            dey                  ; A=A^$FF X=$0008 Y=$0015 ; [SP-310]
            bne  char_decrypt_inner    ; A=A^$FF X=$0008 Y=$0015 ; [SP-310]
; === End of loop (counter: Y) ===

            inx                  ; A=A^$FF X=$0009 Y=$0015 ; [SP-310]
            cpx  #$B8            ; A=A^$FF X=$0009 Y=$0015 ; [SP-310]
            bcc  char_decrypt_outer    ; A=A^$FF X=$0009 Y=$0015 ; [SP-310]
; === End of while loop (counter: X) ===

            ldy  #$80            ; A=A^$FF X=$0009 Y=$0080 ; [SP-310]
            txa                  ; A=$0009 X=$0009 Y=$0080 ; [SP-310]
            sec                  ; A=$0009 X=$0009 Y=$0080 ; [SP-310]
            sbc  #$02            ; A=A-$02 X=$0009 Y=$0080 ; [SP-310]
            ldx  #$10            ; A=A-$02 X=$0010 Y=$0080 ; [SP-310]
            jmp  ($52F3)         ; A=A-$02 X=$0010 Y=$0080 ; [SP-310]

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
; char_combat_turn  [3 calls]
;   Called by: tile_update_bcd_food, game_loop_combat_lookup2
;   Calls: magic_resolve_effect, render_encrypt_records, combat_apply_damage, move_display_party_status
; ---------------------------------------------------------------------------

; FUNC $005C63: register -> A:X [IJ]
; Proto: uint32_t func_005C63(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [3 dead stores]
; XREF: 3 refs (3 calls) from tile_update_bcd_food, game_loop_combat_lookup2, $005C5D
char_combat_turn   lda  $E1             ; A=[$00E1] X=$0010 Y=$0080 ; [SP-456]
            sta  $D5             ; A=[$00E1] X=$0010 Y=$0080 ; [SP-456]
            dec  $D5             ; A=[$00E1] X=$0010 Y=$0080 ; [SP-456]

; === while loop starts here [nest:15] ===
; XREF: 1 ref (1 branch) from char_turn_next
char_turn_loop jsr  magic_resolve_effect       ; A=[$00E1] X=$0010 Y=$0080 ; [SP-458]
            bne  char_turn_next    ; A=[$00E1] X=$0010 Y=$0080 ; [SP-458]
            jsr  render_encrypt_records        ; A=[$00E1] X=$0010 Y=$0080 ; [SP-460]
            lda  #$F7            ; A=$00F7 X=$0010 Y=$0080 ; [SP-460]
            jsr  $4705           ; A=$00F7 X=$0010 Y=$0080 ; [SP-462]
            jsr  render_encrypt_records        ; A=$00F7 X=$0010 Y=$0080 ; [SP-464]
            jsr  $46E7           ; A=$00F7 X=$0010 Y=$0080 ; [SP-466]
            and  #$77            ; A=A&$77 X=$0010 Y=$0080 ; [SP-466]
            jsr  combat_apply_damage       ; A=A&$77 X=$0010 Y=$0080 ; [SP-468]
            lda  $13             ; A=[$0013] X=$0010 Y=$0080 ; [SP-468]
            clc                  ; A=[$0013] X=$0010 Y=$0080 ; [SP-468]
            adc  #$01            ; A=A+$01 X=$0010 Y=$0080 ; [SP-468]
            asl  a               ; A=A+$01 X=$0010 Y=$0080 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-468]
            asl  a               ; A=A+$01 X=$0010 Y=$0080 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-468]
            asl  a               ; A=A+$01 X=$0010 Y=$0080 ; [SP-468]
            jsr  combat_apply_damage       ; A=A+$01 X=$0010 Y=$0080 ; [SP-470]
; XREF: 1 ref (1 branch) from char_turn_loop
char_turn_next dec  $D5             ; A=A+$01 X=$0010 Y=$0080 ; [SP-470]
            bpl  char_turn_loop    ; A=A+$01 X=$0010 Y=$0080 ; [SP-470]
; === End of while loop ===

            jsr  move_display_party_status       ; Call $007338(A, X, 1 stack)
            rts                  ; A=A+$01 X=$0010 Y=$0080 ; [SP-470]

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

char_equip_check_weapon bcc  char_equip_none_msg    ; A=A+$01 X=$0010 Y=$0080 ; [SP-604]
            cmp  #$D1            ; A=A+$01 X=$0010 Y=$0080 ; [SP-604]
            bcs  char_equip_none_msg    ; A=A+$01 X=$0010 Y=$0080 ; [SP-604]
            sec                  ; A=A+$01 X=$0010 Y=$0080 ; [SP-604]
            sbc  #$C1            ; A=A-$C1 X=$0010 Y=$0080 ; [SP-604]
            sta  $F0             ; A=A-$C1 X=$0010 Y=$0080 ; [SP-604]
            jsr  $46F6           ; A=A-$C1 X=$0010 Y=$0080 ; [SP-606]
            ldy  #$30            ; A=A-$C1 X=$0010 Y=$0030 ; [SP-606]
            lda  ($FE),Y         ; A=A-$C1 X=$0010 Y=$0030 ; [SP-606]
            cmp  $F0             ; A=A-$C1 X=$0010 Y=$0030 ; [SP-606]
            bne  char_equip_not_owned    ; A=A-$C1 X=$0010 Y=$0030 ; [SP-606]
            jmp  char_equip_add_weapon    ; A=A-$C1 X=$0010 Y=$0030 ; [SP-606]
; XREF: 1 ref (1 branch) from char_equip_check_weapon
char_equip_not_owned clc                  ; A=A-$C1 X=$0010 Y=$0030 ; [SP-606]
            lda  #$30            ; A=$0030 X=$0010 Y=$0030 ; [SP-606]
            adc  $F0             ; A=$0030 X=$0010 Y=$0030 ; [SP-606]
            tay                  ; A=$0030 X=$0010 Y=$0030 ; [SP-606]
            lda  ($FE),Y         ; A=$0030 X=$0010 Y=$0030 ; [SP-606]
            beq  char_equip_none_msg    ; A=$0030 X=$0010 Y=$0030 ; [SP-606]
            sed                  ; A=$0030 X=$0010 Y=$0030 ; [SP-606]
            sec                  ; A=$0030 X=$0010 Y=$0030 ; [SP-606]
            sbc  #$01            ; A=A-$01 X=$0010 Y=$0030 ; [SP-606]
            cld                  ; A=A-$01 X=$0010 Y=$0030 ; [SP-606]
            sta  ($FE),Y         ; A=A-$01 X=$0010 Y=$0030 ; [SP-606]
            lda  $D6             ; A=[$00D6] X=$0010 Y=$0030 ; [SP-606]
            sta  $D5             ; A=[$00D6] X=$0010 Y=$0030 ; [SP-606]
            lda  #$01            ; A=$0001 X=$0010 Y=$0030 ; [SP-606]
            jsr  combat_add_bcd_field         ; A=$0001 X=$0010 Y=$0030 ; [SP-608]
            jmp  char_turn_done_msg    ; A=$0001 X=$0010 Y=$0030 ; [SP-608]
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

; XREF: 1 ref (1 branch) from $0061CD
char_use_powder sed                  ; A=$00FF X=$0010 Y=$00D5 ; [SP-677]
            lda  ($FE),Y         ; A=$00FF X=$0010 Y=$00D5 ; [SP-677]
            sec                  ; A=$00FF X=$0010 Y=$00D5 ; [SP-677]
            sbc  #$01            ; A=A-$01 X=$0010 Y=$00D5 ; [SP-677]
            sta  ($FE),Y         ; A=A-$01 X=$0010 Y=$00D5 ; [SP-677]
            cld                  ; A=A-$01 X=$0010 Y=$00D5 ; [SP-677]
            lda  #$0A            ; A=$000A X=$0010 Y=$00D5 ; [SP-677]
            sta  $CB             ; A=$000A X=$0010 Y=$00D5 ; [SP-677]
            jmp  game_loop_end_turn   ; A=$000A X=$0010 Y=$00D5 ; [SP-677]

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

; XREF: 1 ref (1 branch) from file_cmd_data_2
file_mark_check_slot  ldx  $F1             ; A=$000A X=$0010 Y=$00D5 ; [SP-716]
            cpx  $02             ; A=$000A X=$0010 Y=$00D5 ; [SP-716]
            beq  file_mark_check_done      ; A=$000A X=$0010 Y=$00D5 ; [SP-716]

; === while loop starts here [nest:15] ===
; XREF: 1 ref (1 branch) from file_mark_check_done
file_mark_apply_loop  jsr  render_encrypt_records        ; A=$000A X=$0010 Y=$00D5 ; [SP-718]
            lda  #$F7            ; A=$00F7 X=$0010 Y=$00D5 ; [SP-718]
            jsr  $4705           ; Call $004705(X)
            jsr  render_encrypt_records        ; A=$00F7 X=$0010 Y=$00D5 ; [SP-722]
            jsr  $46F6           ; A=$00F7 X=$0010 Y=$00D5 ; [SP-724]
            lda  #$00            ; A=$0000 X=$0010 Y=$00D5 ; [SP-724]
            ldy  #$1A            ; A=$0000 X=$0010 Y=$001A ; [SP-724]
            sta  ($FE),Y         ; A=$0000 X=$0010 Y=$001A ; [SP-724]
            lda  #$FF            ; A=$00FF X=$0010 Y=$001A ; [SP-724]
            jsr  combat_apply_damage       ; A=$00FF X=$0010 Y=$001A ; [SP-726]
            jmp  game_loop_end_turn   ; A=$00FF X=$0010 Y=$001A ; [SP-726]
; XREF: 1 ref (1 branch) from file_mark_check_slot
file_mark_check_done  cpx  file_max_slots     ; A=$00FF X=$0010 Y=$001A ; [SP-726]
            bne  file_mark_apply_loop      ; A=$00FF X=$0010 Y=$001A ; [SP-726]
; === End of while loop ===

            inc  file_max_slots     ; A=$00FF X=$0010 Y=$001A ; [SP-726]
            lda  #$04            ; A=$0004 X=$0010 Y=$001A ; [SP-726]
            sta  $D0             ; A=$0004 X=$0010 Y=$001A ; [SP-726]

; === while loop starts here [nest:15] ===
; XREF: 1 ref (1 branch) from file_endgame_setup_loop
file_endgame_setup_loop  jsr  $46FF           ; A=$0004 X=$0010 Y=$001A ; [SP-728]
            lda  #$F0            ; A=$00F0 X=$0010 Y=$001A ; [SP-728]
            sta  ($FE),Y         ; A=$00F0 X=$0010 Y=$001A ; [SP-728]
            jsr  $0230           ; A=$00F0 X=$0010 Y=$001A ; [SP-730]
            lda  #$F7            ; A=$00F7 X=$0010 Y=$001A ; [SP-730]
            jsr  $4705           ; A=$00F7 X=$0010 Y=$001A ; [SP-732]
            jsr  $46FF           ; A=$00F7 X=$0010 Y=$001A ; [SP-734]
            lda  #$7C            ; A=$007C X=$0010 Y=$001A ; [SP-734]
            sta  ($FE),Y         ; A=$007C X=$0010 Y=$001A ; [SP-734]
            jsr  $0230           ; A=$007C X=$0010 Y=$001A ; [SP-736]
            lda  #$F7            ; A=$00F7 X=$0010 Y=$001A ; [SP-736]
            jsr  $4705           ; A=$00F7 X=$0010 Y=$001A ; [SP-738]
            dec  $D0             ; A=$00F7 X=$0010 Y=$001A ; [SP-738]
            bpl  file_endgame_setup_loop      ; A=$00F7 X=$0010 Y=$001A ; [SP-738]
            lda  #$20            ; A=$0020 X=$0010 Y=$001A ; [SP-738]
            ldy  #$00            ; A=$0020 X=$0010 Y=$0000 ; [SP-738]
            sta  ($FE),Y         ; A=$0020 X=$0010 Y=$0000 ; [SP-738]
            jsr  $0230           ; A=$0020 X=$0010 Y=$0000 ; [SP-740]
            lda  file_max_slots     ; A=[$6378] X=$0010 Y=$0000 ; [SP-740]
            cmp  #$22            ; A=[$6378] X=$0010 Y=$0000 ; [SP-740]
            beq  file_endgame_start      ; A=[$6378] X=$0010 Y=$0000 ; [SP-740]
            jmp  game_loop_end_turn   ; A=[$6378] X=$0010 Y=$0000 ; [SP-740]
; XREF: 1 ref (1 branch) from file_endgame_setup_loop
file_endgame_start  lda  #$0A            ; A=$000A X=$0010 Y=$0000 ; [SP-740]
            sta  $B1             ; A=$000A X=$0010 Y=$0000 ; [SP-740]
            sta  $B0             ; A=$000A X=$0010 Y=$0000 ; [SP-740]
            jsr  $46B7           ; A=$000A X=$0010 Y=$0000 ; [SP-742]

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

; XREF: 1 ref (1 branch) from file_overlay_data
file_use_gem_bcd  sed                  ; A=$000A X=$0010 Y=$0000 ; [SP-775]
            lda  ($FE),Y         ; A=$000A X=$0010 Y=$0000 ; [SP-775]
            sec                  ; A=$000A X=$0010 Y=$0000 ; [SP-775]
            sbc  #$01            ; A=A-$01 X=$0010 Y=$0000 ; [SP-775]
            sta  ($FE),Y         ; A=A-$01 X=$0010 Y=$0000 ; [SP-775]
            cld                  ; A=A-$01 X=$0010 Y=$0000 ; [SP-775]
            lda  #$00            ; A=$0000 X=$0010 Y=$0000 ; [SP-775]
            sta  $02             ; A=$0000 X=$0010 Y=$0000 ; [SP-775]
            sta  $03             ; A=$0000 X=$0010 Y=$0000 ; [SP-775]
            lda  $B0             ; A=[$00B0] X=$0010 Y=$0000 ; [SP-775]
            pha                  ; A=[$00B0] X=$0010 Y=$0000 ; [SP-776]
            lda  #$00            ; A=$0000 X=$0010 Y=$0000 ; [SP-776]
            sta  $B1             ; A=$0000 X=$0010 Y=$0000 ; [SP-776]
            sta  $B0             ; A=$0000 X=$0010 Y=$0000 ; [SP-776]

; === while loop starts here [nest:15] ===
; XREF: 1 ref (1 branch) from file_wait_vblank
file_wait_vblank  lda  $B2             ; A=[$00B2] X=$0010 Y=$0000 ; [SP-776]
            bne  file_wait_vblank      ; A=[$00B2] X=$0010 Y=$0000 ; [SP-776]
            jsr  $46B7           ; Call $0046B7(A)

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

            sta  $B1             ; A=$0000 X=$0010 Y=$0000 ; [SP-810]
            sta  $B0             ; A=$0000 X=$0010 Y=$0000 ; [SP-810]

; === while loop starts here [nest:17] ===
; XREF: 1 ref (1 branch) from game_loop_wait_vblank
game_loop_wait_vblank lda  $B2             ; A=[$00B2] X=$0010 Y=$0000 ; [SP-810]
            bne  game_loop_wait_vblank    ; A=[$00B2] X=$0010 Y=$0000 ; [SP-810]
            jsr  $46B7           ; A=[$00B2] X=$0010 Y=$0000 ; [SP-812]

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

game_loop_dispatch_entry inc  $CE00,X         ; SLOTEXP_x600 - Slot expansion ROM offset $600 {Slot}
            sbc  $65,X           ; -> $0075 ; A=[$00B2] X=$0010 Y=$0000 ; [SP-810]

; === while loop starts here [nest:17] ===
; XREF: 2 refs (2 branches) from game_main_loop, game_loop_check_key
game_loop_check_key cmp  #$1A            ; A=[$00B2] X=$0010 Y=$0000 ; [SP-810]
            bne  game_loop_check_key    ; A=[$00B2] X=$0010 Y=$0000 ; [SP-810]
            rts                  ; A=[$00B2] X=$0010 Y=$0000 ; [SP-808]

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

; XREF: 1 ref (1 branch) from $006933
game_loop_food_deduct sed                  ; A=[$00B2] X=$0010 Y=$0000 ; [SP-915]
            sec                  ; A=[$00B2] X=$0010 Y=$0000 ; [SP-915]
            sbc  #$01            ; A=A-$01 X=$0010 Y=$0000 ; [SP-915]
            sta  ($FE),Y         ; A=A-$01 X=$0010 Y=$0000 ; [SP-915]
            cld                  ; A=A-$01 X=$0010 Y=$0000 ; [SP-915]
            jsr  $46FF           ; A=A-$01 X=$0010 Y=$0000 ; [SP-917]
            lda  $09             ; A=[$0009] X=$0010 Y=$0000 ; [SP-917]
            asl  a               ; A=[$0009] X=$0010 Y=$0000 ; [SP-917]
            sta  ($FE),Y         ; A=[$0009] X=$0010 Y=$0000 ; [SP-917]
            jsr  $0230           ; A=[$0009] X=$0010 Y=$0000 ; [SP-919]
            jmp  game_loop_end_turn   ; A=[$0009] X=$0010 Y=$0000 ; [SP-919]

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


; === while loop starts here [nest:14] ===
; XREF: 52 refs (16 jumps) from $006AE9, char_equip_bcd_add, $006064, $005B66, $005E52, ...
game_loop_end_turn jsr  $03AF           ; Call $0003AF(A)
            lda  #$03            ; A=$0003 X=$0010 Y=$0000 ; [SP-1194]
            ldx  #$A3            ; A=$0003 X=$00A3 Y=$0000 ; [SP-1194]
            ldy  #$33            ; A=$0003 X=$00A3 Y=$0033 ; [SP-1194]
            jsr  $03A3           ; Call $0003A3(A, X, Y)
            cmp  #$1A            ; A=$0003 X=$00A3 Y=$0033 ; [SP-1196]
            bne  game_loop_end_turn   ; A=$0003 X=$00A3 Y=$0033 ; [SP-1196]
            lda  $E2             ; A=[$00E2] X=$00A3 Y=$0033 ; [SP-1196]
            bne  game_loop_check_dungeon   ; A=[$00E2] X=$00A3 Y=$0033 ; [SP-1196]
            pha                  ; A=[$00E2] X=$00A3 Y=$0033 ; [SP-1197]
            jsr  check_surface_only     ; Call $006F5D(A, 1 stack)
            pla                  ; A=[stk] X=$00A3 Y=$0033 ; [SP-1198]
; XREF: 1 ref (1 branch) from game_loop_end_turn
game_loop_check_dungeon cmp  #$01            ; A=[stk] X=$00A3 Y=$0033 ; [SP-1198]
            bne  game_loop_check_surface   ; A=[stk] X=$00A3 Y=$0033 ; [SP-1198]
            jsr  $1800           ; A=[stk] X=$00A3 Y=$0033 ; [SP-1200]
            jmp  dungeon_turn_process      ; A=[stk] X=$00A3 Y=$0033 ; [SP-1200]
; XREF: 1 ref (1 branch) from game_loop_check_dungeon
game_loop_check_surface cmp  #$80            ; A=[stk] X=$00A3 Y=$0033 ; [SP-1200]
            bne  game_loop_check_town   ; A=[stk] X=$00A3 Y=$0033 ; [SP-1200]
            jmp  render_combat_loop_start      ; A=[stk] X=$00A3 Y=$0033 ; [SP-1200]
; XREF: 1 ref (1 branch) from game_loop_check_surface
game_loop_check_town cmp  #$02            ; A=[stk] X=$00A3 Y=$0033 ; [SP-1200]
            bcc  game_loop_call_terrain   ; A=[stk] X=$00A3 Y=$0033 ; [SP-1200]
            lda  $00             ; A=[$0000] X=$00A3 Y=$0033 ; [SP-1200]
            beq  game_loop_load_saved_x   ; A=[$0000] X=$00A3 Y=$0033 ; [SP-1200]
            lda  $01             ; A=[$0001] X=$00A3 Y=$0033 ; [SP-1200]
            bne  game_loop_call_terrain   ; A=[$0001] X=$00A3 Y=$0033 ; [SP-1200]
; XREF: 4 refs (3 jumps) (1 branch) from $00559A, input_dungeon_gen_pos, $008F5D, game_loop_check_town
game_loop_load_saved_x lda  $E3             ; A=[$00E3] X=$00A3 Y=$0033 ; [SP-1200]
            sta  $00             ; A=[$00E3] X=$00A3 Y=$0033 ; [SP-1200]
            lda  $E4             ; A=[$00E4] X=$00A3 Y=$0033 ; [SP-1200]
            sta  $01             ; A=[$00E4] X=$00A3 Y=$0033 ; [SP-1200]
            lda  #$FF            ; A=$00FF X=$00A3 Y=$0033 ; [SP-1200]
            sta  $0F             ; A=$00FF X=$00A3 Y=$0033 ; [SP-1200]
            lda  #$00            ; A=$0000 X=$00A3 Y=$0033 ; [SP-1200]
            sta  $E2             ; A=$0000 X=$00A3 Y=$0033 ; [SP-1200]
            sta  $B1             ; A=$0000 X=$00A3 Y=$0033 ; [SP-1200]
            sta  $B0             ; A=$0000 X=$00A3 Y=$0033 ; [SP-1200]

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

; XREF: 2 refs (2 branches) from game_loop_check_town, game_loop_check_town
game_loop_call_terrain jsr  move_process_turn        ; Call $007470(A)
            jsr  move_display_party_status       ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1213]
            jsr  $46FC           ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1215]
            cmp  #$88            ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1215]
            bne  game_loop_check_tile   ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1215]
            jsr  world_move_handler      ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1217]
; XREF: 1 ref (1 branch) from game_loop_call_terrain
game_loop_check_tile jsr  $46FC           ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1219]
            cmp  #$30            ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1219]
            bne  game_loop_check_location   ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1219]
            jsr  shop_handle      ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1221]
; XREF: 1 ref (1 branch) from game_loop_check_tile
game_loop_check_location jsr  check_location        ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1223]
            beq  game_loop_clear_flag   ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1223]
            jmp  game_loop_check_special   ; A=[$00B2] X=$00A3 Y=$00D3 ; [SP-1223]
; XREF: 1 ref (1 branch) from game_loop_check_location
game_loop_clear_flag lda  #$00            ; A=$0000 X=$00A3 Y=$00D3 ; [SP-1223]
            sta  $CB             ; A=$0000 X=$00A3 Y=$00D3 ; [SP-1223]
            lda  #$0B            ; A=$000B X=$00A3 Y=$00D3 ; [SP-1223]
            jsr  $46E4           ; A=$000B X=$00A3 Y=$00D3 ; [SP-1225]
            sta  $02             ; A=$000B X=$00A3 Y=$00D3 ; [SP-1225]
            lda  #$0B            ; A=$000B X=$00A3 Y=$00D3 ; [SP-1225]
            jsr  $46E4           ; Call $0046E4(1 stack)
            sta  $03             ; A=$000B X=$00A3 Y=$00D3 ; [SP-1227]
            cmp  #$05            ; A=$000B X=$00A3 Y=$00D3 ; [SP-1227]
            bne  game_loop_combat_lookup   ; A=$000B X=$00A3 Y=$00D3 ; [SP-1227]
            lda  $02             ; A=[$0002] X=$00A3 Y=$00D3 ; [SP-1227]
            cmp  #$05            ; A=[$0002] X=$00A3 Y=$00D3 ; [SP-1227]
            beq  game_loop_combat_lookup2   ; A=[$0002] X=$00A3 Y=$00D3 ; [SP-1227]
; XREF: 1 ref (1 branch) from game_loop_clear_flag
game_loop_combat_lookup jsr  combat_tile_at_xy      ; A=[$0002] X=$00A3 Y=$00D3 ; [SP-1229]
            cmp  #$10            ; A=[$0002] X=$00A3 Y=$00D3 ; [SP-1229]
            bne  game_loop_jmp_input   ; A=[$0002] X=$00A3 Y=$00D3 ; [SP-1229]
            lda  #$7A            ; A=$007A X=$00A3 Y=$00D3 ; [SP-1229]
            sta  ($FE),Y         ; A=$007A X=$00A3 Y=$00D3 ; [SP-1229]
            jsr  $0328           ; A=$007A X=$00A3 Y=$00D3 ; [SP-1231]
            lda  #$F7            ; A=$00F7 X=$00A3 Y=$00D3 ; [SP-1231]
            jsr  $4705           ; A=$00F7 X=$00A3 Y=$00D3 ; [SP-1233]
            jsr  $0230           ; Call $000230(A)
; XREF: 1 ref (1 branch) from game_loop_combat_lookup
game_loop_jmp_input jmp  world_move_start   ; A=$00F7 X=$00A3 Y=$00D3 ; [SP-1235]
; XREF: 1 ref (1 branch) from game_loop_clear_flag
game_loop_combat_lookup2 jsr  combat_tile_at_xy      ; A=$00F7 X=$00A3 Y=$00D3 ; [SP-1237]
            lda  #$7A            ; A=$007A X=$00A3 Y=$00D3 ; [SP-1237]
            sta  ($FE),Y         ; A=$007A X=$00A3 Y=$00D3 ; [SP-1237]
            jsr  $0328           ; A=$007A X=$00A3 Y=$00D3 ; [SP-1239]
            jsr  char_combat_turn       ; A=$007A X=$00A3 Y=$00D3 ; [SP-1241]
            jsr  $0230           ; A=$007A X=$00A3 Y=$00D3 ; [SP-1243]
; XREF: 1 ref (1 jump) from game_loop_check_location
game_loop_check_special lda  $6E3E           ; A=[$6E3E] X=$00A3 Y=$00D3 ; [SP-1243]
            cmp  #$20            ; A=[$6E3E] X=$00A3 Y=$00D3 ; [SP-1243]
            bne  check_surface_only     ; A=[$6E3E] X=$00A3 Y=$00D3 ; [SP-1243]
            jmp  world_move_start   ; A=[$6E3E] X=$00A3 Y=$00D3 ; [SP-1243]

; ---------------------------------------------------------------------------
; check_location  [3 calls]
;   Called by: game_loop_check_location
; ---------------------------------------------------------------------------

; FUNC $006F43: register -> A:X [L]
; Proto: uint32_t func_006F43(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [3 dead stores]
; XREF: 3 refs (3 calls) from $008428, $0080DE, game_loop_check_location
check_location    lda  $E2             ; A=[$00E2] X=$00A3 Y=$00D3 ; [SP-1243]
            cmp  #$80            ; A=[$00E2] X=$00A3 Y=$00D3 ; [SP-1243]
            bne  check_location_compare     ; A=[$00E2] X=$00A3 Y=$00D3 ; [SP-1243]
            lda  $835E           ; A=[$835E] X=$00A3 Y=$00D3 ; [SP-1243]
; XREF: 1 ref (1 branch) from check_location
check_location_compare cmp  #$03            ; A=[$835E] X=$00A3 Y=$00D3 ; [SP-1243]
            bne  check_location_not_found     ; A=[$835E] X=$00A3 Y=$00D3 ; [SP-1243]
            lda  $E3             ; A=[$00E3] X=$00A3 Y=$00D3 ; [SP-1243]
            cmp  $79B8           ; A=[$00E3] X=$00A3 Y=$00D3 ; [SP-1243]
            bne  check_location_not_found     ; A=[$00E3] X=$00A3 Y=$00D3 ; [SP-1243]
            lda  #$00            ; A=$0000 X=$00A3 Y=$00D3 ; [SP-1243]
            rts                  ; A=$0000 X=$00A3 Y=$00D3 ; [SP-1241]
; XREF: 2 refs (2 branches) from check_location_compare, check_location_compare
check_location_not_found lda  #$FF            ; A=$00FF X=$00A3 Y=$00D3 ; [SP-1241]
            rts                  ; A=$00FF X=$00A3 Y=$00D3 ; [SP-1239]

; ---------------------------------------------------------------------------
; check_surface_only  [2 calls, 1 branch]
;   Called by: game_loop_end_turn
; ---------------------------------------------------------------------------

; FUNC $006F5D: register -> A:X []
; Proto: uint32_t func_006F5D(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y)
; XREF: 3 refs (2 calls) (1 branch) from $005044, game_loop_end_turn, game_loop_check_special
check_surface_only lda  $E2             ; A=[$00E2] X=$00A3 Y=$00D3 ; [SP-1239]
            beq  toggle_music     ; A=[$00E2] X=$00A3 Y=$00D3 ; [SP-1239]
            rts                  ; A=[$00E2] X=$00A3 Y=$00D3 ; [SP-1237]

; ---------------------------------------------------------------------------
; toggle_music  [1 call, 1 branch]
;   Calls: advance_turn
; ---------------------------------------------------------------------------
; XREF: 2 refs (1 call) (1 branch) from check_surface_only, $006171
toggle_music dec  turn_counter_1     ; A=[$00E2] X=$00A3 Y=$00D3 ; [SP-1237]
            bne  toggle_music_phase2  ; A=[$00E2] X=$00A3 Y=$00D3 ; [SP-1237]
            lda  #$0C            ; A=$000C X=$00A3 Y=$00D3 ; [SP-1237]
            sta  turn_counter_1     ; A=$000C X=$00A3 Y=$00D3 ; [OPT] PEEPHOLE: Load after store: 2 byte pattern at $006F69 ; [SP-1237]
            lda  $6FA1           ; A=[$6FA1] X=$00A3 Y=$00D3 ; [SP-1237]
            jsr  advance_turn        ; A=[$6FA1] X=$00A3 Y=$00D3 ; [SP-1239]
            sta  $6FA1           ; A=[$6FA1] X=$00A3 Y=$00D3 ; [SP-1239] ; WARNING: Self-modifying code -> $6FA1
; XREF: 1 ref (1 branch) from toggle_music
toggle_music_phase2 dec  turn_counter_2     ; A=[$6FA1] X=$00A3 Y=$00D3 ; [SP-1239]
            bne  toggle_music_update  ; A=[$6FA1] X=$00A3 Y=$00D3 ; [SP-1239]
            lda  #$04            ; A=$0004 X=$00A3 Y=$00D3 ; [SP-1239]
            sta  turn_counter_2     ; A=$0004 X=$00A3 Y=$00D3 ; [OPT] PEEPHOLE: Load after store: 2 byte pattern at $006F7C ; [SP-1239]
            lda  $6FA4           ; A=[$6FA4] X=$00A3 Y=$00D3 ; [SP-1239]
            jsr  advance_turn        ; Call $006F8B(A)
            sta  $6FA4           ; A=[$6FA4] X=$00A3 Y=$00D3 ; [SP-1241] ; WARNING: Self-modifying code -> $6FA4
; XREF: 1 ref (1 branch) from toggle_music_phase2
toggle_music_update jmp  advance_turn_update     ; A=[$6FA4] X=$00A3 Y=$00D3 ; [SP-1241]

; ---------------------------------------------------------------------------
; advance_turn  [2 calls]
;   Called by: toggle_music_phase2, toggle_music
; ---------------------------------------------------------------------------

; FUNC $006F8B: register -> A:X []
; Proto: uint32_t func_006F8B(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [1 dead stores]
; XREF: 2 refs (2 calls) from toggle_music_phase2, toggle_music
advance_turn    clc                  ; A=[$6FA4] X=$00A3 Y=$00D3 ; [SP-1241]
            adc  #$01            ; A=A+$01 X=$00A3 Y=$00D3 ; [SP-1241]
            cmp  #$B8            ; A=A+$01 X=$00A3 Y=$00D3 ; [SP-1241]
            bcc  advance_turn_done     ; A=A+$01 X=$00A3 Y=$00D3 ; [SP-1241]
            lda  #$B0            ; A=$00B0 X=$00A3 Y=$00D3 ; [SP-1241]
; XREF: 1 ref (1 branch) from advance_turn
advance_turn_done rts                  ; A=$00B0 X=$00A3 Y=$00D3 ; [SP-1239]
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


; ---------------------------------------------------------------------------
; combat_init  [2 calls, 2 branches]
;   Called by: game_loop_check_key, game_loop_food_deduct
;   Calls: input_wait_key
; ---------------------------------------------------------------------------
; XREF: 4 refs (2 calls) (2 branches) from game_loop_check_key, combat_init, combat_init, game_loop_food_deduct
combat_init      jsr  input_wait_key     ; A=$00A8 X=$0008 Y=$0000 ; [SP-1247]
            cmp  #$B0            ; A=$00A8 X=$0008 Y=$0000 ; [SP-1247]
            bcc  combat_init          ; A=$00A8 X=$0008 Y=$0000 ; [SP-1247]
; === End of while loop ===

            cmp  #$BA            ; A=$00A8 X=$0008 Y=$0000 ; [SP-1247]
            bcs  combat_init          ; A=$00A8 X=$0008 Y=$0000 ; [SP-1247]
; === End of while loop ===

            pha                  ; A=$00A8 X=$0008 Y=$0000 ; [SP-1248]
            and  #$7F            ; A=A&$7F X=$0008 Y=$0000 ; [SP-1248]
            jsr  $46CC           ; A=A&$7F X=$0008 Y=$0000 ; [SP-1250]
            jsr  $46BA           ; Call $0046BA(A)
            DB      $FF
            brk  #$AD            ; A=A&$7F X=$0008 Y=$0000 ; [SP-1252]

; ---
            DB      $6F
            DB      $B7,$C9,$AA,$F0,$04,$68,$38,$E9,$B0,$60
; ---


; ---------------------------------------------------------------------------
; combat_setup  [5 calls, 2 branches]
;   Called by: char_use_powder, file_overlay_data
;   Calls: input_wait_key
; ---------------------------------------------------------------------------
; XREF: 7 refs (5 calls) (2 branches) from char_use_powder, $0066D6, $008F7D, file_overlay_data, combat_setup, ...
combat_setup    lda  #$AA            ; A=$00AA X=$0008 Y=$0000 ; [SP-1249]
            sta  $62A5           ; A=$00AA X=$0008 Y=$0000 ; [SP-1249]
            jsr  input_wait_key     ; A=$00AA X=$0008 Y=$0000 ; [SP-1251]
            cmp  #$B0            ; A=$00AA X=$0008 Y=$0000 ; [SP-1251]
            bcc  combat_setup        ; A=$00AA X=$0008 Y=$0000 ; [SP-1251]
; === End of while loop ===

            cmp  #$B5            ; A=$00AA X=$0008 Y=$0000 ; [SP-1251]
            bcs  combat_setup        ; A=$00AA X=$0008 Y=$0000 ; [SP-1251]
; === End of while loop ===

            pha                  ; A=$00AA X=$0008 Y=$0000 ; [SP-1252]
            and  #$7F            ; A=A&$7F X=$0008 Y=$0000 ; [SP-1252]
            jsr  $46CC           ; Call $0046CC(A, 1 stack)
            jsr  $46BA           ; A=A&$7F X=$0008 Y=$0000 ; [SP-1256]
            DB      $FF
            brk  #$68            ; A=A&$7F X=$0008 Y=$0000 ; [SP-1256]
            sec                  ; A=A&$7F X=$0008 Y=$0000 ; [SP-1256]

; ---------------------------------------------------------------------------
; combat_parse_input
; ---------------------------------------------------------------------------
combat_parse_input  sbc  #$B0            ; A=A-$B0 X=$0008 Y=$0000 ; [SP-1256]
            sta  $D5             ; A=A-$B0 X=$0008 Y=$0000 ; [SP-1256]
            dec  $D5             ; A=A-$B0 X=$0008 Y=$0000 ; [SP-1256]
            cmp  #$00            ; A=A-$B0 X=$0008 Y=$0000 ; [SP-1256]
            rts                  ; A=A-$B0 X=$0008 Y=$0000 ; [SP-1254]

; ---------------------------------------------------------------------------
; combat_read_key  [16 calls, 1 branch]
; ---------------------------------------------------------------------------
; XREF: 17 refs (16 calls) from $006C0A, $006DBD, $006D6E, $006D52, $006D16, ...
combat_read_key     lda  #$B7            ; A=$00B7 X=$0008 Y=$0000 ; [SP-1254]
            sta  $705C           ; A=$00B7 X=$0008 Y=$0000 ; [SP-1254] ; WARNING: Self-modifying code -> $705C
            ldx  #$50            ; A=$00B7 X=$0050 Y=$0000 ; [SP-1254]

; === while loop starts here [nest:15] ===
; XREF: 1 ref (1 branch) from combat_key_wait
combat_key_wait  lda  $C000           ; KBD - Keyboard data / 80STORE off {Keyboard} <keyboard_read>
            bpl  combat_key_wait      ; A=[$C000] X=$0050 Y=$0000 ; [SP-1254]
; === End of while loop ===

            bit  $C010           ; KBDSTRB - Clear keyboard strobe {Keyboard} <keyboard_strobe>
            pha                  ; A=[$C000] X=$0050 Y=$0000 ; [SP-1255]
            lda  boot_init_data_2     ; A=[$506F] X=$0050 Y=$0000 ; [SP-1255]
            stx  $705C           ; A=[$506F] X=$0050 Y=$0000 ; [SP-1255] ; WARNING: Self-modifying code -> $705C
            cmp  $62A5           ; A=[$506F] X=$0050 Y=$0000 ; [SP-1255]
            bne  combat_key_check_enter      ; A=[$506F] X=$0050 Y=$0000 ; [SP-1255]
            rts                  ; A=[$506F] X=$0050 Y=$0000 ; [SP-1253]
; XREF: 1 ref (1 branch) from combat_key_wait
combat_key_check_enter  pla                  ; A=[stk] X=$0050 Y=$0000 ; [SP-1252]
            cmp  #$8D            ; A=[stk] X=$0050 Y=$0000 ; [SP-1252]
            bne  combat_key_check_esc      ; A=[stk] X=$0050 Y=$0000 ; [SP-1252]
            rts                  ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]
; XREF: 1 ref (1 branch) from combat_key_check_enter
combat_key_check_esc  cmp  #$9B            ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]
            bne  combat_read_key         ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]
; === End of while loop ===

            pla                  ; A=[stk] X=$0050 Y=$0000 ; [SP-1249]
            pla                  ; A=[stk] X=$0050 Y=$0000 ; [SP-1248]
            jsr  $46BA           ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]
            DB      $FF
            brk  #$4C            ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]
            and  $6E,X           ; -> $00BE ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]

; ---------------------------------------------------------------------------
; combat_bcd_multiply  [1 call]
;   Called by: input_spell_check_done
; ---------------------------------------------------------------------------

; FUNC $00707A: register -> A:X []
; Proto: uint32_t func_00707A(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Liveness: params(A,X,Y) returns(A,X,Y)
; XREF: 1 ref (1 call) from input_spell_check_done
combat_bcd_multiply  sed                  ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]
            sta  $F0             ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]
            clc                  ; A=[stk] X=$0050 Y=$0000 ; [SP-1250]
            lda  #$00            ; A=$0000 X=$0050 Y=$0000 ; [SP-1250]
            cpx  #$00            ; A=$0000 X=$0050 Y=$0000 ; [SP-1250]
            bne  combat_bcd_mul_loop      ; A=$0000 X=$0050 Y=$0000 ; [SP-1250]
            sta  $D0             ; A=$0000 X=$0050 Y=$0000 ; [SP-1250]
            rts                  ; A=$0000 X=$0050 Y=$0000 ; [SP-1248]

; === loop starts here (counter: X) [nest:14] ===
; XREF: 2 refs (2 branches) from combat_bcd_multiply, combat_bcd_mul_loop
combat_bcd_mul_loop  clc                  ; A=$0000 X=$0050 Y=$0000 ; [SP-1248]
            adc  $F0             ; A=$0000 X=$0050 Y=$0000 ; [SP-1248]
            dex                  ; A=$0000 X=$004F Y=$0000 ; [SP-1248]
            bne  combat_bcd_mul_loop      ; A=$0000 X=$004F Y=$0000 ; [SP-1248]
; === End of loop (counter: X) ===

            sta  $D0             ; A=$0000 X=$004F Y=$0000 ; [SP-1248]
            cld                  ; A=$0000 X=$004F Y=$0000 ; [SP-1248]
            rts                  ; A=$0000 X=$004F Y=$0000 ; [SP-1246]

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
; combat_add_hp  [2 calls]
;   Called by: move_turn_add_hp
; ---------------------------------------------------------------------------

; FUNC $007107: register -> A:X []
; Proto: uint32_t func_007107(uint16_t param_A, uint16_t param_X);
; Liveness: params(A,X) returns(A,X,Y) [4 dead stores]
; XREF: 2 refs (2 calls) from move_turn_add_hp, $005710
combat_add_hp  sta  $F0             ; A=$0099 X=$004F Y=$0023 ; [SP-1240]
            jsr  $46F6           ; Call $0046F6(A, Y)
            sed                  ; A=$0099 X=$004F Y=$0023 ; [SP-1242]
            clc                  ; A=$0099 X=$004F Y=$0023 ; [SP-1242]
            ldy  #$1B            ; A=$0099 X=$004F Y=$001B ; [SP-1242]
            lda  ($FE),Y         ; A=$0099 X=$004F Y=$001B ; [SP-1242]
            adc  $F0             ; A=$0099 X=$004F Y=$001B ; [SP-1242]
            sta  ($FE),Y         ; A=$0099 X=$004F Y=$001B ; [SP-1242]
            ldy  #$1A            ; A=$0099 X=$004F Y=$001A ; [SP-1242]
            lda  ($FE),Y         ; A=$0099 X=$004F Y=$001A ; [SP-1242]
            adc  #$00            ; A=A X=$004F Y=$001A ; [SP-1242]
            sta  ($FE),Y         ; A=A X=$004F Y=$001A ; [SP-1242]
            bcs  combat_hp_cap_at_max      ; A=A X=$004F Y=$001A ; [SP-1242]
            sec                  ; A=A X=$004F Y=$001A ; [SP-1242]
            ldy  #$1D            ; A=A X=$004F Y=$001D ; [SP-1242]
            lda  ($FE),Y         ; A=A X=$004F Y=$001D ; [SP-1242]
            ldy  #$1B            ; A=A X=$004F Y=$001B ; [SP-1242]
            sbc  ($FE),Y         ; A=A X=$004F Y=$001B ; [SP-1242]
            ldy  #$1C            ; A=A X=$004F Y=$001C ; [SP-1242]
            lda  ($FE),Y         ; A=A X=$004F Y=$001C ; [SP-1242]
            ldy  #$1A            ; A=A X=$004F Y=$001A ; [SP-1242]
            sbc  ($FE),Y         ; A=A X=$004F Y=$001A ; [SP-1242]
            bcs  combat_hp_add_done      ; A=A X=$004F Y=$001A ; [SP-1242]
; XREF: 1 ref (1 branch) from combat_add_hp
combat_hp_cap_at_max  ldy  #$1C            ; A=A X=$004F Y=$001C ; [SP-1242]
            lda  ($FE),Y         ; A=A X=$004F Y=$001C ; [SP-1242]
            ldy  #$1A            ; A=A X=$004F Y=$001A ; [SP-1242]
            sta  ($FE),Y         ; A=A X=$004F Y=$001A ; [SP-1242]
            ldy  #$1D            ; A=A X=$004F Y=$001D ; [SP-1242]
            lda  ($FE),Y         ; A=A X=$004F Y=$001D ; [SP-1242]
            ldy  #$1B            ; A=A X=$004F Y=$001B ; [SP-1242]
            sta  ($FE),Y         ; A=A X=$004F Y=$001B ; [SP-1242]
; XREF: 1 ref (1 branch) from combat_add_hp
combat_hp_add_done  cld                  ; A=A X=$004F Y=$001B ; [SP-1242]
            rts                  ; A=A X=$004F Y=$001B ; [SP-1240]

; ---------------------------------------------------------------------------
; combat_add_bcd_field  [5 calls]
;   Called by: char_equip_none_msg, char_equip_not_owned
; ---------------------------------------------------------------------------

; FUNC $007145: register -> A:X []
; Proto: uint32_t func_007145(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Liveness: params(A,X,Y) returns(A,X,Y) [1 dead stores]
; XREF: 5 refs (5 calls) from $005F04, $005D51, $005D86, char_equip_none_msg, char_equip_not_owned
combat_add_bcd_field     sta  $F0             ; A=A X=$004F Y=$001B ; [SP-1240]
            sty  $F2             ; A=A X=$004F Y=$001B ; [SP-1240]
            jsr  $46F6           ; A=A X=$004F Y=$001B ; [SP-1242]
            ldy  $F2             ; A=A X=$004F Y=$001B ; [SP-1242]
            sed                  ; A=A X=$004F Y=$001B ; [SP-1242]
            clc                  ; A=A X=$004F Y=$001B ; [SP-1242]
            lda  ($FE),Y         ; A=A X=$004F Y=$001B ; [SP-1242]
            adc  $F0             ; A=A X=$004F Y=$001B ; [SP-1242]
            sta  ($FE),Y         ; A=A X=$004F Y=$001B ; [SP-1242]
            cld                  ; A=A X=$004F Y=$001B ; [SP-1242]
            bcs  combat_bcd_overflow      ; A=A X=$004F Y=$001B ; [SP-1242]
            rts                  ; A=A X=$004F Y=$001B ; [SP-1240]
; XREF: 1 ref (1 branch) from combat_add_bcd_field
combat_bcd_overflow  lda  #$99            ; A=$0099 X=$004F Y=$001B ; [SP-1240]
            sta  ($FE),Y         ; A=$0099 X=$004F Y=$001B ; [SP-1240]
            rts                  ; A=$0099 X=$004F Y=$001B ; [SP-1238]

; ---------------------------------------------------------------------------
; combat_bcd_to_binary  [8 calls]
;   Called by: input_dungeon_random_pos, render_monster_attack, move_turn_regen_mp_wis, move_turn_regen_mp_str, move_turn_regen_mp_int, magic_effect_zero
; ---------------------------------------------------------------------------

; FUNC $00715F: register -> A:X [L]
; Proto: uint32_t func_00715F(uint16_t param_Y);
; Liveness: params(Y) returns(A,X,Y) [1 dead stores]
; XREF: 8 refs (8 calls) from input_dungeon_random_pos, render_monster_attack, $005665, move_turn_regen_mp_wis, move_turn_regen_mp_str, ...
combat_bcd_to_binary   cmp  #$00            ; A=$0099 X=$004F Y=$001B ; [SP-1238]
            beq  combat_bcd_conv_done    ; A=$0099 X=$004F Y=$001B ; [SP-1238]
            ldx  #$00            ; A=$0099 X=$0000 Y=$001B ; [SP-1238]
            sed                  ; A=$0099 X=$0000 Y=$001B ; [SP-1238]

; === while loop starts here [nest:19] ===
; XREF: 1 ref (1 branch) from combat_bcd_sub_loop
combat_bcd_sub_loop inx                  ; A=$0099 X=$0001 Y=$001B ; [SP-1238]
            sec                  ; A=$0099 X=$0001 Y=$001B ; [SP-1238]
            sbc  #$01            ; A=A-$01 X=$0001 Y=$001B ; [SP-1238]
            bne  combat_bcd_sub_loop    ; A=A-$01 X=$0001 Y=$001B ; [SP-1238]
; === End of while loop ===

            cld                  ; A=A-$01 X=$0001 Y=$001B ; [SP-1238]
            txa                  ; A=$0001 X=$0001 Y=$001B ; [SP-1238]
; XREF: 1 ref (1 branch) from combat_bcd_to_binary
combat_bcd_conv_done rts                  ; A=$0001 X=$0001 Y=$001B ; [SP-1236]

; ---------------------------------------------------------------------------
; combat_binary_to_bcd  [9 calls]
;   Called by: input_dungeon_gen_pos, move_turn_regen_mp_str, render_combat_resolve, move_turn_regen_mp_wis, move_turn_regen_mp_int, char_turn_next
; ---------------------------------------------------------------------------

; FUNC $00716F: register -> A:X [L]
; Proto: uint32_t func_00716F(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Liveness: params(A,X,Y) returns(A,X,Y) [1 dead stores]
; XREF: 9 refs (9 calls) from $008445, input_dungeon_gen_pos, $0056EF, move_turn_regen_mp_str, render_combat_resolve, ...
combat_binary_to_bcd   sta  $F3             ; A=$0001 X=$0001 Y=$001B ; [SP-1236]
            cmp  #$00            ; A=$0001 X=$0001 Y=$001B ; [SP-1236]
            beq  combat_bcd_conv_ret    ; A=$0001 X=$0001 Y=$001B ; [SP-1236]
            lda  #$00            ; A=$0000 X=$0001 Y=$001B ; [SP-1236]
            sed                  ; A=$0000 X=$0001 Y=$001B ; [SP-1236]

; === while loop starts here [nest:24] ===
; XREF: 1 ref (1 branch) from combat_bcd_add_loop
combat_bcd_add_loop clc                  ; A=$0000 X=$0001 Y=$001B ; [SP-1236]
            adc  #$01            ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
            dec  $F3             ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
            bne  combat_bcd_add_loop    ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
; === End of while loop ===

            cld                  ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
; XREF: 1 ref (1 branch) from combat_binary_to_bcd
combat_bcd_conv_ret rts                  ; A=A+$01 X=$0001 Y=$001B ; [SP-1234]

; ---------------------------------------------------------------------------
; combat_apply_damage  [12 calls]
;   Called by: render_combat_resolve, combat_end_flag, char_turn_loop, equip_handle, file_mark_apply_loop, move_turn_poison_damage
; ---------------------------------------------------------------------------

; FUNC $007181: register -> A:X []
; Proto: uint32_t func_007181(uint16_t param_A, uint16_t param_X);
; Liveness: params(A,X) returns(A,X,Y) [2 dead stores]
; XREF: 12 refs (12 calls) from render_combat_resolve, combat_end_flag, $005C1A, char_turn_loop, char_turn_loop, ...
combat_apply_damage   sta  $F3             ; A=A+$01 X=$0001 Y=$001B ; [SP-1234]
            jsr  $46F6           ; Call $0046F6(A)
            sed                  ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
            ldy  #$1B            ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
            lda  ($FE),Y         ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
            sec                  ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
            sbc  $F3             ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
            sta  ($FE),Y         ; A=A+$01 X=$0001 Y=$001B ; [SP-1236]
            ldy  #$1A            ; A=A+$01 X=$0001 Y=$001A ; [SP-1236]
            lda  ($FE),Y         ; A=A+$01 X=$0001 Y=$001A ; [SP-1236]
            sbc  #$00            ; A=A X=$0001 Y=$001A ; [SP-1236]
            sta  ($FE),Y         ; A=A X=$0001 Y=$001A ; [SP-1236]
            cld                  ; A=A X=$0001 Y=$001A ; [SP-1236]
            bcc  combat_unit_killed    ; A=A X=$0001 Y=$001A ; [SP-1236]
            lda  #$00            ; A=$0000 X=$0001 Y=$001A ; [SP-1236]
            rts                  ; A=$0000 X=$0001 Y=$001A ; [SP-1234]
; XREF: 1 ref (1 branch) from combat_apply_damage
combat_unit_killed lda  #$C4            ; A=$00C4 X=$0001 Y=$001A ; [SP-1234]
            ldy  #$11            ; A=$00C4 X=$0001 Y=$0011 ; [SP-1234]
            sta  ($FE),Y         ; A=$00C4 X=$0001 Y=$0011 ; [SP-1234]
            lda  #$00            ; A=$0000 X=$0001 Y=$0011 ; [SP-1234]
            ldy  #$1A            ; A=$0000 X=$0001 Y=$001A ; [SP-1234]
            sta  ($FE),Y         ; A=$0000 X=$0001 Y=$001A ; [SP-1234]
            ldy  #$1B            ; A=$0000 X=$0001 Y=$001B ; [SP-1234]
            sta  ($FE),Y         ; A=$0000 X=$0001 Y=$001B ; [SP-1234]
            jsr  combat_end_check       ; Call $007200(A, Y)
            lda  #$FF            ; A=$00FF X=$0001 Y=$001B ; [SP-1236]
            rts                  ; A=$00FF X=$0001 Y=$001B ; [SP-1234]

; ---------------------------------------------------------------------------
; combat_check_party_alive  [3 calls]
;   Called by: boot_clear_floor, render_return_to_game
;   Calls: move_display_party_status
; ---------------------------------------------------------------------------

; FUNC $0071B4: register -> A:X []
; Proto: uint32_t func_0071B4(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [2 dead stores]
; XREF: 3 refs (3 calls) from $008808, boot_clear_floor, render_return_to_game
combat_check_party_alive lda  #$03            ; A=$0003 X=$0001 Y=$001B ; [SP-1234]
            sta  $D5             ; A=$0003 X=$0001 Y=$001B ; [SP-1234]

; === while loop starts here [nest:28] ===
; XREF: 1 ref (1 branch) from combat_alive_check_loop
combat_alive_check_loop jsr  $46F6           ; A=$0003 X=$0001 Y=$001B ; [SP-1236]
            ldy  #$11            ; A=$0003 X=$0001 Y=$0011 ; [SP-1236]
            lda  ($FE),Y         ; A=$0003 X=$0001 Y=$0011 ; [SP-1236]
            cmp  #$C7            ; A=$0003 X=$0001 Y=$0011 ; [SP-1236]
            beq  combat_checksum_xor        ; A=$0003 X=$0001 Y=$0011 ; [SP-1236]
            cmp  #$D0            ; A=$0003 X=$0001 Y=$0011 ; [SP-1236]
            beq  combat_checksum_xor        ; A=$0003 X=$0001 Y=$0011 ; [SP-1236]
            dec  $D5             ; A=$0003 X=$0001 Y=$0011 ; [SP-1236]
            bpl  combat_alive_check_loop  ; A=$0003 X=$0001 Y=$0011 ; [SP-1236]
; === End of while loop ===

            jsr  move_display_party_status       ; A=$0003 X=$0001 Y=$0011 ; [SP-1238]
            jsr  $46BA           ; A=$0003 X=$0001 Y=$0011 ; [SP-1240]
            DB      $FF
            DB      $FF
            cmp  ($CC,X)         ; [SP-1240]

; ---
            DB      $CC,$A0,$D0,$CC,$C1,$D9,$C5,$D2,$D3,$A0,$CF,$D5,$D4,$A1,$FF,$00
            DB      $20,$00,$72,$4C,$16,$BA
; ---


; ---------------------------------------------------------------------------
; combat_checksum_xor  [1 call, 2 branches]
;   Called by: move_turn_checksum
; ---------------------------------------------------------------------------

; FUNC $0071EB: register -> A:X [L]
; Proto: uint32_t func_0071EB(void);
; Liveness: returns(A,X,Y) [1 dead stores]
; XREF: 3 refs (1 call) (2 branches) from move_turn_checksum, combat_alive_check_loop, combat_alive_check_loop
combat_checksum_xor    lda  #$B5            ; A=$00B5 X=$0001 Y=$0011 ; [SP-1240]
            sta  combat_dead_xor_addr     ; A=$00B5 X=$0001 Y=$0011 ; [SP-1240] ; WARNING: Self-modifying code -> combat_dead_xor_addr
            ldy  #$80            ; A=$00B5 X=$0001 Y=$0080 ; [SP-1240]
            lda  #$00            ; A=$0000 X=$0001 Y=$0080 ; [SP-1240]

; === while loop starts here [nest:29] ===
; XREF: 1 ref (1 branch) from combat_dead_xor_addr
combat_xor_loop eor  $50A8,Y         ; -> $5128 ; A=$0000 X=$0001 Y=$0080 ; [SP-1240]
            dey                  ; A=$0000 X=$0001 Y=$007F ; [SP-1240]
            bpl  combat_xor_loop     ; A=$0000 X=$0001 Y=$007F ; [SP-1240]
; === End of while loop ===

            ldx  #$50            ; A=$0000 X=$0050 Y=$007F ; [SP-1240]
            stx  combat_dead_xor_addr     ; A=$0000 X=$0050 Y=$007F ; [SP-1240] ; WARNING: Self-modifying code -> combat_dead_xor_addr
            rts                  ; A=$0000 X=$0050 Y=$007F ; [SP-1238]

; ---------------------------------------------------------------------------
; combat_end_check  [1 call]
;   Called by: combat_unit_killed
;   Calls: file_save_game, game_main_loop
; ---------------------------------------------------------------------------

; FUNC $007200: register -> A:X [I]
; Proto: uint32_t func_007200(uint16_t param_Y);
; Liveness: params(Y) returns(A,X,Y) [1 dead stores]
; XREF: 1 ref (1 call) from combat_unit_killed
combat_end_check   ldx  #$00            ; A=$0000 X=$0000 Y=$007F ; [SP-1238]
            lda  $E2             ; A=[$00E2] X=$0000 Y=$007F ; [SP-1238]
            stx  $E2             ; A=[$00E2] X=$0000 Y=$007F ; [SP-1238]
            pha                  ; A=[$00E2] X=$0000 Y=$007F ; [SP-1239]
            bne  combat_end_check_surface    ; A=[$00E2] X=$0000 Y=$007F ; [SP-1239]

; === while loop starts here [nest:28] ===
; XREF: 1 ref (1 branch) from combat_end_check_surface
combat_end_save_pos lda  $00             ; A=[$0000] X=$0000 Y=$007F ; [SP-1239]
            sta  $E3             ; A=[$0000] X=$0000 Y=$007F ; [SP-1239]
            lda  $01             ; A=[$0001] X=$0000 Y=$007F ; [SP-1239]
            sta  $E4             ; A=[$0001] X=$0000 Y=$007F ; [SP-1239]
            lda  $0E             ; A=[$000E] X=$0000 Y=$007F ; [SP-1239]
            sta  $E0             ; A=[$000E] X=$0000 Y=$007F ; [SP-1239]
            jsr  file_save_game          ; Call $00657D(A, X, 1 stack)
            jmp  combat_end_restore    ; A=[$000E] X=$0000 Y=$007F ; [SP-1241]
; XREF: 1 ref (1 branch) from combat_end_check
combat_end_check_surface cmp  #$80            ; A=[$000E] X=$0000 Y=$007F ; [SP-1241]
            bne  combat_end_return_game    ; A=[$000E] X=$0000 Y=$007F ; [SP-1241]
            lda  $835E           ; A=[$835E] X=$0000 Y=$007F ; [SP-1241]
            cmp  #$00            ; A=[$835E] X=$0000 Y=$007F ; [SP-1241]
            beq  combat_end_save_pos    ; A=[$835E] X=$0000 Y=$007F ; [SP-1241]
; === End of while loop ===

; XREF: 1 ref (1 branch) from combat_end_check_surface
combat_end_return_game jsr  game_main_loop       ; Call $0065B0(A)

; === while loop starts here [nest:27] ===
; XREF: 3 refs (2 jumps) (1 branch) from combat_end_save_pos, move_display_party_status, combat_end_restore
combat_end_restore pla                  ; A=[stk] X=$0000 Y=$007F ; [SP-1242]
            sta  $E2             ; A=[stk] X=$0000 Y=$007F ; [SP-1242]
            rts                  ; A=[stk] X=$0000 Y=$007F ; [SP-1240]

; --- Data region (102 bytes, text data) ---
            DB      $85,$F3,$A0,$00,$A9,$B7,$85,$FD,$A9,$6C,$85,$FC,$B1,$FC,$CD,$A5
            DB      $62,$F0,$E9,$A5,$0E,$C9,$16,$D0,$03,$4C,$12,$73,$A5,$F3,$C9,$40
            DB      $F0,$4A,$C9,$42,$F0,$43,$C9,$44,$F0,$10,$C9,$7C,$F0,$0C,$C9,$18
            DB      $B0,$34,$C9,$00,$F0,$30,$C9,$08,$F0,$2C,$A9,$F6,$20,$05,$47,$A2
            DB      $FF,$A0,$20,$CA,$D0,$FD,$88,$D0,$FA,$A9,$F6,$20,$05,$47,$A5,$0E
            DB      $C9,$14,$D0,$0F,$A2,$FF,$A0,$20,$CA,$D0,$FD,$88,$D0,$FA,$A9,$F6
            DB      $20,$05,$47,$A9,$00,$60
; --- End data region (102 bytes) ---

; XREF: 5 refs (1 jump) (4 branches) from $00731A, combat_end_restore, combat_end_flag, combat_end_restore, combat_end_restore
combat_end_flag lda  #$FF            ; A=$00FF X=$0000 Y=$007F ; [SP-1244]
            rts                  ; A=$00FF X=$0000 Y=$007F ; [SP-1242]

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
; move_save_cursor_pos  [2 calls]
;   Called by: move_display_party_status, advance_turn_update
; ---------------------------------------------------------------------------

; FUNC $007320: register -> A:X [L]
; Proto: uint32_t func_007320(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y)
; XREF: 2 refs (2 calls) from move_display_party_status, advance_turn_update
move_save_cursor_pos lda  $F9             ; A=[$00F9] X=$0000 Y=$007F ; [SP-1270]
            sta  $732B           ; A=[$00F9] X=$0000 Y=$007F ; [SP-1270]
            lda  $FA             ; A=[$00FA] X=$0000 Y=$007F ; [SP-1270]
            sta  move_saved_cursor_y     ; A=[$00FA] X=$0000 Y=$007F ; [SP-1270]
            rts                  ; A=[$00FA] X=$0000 Y=$007F ; [SP-1268]
            DB      $00
move_saved_cursor_y
            DB      $00

; === while loop starts here (counter: Y 'j') [nest:27] ===
; XREF: 1 ref (1 jump) from move_status_restore
move_restore_cursor_pos  lda  move_saved_cursor_y     ; A=[$732C] X=$0000 Y=$007F ; [SP-1271]
            sta  $FA             ; A=[$732C] X=$0000 Y=$007F ; [SP-1271]
            lda  $732B           ; A=[$732B] X=$0000 Y=$007F ; [SP-1271]
            sta  $F9             ; A=[$732B] X=$0000 Y=$007F ; [SP-1271]
            rts                  ; A=[$732B] X=$0000 Y=$007F ; [SP-1269]

; ---------------------------------------------------------------------------
; move_display_party_status  [13 calls]
;   Called by: game_loop_call_terrain, render_combat_mon_status, dungeon_chest_status, move_turn_display_status, dungeon_turn_process, render_call_turn, char_turn_next, render_combat_status_upd
;   Calls: move_save_cursor_pos
; ---------------------------------------------------------------------------

; FUNC $007338: register -> A:X []
; Liveness: returns(A,X,Y) [22 dead stores]
; XREF: 13 refs (13 calls) from $0092BB, $00503E, $00922D, $00925B, game_loop_call_terrain, ...
move_display_party_status   jsr  move_save_cursor_pos     ; A=[$732B] X=$0000 Y=$007F ; [SP-1271]
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
; input_wait_key  [4 calls]
;   Called by: render_combat_wait_key, combat_setup, combat_init
; ---------------------------------------------------------------------------

; FUNC $007446: register -> A:X []
; Proto: uint32_t func_007446(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [1 dead stores]
; XREF: 4 refs (4 calls) from render_combat_wait_key, combat_setup, combat_init, $005449
input_wait_key stx  input_wait_selfmod  ; A=$0099 X=$0010 Y=$0000 ; [SP-1325] ; WARNING: Self-modifying code -> input_wait_selfmod
            sty  input_wait_restore_y  ; A=$0099 X=$0010 Y=$0000 ; [SP-1325] ; WARNING: Self-modifying code -> input_wait_restore_y

; === while loop starts here [nest:32] ===
; XREF: 1 ref (1 branch) from input_wait_poll
input_wait_animate lda  $E2             ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1325]
            cmp  #$01            ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1325]
            beq  input_wait_poll  ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1325]
            jsr  $46ED           ; Call $0046ED(A)
            jsr  $46F0           ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1329]
            jsr  $470E           ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1331]
            jsr  $0328           ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1333]
; XREF: 1 ref (1 branch) from input_wait_animate
input_wait_poll lda  $C000           ; KBD - Keyboard data / 80STORE off {Keyboard} <keyboard_read>
            bpl  input_wait_animate  ; A=[$C000] X=$0010 Y=$0000 ; [SP-1333]
; === End of while loop ===

            bit  $C010           ; KBDSTRB - Clear keyboard strobe {Keyboard} <keyboard_strobe>
            ldx  input_wait_selfmod  ; A=[$C000] X=$0010 Y=$0000 ; [SP-1333]
            ldy  input_wait_restore_y  ; A=[$C000] X=$0010 Y=$0000 ; [SP-1333]
            rts                  ; A=[$C000] X=$0010 Y=$0000 ; [SP-1331]

; === while loop starts here [nest:32] ===
; XREF: 2 refs from input_wait_poll, input_wait_key
; *** MODIFIED AT RUNTIME by input_wait_key ($7446) ***
input_wait_selfmod brk  #$00            ; A=[$C000] X=$0010 Y=$0000 ; [SP-1334]
            DB      $20

; ---------------------------------------------------------------------------
; move_process_turn  [3 calls]
;   Called by: dungeon_turn_process, game_loop_call_terrain, render_call_turn
; ---------------------------------------------------------------------------

; FUNC $007470: register -> A:X []
; Proto: uint32_t func_007470(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y) [2 dead stores]
; XREF: 3 refs (3 calls) from dungeon_turn_process, game_loop_call_terrain, render_call_turn
move_process_turn    lda  $B769           ; A=[$B769] X=$0010 Y=$0000 ; [SP-1336]
            ora  #$55            ; A=A|$55 X=$0010 Y=$0000 ; [SP-1336]
            cmp  #$FF            ; A=A|$55 X=$0010 Y=$0000 ; [SP-1336]
            beq  input_wait_selfmod  ; A=A|$55 X=$0010 Y=$0000 ; [SP-1336]
; === End of while loop ===

            lda  $E2             ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1336]
            beq  move_turn_party_loop     ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1336]
            dec  move_encounter_counter     ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1336]
            beq  move_turn_encounter_roll     ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1336]
            rts                  ; A=[$00E2] X=$0010 Y=$0000 ; [SP-1336]

; === while loop starts here [nest:34] ===
; XREF: 1 ref (1 branch) from move_turn_encounter_roll
move_turn_encounter_roll lda  #$04            ; A=$0004 X=$0010 Y=$0000 ; [SP-1336]
            sta  move_encounter_counter     ; A=$0004 X=$0010 Y=$0000 ; [SP-1336]
            ldx  #$31            ; A=$0004 X=$0031 Y=$0000 ; [SP-1336]
            clc                  ; A=$0004 X=$0031 Y=$0000 ; [SP-1336]
            adc  #$B3            ; A=A+$B3 X=$0031 Y=$0000 ; [SP-1336]
            ldy  #$1B            ; A=A+$B3 X=$0031 Y=$001B ; [SP-1336]
            jsr  $03A3           ; A=A+$B3 X=$0031 Y=$001B ; [SP-1338]
            cmp  #$32            ; A=A+$B3 X=$0031 Y=$001B ; [SP-1338]
            bne  move_turn_encounter_roll     ; A=A+$B3 X=$0031 Y=$001B ; [SP-1338]
; === End of while loop ===

move_turn_party_loop lda  #$04            ; A=$0004 X=$0031 Y=$001B ; [SP-1338]
            sta  $D5             ; A=$0004 X=$0031 Y=$001B ; [SP-1338]
            dec  move_regen_counter     ; A=$0004 X=$0031 Y=$001B ; [SP-1338]
            bpl  move_turn_check_next     ; A=$0004 X=$0031 Y=$001B ; [SP-1338]
            lda  #$09            ; A=$0009 X=$0031 Y=$001B ; [SP-1338]
            sta  move_regen_counter     ; A=$0009 X=$0031 Y=$001B ; [SP-1338]

; === while loop starts here [nest:22] ===
; XREF: 2 refs (1 jump) (1 branch) from move_turn_party_loop, move_turn_checksum
move_turn_check_next dec  $D5             ; A=$0009 X=$0031 Y=$001B ; [SP-1338]
            bpl  move_turn_check_class     ; A=$0009 X=$0031 Y=$001B ; [SP-1338]
            lda  $B769           ; A=[$B769] X=$0031 Y=$001B ; [SP-1338]
            cmp  #$AA            ; A=[$B769] X=$0031 Y=$001B ; [SP-1338]
            bne  move_turn_display_status     ; A=[$B769] X=$0031 Y=$001B ; [SP-1338]
            pla                  ; A=[stk] X=$0031 Y=$001B ; [SP-1337]
; XREF: 1 ref (1 branch) from move_turn_check_next
move_turn_display_status jsr  move_display_party_status       ; A=[stk] X=$0031 Y=$001B ; [OPT] TAIL_CALL: Tail call: JSR/JSL at $0074B0 followed by RTS ; [SP-1339]
            rts                  ; A=[stk] X=$0031 Y=$001B ; [SP-1337]
; XREF: 1 ref (1 branch) from move_turn_check_next
move_turn_check_class jsr  $46F6           ; A=[stk] X=$0031 Y=$001B ; [SP-1339]
            ldy  #$17            ; A=[stk] X=$0031 Y=$0017 ; [SP-1339]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0017 ; [SP-1339]
            cmp  #$D7            ; A=[stk] X=$0031 Y=$0017 ; [SP-1339]
            bne  move_turn_check_cleric     ; A=[stk] X=$0031 Y=$0017 ; [SP-1339]
            ldy  #$19            ; A=[stk] X=$0031 Y=$0019 ; [SP-1339]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0019 ; [SP-1339]
            ldy  #$14            ; A=[stk] X=$0031 Y=$0014 ; [SP-1339]
            cmp  ($FE),Y         ; A=[stk] X=$0031 Y=$0014 ; [SP-1339]
            bcs  move_turn_check_cleric     ; A=[stk] X=$0031 Y=$0014 ; [SP-1339]
            jsr  magic_cast_spell       ; A=[stk] X=$0031 Y=$0014 ; [SP-1341]
; XREF: 2 refs (2 branches) from move_turn_check_class, move_turn_check_class
move_turn_check_cleric ldy  #$17            ; A=[stk] X=$0031 Y=$0017 ; [SP-1341]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0017 ; [SP-1341]
            cmp  #$C3            ; A=[stk] X=$0031 Y=$0017 ; [SP-1341]
            bne  move_turn_check_lark     ; A=[stk] X=$0031 Y=$0017 ; [SP-1341]
            ldy  #$19            ; A=[stk] X=$0031 Y=$0019 ; [SP-1341]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0019 ; [SP-1341]
            ldy  #$15            ; A=[stk] X=$0031 Y=$0015 ; [SP-1341]
            cmp  ($FE),Y         ; A=[stk] X=$0031 Y=$0015 ; [SP-1341]
            bcs  move_turn_check_lark     ; A=[stk] X=$0031 Y=$0015 ; [SP-1341]
            jsr  magic_cast_spell       ; A=[stk] X=$0031 Y=$0015 ; [SP-1343]
; XREF: 2 refs (2 branches) from move_turn_check_cleric, move_turn_check_cleric
move_turn_check_lark ldy  #$17            ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
            cmp  #$CC            ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
            beq  move_turn_regen_mp_str     ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
            cmp  #$C4            ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
            beq  move_turn_regen_mp_str     ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
            cmp  #$C1            ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
            beq  move_turn_regen_mp_str     ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
            jmp  move_turn_check_wizard     ; A=[stk] X=$0031 Y=$0017 ; [SP-1343]
; XREF: 3 refs (3 branches) from move_turn_check_lark, move_turn_check_lark, move_turn_check_lark
move_turn_regen_mp_str ldy  #$14            ; A=[stk] X=$0031 Y=$0014 ; [SP-1343]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0014 ; [SP-1343]
            jsr  combat_bcd_to_binary       ; A=[stk] X=$0031 Y=$0014 ; [SP-1345]
            lsr  a               ; A=[stk] X=$0031 Y=$0014 ; [SP-1345]
            jsr  combat_binary_to_bcd       ; A=[stk] X=$0031 Y=$0014 ; [SP-1347]
            ldy  #$19            ; A=[stk] X=$0031 Y=$0019 ; [SP-1347]
            cmp  ($FE),Y         ; A=[stk] X=$0031 Y=$0019 ; [SP-1347]
            bcc  move_turn_check_wizard     ; A=[stk] X=$0031 Y=$0019 ; [SP-1347]
            beq  move_turn_check_wizard     ; A=[stk] X=$0031 Y=$0019 ; [SP-1347]
            jsr  magic_cast_spell       ; A=[stk] X=$0031 Y=$0019 ; [SP-1349]
; XREF: 3 refs (1 jump) (2 branches) from move_turn_check_lark, move_turn_regen_mp_str, move_turn_regen_mp_str
move_turn_check_wizard ldy  #$17            ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
            cmp  #$D0            ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
            beq  move_turn_regen_mp_wis    ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
            cmp  #$C9            ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
            beq  move_turn_regen_mp_wis    ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
            cmp  #$C4            ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
            beq  move_turn_regen_mp_wis    ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
            jmp  move_turn_regen_mp_int    ; A=[stk] X=$0031 Y=$0017 ; [SP-1349]
; XREF: 3 refs (3 branches) from move_turn_check_wizard, move_turn_check_wizard, move_turn_check_wizard
move_turn_regen_mp_wis ldy  #$15            ; A=[stk] X=$0031 Y=$0015 ; [SP-1349]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0015 ; [SP-1349]
            jsr  combat_bcd_to_binary       ; A=[stk] X=$0031 Y=$0015 ; [SP-1351]
            lsr  a               ; A=[stk] X=$0031 Y=$0015 ; [SP-1351]
            jsr  combat_binary_to_bcd       ; A=[stk] X=$0031 Y=$0015 ; [SP-1353]
            ldy  #$19            ; A=[stk] X=$0031 Y=$0019 ; [SP-1353]
            cmp  ($FE),Y         ; A=[stk] X=$0031 Y=$0019 ; [SP-1353]
            bcc  move_turn_regen_mp_int    ; A=[stk] X=$0031 Y=$0019 ; [SP-1353]
            beq  move_turn_regen_mp_int    ; A=[stk] X=$0031 Y=$0019 ; [SP-1353]
            jsr  magic_cast_spell       ; A=[stk] X=$0031 Y=$0019 ; [SP-1355]
; XREF: 3 refs (1 jump) (2 branches) from move_turn_regen_mp_wis, move_turn_check_wizard, move_turn_regen_mp_wis
move_turn_regen_mp_int ldy  #$17            ; A=[stk] X=$0031 Y=$0017 ; [SP-1355]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0017 ; [SP-1355]
            cmp  #$D2            ; A=[stk] X=$0031 Y=$0017 ; [SP-1355]
            bne  move_turn_poison_damage    ; A=[stk] X=$0031 Y=$0017 ; [SP-1355]
            ldy  #$15            ; A=[stk] X=$0031 Y=$0015 ; [SP-1355]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0015 ; [SP-1355]
            jsr  combat_bcd_to_binary       ; A=[stk] X=$0031 Y=$0015 ; [SP-1357]
            lsr  a               ; A=[stk] X=$0031 Y=$0015 ; [SP-1357]
            jsr  combat_binary_to_bcd       ; A=[stk] X=$0031 Y=$0015 ; [SP-1359]
            ldy  #$19            ; A=[stk] X=$0031 Y=$0019 ; [SP-1359]
            cmp  ($FE),Y         ; A=[stk] X=$0031 Y=$0019 ; [SP-1359]
            bcc  move_turn_poison_damage    ; A=[stk] X=$0031 Y=$0019 ; [SP-1359]
            beq  move_turn_poison_damage    ; A=[stk] X=$0031 Y=$0019 ; [SP-1359]
            ldy  #$14            ; A=[stk] X=$0031 Y=$0014 ; [SP-1359]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0014 ; [SP-1359]
            jsr  combat_bcd_to_binary       ; A=[stk] X=$0031 Y=$0014 ; [SP-1361]
            lsr  a               ; A=[stk] X=$0031 Y=$0014 ; [SP-1361]
            jsr  combat_binary_to_bcd       ; A=[stk] X=$0031 Y=$0014 ; [SP-1363]
            ldy  #$19            ; A=[stk] X=$0031 Y=$0019 ; [SP-1363]
            cmp  ($FE),Y         ; A=[stk] X=$0031 Y=$0019 ; [SP-1363]

; === while loop starts here [nest:25] ===
; XREF: 1 ref (1 branch) from move_turn_add_exp
move_turn_poison_check bcc  move_turn_poison_damage    ; A=[stk] X=$0031 Y=$0019 ; [SP-1363]
            beq  move_turn_poison_damage    ; A=[stk] X=$0031 Y=$0019 ; [SP-1363]
            jsr  magic_cast_spell       ; A=[stk] X=$0031 Y=$0019 ; [SP-1365]
; XREF: 5 refs (5 branches) from move_turn_poison_check, move_turn_regen_mp_int, move_turn_poison_check, move_turn_regen_mp_int, move_turn_regen_mp_int
move_turn_poison_damage ldy  #$11            ; A=[stk] X=$0031 Y=$0011 ; [SP-1365]
            lda  ($FE),Y         ; A=[stk] X=$0031 Y=$0011 ; [SP-1365]
            cmp  #$C4            ; A=[stk] X=$0031 Y=$0011 ; [SP-1365]
            beq  move_turn_checksum    ; A=[stk] X=$0031 Y=$0011 ; [SP-1365]
            cmp  #$C1            ; A=[stk] X=$0031 Y=$0011 ; [SP-1365]
            beq  move_turn_checksum    ; A=[stk] X=$0031 Y=$0011 ; [SP-1365]
            cmp  #$00            ; A=[stk] X=$0031 Y=$0011 ; [SP-1365]
            beq  move_turn_checksum    ; A=[stk] X=$0031 Y=$0011 ; [SP-1365]
            lda  #$10            ; A=$0010 X=$0031 Y=$0011 ; [SP-1365]
            jsr  magic_check_mp       ; A=$0010 X=$0031 Y=$0011 ; [SP-1367]
            ldy  #$11            ; A=$0010 X=$0031 Y=$0011 ; [SP-1367]
            lda  ($FE),Y         ; A=$0010 X=$0031 Y=$0011 ; [SP-1367]
            cmp  #$D0            ; A=$0010 X=$0031 Y=$0011 ; [SP-1367]
            bne  move_turn_add_hp    ; A=$0010 X=$0031 Y=$0011 ; [SP-1367]
            lda  #$01            ; A=$0001 X=$0031 Y=$0011 ; [SP-1367]
            jsr  combat_apply_damage       ; A=$0001 X=$0031 Y=$0011 ; [SP-1369]

; === while loop starts here [nest:23] ===
; XREF: 1 ref (1 branch) from move_turn_checksum
move_turn_add_exp jsr  render_encrypt_records        ; A=$0001 X=$0031 Y=$0011 ; [SP-1371]
            jsr  $46BA           ; A=$0001 X=$0031 Y=$0011 ; [SP-1373]
            bne  move_turn_poison_check    ; A=$0001 X=$0031 Y=$0011 ; [SP-1373]
            cmp  #$D3            ; A=$0001 X=$0031 Y=$0011 ; [SP-1373]
            DB      $CF
            dec  $FFA1           ; A=$0001 X=$0031 Y=$0011 ; [SP-1373]
            DB      $00,$20,$E4,$88
; XREF: 1 ref (1 branch) from move_turn_poison_damage
move_turn_add_hp lda  move_regen_counter     ; A=[$75AD] X=$0031 Y=$0011 ; [SP-1376]
            bne  move_turn_checksum    ; A=[$75AD] X=$0031 Y=$0011 ; [SP-1376]
            lda  #$01            ; A=$0001 X=$0031 Y=$0011 ; [SP-1376]
            jsr  combat_add_hp      ; A=$0001 X=$0031 Y=$0011 ; [SP-1378]
; XREF: 4 refs (4 branches) from move_turn_poison_damage, move_turn_add_hp, move_turn_poison_damage, move_turn_poison_damage
move_turn_checksum jsr  combat_checksum_xor        ; A=$0001 X=$0031 Y=$0011 ; [SP-1380]
            cmp  #$0F            ; A=$0001 X=$0031 Y=$0011 ; [SP-1380]
            bne  move_turn_add_exp    ; A=$0001 X=$0031 Y=$0011 ; [SP-1380]
            jmp  move_turn_check_next     ; A=$0001 X=$0031 Y=$0011 ; [SP-1380]
move_encounter_counter
            DB      $0A
move_regen_counter
            DB      $09

; ---------------------------------------------------------------------------
; magic_cast_spell  [5 calls]
;   Called by: move_turn_check_class, move_turn_poison_check, move_turn_regen_mp_str, move_turn_check_cleric, move_turn_regen_mp_wis
; ---------------------------------------------------------------------------

; FUNC $0075AE: register -> A:X [L]
; Proto: uint32_t func_0075AE(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [1 dead stores]
; XREF: 5 refs (5 calls) from move_turn_check_class, move_turn_poison_check, move_turn_regen_mp_str, move_turn_check_cleric, move_turn_regen_mp_wis
magic_cast_spell   sed                  ; A=$0001 X=$0031 Y=$0011 ; [SP-1380]
            ldy  #$19            ; A=$0001 X=$0031 Y=$0019 ; [SP-1380]
            lda  ($FE),Y         ; A=$0001 X=$0031 Y=$0019 ; [SP-1380]
            clc                  ; A=$0001 X=$0031 Y=$0019 ; [SP-1380]
            adc  #$01            ; A=A+$01 X=$0031 Y=$0019 ; [SP-1380]
            sta  ($FE),Y         ; A=A+$01 X=$0031 Y=$0019 ; [SP-1380]
            cld                  ; A=A+$01 X=$0031 Y=$0019 ; [SP-1380]
            rts                  ; A=A+$01 X=$0031 Y=$0019 ; [SP-1378]

; ---------------------------------------------------------------------------
; magic_resolve_effect  [11 calls]
;   Called by: render_party_status_disp, char_turn_loop, char_turn_next, char_use_powder, loc_00917A, combat_end_flag, dungeon_lava
; ---------------------------------------------------------------------------

; FUNC $0075BA: register -> A:X [I]
; Proto: uint32_t func_0075BA(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [1 dead stores]
; XREF: 11 refs (11 calls) from render_party_status_disp, char_turn_loop, char_turn_next, char_use_powder, loc_00917A, ...
magic_resolve_effect   jsr  $46F6           ; A=A+$01 X=$0031 Y=$0019 ; [SP-1380]
            ldy  #$11            ; A=A+$01 X=$0031 Y=$0011 ; [SP-1380]
            lda  ($FE),Y         ; A=A+$01 X=$0031 Y=$0011 ; [SP-1380]
            cmp  #$C7            ; A=A+$01 X=$0031 Y=$0011 ; [SP-1380]
            beq  magic_effect_zero    ; A=A+$01 X=$0031 Y=$0011 ; [SP-1380]
            cmp  #$D0            ; A=A+$01 X=$0031 Y=$0011 ; [SP-1380]
            beq  magic_effect_zero    ; A=A+$01 X=$0031 Y=$0011 ; [SP-1380]
            lda  #$FF            ; A=$00FF X=$0031 Y=$0011 ; [SP-1380]
            rts                  ; A=$00FF X=$0031 Y=$0011 ; [SP-1378]
; XREF: 2 refs (2 branches) from magic_resolve_effect, magic_resolve_effect
magic_effect_zero lda  #$00            ; A=$0000 X=$0031 Y=$0011 ; [SP-1378]
            rts                  ; A=$0000 X=$0031 Y=$0011 ; [SP-1376]

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
; magic_check_mp  [1 call]
;   Called by: move_turn_poison_damage
; ---------------------------------------------------------------------------

; FUNC $00761D: register -> A:X []
; Proto: uint32_t func_00761D(uint16_t param_A, uint16_t param_X);
; Liveness: params(A,X) returns(A,X,Y) [3 dead stores]
; XREF: 1 ref (1 call) from move_turn_poison_damage
magic_check_mp   sta  $D0             ; A=$00FF X=$0031 Y=$0011 ; [SP-1378]
            sed                  ; A=$00FF X=$0031 Y=$0011 ; [SP-1378]
            sec                  ; A=$00FF X=$0031 Y=$0011 ; [SP-1378]
            ldy  #$22            ; A=$00FF X=$0031 Y=$0022 ; [SP-1378]
            lda  ($FE),Y         ; A=$00FF X=$0031 Y=$0022 ; [SP-1378]
            sbc  $D0             ; A=$00FF X=$0031 Y=$0022 ; [SP-1378]
            sta  ($FE),Y         ; A=$00FF X=$0031 Y=$0022 ; [SP-1378]
            dey                  ; A=$00FF X=$0031 Y=$0021 ; [SP-1378]
            lda  ($FE),Y         ; A=$00FF X=$0031 Y=$0021 ; [SP-1378]
            sbc  #$00            ; A=A X=$0031 Y=$0021 ; [SP-1378]
            sta  ($FE),Y         ; A=A X=$0031 Y=$0021 ; [SP-1378]
            dey                  ; A=A X=$0031 Y=$0020 ; [SP-1378]
            lda  ($FE),Y         ; A=A X=$0031 Y=$0020 ; [SP-1378]
            sbc  #$00            ; A=A X=$0031 Y=$0020 ; [SP-1378]
            sta  ($FE),Y         ; A=A X=$0031 Y=$0020 ; [SP-1378]
            cld                  ; A=A X=$0031 Y=$0020 ; [SP-1378]
            bcc  equip_handle        ; A=A X=$0031 Y=$0020 ; [SP-1378]
            rts                  ; A=A X=$0031 Y=$0020 ; [SP-1376]

; ---------------------------------------------------------------------------
; equip_handle  [1 call, 2 branches]
;   Called by: dungeon_trap_setup
; ---------------------------------------------------------------------------

; FUNC $00763B: register -> A:X []
; Proto: uint32_t func_00763B(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [1 dead stores]
; XREF: 3 refs (1 call) (2 branches) from magic_check_mp, equip_load_state, dungeon_trap_setup
equip_handle    lda  #$00            ; A=$0000 X=$0031 Y=$0020 ; [SP-1376]
            ldy  #$20            ; A=$0000 X=$0031 Y=$0020 ; [SP-1376]
            sta  ($FE),Y         ; A=$0000 X=$0031 Y=$0020 ; [SP-1376]
            ldy  #$21            ; A=$0000 X=$0031 Y=$0021 ; [SP-1376]
            sta  ($FE),Y         ; A=$0000 X=$0031 Y=$0021 ; [SP-1376]
            jsr  $46BA           ; A=$0000 X=$0031 Y=$0021 ; [SP-1378]
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
; equip_check_class  [2 calls]
;   Called by: shop_handle, equip_load_state
; ---------------------------------------------------------------------------

; FUNC $0077A2: register -> A:X [I]
; Proto: uint32_t func_0077A2(void);
; Liveness: returns(A,X,Y) [2 dead stores]
; XREF: 2 refs (2 calls) from shop_handle, equip_load_state
equip_check_class    lda  $10             ; A=[$0010] X=$0008 Y=$0023 ; [SP-1411]
            bmi  equip_class_done     ; A=[$0010] X=$0008 Y=$0023 ; [SP-1411]
            lda  #$40            ; A=$0040 X=$0008 Y=$0023 ; [SP-1411]
            sta  $F3             ; A=$0040 X=$0008 Y=$0023 ; [SP-1411]

; === while loop starts here [nest:25] ===
; XREF: 1 ref (1 branch) from equip_class_push_state
equip_class_check_offset ldy  #$14            ; A=$0040 X=$0008 Y=$0014 ; [SP-1411]

; === loop starts here (counter: Y, range: 20..0, iters: 20) [nest:26] ===
; XREF: 1 ref (1 branch) from equip_class_push_state
equip_class_load_ptr ldx  $F3             ; A=$0040 X=$0008 Y=$0014 ; [SP-1411]

; === loop starts here (counter: X) [nest:27] ===
; XREF: 1 ref (1 branch) from equip_class_push_state
equip_class_push_state pha                  ; A=$0040 X=$0008 Y=$0014 ; [OPT] PEEPHOLE: Redundant PHA/PLA: 2 byte pattern at $0077AE ; [SP-1412]
            pla                  ; A=[stk] X=$0008 Y=$0014 ; [SP-1411]
            dex                  ; A=[stk] X=$0007 Y=$0014 ; [SP-1411]
            bne  equip_class_push_state     ; A=[stk] X=$0007 Y=$0014 ; [SP-1411]
; === End of loop (counter: X) ===

            bit  $C030           ; SPKR - Speaker toggle {Speaker} <speaker_toggle>
            dey                  ; A=[stk] X=$0007 Y=$0013 ; [SP-1411]
            bne  equip_class_load_ptr     ; A=[stk] X=$0007 Y=$0013 ; [SP-1411]
; === End of loop (counter: Y) ===

            inc  $F3             ; A=[stk] X=$0007 Y=$0013 ; [SP-1411]
            lda  $F3             ; A=[$00F3] X=$0007 Y=$0013 ; [SP-1411]
            cmp  #$C0            ; A=[$00F3] X=$0007 Y=$0013 ; [SP-1411]
            bcc  equip_class_check_offset     ; A=[$00F3] X=$0007 Y=$0013 ; [SP-1411]
; XREF: 1 ref (1 branch) from equip_check_class
equip_class_done rts                  ; A=[$00F3] X=$0007 Y=$0013 ; [SP-1409]

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


; ---------------------------------------------------------------------------
; world_move_handler  [1 call]
;   Called by: game_loop_call_terrain
;   Calls: char_decrypt_records
; ---------------------------------------------------------------------------

; FUNC $007961: register -> A:X []
; Liveness: returns(A,X,Y) [5 dead stores]
; XREF: 1 ref (1 call) from game_loop_call_terrain
world_move_handler  jsr  $0230           ; A=[$00F3] X=$0007 Y=$0013 ; [SP-1455]
            jsr  char_decrypt_records       ; A=[$00F3] X=$0007 Y=$0013 ; [SP-1457]
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

; ---------------------------------------------------------------------------
; dungeon_handle  [1 call]
;   Called by: world_move_dungeon
; ---------------------------------------------------------------------------

; FUNC $007A0C: register -> A:X [I]
; Proto: uint32_t func_007A0C(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y)
; XREF: 1 ref (1 call) from world_move_dungeon
dungeon_handle lda  $E2             ; A=[$00E2] X=$00C0 Y=$0020 ; [SP-1476]
            beq  dungeon_check_light  ; A=[$00E2] X=$00C0 Y=$0020 ; [SP-1476]
            rts                  ; A=[$00E2] X=$00C0 Y=$0020 ; [SP-1474]
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
; tile_update  [1 call]
;   Called by: world_move_dungeon
; ---------------------------------------------------------------------------

; FUNC $007A81: register -> A:X [I]
; Proto: uint32_t func_007A81(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y)
; XREF: 1 ref (1 call) from world_move_dungeon
tile_update lda  #$20            ; A=$0020 X=$00C0 Y=$000D ; [SP-1480]
            sta  $D0             ; A=$0020 X=$00C0 Y=$000D ; [SP-1480]

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

; ---------------------------------------------------------------------------
; tile_check_passable  [3 calls]
;   Called by: tile_update_char_ptr
;   Preserves: A
; ---------------------------------------------------------------------------

; FUNC $007C0C: register -> A:X [I]
; Proto: uint32_t func_007C0C(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Frame: push_only [saves: A]
; Liveness: params(A,X,Y) returns(A,X,Y) [3 dead stores]
; XREF: 3 refs (3 calls) from tile_update_char_ptr, tile_update_char_ptr, tile_update_char_ptr
tile_check_passable pha                  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            lda  $4F00,X         ; -> $4FC0 ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            cmp  #$40            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            bcs  tile_passable_check_type  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            cmp  #$2C            ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            bcc  tile_passable_check_type  ; A=A&$3F X=$00C0 Y=$000D ; [SP-1531]
            pla                  ; A=[stk] X=$00C0 Y=$000D ; [SP-1530]
            cmp  #$00            ; A=[stk] X=$00C0 Y=$000D ; [SP-1530]
            bne  tile_not_passable  ; A=[stk] X=$00C0 Y=$000D ; [SP-1530]
            jmp  tile_is_passable  ; A=[stk] X=$00C0 Y=$000D ; [SP-1530]
; XREF: 2 refs (2 branches) from tile_check_passable, tile_check_passable
tile_passable_check_type pla                  ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
            cmp  #$04            ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
            beq  tile_is_passable  ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
            cmp  #$08            ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
            beq  tile_is_passable  ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
            cmp  #$0C            ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
            beq  tile_is_passable  ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
            cmp  #$20            ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
            beq  tile_is_passable  ; A=[stk] X=$00C0 Y=$000D ; [SP-1529]
; XREF: 1 ref (1 branch) from tile_check_passable
tile_not_passable lda  #$FF            ; A=$00FF X=$00C0 Y=$000D ; [SP-1529]
            rts                  ; A=$00FF X=$00C0 Y=$000D ; [SP-1527]
; XREF: 5 refs (1 jump) (4 branches) from tile_passable_check_type, tile_passable_check_type, tile_check_passable, tile_passable_check_type, tile_passable_check_type
tile_is_passable lda  #$00            ; A=$0000 X=$00C0 Y=$000D ; [SP-1527]
            rts                  ; A=$0000 X=$00C0 Y=$000D ; [SP-1525]

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


; ===========================================================================
; COMPUTATION (7 functions)
; ===========================================================================

; ---------------------------------------------------------------------------
; render_sign_extend  [6 calls, 1 jump]
;   Called by: render_target_calc_dist, tile_check_special, tile_update_wait_anim3
; ---------------------------------------------------------------------------

; FUNC $007DFC: register -> A:X [L]
; Proto: uint32_t func_007DFC(uint16_t param_X, uint16_t param_Y);
; Liveness: params(X,Y) returns(A,X,Y)
; XREF: 7 refs (6 calls) (1 jump) from render_target_calc_dist, tile_check_special, tile_update_wait_anim3, tile_check_special, render_tile_scale, ...
render_sign_extend   cmp  #$00            ; A=$00FF X=$0007 Y=$0001 ; [SP-1555]
            beq  render_sign_done    ; A=$00FF X=$0007 Y=$0001 ; [SP-1555]
            bmi  render_sign_negative    ; A=$00FF X=$0007 Y=$0001 ; [SP-1555]
            lda  #$01            ; A=$0001 X=$0007 Y=$0001 ; [SP-1555]
; XREF: 1 ref (1 branch) from render_sign_extend
render_sign_done rts                  ; A=$0001 X=$0007 Y=$0001 ; [SP-1553]
; XREF: 1 ref (1 branch) from render_sign_extend
render_sign_negative lda  #$FF            ; A=$00FF X=$0007 Y=$0001 ; [SP-1553]
            rts                  ; A=$00FF X=$0007 Y=$0001 ; [SP-1551]

; ---------------------------------------------------------------------------
; render_tile_scale  [2 calls]
;   Called by: tile_special_surface
; ---------------------------------------------------------------------------

; FUNC $007E08: register -> A:X []
; Proto: uint32_t func_007E08(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Liveness: params(A,X,Y) returns(A,X,Y)
; XREF: 2 refs (2 calls) from tile_special_surface, tile_special_surface
render_tile_scale  asl  a               ; A=$00FF X=$0007 Y=$0001 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1551]
            asl  a               ; A=$00FF X=$0007 Y=$0001 ; [SP-1551]
            jmp  render_sign_extend       ; A=$00FF X=$0007 Y=$0001 ; [SP-1551]
; === End of while loop ===


; ---------------------------------------------------------------------------
; render_abs_value  [4 calls]
;   Called by: render_target_check_alive, tile_special_calc_dist
; ---------------------------------------------------------------------------

; FUNC $007E0D: register -> A:X [L]
; Proto: uint32_t func_007E0D(uint16_t param_A, uint16_t param_X, uint16_t param_Y);
; Liveness: params(A,X,Y) returns(A,X,Y)
; XREF: 4 refs (4 calls) from render_target_check_alive, render_target_check_alive, tile_special_calc_dist, tile_special_calc_dist
render_abs_value    cmp  #$80            ; A=$00FF X=$0007 Y=$0001 ; [SP-1551]
            bcs  render_negate     ; A=$00FF X=$0007 Y=$0001 ; [SP-1551]
            rts                  ; A=$00FF X=$0007 Y=$0001 ; [SP-1549]
; XREF: 1 ref (1 branch) from render_abs_value
render_negate eor  #$FF            ; A=A^$FF X=$0007 Y=$0001 ; [SP-1549]
            clc                  ; A=A^$FF X=$0007 Y=$0001 ; [SP-1549]
            adc  #$01            ; A=A+$01 X=$0007 Y=$0001 ; [SP-1549]
            rts                  ; A=A+$01 X=$0007 Y=$0001 ; [SP-1547]

; ---------------------------------------------------------------------------
; combat_tile_at_xy  [25 calls]
;   Called by: tile_update_bcd_food, game_loop_combat_lookup, render_combat_dec_range, render_combat_resolve, render_target_calc_dist, render_party_final, render_combat_check_mon, render_combat_mon_special
; ---------------------------------------------------------------------------

; FUNC $007E18: register -> A:X [L]
; Proto: uint32_t func_007E18(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [4 dead stores]
; XREF: 25 refs (16 calls) from tile_update_bcd_food, game_loop_combat_lookup, $00812F, render_combat_dec_range, render_combat_resolve, ...
combat_tile_at_xy  clc                  ; A=A+$01 X=$0007 Y=$0001 ; [SP-1547]
            lda  $03             ; A=[$0003] X=$0007 Y=$0001 ; [SP-1547]
            asl  a               ; A=[$0003] X=$0007 Y=$0001 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1547]
            asl  a               ; A=[$0003] X=$0007 Y=$0001 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1547]
            asl  a               ; A=[$0003] X=$0007 Y=$0001 ; [SP-1547]
            adc  $03             ; A=[$0003] X=$0007 Y=$0001 ; [SP-1547]
            adc  $03             ; A=[$0003] X=$0007 Y=$0001 ; [SP-1547]
            adc  $03             ; A=[$0003] X=$0007 Y=$0001 ; [SP-1547]
            adc  $02             ; A=[$0003] X=$0007 Y=$0001 ; [SP-1547]
            sta  $FE             ; A=[$0003] X=$0007 Y=$0001 ; [SP-1547]
            lda  #$99            ; A=$0099 X=$0007 Y=$0001 ; [SP-1547]
            sta  $FF             ; A=$0099 X=$0007 Y=$0001 ; [SP-1547]
            ldy  #$00            ; A=$0099 X=$0007 Y=$0000 ; [SP-1547]
            lda  ($FE),Y         ; A=$0099 X=$0007 Y=$0000 ; [SP-1547]
            rts                  ; A=$0099 X=$0007 Y=$0000 ; [SP-1545]

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
; render_viewport_flash  [1 call]
; ---------------------------------------------------------------------------
; XREF: 1 ref (1 call) from $0082B2
render_viewport_flash cmp  #$02            ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]
            beq  render_flash_activate ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]
            cmp  #$04            ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]
            beq  render_flash_activate ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]
            cmp  #$06            ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]
            beq  render_flash_activate ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]
            cmp  #$10            ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]
            beq  render_flash_activate ; A=$0000 X=$0007 Y=$0000 ; [SP-1540]
            lda  #$FF            ; A=$00FF X=$0007 Y=$0000 ; [SP-1540]
            rts                  ; A=$00FF X=$0007 Y=$0000 ; [SP-1538]
; XREF: 4 refs (4 branches) from render_viewport_flash, render_viewport_flash, render_viewport_flash, render_viewport_flash
render_flash_activate lda  #$F6            ; A=$00F6 X=$0007 Y=$0000 ; [SP-1538]
            jsr  $4705           ; Call $004705(A, 1 stack)
            ldx  #$FF            ; A=$00F6 X=$00FF Y=$0000 ; [SP-1540]
            ldy  #$20            ; A=$00F6 X=$00FF Y=$0020 ; [SP-1540]

; === loop starts here (counter: X) [nest:31] ===
; XREF: 2 refs (2 branches) from render_flash_delay_loop, render_flash_delay_loop
render_flash_delay_loop dex                  ; A=$00F6 X=$00FE Y=$0020 ; [SP-1540]
            bne  render_flash_delay_loop ; A=$00F6 X=$00FE Y=$0020 ; [SP-1540]
; === End of loop (counter: X) ===

            dey                  ; A=$00F6 X=$00FE Y=$001F ; [SP-1540]
            bne  render_flash_delay_loop ; A=$00F6 X=$00FE Y=$001F ; [SP-1540]
; === End of loop (counter: Y) ===

            lda  #$F6            ; A=$00F6 X=$00FE Y=$001F ; [SP-1540]
            jsr  $4705           ; A=$00F6 X=$00FE Y=$001F ; [SP-1542]
            lda  #$00            ; A=$0000 X=$00FE Y=$001F ; [SP-1542]
            rts                  ; A=$0000 X=$00FE Y=$001F ; [SP-1540]

; ---------------------------------------------------------------------------
; render_find_target  [1 call]
;   Called by: render_combat_mon_check
;   Calls: render_abs_value, render_sign_extend, combat_tile_at_xy, render_check_solid
; ---------------------------------------------------------------------------

; FUNC $007E85: register -> A:X [I]
; Proto: uint32_t func_007E85(void);
; Liveness: returns(A,X,Y) [9 dead stores]
; XREF: 1 ref (1 call) from render_combat_mon_check
render_find_target lda  #$FF            ; A=$00FF X=$00FE Y=$001F ; [SP-1540]
            sta  $D6             ; A=$00FF X=$00FE Y=$001F ; [SP-1540]
            sta  $D5             ; A=$00FF X=$00FE Y=$001F ; [SP-1540]
            sta  $D0             ; A=$00FF X=$00FE Y=$001F ; [SP-1540]

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

; ---------------------------------------------------------------------------
; render_encrypt_records  [29 calls]
;   Called by: render_combat_resolve, input_dungeon_gen_pos, file_mark_apply_loop, combat_end_flag, equip_handle, char_turn_next, char_turn_loop, move_turn_add_exp
; ---------------------------------------------------------------------------

; FUNC $0088E4: register -> A:X []
; Proto: uint32_t func_0088E4(void);
; Liveness: returns(A,X,Y) [2 dead stores]
; XREF: 29 refs (16 calls) from $005713, render_combat_resolve, $0092AD, render_combat_resolve, $0092B5, ...
render_encrypt_records    lda  $D5             ; A=[$00D5] X=X-$01 Y=$001F ; [SP-1888]
            asl  a               ; A=[$00D5] X=X-$01 Y=$001F ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1888]
            asl  a               ; A=[$00D5] X=X-$01 Y=$001F ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1888]
            asl  a               ; A=[$00D5] X=X-$01 Y=$001F ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1888]
            asl  a               ; A=[$00D5] X=X-$01 Y=$001F ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-1888]
            asl  a               ; A=[$00D5] X=X-$01 Y=$001F ; [SP-1888]
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
; render_draw_text_row  [14 calls]
;   Called by: render_monster_attack, input_cmd_table
;   Calls: render_advance_ptr
; ---------------------------------------------------------------------------

; FUNC $008932: register -> A:X []
; Proto: uint32_t func_008932(void);
; Liveness: returns(A,X,Y) [2 dead stores]
; XREF: 14 refs (14 calls) from $00846C, render_monster_attack, $005D41, $005D76, $006D4F, ...
render_draw_text_row tay                  ; A=$0098 X=$0000 Y=$0098 ; [SP-1886]
            lda  #$7A            ; A=$007A X=$0000 Y=$0098 ; [SP-1886]
            sta  $FE             ; A=$007A X=$0000 Y=$0098 ; [SP-1886]
            lda  #$89            ; A=$0089 X=$0000 Y=$0098 ; [SP-1886]
            sta  $FF             ; A=$0089 X=$0000 Y=$0098 ; [SP-1886]
            ldx  #$00            ; A=$0089 X=$0000 Y=$0098 ; [SP-1886]

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

; --- Data region (921 bytes, text data) ---
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


; ---------------------------------------------------------------------------
; calc_hgr_scanline  [11 calls]
;   Called by: dungeon_check_tile, dungeon_tile_table, dungeon_set_encounter, dungeon_tile_inscription, input_dungeon_gen_pos, dungeon_fountain, dungeon_lava
; ---------------------------------------------------------------------------

; FUNC $0093DE: register -> A:X []
; Proto: uint32_t func_0093DE(uint16_t param_X);
; Liveness: params(X) returns(A,X,Y) [2 dead stores]
; XREF: 11 refs (11 calls) from $005BC4, dungeon_check_tile, dungeon_tile_table, dungeon_set_encounter, dungeon_tile_inscription, ...
calc_hgr_scanline  clc                  ; A=[$00B2] X=$0000 Y=$0020 ; [SP-2381]
            lda  $03             ; A=[$0003] X=$0000 Y=$0020 ; [SP-2381]
            asl  a               ; A=[$0003] X=$0000 Y=$0020 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-2381]
            asl  a               ; A=[$0003] X=$0000 Y=$0020 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-2381]
            asl  a               ; A=[$0003] X=$0000 Y=$0020 ; [OPT] STRENGTH_RED: Multiple ASL A: consider using lookup table for render_encrypt_records ; [SP-2381]
            asl  a               ; A=[$0003] X=$0000 Y=$0020 ; [SP-2381]
            adc  $02             ; A=[$0003] X=$0000 Y=$0020 ; [SP-2381]
            sta  $FE             ; A=[$0003] X=$0000 Y=$0020 ; [SP-2381]
            clc                  ; A=[$0003] X=$0000 Y=$0020 ; [SP-2381]
            lda  #$10            ; A=$0010 X=$0000 Y=$0020 ; [SP-2381]
            adc  $13             ; A=$0010 X=$0000 Y=$0020 ; [SP-2381]
            sta  $FF             ; A=$0010 X=$0000 Y=$0020 ; [SP-2381]
            ldy  #$00            ; A=$0010 X=$0000 Y=$0000 ; [SP-2381]
            lda  ($FE),Y         ; A=$0010 X=$0000 Y=$0000 ; [SP-2381]
            rts                  ; A=$0010 X=$0000 Y=$0000 ; [SP-2379]

; ---
            DB      $00,$01,$00,$FF,$FF,$00,$01,$00,$32,$22,$0D
