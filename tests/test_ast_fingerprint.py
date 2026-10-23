"""Regression checks for a graph generated on a different Python version."""

import ast
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/business-observer/scripts"))
from behavior_model import ast_fingerprint
from code_structure import parse_unit, scan, enrich


class FingerprintTests(unittest.TestCase):
    def test_new_empty_fields_do_not_invalidate_existing_source(self):
        for source in ("def run(x): return x + 1", "async def run(x): return x", "class Job: pass"):
            current = ast.parse(source).body[0]
            legacy = copy.deepcopy(current)
            legacy._fields = tuple(f for f in legacy._fields if f != "type_params")
            current._fields = (*legacy._fields, "type_params")
            current.type_params = []
            self.assertEqual(ast_fingerprint(legacy), ast_fingerprint(current))

    def test_real_type_parameters_are_not_discarded(self):
        node = ast.parse("def run(x): return x").body[0]
        old = ast_fingerprint(node)
        if "type_params" not in node._fields:
            node._fields = (*node._fields, "type_params")
        node.type_params = [ast.Name(id="T", ctx=ast.Load())]
        self.assertNotEqual(old, ast_fingerprint(node))

    def test_changed_guard_invalidates_fingerprint(self):
        before = ast.parse("def allowed(v): return v >= 2")
        after = ast.parse("def allowed(v): return v > 2")
        self.assertNotEqual(ast_fingerprint(before), ast_fingerprint(after))

    def test_positions_and_comments_do_not_change_syntax(self):
        self.assertEqual(
            ast_fingerprint(ast.parse("x = 1")), ast_fingerprint(ast.parse("\n# comment\nx = 1\n"))
        )

    def test_source_binding_and_static_slice_agree(self):
        source = "def run(x: int): return x + 1"
        item = parse_unit("app.py", source)["symbols"]["run"]
        self.assertEqual(ast_fingerprint(ast.parse(source).body[0]), item["ast_hash"])

    def test_static_relation_ids_survive_line_shifts_and_keep_repeated_calls(self):
        authored = {
            "nodes": [
                {
                    "id": "run",
                    "kind": "function",
                    "layer": "business",
                    "source": {"path": "app.py", "symbol": "run"},
                },
                {
                    "id": "helper",
                    "kind": "function",
                    "parent": "run",
                    "source": {"path": "app.py", "symbol": "helper"},
                },
            ],
            "edges": [],
            "graph_roots": ["run"],
        }
        source = "def helper(value): return value\ndef run():\n    return helper(1) + helper(1)\n"
        scratch = Path(__file__).resolve().parents[1] / ".validation"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            root = Path(folder)
            path = root / "app.py"
            path.write_text(source, encoding="utf-8")
            before = enrich(authored, scan(root, ["app.py"]))
            path.write_text("# unrelated comment\n\n" + source, encoding="utf-8")
            after = enrich(authored, scan(root, ["app.py"]))
        calls = lambda model: [edge for edge in model["edges"] if edge["id"].startswith("call.")]
        self.assertEqual(len(calls(before)), 2)
        self.assertEqual({e["id"] for e in calls(before)}, {e["id"] for e in calls(after)})
        self.assertNotEqual(
            calls(before)[0]["callsite"]["line"], calls(after)[0]["callsite"]["line"]
        )


if __name__ == "__main__":
    unittest.main()
