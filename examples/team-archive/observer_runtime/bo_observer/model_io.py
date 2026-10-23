"""One graph document in either an existing v3 model or a common project envelope."""
import json
from pathlib import Path


def read_model(path):
    value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if value.get('protocol')=='bo-project/v1':
        from .protocol import validate_project
        return validate_project(value)['model']
    return value
