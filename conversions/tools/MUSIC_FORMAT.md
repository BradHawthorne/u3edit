# MBS Music Format Reference

## Overview

The MBS file (5456 bytes, loaded at $9A00) contains Mockingboard AY-3-8910
sound chip register sequences for Ultima III's music. The Mockingboard is an
Apple II expansion card containing two General Instrument AY-3-8910 Programmable
Sound Generators (PSGs), providing 6 channels of square wave / noise synthesis.

## AY-3-8910 Registers

Each PSG has 14 registers (R0-R13):

| Register | Name | Range | Description |
|----------|------|-------|-------------|
| R0-R1 | Channel A Frequency | 12-bit | Tone period (lower = higher pitch) |
| R2-R3 | Channel B Frequency | 12-bit | Tone period |
| R4-R5 | Channel C Frequency | 12-bit | Tone period |
| R6 | Noise Period | 5-bit (0-31) | Noise generator frequency |
| R7 | Mixer Control | 8-bit | Enable/disable tone+noise per channel |
| R8 | Channel A Volume | 4-bit (0-15) | Volume or envelope mode |
| R9 | Channel B Volume | 4-bit (0-15) | Volume or envelope mode |
| R10 | Channel C Volume | 4-bit (0-15) | Volume or envelope mode |
| R11-R12 | Envelope Frequency | 16-bit | Envelope period |
| R13 | Envelope Shape | 4-bit (0-15) | Envelope waveform |

### Mixer Control (R7)

Bit layout: `--NCBA-ncba` (active low — 0 = enabled)

| Bit | Function |
|-----|----------|
| 0 | Channel A tone enable |
| 1 | Channel B tone enable |
| 2 | Channel C tone enable |
| 3 | Channel A noise enable |
| 4 | Channel B noise enable |
| 5 | Channel C noise enable |
| 6-7 | I/O port direction (unused) |

Example: `0x38` = all tones enabled, all noise disabled

### Frequency to Note Conversion

The AY-3-8910 clock in a Mockingboard is typically 1.0 MHz. The tone period
formula is:

```
frequency = clock / (16 * period)
period = clock / (16 * frequency)
```

Common note periods at 1.0 MHz clock:

| Note | Freq (Hz) | Period (decimal) | Period (hex) |
|------|-----------|-----------------|-------------|
| C2 | 65.4 | 956 | 03BC |
| D2 | 73.4 | 852 | 0354 |
| E2 | 82.4 | 759 | 02F7 |
| F2 | 87.3 | 717 | 02CD |
| G2 | 98.0 | 638 | 027E |
| A2 | 110.0 | 568 | 0238 |
| B2 | 123.5 | 506 | 01FA |
| C3 | 130.8 | 478 | 01DE |
| D3 | 146.8 | 426 | 01AA |
| E3 | 164.8 | 379 | 017B |
| F3 | 174.6 | 358 | 0166 |
| G3 | 196.0 | 319 | 013F |
| A3 | 220.0 | 284 | 011C |
| B3 | 246.9 | 253 | 00FD |
| C4 | 261.6 | 239 | 00EF |
| D4 | 293.7 | 213 | 00D5 |
| E4 | 329.6 | 190 | 00BE |
| F4 | 349.2 | 179 | 00B3 |
| G4 | 392.0 | 160 | 00A0 |
| A4 | 440.0 | 142 | 008E |
| B4 | 493.9 | 127 | 007F |
| C5 | 523.3 | 119 | 0077 |

## MBS Stream Opcodes

The MBS music driver reads a stream of opcodes. Values $00-$3F are note
pitch indices (the driver converts these to AY register values). Higher
values are control opcodes:

| Opcode | Name | Params | Description |
|--------|------|--------|-------------|
| $00 | REST | — | Silence (no note) |
| $01-$3F | NOTE | — | Play note at pitch index |
| $80 | LOOP | 2 bytes (addr) | Mark loop point / repeat to address |
| $81 | JUMP | 2 bytes (addr) | Jump to absolute address |
| $82 | END | — | End of music stream |
| $83 | WRITE | 2 bytes (reg, val) | Write value to AY register directly |
| $84 | TEMPO | 1 byte (speed) | Set playback speed (frames per tick) |
| $85 | MIXER | 1 byte (mask) | Set mixer control register |

### Pitch Index Table

The driver maps pitch indices ($01-$3F) to note names across 4+ octaves:

| Index | Note | Index | Note | Index | Note |
|-------|------|-------|------|-------|------|
| $01 | C1 | $0D | C2 | $19 | C3 |
| $02 | C#1 | $0E | C#2 | $1A | C#3 |
| $03 | D1 | $0F | D2 | $1B | D3 |
| $04 | D#1 | $10 | D#2 | $1C | D#3 |
| $05 | E1 | $11 | E2 | $1D | E3 |
| $06 | F1 | $12 | F2 | $1E | F3 |
| $07 | F#1 | $13 | F#2 | $1F | F#3 |
| $08 | G1 | $14 | G2 | $20 | G3 |
| $09 | G#1 | $15 | G#2 | $21 | G#3 |
| $0A | A1 | $16 | A2 | $22 | A3 |
| $0B | A#1 | $17 | A#2 | $23 | A#3 |
| $0C | B1 | $18 | B2 | $24 | B3 |
| $25 | C4 | $31 | C5 | — | — |

## Editing Workflow

### Viewing current music data
```bash
u3edit sound view MBS              # Full hex dump + stream analysis
u3edit sound view MBS --stream     # Decoded note/opcode stream
```

### Patching individual bytes
```bash
# Change a single note (e.g., at offset $0100)
u3edit sound edit MBS --offset 0x0100 --data "0A"

# Change a sequence of notes
u3edit sound edit MBS --offset 0x0100 --data "0A 0C 0E 10 12"
```

### Bulk replacement via JSON
```bash
# Export current state
u3edit sound view MBS --json -o mbs_current.json

# Modify JSON, then import
u3edit sound import MBS mbs_modified.json --backup
```

## External Tools

For creating entirely new music:

1. **AY-3-8910 Trackers**: Programs like Vortex Tracker II or Arkos Tracker
   can compose music for the AY chip and export register dumps.

2. **Manual hex editing**: Use the note table above to write melodies directly
   as pitch index sequences, with TEMPO opcodes to control speed.

3. **Register dump conversion**: If you have raw AY register writes from a
   tracker, convert them to MBS format using the WRITE ($83) opcode for
   direct register control.

## File Layout

The 5456-byte MBS file contains:

| Offset | Size | Description |
|--------|------|-------------|
| $0000+ | varies | Music stream data (notes, opcodes, control) |

The exact layout of music streams within the file depends on the number and
length of songs. Use `u3edit sound view MBS` to identify stream boundaries
by looking for END ($82) and JUMP ($81) opcodes.
