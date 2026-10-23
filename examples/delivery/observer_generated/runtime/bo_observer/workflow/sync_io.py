"""Atomic JSON artifacts shared by the development gate."""

import json
import os
from pathlib import Path
import uuid
import time


def at_path(value, path):
    for field in path:
        if isinstance(value, list) and isinstance(field, str):
            selected = [v for v in value if isinstance(v, dict) and v.get("id") == field]
            if len(selected) != 1:
                raise ValueError("missing unique node ID: " + field)
            value = selected[0]
        else:
            value = value[field]
    return value


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.025 * (2**attempt))
    finally:
        if temporary.exists():
            temporary.unlink()
