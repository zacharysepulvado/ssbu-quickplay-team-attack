import tempfile
import unittest
from pathlib import Path
from summarize_offline_batch import read_session, summarize

HEADER = '# observer_version=0.2.2\n# game_version=13.0.5\n# poll_global_team_attack=true\n# global_text_offset=0x530a981\n'
def watch(t, value, init=1):
    return f'# watch: elapsed_ms:{t} initialized:{init} team_attack_global:{value} serializer_calls:0 stored_dumps:0\n'

class OfflineBatchTests(unittest.TestCase):
    def test_distinguishes_global_samples_from_serializer_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'one.log'
            p.write_text(HEADER+watch(250,'--',0)+watch(5250,'00')+watch(10250,'01')+watch(15250,'00'))
            result=read_session(p)
            self.assertEqual(result['watch_rows'],4)
            self.assertEqual(result['serializer_dumps'],0)
            self.assertEqual(result['initialized_global_values'],[0,1])
            self.assertEqual([x['value'] for x in result['global_transitions']],[0,1,0])

    def test_rejects_uninitialized_value_reversed_clock_and_duplicate_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.log'
            for text in (HEADER+watch(250,'01',0), HEADER+watch(5250,'00')+watch(250,'01'), HEADER+HEADER):
                p.write_text(text)
                with self.assertRaises(ValueError): read_session(p)

    def test_old_header_only_log_is_not_a_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'old.log'
            p.write_text('# observer_version=0.2.1\n# observer_status: hook_installed\n')
            result=read_session(p)
            self.assertEqual(result['watch_rows'],0)
            self.assertEqual(result['serializer_dumps'],0)
            self.assertIsNone(result['serializer_calls'])

    def test_rejects_mixed_builds_and_reused_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[Path(tmp)/f'{i}.log' for i in range(3)]
            for p in paths: p.write_text(HEADER+watch(250,'00'))
            result=summarize(paths)
            self.assertEqual(result['sessions'][1]['operator_reported_condition'],'ON')
            with self.assertRaises(ValueError): summarize([paths[0]]*3)
            paths[2].write_text(HEADER.replace('13.0.5','13.0.4')+watch(250,'00'))
            with self.assertRaises(ValueError): summarize(paths)
