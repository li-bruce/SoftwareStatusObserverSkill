"""Check source ownership and static dependency direction; export a core ZIP.

Static imports are checked without importing the program. Dynamic imports in the
business layer are rejected as uncovered. This is not a sandbox or semantic proof.
"""

from __future__ import annotations
import argparse
import fnmatch
import ast
import hashlib
import json
from pathlib import Path
import zipfile


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(root, name):
    p = Path(name)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("expected project-relative path: " + name)
    target = (root / p).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("path escapes root: " + name)
    return target


def matches(name, prefix):
    return name == prefix.rstrip("/") or name.startswith(prefix.rstrip("/") + "/")


def owner(name, cfg):
    found = [
        (len(p), layer)
        for layer, spec in cfg["layers"].items()
        for p in spec["paths"]
        if matches(name, p)
    ]
    if not found:
        return None
    best = max(n for n, _ in found)
    layers = {layer for n, layer in found if n == best}
    if len(layers) != 1:
        raise ValueError("ambiguous ownership: " + name)
    return layers.pop()


def collect(root, prefixes):
    files = set()
    for prefix in prefixes:
        target = inside(root, prefix)
        if not target.exists():
            raise ValueError("missing configured path: " + prefix)
        for p in [target] if target.is_file() else target.rglob("*"):
            if p.is_symlink():
                raise ValueError("symlink not supported: " + str(p))
            if (
                p.is_file()
                and not set(p.parts) & {"__pycache__", "node_modules", ".stategraph"}
                and p.suffix != ".pyc"
            ):
                if not p.resolve().is_relative_to(root.resolve()):
                    raise ValueError("file escapes root")
                files.add(p.relative_to(root).as_posix())
    return sorted(files)


