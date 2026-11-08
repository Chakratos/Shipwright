# Original NG5E Player Action and Graphics Writer Scan, 2026-11-08

## Exact verified result

Owner-PC original NG5E ROM (original and decompressed hashes checked), self-hosted Windows [run 42480203308](https://github.com/Chakratos/Shipwright/actions/runs/42480203308), SUCCESS, **320/320 Python tests plus native C++20 checks passed**.

Original source tool: tools/goemon/re/scan_player_object_writers.py (synthetic tests: tools/goemon/re/tests/test_scan_player_object_writers.py). The known character graphics-select routine func_801DC9C8 at VRAM 0x801DC9C8 / ROM offset 0x5988D8 establishes the executable player overlay to be **file-table entry 10**. It scans original MIPS machine-code metadata but NEVER exports raw original ROM bytes or instructions. Real writer *ownership remains unverified*.

| Executable region | Bytes examined | All tracked field-offset store matches | sb +0xCC PlayerTask.action_id syntactic candidates | sw +0x2C Object.graphics_1 syntactic candidates |
| --- | ---: | ---: | ---: | ---: |
| Original main | 524288 | 1131 | 0 | 248 |
| Original player overlay, runtime file 10 | 267264 | 664 | **10** | **131** |

All ten action byte-store offset matches in player overlay:
- PC 0x801CC3DC: store byte r13 at +0xCC(r16).
- PC 0x801D9E74: store byte r15 at +0xCC(r4).
- PC 0x801DA5D8: store byte r10 at +0xCC(r16).
- PC 0x801DAED4: store byte r17 at +0xCC(r16).
- PC 0x801DD640: store byte r11 at +0xCC(r4).
- PC 0x801DD6B4: store byte r10 at +0xCC(r4).
- PC 0x801E0AEC: store byte r9 at +0xCC(r16).
- PC 0x801E0B98: store byte r11 at +0xCC(r16).
- PC 0x801E0BD0: store byte r25 at +0xCC(r16).
- PC 0x801E0BE0: store byte r0 at +0xCC(r16).

All use base register r4 or r16 (plausible PlayerTask pointer registers, NOT YET PROVEN). The first original player-overlay word-store +0x2C candidate is PC 0x801CBC70, base r4, value r2. Many of 131 graphics offset candidates use base r29 (stack pointer) and are misleading if labeled actual Object fields.

**Next:** inspect enclosing original functions and register-definitions/callers for the 10 action-offset sites and non-stack graphics_1 sites; prove whether base register truly points to PlayerTask (known global D_801FC604) or player model Object (global D_801FC60C). Correlate later with live original game object/animation ownership from docs/goemon/LIVE_ORIGINAL_ANIMATION_OWNER_2026-11-08.md. All 10 are syntax candidates, not yet verified writers. Do not claim original animation until nonzero numerical MtxF movement across genuine frames.

The bounded detailed scan report (candidate addresses/registers/contexts, NO ROM payloads) is saved ONLY locally at C:\actions-runner-goemon\original-player-object-writer-sites.json.

The authoritative queue is docs/goemon/NEXT_TASKS.md, source of truth is docs/goemon/CURRENT_STATE.md and machine-state is docs/goemon/agent_state.json. No chat history is needed.
