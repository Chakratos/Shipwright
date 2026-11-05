"""Tests for original game/render counter diagnostics."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tick_analysis import parse_lines,summary

class Tests(unittest.TestCase):
    def test_repeated_render_samples_are_counted(self):
        rows=parse_lines([
            'GOEMON_TICK,0,10,20,2,15',
            'GOEMON_TICK,1,10,20,2,16',
            'GOEMON_TICK,2,11,21,2,17',
            'GOEMON_TICK,3,12,22,2,18',
        ])
        report=summary(rows)
        self.assertEqual(report['capture_count'],4)
        self.assertEqual(report['repeated_loop_counter_samples'],1)
        self.assertEqual(report['game_loop_step_deltas'],{'0':1,'1':2})
        self.assertEqual(report['retrace_steps_observed'],[2])

    def test_nonconsecutive_capture_frame(self):
        with self.assertRaisesRegex(ValueError,'nonconsecutive'):
            parse_lines(['GOEMON_TICK,2,10,20,2,15'])

    def test_discontinuity_is_not_silently_ignored(self):
        rows=parse_lines(['GOEMON_TICK,0,10,20,2,15',
                          'GOEMON_TICK,1,11,24,2,16'])
        self.assertEqual(summary(rows)['loop_counter_discontinuities'],1)

if __name__=='__main__':unittest.main()