def inspect(root, cfg, verify_generated=True):
    errors, imports = [], []
    files = collect(root, cfg["scan"])
    sources = [p for p in files if p.endswith(".py")]
    modules = {p[:-3].replace("/", ".").removesuffix(".__init__"): p for p in sources}
    ownership = {p: owner(p, cfg) for p in files}
    for p, layer in ownership.items():
        if layer is None:
            errors.append({"unowned": p})
    for name in sources:
        layer = ownership[name]
        if layer is None:
            continue
        spec = cfg["layers"][layer]
        try:
            tree = ast.parse((root / name).read_text(encoding="utf-8-sig"))
        except SyntaxError as exc:
            errors.append({"syntax": name, "line": exc.lineno})
            continue
        package = name[:-3].replace("/", ".").split(".")[:-1]
        for n in ast.walk(tree):
            targets = []
            if isinstance(n, ast.Import):
                targets = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                base = ".".join(package[: len(package) - n.level + 1]) if n.level else ""
                base = ".".join(x for x in (base, n.module or "") if x)
                targets = [base] + [".".join(x for x in (base, a.name) if x) for a in n.names]
            for target in targets:
                found = next(
                    (
                        modules[k]
                        for k in sorted(modules, key=len, reverse=True)
                        if target == k or target.startswith(k + ".")
                    ),
                    None,
                )
                if not found:
                    # Only the base module matters for third-party symbols.
                    if (
                        spec.get("external") is not None
                        and target.split(".")[0] not in spec["external"]
                    ):
                        errors.append(
                            {"external_dependency": target, "file": name, "line": n.lineno}
                        )
                    continue
                target_layer = ownership[found]
                imports.append({"from": name, "to": found, "line": n.lineno})
                if target_layer not in spec.get("allows", [layer]):
                    errors.append(
                        {
                            "forbidden_dependency": name + " -> " + found,
                            "line": n.lineno,
                            "layers": [layer, target_layer],
                        }
                    )
            if spec.get("reject_dynamic") and isinstance(n, ast.Call):
                call = ast.unparse(n.func)
                if call in ("__import__", "eval", "exec") or call.endswith(".import_module"):
                    errors.append({"uncovered_dynamic_call": call, "file": name, "line": n.lineno})
    vendor = cfg.get("vendor_files", {})
    for name, expected in vendor.items():
        if not inside(root, name).is_file() or sha(inside(root, name)) != expected:
            errors.append({"changed_vendor_file": name})
    js = [
        p
        for p in files
        if Path(p).suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".vue"}
        and p not in vendor
    ]
    if js:
        from ..sources import scan

        index = scan(root, js)
        errors.extend(index["errors"])
        for name, unit in index["units"].items():
            layer = ownership[name]
            if layer is None:
                continue
            spec = cfg["layers"][layer]
            refs = {v["module"] for v in unit.get("imports", {}).values()}
            for symbol in unit["symbols"].values():
                for call in symbol["calls"]:
                    if call["expression"] in ("import", "require", "eval", "Function"):
                        if spec.get("reject_dynamic"):
                            errors.append(
                                {
                                    "uncovered_dynamic_call": call["expression"],
                                    "file": name,
                                    "line": call["line"],
                                }
                            )
                        if call.get("args") and call["expression"] in ("import", "require"):
                            try:
                                refs.add(ast.literal_eval(call["args"][0]))
                            except (ValueError, SyntaxError):
                                pass
            for ref in refs:
                if not ref.startswith("."):
                    if spec.get("external") is not None and ref not in spec["external"]:
                        errors.append({"external_dependency": ref, "file": name})
                    continue
                candidate = (root / name).parent / ref
                choices = (
                    [candidate]
                    + [
                        candidate.with_suffix(ext)
                        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".json")
                    ]
                    + [candidate / ("index" + ext) for ext in (".ts", ".tsx", ".js", ".mjs")]
                )
                found = next((p.absolute().resolve() for p in choices if p.is_file()), None)
                if found is None or not found.is_relative_to(root):
                    errors.append({"unresolved_local_import": ref, "file": name})
                    continue
                target = found.relative_to(root).as_posix()
                target_layer = owner(target, cfg)
                imports.append({"from": name, "to": target})
                if target_layer not in spec.get("allows", [layer]):
                    errors.append(
                        {
                            "forbidden_dependency": name + " -> " + target,
                            "layers": [layer, target_layer],
                        }
                    )
    managed = collect(root, cfg.get("managed_paths", []))
    if verify_generated:
        recorded = cfg.get("managed_hashes", {})
        for p in set(managed) | set(recorded):
            if p not in managed or p not in recorded or sha(root / p) != recorded[p]:
                errors.append(
                    {
                        "managed_file_changed": p,
                        "action": "regenerate/review then explicitly seal; do not patch generated output",
                    }
                )
    return {
        "valid": not errors,
        "errors": errors,
        "ownership": ownership,
        "imports": imports,
        "managed": managed,
        "limits": [
            "Python and JS/TS/SFC static imports in configured scan paths",
            "Dynamic aliases and external package internals need independent review",
            "Sealing is a recorded regeneration, not business acceptance; run change_sync verify",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["check", "inventory", "seal", "package"])
    p.add_argument("--root", default=".")
    p.add_argument("--config", default="ownership.json")
    p.add_argument("--reason")
    p.add_argument("--out")
    a = p.parse_args()
    root = Path(a.root).absolute().resolve()
    path = inside(root, a.config)
    cfg = read(path)
    result = inspect(root, cfg, verify_generated=a.command not in ("seal", "inventory"))
    if a.command == "seal":
        if not a.reason or not a.reason.strip():
            raise ValueError("seal needs a reviewed regeneration reason")
        if result["valid"]:
            hashes = {n: sha(root / n) for n in result["managed"]}
            if a.config in hashes:
                raise ValueError("ownership manifest must not hash itself")
            changed = sorted(
                n
                for n in set(hashes) | set(cfg.get("managed_hashes", {}))
                if hashes.get(n) != cfg.get("managed_hashes", {}).get(n)
            )
            cfg.setdefault("regenerations", []).append({"reason": a.reason, "changed": changed})
            cfg["managed_hashes"] = hashes
            save(path, cfg)
            result["sealed"] = changed
    if a.command == "package" and result["valid"]:
        if not a.out:
            raise ValueError("package needs --out project-relative ZIP")
        target = inside(root, a.out)
        if target.exists():
            raise ValueError("refuse to overwrite existing package")
        paths = [
            name
            for name in collect(root, cfg["core_include"])
            if not any(
                fnmatch.fnmatchcase(name, pattern) for pattern in cfg.get("core_exclude", [])
            )
        ]
        for name in paths:
            layer = owner(name, cfg)
            if layer not in cfg["core_layers"] and not any(
                matches(name, p) for p in cfg.get("core_resources", [])
            ):
                raise ValueError("core package contains non-core file: " + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as z:
            for name in paths:
                z.write(root / name, name)
        result["package"] = {
            "path": a.out,
            "files": len(paths),
            "sha256": sha(target),
            "retains": "business state machine; neutral observation port has no observer implementation",
        }
    if a.out and a.command != "package":
        save(inside(root, a.out), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False))
        raise SystemExit(1)
