"""Export explicit, synthetic project/review files; verify without executing them."""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import zipfile
try:
    from ...behavior_model import read, contained, digest
except ImportError:
    from behavior_model import read, contained, digest

MANIFEST = "stategraph-bundle.json"


def safe_name(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("bundle names must be portable relative paths")
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in {".", "..", ".git", ".aws"} for p in path.parts):
        raise ValueError("invalid bundle path")
    if str(path) != name or name == MANIFEST:
        raise ValueError("noncanonical or reserved bundle path")
    if path.name.startswith(".env") or path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".pem", ".key"}:
        raise ValueError("exclude database and credential files; use synthetic fixtures")
    return name


def export(root, config, out):
    names = config.get("files", [])
    if config.get("schema_version") != 1 or config.get("data_policy") != "synthetic-only":
        raise ValueError("bundle requires schema_version 1 and explicit synthetic-only data policy")
    if not names or len(set(names)) != len(names) or len({n.casefold() for n in names}) != len(names):
        raise ValueError("bundle needs unique files, including on case-insensitive systems")
    if config.get("kind") not in {"project", "review"} or not config.get("project_id"):
        raise ValueError("bundle needs project_id and kind project/review")
    target = contained(root, out)
    if target.exists():
        raise ValueError("bundle already exists; choose a new versioned output")
    files = {}
    contents = {}
    for name in sorted(names):
        safe_name(name)
        source = contained(root, name)
        if source == target or not source.is_file():
            raise ValueError("export file missing or is the output")
        contents[name] = source.read_bytes()
        files[name] = {"sha256": digest(contents[name]), "bytes": len(contents[name])}
    manifest = {"schema_version": 1, "kind": config["kind"], "project_id": config["project_id"],
                "data_policy": config["data_policy"], "versions": config.get("versions", {}),
                "files": files, "commands": config.get("commands", []),
                "meaning": "Integrity and explicit scope; included commands are never automatically executed."}
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"valid": True, "files": len(files), "sha256": digest(target.read_bytes()), "out": out}


def inspect(archive_path):
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist(); names = [i.filename for i in infos]
        if len(names) != len(set(names)) or len({n.casefold() for n in names}) != len(names):
            raise ValueError("duplicate archive path")
        if len(infos) > 10000 or sum(i.file_size for i in infos) > 256 * 1024 * 1024:
            raise ValueError("archive exceeds review limit")
        if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos):
            raise ValueError("archive symlinks are unsupported")
        for name in names:
            if name != MANIFEST:
                safe_name(name)
        manifest = json.loads(archive.read(MANIFEST))
        if manifest.get("schema_version") != 1 or manifest.get("data_policy") != "synthetic-only":
            raise ValueError("unsupported manifest")
        if set(names) != {MANIFEST, *manifest["files"]}:
            raise ValueError("manifest/archive scope differs")
        for name, spec in manifest["files"].items():
            data = archive.read(name)
            if len(data) != spec["bytes"] or digest(data) != spec["sha256"]:
                raise ValueError("file content differs: " + name)
    return {"valid": True, "files": len(manifest["files"]), "manifest": manifest,
            "sha256": digest(Path(archive_path).read_bytes()), "executed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["export", "inspect"])
    p.add_argument("--root", required=True); p.add_argument("--config")
    p.add_argument("--out"); p.add_argument("--archive")
    a = p.parse_args(); root = Path(a.root).absolute().resolve()
    if a.command == "export":
        if not a.config or not a.out:
            p.error("export requires --config and --out")
        result = export(root, read(contained(root, a.config)), a.out)
    else:
        if not a.archive:
            p.error("inspect requires --archive")
        result = inspect(contained(root, a.archive))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
