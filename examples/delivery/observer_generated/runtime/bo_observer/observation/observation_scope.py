"""Observer infrastructure is not an application operation.

Keep exact source classifications for inspection, but never turn collection or
reporting into business events. No filtering by business labels or event values.
"""

import ast
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import PurePosixPath
from urllib.parse import urlsplit


WEB_APIS = (
    "/api/view",
    "/api/source",
    "/api/code",
    "/api/preferences",
    "/api/recordings",
    "/api/stategraph",
    "/api/versions",
    "/api/design",
)
_internal = ContextVar("bo_observer_internal", default=False)


def bo_is_internal():
    return _internal.get()


@contextmanager
def bo_internal():
    token = _internal.set(True)
    try:
        yield
    finally:
        _internal.reset(token)


def observer_route(path):
    path = urlsplit(path).path
    return (
        path in {"/graph", "/graph/"}
        or path.startswith("/api/bo/")
        or any(path == prefix or path.startswith(prefix + "/") for prefix in WEB_APIS)
    )


def endpoint_paths(symbol):
    """None means an unresolved/non-HTTP declaration, never a safe exclusion."""
    paths = []
    for declaration in symbol.get("entrypoints", []):
        try:
            call = ast.parse(declaration, mode="eval").body
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                return None
            if call.func.attr not in {
                "route",
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "websocket",
            }:
                return None
            value = (
                call.args[0]
                if call.args
                else next(k.value for k in call.keywords if k.arg == "path")
            )
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            paths.append(value.value)
        except (SyntaxError, StopIteration, IndexError, TypeError):
            return None
    return sorted(set(paths))


def observer_exclusion(symbol, item):
    if item.get("category") != "observer" or not item.get("reason", "").strip():
        return False
    if symbol.get("entrypoints"):
        paths = endpoint_paths(symbol)
        return bool(paths and all(observer_route(p) for p in paths) and item.get("routes") == paths)
    path = PurePosixPath(symbol["path"])
    return (
        path.stem.startswith(("bo_", "observer_"))
        or path.name in {"ports.py", "run.py"}
        or symbol["symbol"].split(".")[-1].startswith("bo_")
        or any(part.startswith("BO") for part in symbol["symbol"].split("."))
    )


def observer_symbols(plan, index):
    return {
        sid
        for sid, item in (plan or {}).get("excluded", {}).items()
        if sid in index["symbols"]
        and isinstance(item, dict)
        and observer_exclusion(index["symbols"][sid], item)
    }


def observer_nodes(model):
    excluded = {
        sid
        for sid, item in (model.get("implementation") or {}).get("excluded", {}).items()
        if isinstance(item, dict) and item.get("category") == "observer"
    }
    return {
        n["id"]
        for n in model["nodes"]
        if n.get("source") and n["source"]["path"] + "::" + n["source"]["symbol"] in excluded
    }
