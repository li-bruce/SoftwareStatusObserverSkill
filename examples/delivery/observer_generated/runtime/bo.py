"""Common JSON service commands; existing project verification commands remain available."""

import argparse
import json
from pathlib import Path
import sys


def main():
    """Dispatch project validation, source inspection, export, or the local graph server.

    Return a nonzero exit code when a declaration or source check fails.
    """
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["serve", "validate", "sources", "questions", "export"])
    p.add_argument("--root", required=True)
    p.add_argument("--project", default="bo_stategraph/project.json")
    p.add_argument("--port", type=int, default=8830)
    p.add_argument("--origin", action="append", default=[])
    p.add_argument("--out")
    a = p.parse_args()
    root = Path(a.root).absolute().resolve()
    from behavior_model import read, contained, capture
    from bo_observer.protocol import validate_project
    from bo_observer.development import questions
    from bo_sync import source_inventory
    from code_structure import scan

    try:
        project = read(contained(root, a.project))
        cfg_path = root / ("sync.json" if (root / "sync.json").exists() else "source-scope.json")
        cfg = read(cfg_path) if cfg_path.exists() else {}
        if a.command in ("sources", "questions", "validate"):
            inventory = source_inventory(root, cfg)
            index = scan(root, inventory["files"])
            if a.command == "validate":
                from implementation_coverage import inventory_errors, static_errors

                validate_project(project)
                errors = (
                    inventory_errors({**cfg, "stategraph": True}, inventory)
                    + index["errors"]
                    + static_errors(project["model"].get("implementation"), project["model"], index)
                )
                result = {
                    "valid": not errors,
                    "errors": errors,
                    "build_id": capture(root, project["model"])["build_id"],
                    "mode": project["selection"]["mode"],
                    "scope": "declaration, source inventory and implementation mapping; runtime acceptance is separate",
                }
            else:
                result = (
                    questions(
                        project,
                        index,
                        (
                            read(root / "discovery.json")
                            if (root / "discovery.json").exists()
                            else None
                        ),
                    )
                    if a.command == "questions"
                    else {
                        "protocol": "bo-source/v1",
                        "project_id": project["project_id"],
                        "files": inventory["files"],
                        **{k: index[k] for k in ("symbols", "edges", "unresolved", "errors")},
                    }
                )
        else:
            validate_project(project)
            if a.command == "export":
                result = project
            else:
                from bo_observer.service import GraphSession, make_server

                session = GraphSession(root, a.project)
                server = make_server(session, a.port, origins=a.origin)
                settings = root / ".stategraph/collector.json"
                settings.parent.mkdir(parents=True, exist_ok=True)
                settings.write_text(
                    json.dumps(
                        {
                            "endpoint": f"http://127.0.0.1:{server.server_port}",
                            "token": server.bo_token,
                            "build_id": session.manifest["build_id"],
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                print(
                    f"Graph: http://127.0.0.1:{server.server_port}/graph ; local SDK settings: {settings}",
                    flush=True,
                )
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    server.server_close()
                    session.close()
                return 0
        if a.out:
            contained(root, a.out).write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("errors") else 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
