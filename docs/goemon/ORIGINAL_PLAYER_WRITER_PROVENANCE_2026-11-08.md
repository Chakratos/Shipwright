# Original player writer provenance (2026-11-08)

**Status: original Windows ROM scan completed [run 42481382788](https://github.com/Chakratos/Shipwright/actions/runs/42481382788) successfully, 327/327 Python + C++20 checks. Extended static caller-a0 analysis has 9 synthetic tests passed locally, Windows rerun pending. G1 OPEN.**

## Method

- Source: tools/goemon/re/trace_player_writer_provenance.py, regression tools/goemon/re/tests/test_trace_player_writer_provenance.py.
- Reads the exact original decompressed, verified NG5E ROM using the existing owner-local ROM verification and known player handler file-table mapping. Scans only original player overlay file ID found by handler address.
- Finds byte stores at +0xCC (action-offset candidates) and word stores at +0x2C (graphics_1-offset candidates); excludes base r29 stack writes from graphics candidate inventory.
- Bounded conservative backwards register origin of the base register, including LUI+signed ADDIU/LW, ORI, zero-register moves and some arithmetic. Reports a known pointer only when the address of an **LW** is one of the pinned D_801FC604..D_801FC618 pointer globals. Literal global addresses are *not* pointer contents. Any unknown overwrite or control-flow transfer terminates the proof.
- Finds nearby negative stack allocation as **unverified function prologue hint**, scans same overlay for static direct-JAL targets to the hint, never claims inferred function identity or executable path.
- Only PC metadata, source symbol names, counts, uncertainty flags are logged; no raw code/ROM/matrices. Detailed JSON remains on owner computer at C:\actions-runner-goemon\original-player-writer-provenance.json. Explicit one-shot CI marker: **[goemon-player-writer-provenance]**.

## Evidence and interpretation

Local synthetic unit tests: 9 cases passing (including new caller a0 and delay-slot overrides). They exercise signed-16 pointer loads, aliased r16, model-Object global, stack false positives, intervening JAL barrier, register clobber, guessed call-site flags, and a bare literal global address. The synthetic test pass does **not** establish the actual game action writer.

First private Windows ROM scan [run 42481382788](https://github.com/Chakratos/Shipwright/actions/runs/42481382788) passed. It found 10 action +0xCC candidate stores and 21 non-r29 graphics +0x2C candidate stores; **zero exact local player-global-pointer load proofs in both categories**. For action stores, local origin stopped at a control-flow boundary for nine sites and remained unresolved for one. Nearest-stack-allocation direct-JAL caller counts were 1, 1, 0, 3, 2, 0, 0, 0, 0, 0; these are not proven function callers. A second source update records a0 origin at those possible callers and rejects a0-setting JAL delay slots; its private ROM rerun must still be inspected. A result of zero local known-global loads would only mean no *intra-basic-block* proof; original game code may pass r4/r16 from callers or preserve s0 across JAL. Prologue matching has false-positive risk. **Do not change action/animation ownership gates based solely on this scan.**

## Next falsifiable step

Correlate the ten action writer PCs with caller argument passing and **verified** PlayerTask global acquisition across true function boundaries / CFG; verify player model Object.graphics_1 separately from PlayerTask.action_id and root Object. Prefer new original runtime GOEMON_ANIM_OWNER + GOEMON_ANIM_ACTIVE trace when available. Only nonzero actual MtxF numerical changes at genuine animation ticks advance G1.
