# Original NG5E character-ID → graphics-file binding (2026-11-06)

**Evidence:** exact NTSC-U NG5E user ROM SHA-256
`1603be37427a33548857fc3d2e8867ede71121c353fb631b79b44f1d94845d80`,
decompressed SHA-256
`e40bee20508c2e29e651dca4e47504e40f908f0a2186e34a582784bf5a64be4c`.

## Proven from original machine code

The original character handling function
`func_801DC9C8_5988D8` starts at original CPU address `0x801DC9C8`,
decompressed ROM file offset `0x5988D8`. It accepts the numerical
character index as its second argument (a1, consistent with pinned
Goemon64Recomp symbol/source signature).

Critical original MIPS instructions (addresses inside function):

| Function offset | Original operation | Semantics |
|---|---|---|
| +0x04 | `sw a1, 0x34(sp)` | Stores the supplied numeric index |
| +0x08 | `lbu t6, 0x37(sp)` | Reads its low 8-bit character ID |
| +0x0C | `lui t8, 0x8020` | Table high address |
| +0x14 | `addiu t8, t8, 0x4020` | Character graphic ID array at `0x80204020` |
| +0x18 | `sll t7, t6, 1` | Multiplies character ID by 2 (16-bit array elements) |
| +0x1C | `addu v0, t7, t8` | Computes `&graphics_file_ids[character_id]` |
| +0x28 | `lhu t9, 0(v0)` | Reads the indexed original graphics file ID |
| +0x38 | `sh t9, 0x3C(a2)` | Writes the selected file ID into the destination object |

The exact original table at CPU address `0x80204020` (decompressed
file offset `0x5BFF30`) contains four big-endian u16 IDs.

| Original numeric character ID | Corroborated name | Original graphics root file ID |
|---:|---|---:|
| 0 | Goemon | 288 |
| 1 | Ebisumaru | 292 |
| 2 | Sasuke | 296 |
| 3 | Yae | 300 |

**This mapping is now directly source-proven.** It is not derived merely
from the order of four asset files or from guessed character names.
The first root file IDs each begin a four-resource group; the +1 files
contain the already catalogued 45 PIC0000 blocks.

## Character name binding (external evidence + original runtime correlation)

The original Goemon trace records the global selected-character variable
`D_8015C5DC_15D1DC` (N64 big-endian u32 at `0x8015C5DC`) and the
`PlayerTask.character_id` at `+0x60`. The verified four-character,
1,691-frame runtime trace observed **0 mismatches** between them.

Two published USA GameShark tables identify the selected character
modifier at **`8015C5DF 00XX`**, which writes the low byte of that same
global u32, and give the names exactly as in the table above:

- [GameGenie: Mystical Ninja Starring Goemon USA](https://gamegenie.com/cheats/gameshark/n64/mystical_ninja_goemon.html)
- [Almar's Guides: N64 USA Action Replay character modifiers](https://almarsguides.com/retro/walkthroughs/n64/games/mysticalninjastarringgoemon/actionreplay/)

Thus the source-verified numeric PlayerTask ID → graphics file root
can be joined to the externally corroborated ID → character name.
**Important provenance boundary:** the numeric ID→file table is proven
by original ROM machine instructions, while the name labels come from
published cheat tables, not from strings decoded directly from the ROM.
Original mesh/rig, palettes and animation decoders are still missing.

`tools/goemon/re/character_names.py` preserves these two kinds of
evidence separately. The private character asset pack, graphics manifest
and PIC0000 catalog now label each character slot with that provenance.
Generic/synthetic ROM fixtures remain unnamed unless their graphics
roots match the corroborated NG5E table.

## Automated checks added

- `tools/goemon/re/character_id_binding.py` checks exact source
  instructions and the four original file IDs.
- `test_character_id_binding.py` guards against changes to indexing
  semantics and ambiguous IDs, using independent source-free fixtures.
- On `goemon-builder`, `real_rom_check.py` checks the **actual ROM
  machine instructions**, so green CI verifies both real ROM identity
  and this original executable-code invariant.
- The local original asset-pack manifest now includes
  `original_numeric_character_id` with the source proof. It still
  includes no guessed character name, and no copyrighted assets enter
  the repository or CI artifacts.

Next: recover original skeleton root pointers and texture/display-list
decoding, and connect runtime-generated private graphic assets to Ship's
resource subsystem. Verify the externally assigned character names via
direct on-screen character-switch capture if additional independent
ROM-internal confirmation is desired.
