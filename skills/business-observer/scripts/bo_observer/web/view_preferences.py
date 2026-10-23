"""Project-owned presentation settings. They never mutate the executable model."""
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import uuid
from contextlib import contextmanager


class PreferenceConflict(ValueError):
    pass


@contextmanager
def file_lock(path):
    """Serialize revisions across server processes as well as browser windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.tell() == 0: stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise PreferenceConflict('The view file is being saved; try again shortly') from exc
        try: yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(stream, fcntl.LOCK_UN)


class Preferences:
    def __init__(self, project_root, project_id, *, legacy_project_ids=()):
        self.path = Path(project_root) / 'bo_stategraph/config/views/local.json'
        self.project_id = project_id
        if not isinstance(legacy_project_ids, (list, tuple)) or any(not isinstance(x, str) for x in legacy_project_ids):
            raise ValueError('legacy_project_ids must be explicit project identifiers')
        self.legacy_project_ids = set(legacy_project_ids)
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            if not self.path.exists():
                return {'schema': 1, 'project_id': self.project_id, 'revision': 0, 'entries': {}}
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(value, dict) and value.get('project_id') in self.legacy_project_ids:
                value['project_id'] = self.project_id
            self.validate(value)
            return deepcopy(value)

    def validate(self, value):
        if value.get('schema') != 1 or value.get('project_id') != self.project_id:
            raise ValueError('View preferences belong to another project or an unsupported version')
        if type(value.get('revision')) is not int or value['revision'] < 0:
            raise ValueError('Invalid view preference revision')
        entries = value.get('entries')
        if not isinstance(entries, dict) or len(entries) > 200:
            raise ValueError('View preference entry limit exceeded')
        for key, body in entries.items():
            if not isinstance(key, str) or not key.startswith('business-observer.layout.v2:') or len(key) > 400:
                raise ValueError('Unknown view preference key')
            if not isinstance(body, str):
                raise ValueError('View preferences must be a JSON object')
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                raise ValueError('View preferences must be a JSON object')
            # Entries are encoded JSON; validating only the outer strings misses
            # NaN/Infinity in camera coordinates and node positions.
            json.dumps(parsed, allow_nan=False)
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(raw.encode('utf-8')) > 2 * 1024 * 1024:
            raise ValueError('View preferences exceed 2 MiB')
        return raw

    def save(self, value):
        with self.lock, file_lock(self.path.with_suffix('.lock')):
            self.validate(value)
            current = self.read()
            if value['revision'] != current['revision']:
                raise PreferenceConflict('Another window updated the view. Refresh before saving; your changes were not written.')
            result = {**deepcopy(value), 'revision': current['revision'] + 1}
            raw = self.validate(result)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name('.local-' + uuid.uuid4().hex + '.tmp')
            try:
                with temporary.open('x', encoding='utf-8', newline='\n') as stream:
                    stream.write(raw + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary.exists(): temporary.unlink()
            return result
