"""Run the same behavior with a state-machine driver or ordinary Python logic."""
import argparse
import json
from pathlib import Path
from app import Job, OwnLogic
from bo_stategraph.driver import MachineLogic
from bo_stategraph import BOStateGraph

ROOT = Path(__file__).resolve().parent


def bo_session(mode):
    model = json.loads((ROOT / "bo_stategraph/model.json").read_text(encoding="utf-8"))
    from bo_stategraph.binding import bo_check_sources
    binding = bo_check_sources(ROOT)
    if binding["status"] != "current":
        raise ValueError("Source changed; update the model and tests, then run build_model.py")
    graph = BOStateGraph(model, build_id=binding["build_id"], mode=mode)
    def bo_notify(snapshot, event=None, guards=None):
        return graph.bo_observe("job:1", **snapshot, event=event, guards=guards,
            evidence_id="job:1:" + str(snapshot["revision"]), build_id=graph.build_id)
    logic = MachineLogic(graph.bo_definition()) if mode == "drive" else OwnLogic()
    job = Job(logic, bo_notify)
    bo_notify(job.snapshot())
    return job, graph, binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("observe", "drive"), required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    job, graph, binding = bo_session(args.mode)
    history = [job.snapshot()]
    for event, slots in (("start", 0), ("resume", 1), ("finish", 1)):
        history.append(job.run(event, slots))
    value = graph.bo_export(runtime={"snapshots": history}, binding=binding)
    if args.out:
        with Path(args.out).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"mode": args.mode, "states": [x["state"] for x in history],
                      "effects": job.effects, "nodes": len(value["model"]["nodes"])}, ensure_ascii=False))


if __name__ == "__main__": main()
