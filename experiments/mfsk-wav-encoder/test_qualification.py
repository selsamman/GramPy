"""Integrity and false-positive checks for the independent receive scorer."""
import json
from pathlib import Path
import tempfile
import unittest
import wave
from jsonschema import Draft202012Validator

from evaluate import artifact, prefix_pcm, receiver_events, verify_artifacts, verify_cross_fields


class EvidenceTests(unittest.TestCase):
    def test_receiver_events_ignore_expected_text_and_deduplicate_polling(self):
        self.assertEqual(receiver_events("decoded text MFSK32 MFSK64; modem.set_by_name('MFSK32')"), [])
        line = "status during playback: mode='MFSK32' carrier=1400 quality=9"
        retune = "status during playback: mode='MFSK32' carrier=1600 quality=9"
        reverse = "status during playback: mode='MFSK64' carrier=1600 quality=9"
        events = receiver_events("\n".join([line, line, retune, retune, reverse]))
        self.assertEqual([(e['mode'], e['frequency_hz']) for e in events],
                         [('MFSK32', 1400), ('MFSK32', 1600), ('MFSK64', 1600)])

    def test_artifact_mutation_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'decoded.txt'
            path.write_text('expected')
            evidence = {'cases': [{'text': artifact(path, root)}]}
            verify_artifacts(evidence, root)
            path.write_text('mutated!')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                verify_artifacts(evidence, root)
            with self.assertRaisesRegex(ValueError, 'escaped'):
                verify_artifacts({'path': '../outside', 'bytes': 0, 'sha256': '0'*64}, root)

    def test_rsid_integrator_has_frozen_lengths_and_silent_guards(self):
        root = Path(__file__).resolve().parents[2]
        oracle = json.loads((root / 'docs/encoder/data/mfsk_encoder_rsid_oracle_v1.json').read_text())
        for mode, frames in [('MFSK32', 111450), ('MFSK64', 222900)]:
            pcm = prefix_pcm(mode, 1500, oracle)
            self.assertEqual(len(pcm), frames * 2)
            self.assertEqual(pcm[:4458*5*2], bytes(4458*5*2))
            self.assertEqual(pcm[-4458*5*2:], bytes(4458*5*2))
            self.assertNotEqual(pcm[4458*5*2:4458*20*2], bytes(4458*15*2))

    def test_failure_reporting_does_not_allow_empty_events_to_pass(self):
        root = Path(__file__).resolve().parents[2]
        schema = json.loads((root / 'docs/encoder/data/mfsk_encoder_pi_qualification_manifest_v2.schema.json').read_text())
        validator = Draft202012Validator({'$ref': '#/$defs/case', '$defs': schema['$defs']})
        item = {'path': 'evidence', 'bytes': 0, 'sha256': '0'*64}
        case = {'id': 'failed-acquisition', 'status': 'fail', 'generated_wav': item, 'encoder_result': item,
                'continuous_receiver_runs': [{'input_interval': {'start_frame': 0, 'end_frame': 1},
                    'manual_mode_changes': 0, 'exit_code': 0, 'log': item, 'rxid_events': [],
                    'recovered_text': item, 'recovered_images': []}],
                'checks': [{'id': 'acquisition', 'status': 'fail', 'expected': 'MFSK32', 'observed': None,
                            'evidence': ['evidence']}], 'discrepancies': []}
        self.assertTrue(validator.is_valid(case))
        case['status'] = 'pass'
        self.assertFalse(validator.is_valid(case))
        case['checks'][0]['status'] = 'pass'
        self.assertFalse(validator.is_valid(case))

    def test_window_replay_or_missing_case_cannot_pass_cross_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with wave.open(str(root / 'input.wav'), 'wb') as wav:
                wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                wav.writeframes(b'\0\0'*10)
            case = {'id': 'whole-wav', 'status': 'pass', 'generated_wav': {'path': 'input.wav'},
                    'checks': [{'status': 'pass'}], 'discrepancies': [],
                    'continuous_receiver_runs': [{'input_interval': {'start_frame': 0, 'end_frame': 10},
                                                 'manual_mode_changes': 0}]}
            manifest = {'status': 'complete', 'cases': [case],
                        'summary': {'total': 1, 'passed': 1, 'failed': 0, 'blocked': 0}}
            matrix = {'cases': [{'id': 'whole-wav', 'composition': []}]}
            verify_cross_fields(manifest, matrix, root)
            case['continuous_receiver_runs'][0]['input_interval']['start_frame'] = 1
            with self.assertRaisesRegex(ValueError, 'entire'):
                verify_cross_fields(manifest, matrix, root)
            matrix['cases'].append({'id': 'missing', 'composition': []})
            with self.assertRaisesRegex(ValueError, 'coverage'):
                verify_cross_fields(manifest, matrix, root)


if __name__ == '__main__':
    unittest.main()
