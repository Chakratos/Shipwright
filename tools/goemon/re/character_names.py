#!/usr/bin/env python3
"""Corroborated NG5E character names for the original 0..3 character IDs.

Source boundaries:
- The original MIPS routine binds numeric IDs to graphics roots, independently
  verified from the user's genuine ROM.
- The original 1,691-frame game capture observed PlayerTask.character_id
  equal global selected character D_8015C5DC in every sample.
- Published USA GameShark character modifiers write the *last byte*
  of that 32-bit big-endian global at 0x8015C5DF and label 00..03.
  Those externally sourced NAME labels are not proven from a ROM text table.
"""
from __future__ import annotations

GLOBAL_CHARACTER_U32_ADDR = 0x8015C5DC
GAMESHARK_CHARACTER_BYTE_ADDR = 0x8015C5DF
CHARACTER_NAMES = ("Goemon", "Ebisumaru", "Sasuke", "Yae")
CHARACTER_GRAPHICS_ROOTS = (288, 292, 296, 300)
NAME_SOURCES = (
    "https://gamegenie.com/cheats/gameshark/n64/mystical_ninja_goemon.html",
    "https://almarsguides.com/retro/walkthroughs/n64/games/mysticalninjastarringgoemon/actionreplay/",
)

def corroborated_character_names(roots: tuple[int, ...]) -> dict[int, dict]:
    if GAMESHARK_CHARACTER_BYTE_ADDR != GLOBAL_CHARACTER_U32_ADDR + 3:
        raise ValueError("GameShark byte must be the low byte of original BE u32")
    if tuple(roots) != CHARACTER_GRAPHICS_ROOTS:
        raise ValueError("graphics roots differ from the original source-verified order")
    return {
        index: {
            "original_character_id": index,
            "character_name": name,
            "graphics_root_file_id": roots[index],
            "name_evidence": "two published NG5E USA GameShark character modifiers",
            "name_source_urls": list(NAME_SOURCES),
            "game_global_character_word_address": f"0x{GLOBAL_CHARACTER_U32_ADDR:08X}",
            "gameshark_character_byte_address": f"0x{GAMESHARK_CHARACTER_BYTE_ADDR:08X}",
            "name_provenance": "external_cheat_tables_correlated_with_original_runtime",
            "rom_proven_name_string": False,
        }
        for index, name in enumerate(CHARACTER_NAMES)
    }
