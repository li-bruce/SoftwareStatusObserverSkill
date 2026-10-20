"""Bind saved code before loading the application, then serve only on loopback."""
import argparse
import json
from pathlib import Path
import sys
from observer_runtime.behavior_model import capture, check

ROOT=Path(__file__).absolute().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8824)
    parser.add_argument("--db",default="data/archive.sqlite3")
    parser.add_argument("--delay",type=float,default=4.0)
    parser.add_argument("--candidate",action="store_true",help="Development only: visibly unverified candidate.")
    args=parser.parse_args()
    if not 0<=args.delay<=30:
        parser.error("delay must be 0..30")
    model=json.loads((ROOT/"behavior.json").read_text(encoding="utf-8"))
    loaded=capture(ROOT,model)
    if not args.candidate:
        manifest=json.loads((ROOT/"manifest.json").read_text(encoding="utf-8"))
        if check(ROOT,model,manifest)["status"]!="current" or manifest["build_id"]!=loaded["build_id"]:
            raise RuntimeError("源码与已验收版本不一致，请先完成项目检查。")
    sources={p:(ROOT/p).read_text(encoding="utf-8-sig") for p in loaded["files"] if p.endswith((".py",".json",".js",".html",".css"))}
    from integrations.bo_server import serve
    if capture(ROOT,model)["build_id"]!=loaded["build_id"]:
        raise RuntimeError("源码在加载时发生变化")
    serve(ROOT,args,model,loaded,sources)


if __name__=="__main__":
    main()
