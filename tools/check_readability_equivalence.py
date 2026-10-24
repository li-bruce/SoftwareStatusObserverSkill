"""Verify source-only readability edits against a Git baseline.

Ignore Python docstrings and source locations, then compare executable ASTs.
JavaScript syntax equivalence is checked separately with TypeScript in the
readability review. Runtime tests remain necessary for behavior and integration.
"""

import argparse
import ast
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class WithoutDocumentation(ast.NodeTransformer):
    """Strip only a leading docstring from modules, classes, and functions."""

    def remove_docstring(self, node):
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr):
            value = node.body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                node.body = node.body[1:]
        return node

    visit_Module = remove_docstring
    visit_ClassDef = remove_docstring
    visit_FunctionDef = remove_docstring
    visit_AsyncFunctionDef = remove_docstring


def executable_tree(source, name):
    """Normalize documentation and locations without rewriting executable nodes."""
    return ast.dump(WithoutDocumentation().visit(ast.parse(source, filename=name)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--base-skill-path", default="skills/vibelens",
                        help="Skill path in the baseline, such as skills/business-observer before the rename")
    parser.add_argument("--out")
    args = parser.parse_args()
    files = sorted((ROOT / "skills/vibelens/scripts").rglob("*.py"))
    checked, changed = [], []
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        baseline_name = args.base_skill_path.rstrip('/') + '/' + path.relative_to(ROOT/'skills/vibelens').as_posix()
        previous = subprocess.run(
            ["git", "show", args.base + ":" + baseline_name],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8-sig")
        current = path.read_text(encoding="utf-8-sig")
        checked.append(name)
        if executable_tree(previous, name) != executable_tree(current, name):
            changed.append(name)
    result = {
        "base": args.base,
        "python_modules": len(checked),
        "executable_ast_changes": changed,
        "valid": not changed,
        "scope": "Python executable AST equality; comments, docstrings, and source locations excluded",
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(changed))


if __name__ == "__main__":
    main()
