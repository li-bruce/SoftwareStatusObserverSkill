"""Language-neutral source inventory and adapter dispatch. Never execute source."""

from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess

SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx", ".vue"}
# Known code languages without a registered adapter must make coverage incomplete.
UNSUPPORTED_SUFFIXES = {
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".cs",
    ".cpp",
    ".c",
    ".rb",
    ".php",
    ".swift",
    ".svelte",
}
ADAPTER = Path(__file__).parent / "adapters/javascript"


def supported_path(name):
    """Include known source extensions, including unsupported ones that must be reported."""
    return Path(name).suffix.lower() in SOURCE_SUFFIXES | UNSUPPORTED_SUFFIXES


def adapter_identity():
    """Fingerprint the parser implementation and dependencies used to populate the cache."""
    files = [Path(__file__), ADAPTER / "scan.mjs", ADAPTER / "package-lock.json"]
    return hashlib.sha256(b"".join(p.read_bytes() for p in files if p.is_file())).hexdigest()


def parse_javascript(files):
    """Send a batch of source texts to the Node parser and return its structured result.

    A parser failure is explicit so missing code cannot appear successfully mapped.
    """
    node = os.environ.get("BO_NODE") or shutil.which("node")
    if not node:
        raise ValueError("JavaScript adapter requires Node >=20; set BO_NODE or install Node")
    result = subprocess.run(
        [node, str(ADAPTER / "scan.mjs")],
        input=json.dumps({"files": files}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    if result.returncode:
        raise ValueError(
            'JavaScript parser unavailable: run npm ci --prefix "'
            + str(ADAPTER)
            + '". '
            + result.stderr[-1500:]
        )
    return json.loads(result.stdout)


def scan(root, paths, previous=None):
    """Index source declarations and resolvable calls without executing application code.

    Reuse a unit only when both its bytes and the parser fingerprint match. Keep
    unresolved calls in the result for follow-up instead of inventing destinations.
    """
    try:
        from ..behavior_model import digest, contained
        from ..code_structure import parse_unit, module_name
    except ImportError:
        from behavior_model import digest, contained
        from code_structure import parse_unit, module_name
    root = Path(root).absolute().resolve()
    units, errors, parsed, reused, pending = {}, [], [], [], []
    old = (previous or {}).get("units", {})
    # Include the Python implementation, not just the dispatcher's bytes.
    import inspect

    extractor = digest([adapter_identity(), digest(inspect.getsource(parse_unit).encode())])
    for name in sorted(set(paths)):
        suffix = Path(name).suffix.lower()
        if suffix not in SOURCE_SUFFIXES:
            errors.append(
                {"path": name, "error": "no source adapter registered; mapping is incomplete"}
            )
            continue
        try:
            raw = contained(root, name).read_bytes()
            if len(raw) > 2_000_000:
                raise ValueError("source exceeds 2 MB limit")
            content_hash = digest(raw)
            if (
                old.get(name, {}).get("file_hash") == content_hash
                and old[name].get("extractor_hash") == extractor
            ):
                units[name] = copy.deepcopy(old[name])
                reused.append(name)
                continue
            text = raw.decode("utf-8-sig")
            if suffix == ".py":
                units[name] = {
                    "file_hash": content_hash,
                    "extractor_hash": extractor,
                    "language": "python",
                    **parse_unit(name, text),
                }
                parsed.append(name)
            else:
                pending.append({"path": name, "source": text, "file_hash": content_hash})
        except (OSError, SyntaxError, ValueError, UnicodeError) as exc:
            errors.append({"path": name, "error": str(exc)})
    if pending:
        try:
            result = parse_javascript([{"path": f["path"], "source": f["source"]} for f in pending])
            errors.extend(result["errors"])
            for f in pending:
                if f["path"] in result["units"]:
                    units[f["path"]] = {
                        **result["units"][f["path"]],
                        "file_hash": f["file_hash"],
                        "extractor_hash": extractor,
                    }
                    parsed.append(f["path"])
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            errors.extend({"path": f["path"], "error": str(exc)} for f in pending)
    symbols = {s["id"]: copy.deepcopy(s) for u in units.values() for s in u["symbols"].values()}
    qualified = {
        module_name(s["path"]) + "." + s["symbol"]: s["id"]
        for s in symbols.values()
        if units[s["path"]]["language"] == "python"
    }
    edges, unresolved = [], []

    def js_import(path, ref, tail):
        module = ref["module"]
        if not module.startswith("."):
            return None
        # Normalize within project; no filesystem access or module execution.
        base = (root / PurePosixPath(path).parent / module).resolve()
        if not base.is_relative_to(root):
            return None
        stem = base.relative_to(root).as_posix()
        candidates = [stem]
        if Path(stem).suffix in {".js", ".mjs", ".cjs"}:
            candidates += [
                str(PurePosixPath(stem).with_suffix(ext)) for ext in (".ts", ".tsx", ".mts", ".cts")
            ]
        if not Path(stem).suffix:
            candidates += [stem + ext for ext in SOURCE_SUFFIXES] + [
                stem + "/index" + ext for ext in (".js", ".ts", ".tsx")
            ]
        name = ".".join(tail) if ref["name"] == "*" else ".".join([ref["name"], *tail])
        return next((f"{p}::{name}" for p in candidates if f"{p}::{name}" in symbols), None)

    for symbol in symbols.values():
        unit = units[symbol["path"]]
        language = unit["language"]
        for call in symbol["calls"]:
            expr = call["expression"]
            head, *tail = expr.split(".")
            candidate = None
            if head in {"self", "cls", "this"} and len(tail) == 1 and symbol["class"]:
                candidate = f"{symbol['path']}::{symbol['class']}.{tail[0]}"
            elif head not in symbol.get("local_names", []) and head not in unit.get(
                "shadowed_globals", []
            ):
                alias = unit["imports"].get(head)
                if alias:
                    candidate = (
                        qualified.get(".".join([alias, *tail]))
                        if language == "python"
                        else js_import(symbol["path"], alias, tail)
                    )
                else:
                    prefixes = symbol["symbol"].split(".")
                    for length in range(len(prefixes), -1, -1):
                        possible = f"{symbol['path']}::" + ".".join([*prefixes[:length], expr])
                        if possible in symbols:
                            candidate = possible
                            break
            evidence = {
                "from": symbol["id"],
                **call,
                "evidence": f"{language} syntax reference; execution unproven",
            }
            if candidate in symbols:
                edges.append({**evidence, "to": candidate})
            else:
                unresolved.append(
                    {**evidence, "reason": "external, dynamic, shadowed or outside selected scope"}
                )
    return {
        "schema_version": 1,
        "units": units,
        "symbols": symbols,
        "edges": edges,
        "unresolved": unresolved,
        "errors": errors,
        "incremental": {"parsed": parsed, "reused": reused},
        "limits": [
            "Static call candidates are not runtime calls or proven value flow.",
            "Dynamic dispatch, callbacks, generated source and framework bindings require coding-side review and runtime evidence.",
        ],
    }
