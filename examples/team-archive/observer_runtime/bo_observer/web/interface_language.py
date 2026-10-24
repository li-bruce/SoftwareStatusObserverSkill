"""Keep the coding conversation's UI language separate from personal overrides."""

import json
from pathlib import Path

from ..workflow.sync_io import write
from .view_preferences import file_lock

LOCALES = {"en", "zh-CN"}


def read_language(root):
    """Return English until the coding assistant records a supported conversation language."""
    path = Path(root) / "bo_stategraph/config/interface.json"
    value = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"schema": 1, "conversation_locale": "en", "source": ""}
    )
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "conversation_locale", "source"}
        or type(value.get("schema")) is not int
        or value["schema"] != 1
        or not isinstance(value.get("conversation_locale"), str)
        or value["conversation_locale"] not in LOCALES
        or not isinstance(value.get("source"), str)
        or len(value["source"]) > 500
    ):
        raise ValueError("Invalid interface language configuration")
    return value


def set_language(root, locale, source):
    """Record language only; never change labels, graph identity or saved personal views."""
    if not isinstance(locale, str) or locale not in LOCALES:
        raise ValueError("Interface language must be en or zh-CN")
    if not isinstance(source, str) or not source.strip() or len(source) > 500:
        raise ValueError("A conversation source reference is required")
    path = Path(root) / "bo_stategraph/config/interface.json"
    with file_lock(path.with_suffix(".lock")):
        read_language(root)
        write(path, {"schema": 1, "conversation_locale": locale, "source": source.strip()})
    return read_language(root)
