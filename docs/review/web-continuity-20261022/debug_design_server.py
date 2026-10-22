"""Diagnostic wrapper: log actual save destinations without changing persistence."""
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'skills/business-observer/scripts'))
import bo_web
save=bo_web.Preferences.save
def logged(self,value):
    result=save(self,value)
    print(json.dumps({'cwd':os.getcwd(),'path':str(self.path),'exists':self.path.exists(),'revision':result['revision']},ensure_ascii=False),flush=True)
    return result
bo_web.Preferences.save=logged
bo_web.bo_serve(sys.argv[1],port=int(sys.argv[2]))
