# Original NG5E Player JR Switch Evidence (2026-11-08)

**Status: structural source code evidence only. G1 OPEN.** Raw original ROM, original assembly words, matrix samples and commercial assets stay on the owner PC. The public source symbol map (Goemon64RecompSyms 49f4e3269f05c737cb4bf698b9ef7142c92f1ac7, section .file_11) supplies 906 original player overlay function ranges.

## Pinned original player indirect switches

- Original JR 0x801DA23C, target r12 loaded at 0x801DA238: structurally matched contiguous ten-target table (nine unique target PCs) in original private overlay at +0x03FAA0.
- Original JR 0x801E0980, target r24 loaded at 0x801E097C: six unique in-function target PCs at +0x03FD78.
- Both table bases matched static LUI, signed LW displacement and indexed ADDU. These are *address structure matches*, not proof of actual player action selection.
- Supplying those table targets as hypotheses to the bounded CFG reaches five new sb+0xCC syntactic action-offset stores; four existing stores have direct entry-a0 provenance; one remains unknown. Those five have incomplete CFG status explicitly. This neither proves PlayerTask pointer identity nor animated stream.
- Second selector index originates from a halfword load at +0x30(r3), 0x801E0964, r3 owner unresolved. First selector has shifts and ADDIU; earlier producer of the SLL at 0x801DA1FC is not detected within 64 backward instructions. Do not equate these values to the real PlayerTask.action_id +0xCC without actual pointer provenance.

## Private Windows evidence

| GitHub Actions run | Verified results |
| --- | --- |
| [42484532406](https://github.com/Chakratos/Shipwright/actions/runs/42484532406) | 358 Python and native C++20 PASS, two JR targets and source tables |
| [42484757248](https://github.com/Chakratos/Shipwright/actions/runs/42484757248) | 360 and native PASS, LUI/ADDU/LW source table base links |
| [42484877490](https://github.com/Chakratos/Shipwright/actions/runs/42484877490) | 362 and native PASS, CFG source target hypothetical reachability |
| [42485168086](https://github.com/Chakratos/Shipwright/actions/runs/42485168086) | 364 and native PASS, second selector halfword source |
| [42485342018](https://github.com/Chakratos/Shipwright/actions/runs/42485342018) | 365 and native PASS, indexed operand categories |
| [42485490918](https://github.com/Chakratos/Shipwright/actions/runs/42485490918) | 366 and native PASS, first selector ADDIU ancestry |
| [42485638269](https://github.com/Chakratos/Shipwright/actions/runs/42485638269) | 367 and native PASS, first selector unknown MIPS shift |
| [42485758402](https://github.com/Chakratos/Shipwright/actions/runs/42485758402) | 368 and native PASS, first selector SLL tracked |

## Next executable work

The ROM-private tool is tools/goemon/re/inspect_original_player_jump_tables.py and retains only the JSON metadata locally under C:\actions-runner-goemon\original-player-jump-table-candidates.json. To replay portable regressions: python tools/goemon/verify.py --native. To run the private owner-ROM experiment: use an explicit one-shot commit marker [goemon-player-jump-tables] on the goemon-selfhosted workflow, then inspect the actual Actions run log. Extend first register ancestry to actual source function bounds with branch ambiguity metadata, track second r3 source to a verified player global or call argument, then resolve active Object.graphics_1 / AnimatedSkeleton.animation and numerical source pose over real original frame increments.

Never upgrade G1 merely because a jump table appears coherent. Runtime capture of actual original game is useful for validation but not necessary to progress on static ROM MIPS analysis.

## 2026-11-09 follow-up

First switch ancestry ends with zero-register input to an ADDIU. Added private-only numeric candidate evaluation of the ADDIU transform and subsequent shift; new diagnostic logs only candidate index and intervening control transfers, not ROM words. Static nearest textual definition is not a dominance or runtime ownership proof. Await the new marker-gated Windows ROM run.
