# Original Player memory states (NG5E, 2026-11-05)

Evidence: the genuine user Goemon64Recompiled run
run-20261105-123100.zip contains **594** snapshots of the original
448-byte Player structure, sampled every fourth original game update.

**Caveat:** these are real numerical correlations with original
action IDs, not yet authoritative source names or collision callsites.

## Ground and character-change correlations

| Player byte | Observed value | Number of original samples | Original action |
|---|---:|---:|---|
| +0x18 | 0 | 111/111 | Actions 23,25,26 (jump phases) |
| +0x18 | 2 | 483/483 | All other sampled actions |
| +0x69 | 1 | 21 | Character switching action 186 |
| +0x69 | 0 | 28 | Remaining action 186 samples |
| +0x69 | 0 | 545/545 | Outside action 186 |

Player+0x18 is a strong **airborne movement-mode candidate**.
Action 28 can persist after landing and uses +0x18=2 in the
capture. An original collision writer must still establish whether
this byte reports authoritative ground contact, movement mode or
animation phase.

Player+0x69 is explicitly set to 1 by original character initializer
routines, and is only 1 during original character-switch action 186
in the recorded run. It is a verified character-switch **transient
marker**, not a persistent current-character identifier.

Player+0x2C takes 0/1/2 in several action/attack sequences.
It is NOT proven to be a weapon ID or hitbox flag.
Player+0x31 advances during many jump/animation phases, but is
not yet source-proven as an animation counter.

## Code and verification

- OriginalMemory.hpp now exposes byte-exact PlayerView accessors
  for +0x18, +0x69, +0x2C and +0x31 using N64 byte offsets.
- test_original_memory.cpp checks these offsets in synthetic buffers.
- player_state_fit.py independently generates an all-character
  correlation report from every original GOEMON_MEM snapshot,
  including additional low-cardinality candidate bytes.
- test_player_state_fit.py verifies those correlations using
  synthetic records, including deliberate mismatches.
- reprocess_log.py includes player_state.json in capture ZIPs.

## Pending original analysis

1. Locate original MIPS writers/readers of Player+0x18 and clarify
   whether it is directly connected to collision contacts.
2. Recover weapon/equipment IDs from genuine original code; the
   numeric action IDs and Player+0x2C phase changes do not suffice.
3. Connect source-grounded states to authentic Ship collision, action,
   rig and combat integration.

No original ROM, player memory captures, models or animation bytes
are committed; the report contains derived field offsets and counts.
