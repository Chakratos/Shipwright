#!/usr/bin/env python3
"""Classify original opaque Player byte states from real GOEMON_MEM samples.

Observational only; correlation with action IDs is not proof of a
particular original code path, equipment identity or collision callback.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
from memory_candidates import parse_log

AIR_ACTIONS={23,25,26}
SWITCH_ACTION=186

def analyze_samples(samples:list)->dict:
    if not samples:raise ValueError("no original Player memory snapshots")
    groups=defaultdict(list)
    for sample in samples:
        groups[sample.character_id].append(sample)
    air=[s for s in samples if s.action_id in AIR_ACTIONS]
    other=[s for s in samples if s.action_id not in AIR_ACTIONS]
    switch=[s for s in samples if s.action_id==SWITCH_ACTION]
    nonswitch=[s for s in samples if s.action_id!=SWITCH_ACTION]
    all_fields={
        "jump_mode_byte_0x18": {
            "normal_jump_actions_23_25_26":dict(sorted(Counter(s.raw[0x18] for s in air).items())),
            "all_other_actions":dict(sorted(Counter(s.raw[0x18] for s in other).items())),
            "matches_observed_jumping_zero_other_two":(
                sum(s.raw[0x18]==0 for s in air)+
                sum(s.raw[0x18]==2 for s in other)
            ),
        },
        "character_switch_marker_0x69": {
            "during_action_186":dict(sorted(Counter(s.raw[0x69] for s in switch).items())),
            "outside_action_186":dict(sorted(Counter(s.raw[0x69] for s in nonswitch).items())),
            "marked_during_character_change":sum(s.raw[0x69]==1 for s in switch),
            "marked_outside_character_change":sum(s.raw[0x69]==1 for s in nonswitch),
        },
        "action_phase_byte_0x2c": {
            "during_air_actions":dict(sorted(Counter(s.raw[0x2c] for s in air).items())),
            "during_other_actions":dict(sorted(Counter(s.raw[0x2c] for s in other).items())),
        },
    }
    candidate_rows=[]
    for offset in range(0x1C0):
        grouped_counts=[]
        transitions=0
        for character,records in sorted(groups.items()):
            values=[s.raw[offset] for s in records]
            unique=sorted(set(values))
            grouped_counts.append({"character_id":character,"distinct_values":unique})
            transitions+=sum(x!=y for x,y in zip(values,values[1:]))
        all_values={s.raw[offset] for s in samples}
        if 2<=len(all_values)<=12 and 2<=transitions<=70:
            candidate_rows.append({
                "offset":offset,"offset_hex":f"0x{offset:03X}",
                "distinct_values":sorted(all_values),
                "within_character_changes":transitions,
                "character_values":grouped_counts,
            })
    candidate_rows.sort(key=lambda v:(v["within_character_changes"],v["offset"]))
    return {
        "samples":len(samples),
        "by_character":{str(ch):len(value) for ch,value in sorted(groups.items())},
        "normal_jump_samples":len(air),
        "other_action_samples":len(other),
        "switch_action_samples":len(switch),
        "measured_fields":all_fields,
        "low_cardinality_state_candidates":candidate_rows,
        "warning":(
            "Byte 0x18 strongly correlates with normal jump action phases, "
            "but independent original writer/collision analysis is still "
            "needed before naming it an authoritative grounded flag. "
            "The 0x2C phase byte is NOT a proven weapon ID."
        ),
    }

def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime_log",type=Path)
    parser.add_argument("--output",type=Path)
    a=parser.parse_args(argv)
    try:
        result=analyze_samples(parse_log(
            a.runtime_log.read_text(encoding="utf-8",errors="replace")))
        payload=json.dumps(result,indent=2)+"\n"
        if a.output:a.output.write_text(payload,encoding="utf-8")
        else:print(payload,end="")
    except (OSError,ValueError) as e:
        print(f"ERROR: {e}",file=sys.stderr)
        return 2
    return 0
if __name__=="__main__":sys.exit(main())
