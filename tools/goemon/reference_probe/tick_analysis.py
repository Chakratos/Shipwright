#!/usr/bin/env python3
"""Analyze original Goemon rendered-sample/game-loop counters for tick alignment.

Reports counter duplication and discontinuities; does not assume a render
callback is a physics tick or infer a target game frame rate from a log alone.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

PREFIX='GOEMON_TICK,'
FIELDS=('sample','frames_elapsed','game_loops_count','retraces_per_game_step','retrace_count')

def parse_lines(lines:list[str])->list[dict[str,int]]:
    out=[]
    for line_number,line in enumerate(lines,1):
        idx=line.find(PREFIX)
        if idx<0:continue
        values=line[idx+len(PREFIX):].strip().split(',')
        if len(values)!=len(FIELDS):
            raise ValueError(f'line {line_number}: expected {len(FIELDS)} tick values')
        try: row=dict(zip(FIELDS,(int(v) for v in values)))
        except ValueError as ex:raise ValueError(f'line {line_number}: invalid tick field') from ex
        if row['sample']!=len(out):
            raise ValueError(f'line {line_number}: nonconsecutive capture frame')
        if not 0<=row['retraces_per_game_step']<=255:
            raise ValueError(f'line {line_number}: invalid retraces_per_game_step')
        out.append(row)
    if not out:raise ValueError('no GOEMON_TICK rows found')
    return out

def summary(rows:list[dict[str,int]])->dict:
    def deltas(field):
        return [b[field]-a[field] for a,b in zip(rows,rows[1:])]
    loop_steps=deltas('game_loops_count')
    render_steps=deltas('frames_elapsed')
    steps=Counter(loop_steps)
    frames=Counter(render_steps)
    return {
        'capture_count':len(rows),
        'game_loop_step_deltas':{str(k):v for k,v in sorted(steps.items())},
        'frames_elapsed_deltas':{str(k):v for k,v in sorted(frames.items())},
        'retrace_steps_observed':sorted({r['retraces_per_game_step'] for r in rows}),
        'repeated_loop_counter_samples':sum(step==0 for step in loop_steps),
        'loop_counter_discontinuities':sum(step not in (0,1) for step in loop_steps),
        'warning':'Counter sampling is observational; original physics tick must be confirmed at its actual update callsite.'
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('goemon_runtime_log',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        result=summary(parse_lines(a.goemon_runtime_log.read_text('utf-8',errors='replace').splitlines()))
        data=json.dumps(result,indent=2)+'\n'
        if a.output:a.output.write_text(data,encoding='utf-8')
        else:print(data,end='')
    except (ValueError,OSError) as ex:
        print(f'ERROR: {ex}',file=sys.stderr);return 2
    return 0

if __name__=='__main__':sys.exit(main())
