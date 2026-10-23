"""Independent source, query and HTTP regressions for optional code structure."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "skills/business-observer/scripts"), str(ROOT / "tools")]
from bo_observer.code_graph.service import CodeGraph
from bo_observer.code_graph.query import query
from bo_observer.service import GraphSession, make_server
from observation_scope import observer_route
from test_multilanguage import project_fixture


class CodeGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".validation")
        self.root = Path(self.temp.name)
        self.project = project_fixture(self.root)
        self.service = CodeGraph(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, text):
        (self.root / path).write_text(text, encoding="utf-8")

    def test_independent_new_file_and_deleted_file(self):
        old, _ = self.service.refresh()
        self.write("new_feature.py", "def added(value):\n    return value\n")
        new, _ = self.service.refresh()
        self.assertNotEqual(old["revision"], new["revision"])
        self.assertIn("new_feature.py::added", new["symbols"])
        self.assertIn("worker.py", new["incremental"]["reused"])
        (self.root / "new_feature.py").unlink()
        latest, _ = self.service.refresh()
        self.assertNotIn("new_feature.py::added", latest["symbols"])

    def test_stable_identity_parameters_and_repeated_calls(self):
        source = "def target(v):\n    return v\ndef caller(v):\n    target(v)\n    return target(v)\n"
        self.write("calls.py", source)
        first, _ = self.service.refresh()
        calls = [e for e in first["edges"] if e["code_relation"] == "calls"]
        self.assertEqual(len(calls), 2)
        self.assertEqual(len({e["id"] for e in calls}), 2)
        self.write("calls.py", "# A comment moves source locations\n" + source)
        second, _ = self.service.refresh()
        self.assertEqual([e["id"] for e in calls], [e["id"] for e in second["edges"] if e["code_relation"] == "calls"])
        self.assertTrue(any(n["code_role"] == "parameter" for n in second["nodes"]))

    def test_calls_imports_inheritance_and_unknowns(self):
        self.write("base.py", "class Base:\n    pass\ndef helper(x):\n    return x\n")
        self.write("child.py", "from base import Base, helper\nclass Child(Base):\n    def run(self, x):\n        unknown(x)\n        return helper(x)\n")
        graph, _ = self.service.refresh()
        self.assertFalse(graph["errors"])
        relations = {e["code_relation"] for e in graph["edges"]}
        self.assertTrue({"calls", "imports", "inherits", "defines", "parameter"} <= relations)
        unknown = next(n for n in graph["nodes"] if n["label"] == "unknown")
        self.assertEqual(unknown["code_role"], "unresolved")
        inherit = next(e for e in graph["edges"] if e["code_relation"] == "inherits")
        self.assertEqual(inherit["to"], graph["symbols"]["base.py::Base"])

    def test_focused_authored_binding_and_relation_endpoints(self):
        graph = self.service.view(focus="advance")
        self.assertTrue(any(e["code_relation"] == "maps" and e["from"] == "advance" for e in graph["edges"]))
        self.assertEqual(graph["status"], "current")
        ids = {n["id"] for n in graph["nodes"]} | {"advance"}
        self.assertTrue(all(e["from"] in ids and e["to"] in ids for e in graph["edges"]))
        with self.assertRaises(ValueError):
            self.service.view(focus="fabricated")

    def test_limits_are_explicit_and_sources_revision_bound(self):
        graph, _ = self.service.refresh()
        full = deepcopy(graph)
        limited = self.service.view(limit=1)
        self.assertEqual(limited["loaded_nodes"], 1)
        self.assertGreater(limited["omitted_nodes"], 0)
        self.assertEqual(graph, full)
        with self.assertRaises(ValueError):
            self.service.view(limit=5001)
        self.assertIn("advance", self.service.source("worker.py", graph["revision"])["source"])
        for path in ("../private.py", "intent.json"):
            with self.assertRaises(ValueError): self.service.source(path, graph["revision"])
        self.write("worker.py", "def advance():\n    return 1\n")
        with self.assertRaises(ValueError): self.service.source("worker.py", graph["revision"])

    def test_parse_failure_removes_stale_nodes_and_recovers(self):
        first, _ = self.service.refresh()
        self.write("worker.py", "def broken(:\n")
        partial = self.service.view()
        self.assertEqual(partial["status"], "incomplete")
        self.assertTrue(partial["errors"])
        self.assertFalse(any(n.get("code_symbol") == "worker.py::advance" for n in partial["nodes"]))
        self.write("worker.py", "def recovered():\n    return True\n")
        recovered, _ = self.service.refresh()
        self.assertIn("worker.py::recovered", recovered["symbols"])
        self.assertFalse(recovered["errors"])

    def test_node_react_vue_share_protocol(self):
        self.write("logic.ts", "export class Base {}\nexport function save(value: string) { return value; }\n")
        self.write("Panel.tsx", 'import {save, Base} from "./logic";\nclass Panel extends Base { run(value: string) { return save(value); } }\nexport function View() { return <button onClick={() => save("x")}>Save</button>; }')
        self.write("Form.vue", '<script setup lang="ts">\nimport {save} from "./logic";\nfunction submit() { return save("x"); }\n</script><template><button @click="submit">Save</button></template>')
        graph, _ = self.service.refresh()
        self.assertFalse(graph["errors"], graph["errors"])
        self.assertIn("Panel.tsx::Panel.run", graph["symbols"])
        target = graph["symbols"]["logic.ts::save"]
        self.assertGreaterEqual(sum(e["to"] == target and e["code_relation"] == "calls" for e in graph["edges"]), 2)
        self.assertIn("Form.vue::submit", graph["symbols"])

    def test_module_initialization_and_commonjs(self):
        self.write("init.py", "def initialize():\n    return 1\nvalue = initialize()\n")
        self.write("library.cjs", "function save(v) { return v; }\nexports.save = save;\n")
        self.write("client.cjs", 'const {save} = require("./library.cjs");\nfunction run(v) { return save(v); }\nfunction callback(save) { return save(2); }\nfunction destructured({save}) { return save(2); }')
        graph, _ = self.service.refresh()
        self.assertFalse(graph["errors"])
        module = graph["symbols"]["init.py::<module>"]
        target = graph["symbols"]["init.py::initialize"]
        self.assertTrue(any(e["from"] == module and e["to"] == target for e in graph["edges"]))
        save = graph["symbols"]["library.cjs::save"]
        caller = graph["symbols"]["client.cjs::run"]
        callback = graph["symbols"]["client.cjs::callback"]
        self.assertTrue(any(e["from"] == caller and e["to"] == save for e in graph["edges"]))
        self.assertFalse(any(e["from"] == callback and e["to"] == save for e in graph["edges"]))
        destructured = graph["symbols"]["client.cjs::destructured"]
        self.assertFalse(any(e["from"] == destructured and e["to"] == save for e in graph["edges"]))

    def test_http_disabled_web_and_no_observer_events(self):
        session = GraphSession(self.root)
        server = make_server(session, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            self.assertIsNone(session.web.code_graph.graph)
            for _ in range(3):
                with urlopen(url + "/api/code/graph?focus=advance") as response:
                    self.assertEqual(json.load(response)["status"], "current")
            self.assertEqual(session.sequence, 0)
            self.assertTrue(observer_route("/api/code/graph?focus=advance"))
            self.assertEqual(session.model, self.project["model"])
            session.web.set_mode("disabled")
            with self.assertRaises(HTTPError) as error: urlopen(url + "/api/code/graph")
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown(); server.server_close(); thread.join(); session.close()

    def test_independent_check_rejects_stale_and_tampered_graph(self):
        graph, _ = self.service.refresh()
        self.assertTrue(self.service.check()["valid"])
        self.write("worker.py", "def changed():\n    return 2\n")
        self.assertFalse(self.service.check()["valid"])
        self.assertEqual(json.loads(self.service.cache.read_text())["revision"], graph["revision"])
        self.service.refresh()
        self.assertTrue(self.service.check()["valid"])
        forged = json.loads(self.service.cache.read_text())
        forged["nodes"] = []
        self.service.cache.write_text(json.dumps(forged), encoding="utf-8")
        self.assertFalse(self.service.check()["valid"])

    def test_conditional_declarations_and_maintenance_refresh(self):
        from bo_sync import maintenance_task
        self.write("conditional.py", "if True:\n    def callback(value):\n        return value\n")
        graph, _ = self.service.refresh()
        self.assertIn("conditional.py::callback", graph["symbols"])
        cfg = {"model": "bo_stategraph/project.json", "source_scope": {"roots": ["worker.py", "conditional.py"]}, "code_files": ["worker.py", "conditional.py"]}
        self.write("sync.json", json.dumps(cfg))
        self.write("conditional.py", "if True:\n    def updated(value):\n        return value\n")
        self.assertFalse(self.service.check()["valid"])
        maintenance_task(self.root, cfg)
        self.assertTrue(self.service.check()["valid"])
        saved = json.loads(self.service.cache.read_text())
        self.assertIn("conditional.py::updated", saved["symbols"])


if __name__ == "__main__":
    unittest.main()
