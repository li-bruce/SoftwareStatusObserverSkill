"""Validate an exact frame with the recorder before testing full-graph export."""
from copy import deepcopy
import json
from reproduce import OUT, model, bo_export_view, bo_validate_export
from recording_session import checkpoint
from runtime_frames import merge_frames

definition = model(['a', 'b'], ['a', 'b'], 'a', [{'source': 'a', 'dest': 'b', 'trigger': 'go'}])
machine = {'current': 'a', 'state_revision': 1, 'configurations': [
    {'attempt': 'i', 'phase': 'a', 'context': {}, 'state_revision': 1, 'run_build_id': 'audit'}]}
event = {'id': 'producer:1', 'seq': 1, 'revision': 1, 'run_id': 'producer', 'build_id': 'audit'}
frame = {'event_id': event['id'], 'run_id': 'producer', 'build_id': 'audit', 'revision': 1,
         'machine': deepcopy(machine), 'authority': {'state': 'a'}}
view = {'model': definition, 'manifest': {'build_id': 'audit'}, 'machine': machine,
        'authority': {'state': 'a'}, 'events': [event], 'health': {'run_id': 'producer'},
        'binding_status': {'status': 'current'},
        'runtime_frames': {'schema': 'stategraph-runtime-frames/v1', 'frames': [frame]}}
recording = {'events': [event], 'run_id': 'producer', 'build_id': 'audit', 'gaps': []}
merge_frames(recording, view, checkpoint)
assert len(recording['runtime_frames']['frames']) == 1 and not recording['gaps']
exported = bo_export_view(view)
result = {'recorder_accepted_frames': len(recording['runtime_frames']['frames']),
          'recording_gaps': recording['gaps'], 'export_has_frames': 'runtime_frames' in exported['runtime'],
          'export_checks_valid': bo_validate_export(exported) is exported}
(OUT / 'frame-export-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
