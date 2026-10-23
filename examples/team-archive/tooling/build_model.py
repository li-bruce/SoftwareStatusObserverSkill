"""Generate the developer graph from authored mappings + executable declarations + AST."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT))
from bo_stategraph.workflow import definition
from observer_runtime.code_structure import scan, enrich


def build() -> dict:
    model = json.loads((ROOT/"tooling/behavior_source.json").read_text(encoding="utf-8-sig"))
    model.update(revision="1.1.0",status="implemented",machine=definition())
    nodes = {n["id"]:n for n in model["nodes"]}
    bindings = {
        "archive_request":("service","ArchiveService.create_run"),
        "document":("storage","ArchiveStore.snapshot"),
        "scope_check":("policy","is_direct_manager"),
        "approval_check":("policy","evaluate_approvals"),
        "content_check":("policy","check_content"),"index_check":("policy","check_index"),
        "processing_slots":("workflow","initial_configuration"),
        "archive_commit":("service","ArchiveService.try_commit"),
        "approval_revoked":("service","ArchiveService.revoke_approval"),
        "content_changed":("service","ArchiveService.edit_document"),
        "folder_assignments":("service","ArchiveService.evaluate"),
        "approval_target":("policy","candidate_allowed"),
        "archive_unique":("storage","ArchiveStore.find_archive"),
        "resume_run":("service","ArchiveService.resume_run"),
        "run_identity":("workflow","initial_configuration"),
        "flow.policy":("service","ArchiveService.evaluate"),
        "flow.checks":("service","ArchiveService.advance"),
        "flow.archive":("service","ArchiveService.try_commit"),
        "authority_read":("service","ArchiveService.evaluate"),
        "approval_candidate":("policy","candidate_allowed"),
        "commit_guard":("service","ArchiveService.evaluate"),
        "checks_join":("workflow","activity_step"),
        "cancel_run":("service","ArchiveService.cancel_run"),
        "lifecycle":("workflow","Workflow"),
        "issue_approval":("service","ArchiveService.add_approval"),
        "move_folder":("service","ArchiveService.move_document"),
        "recover_run":("service","ArchiveService.recover_interrupted"),
        "worker_call":("service","ArchiveService.worker"),
        "project_limit":("storage","ArchiveStore.project_limit"),
        "size_guard":("policy","check_size"),
        "set_size_limit":("service","ArchiveService.set_archive_limit"),
    }
    for ident,kind,label,summary in [
        ("flow.policy","action","Check archive eligibility","Current direct ownership, valid approval, and body size conditions hold."),
        ("flow.checks","action","Complete both checks for this run","Each run owns its slots; retain individual activities and resource state."),
        ("flow.archive","action","Recheck and persist snapshot","In one transaction, verify current relationships, version, approvals, size limit, and this run's checks."),
        ("authority_read","function","Read current authoritative relationships","Read the document, direct owner, and full approval candidates in one SQLite transaction."),
        ("approval_candidate","decision","Evaluate each approval","Independently evaluate each approval's target, identity, revocation, and expiry conditions."),
        ("commit_guard","decision","Is the actor still eligible?","Reread current version and relationships before commit; do not reuse an earlier success."),
        ("checks_join","data","Both checks passed for this run","The ALL join uses results from the same run and content version only."),
        ("cancel_run","action","Cancel this run","Prevent pending checks from starting; active checks release slots only after actual completion."),
        ("lifecycle","data","This run's phase","Expand actual state transitions; historical frames use their recorded state."),
        ("issue_approval","function","Approve the current version","Record another reviewer's version-bound approval; existing waiting runs still need manual continuation."),
        ("move_folder","function","Change classification folder","Update the folder and relationship revision, then recheck direct ownership."),
        ("recover_run","function","Recover interrupted records","Restart does not revive lost workers; preserve records and release their capacity."),
        ("worker_call","function","Execute and persist check results","Update the same run after the real worker finishes, then release its slot."),
        ("project_limit","data","Project archive size limit","Persist per project, default 8192 bytes; changing it does not change content versions or approvals."),
        ("size_guard","decision","Is the body within the current limit?","Count body UTF-8 bytes only; equality is allowed; reread the limit at start, resume, and commit."),
        ("set_size_limit","function","Change project size limit","Accept positive integers only; oversized runs wait, active checks finish, and recovery requires manual continuation."),
    ]:
        nodes[ident]={"id":ident,"kind":kind,"label":label,"summary":summary,"capture":{"in":{},"out":{}}}
    groups = {
        "flow.policy":["archive_request","document","scope_check","approval_check","authority_read",
                       "folder_assignments","approval_target","resume_run","move_folder",
                       "project_limit","size_guard","set_size_limit"],
        "flow.checks":["content_check","index_check","processing_slots","checks_join","run_identity","content_changed","cancel_run","lifecycle","recover_run","worker_call"],
        "flow.archive":["archive_commit","archive_unique","commit_guard"],
        "approval_check":["approval_candidate","approval_revoked","issue_approval"],
    }
    for group, children in groups.items():
        if group.startswith("flow."):
            nodes[group]["layer"]="business"
        for ident in children:
            nodes[ident]["parent"]=group
    for ident,(module,symbol) in bindings.items():
        nodes[ident]["source"]={"path":("bo_stategraph/" if module=="workflow" else "archive_app/")+module+".py","symbol":symbol}
        nodes[ident].pop("planned_source",None)
        nodes[ident].pop("binding_status",None)
    for ident in ("content_check","index_check"):
        nodes[ident]["execution_role"]="activity"
    for ident,label,symbol,parent in [('run.storage',"Persist run state",'ArchiveStore.save_run','flow.checks'),
            ('run.lookup',"Read a specific run",'ArchiveStore.get_run','flow.checks'),
            ('relations.revision',"Increment relationship revision",'ArchiveStore.bump','flow.policy')]:
        nodes[ident]={'id':ident,'label':label,'summary':label,'kind':'function','layer':'program',
            'parent':parent,'analysis_level':'advanced','source':{'path':'archive_app/storage.py','symbol':symbol}}
    nodes["processing_slots"]["execution_role"]="resource"
    for symbol,label,parent in [('schedule',"Schedule waiting, starts, and joins",'flow.checks'),
            ('request_stop',"Stop starting new checks",'cancel_run'),('settle',"Wait for active checks to finish",'cancel_run'),
            ('checks_passed',"Verify same-run check results",'checks_join'),('interrupt',"Mark interruption and release slots",'recover_run'),
            ('finish_activity',"Finish an activity and record its result",'worker_call'),('resume',"Resume this run",'resume_run')]:
        ident='execution.'+symbol
        nodes[ident]={'id':ident,'label':label,'summary':label,'kind':'function','layer':'program',
            'parent':parent,'analysis_level':'advanced','source':{'path':'bo_stategraph/workflow.py','symbol':symbol}}
    nodes["checks_join"]["execution_role"]="join"
    nodes["processing_slots"]["summary"]="Each run owns its capacity, chosen as 1 or 2; checks release slots after finishing."
    nodes["content_changed"]["summary"]="Old runs cannot commit; pending checks are discarded, active checks finish, and the new version has a separate run."
    nodes["content_check"]["summary"]="Check SECRET: against this run's fixed input; capture length, digest, and actual decisions, never body text."
    nodes["index_check"]["summary"]="Verify this run's title, project, and document ID."
    b,n,s="boolean","number","string"
    candidate_flags={k:b for k in ("project_ok","operator_ok","document_ok","version_ok","reviewer_ok",
                                   "different_actor","not_revoked","time_ok","target_matches","allowed")}
    captures={
      "scope_check":({"project_id":s,"operator_id":s,"folder_id":s,
          "assignments":[{"project_id":s,"operator_id":s,"folder_id":s}]},{"allowed":b,"inherit_ancestors":b}),
      "approval_candidate":({"id":s,"project_id":s,"operator_id":s,"document_id":s,"content_version":n,
          "reviewer_id":s,"deadline":n,"revoked":n,"request_project":s,"request_operator":s,"request_document":s,
          "request_version":n,"clock":n},candidate_flags),
      "approval_check":({"project_id":s,"operator_id":s,"document_id":s,"content_version":n,"clock":n,"candidate_count":n},
          {"allowed":b,"candidates":[{"id":s,**candidate_flags}]}),
      "content_check":({"attempt":s,"content_version":n,"content_length":n,"content_sha256":s,"forbidden_marker":s},
          {"passed":b,"marker_present":b}),
      "index_check":({"attempt":s,"content_version":n,"title_length":n,"project_id":s,"document_number":s},
          {"title_present":b,"project_present":b,"number_present":b,"passed":b}),
      "commit_guard":({"stage":s,"project_id":s,"folder_id":s,"operator_id":s,"run_version":n,"current_version":n,"all_passed":b},
          {"allowed":b,"scope_allowed":b,"approval_allowed":b,"size_allowed":b,"version_current":b,"reasons":[s]}),
      "project_limit":({"project_id":s},{"project_id":s,"limit_bytes":n,"limit_revision":n}),
      "size_guard":({"project_id":s,"content_bytes":n,"limit_bytes":n,"limit_revision":n},
          {"allowed":b,"content_bytes":n,"limit_bytes":n,"limit_revision":n,"excess_bytes":n}),
      "archive_commit":({"attempt":s,"document_id":s,"content_version":n},{"effect_id":s,"persisted":b}),
      "archive_unique":({"document_id":s,"content_version":n},{"effect_id":s,"reused":b}),
      "authority_read":({"document_id":s},{"project_id":s,"folder_id":s,"content_version":n,"relation_epoch":n,"approval_count":n}),
      "archive_request":({"document_id":s,"operator_id":s,"capacity":n,"content_version":n},{"attempt":s}),
      "flow.checks":({"attempt":s,"content_version":n},{"revision":n,"phase":s,"available":n,"join_state":s}),
      "resume_run":({"attempt":s},{"allowed":b}),
      "cancel_run":({"attempt":s},{"phase":s,"running_count":n}),
    }
    for ident,(inputs,outputs) in captures.items():
        nodes[ident]["capture"]={"in":inputs,"out":outputs}
    nodes["commit_guard"]["capture"]["in"].update(content_bytes=n,limit_bytes=n,limit_revision=n)
    for ident in ("project_limit","size_guard","set_size_limit"):
        nodes[ident]["requirements"]=["R14","R15","R16"]
    nodes["size_guard"]["rule"]={"encoding":"utf-8","body_only":True,"inclusive":True}
    for value in model["machine"]["values"]:
        ident="state."+value
        parent="flow.archive" if value in ("ready","completed") else "flow.policy" if value=="created" else "flow.checks"
        nodes[ident]={"id":ident,"kind":"state","layer":"state","value":value,
            "label":model["machine"]["labels"][value],"summary":"Persisted application state "+value,
            "parent":"lifecycle","source":model["machine"]["source"]}
    edges=[e for e in model["edges"] if e["id"] not in ("slots_content","slots_index","content_archive","index_archive")]
    for ident,node in nodes.items():
        if node.get("parent"):
            edges.append({"id":"contains:"+ident,"from":node["parent"],"to":ident,
                "type":"contains","label":"Contains","evidence":"Project business grouping"})
    for activity in model["machine"]["execution"]["activities"]:
        for rid,units in activity["requires"].items():
            edges.append({"id":"resource:"+activity["id"],"from":rid,"to":activity["id"],
                "type":"resource","units":units,"label":"Acquire one slot owned by this run","evidence":"Actual machine.execution declaration"})
        edges.append({"id":"join:"+activity["id"],"from":activity["id"],"to":"checks_join",
            "type":"join","label":"This run's check finished","evidence":"Actual ALL join declaration"})
    edges += [
        {"id":"all-to-commit","from":"checks_join","to":"archive_commit","type":"guard","label":"Both passed in this run","evidence":"U03-U04"},
        {"id":"policy-to-checks","from":"flow.policy","to":"flow.checks","type":"flow","label":"Start when current eligibility holds","evidence":"U04"},
        {"id":"checks-to-archive","from":"flow.checks","to":"flow.archive","type":"flow","label":"Recheck after both pass","evidence":"U03-U04"},
        {"id":"candidate-to-aggregate","from":"approval_candidate","to":"approval_check","type":"guard","label":"At least one valid approval","evidence":"U03"},
        {"id":"limit-to-size","from":"project_limit","to":"size_guard","type":"data","label":"Read the current byte limit","evidence":"U05-U06"},
        {"id":"set-to-limit","from":"set_size_limit","to":"project_limit","type":"data","label":"Persist project configuration","evidence":"U06"},
        {"id":"size-to-commit","from":"size_guard","to":"commit_guard","type":"guard","label":"Current body is within the limit","evidence":"U05-U06"},
    ]
    model["nodes"],model["edges"]=list(nodes.values()),edges
    model["graph_roots"]=["flow.policy","flow.checks","flow.archive"]
    model["overview"]=[{"node":n,"x":80+i*400,"y":120} for i,n in enumerate(model["graph_roots"])]
    model["presentation"].update(default_expanded=[],
                                 title="Team archive · developer runtime graph")
    model["presentation"]["replay_parameters"]={
        "content_bytes":{"node":"size_guard","direction":"in","field":"content_bytes"},
        "limit_bytes":{"node":"project_limit","direction":"out","field":"limit_bytes"},
        "limit_revision":{"node":"project_limit","direction":"out","field":"limit_revision"},
    }
    model['presentation']['context_fields']=[{'key':'content_bytes','label':"Current body",'unit':"bytes"},
        {'key':'limit_bytes','label':"Current project limit",'saved_label':"Limit at save",'unit':"bytes"}]
    model["scope"]["unknowns"]=[
        "Covers local synthetic documents, direct ownership, and embedded approval rules; not a generic ReBAC engine.",
        "Capture body digest and length only; external authentication, filesystem archives, and external services are outside the first version.",
        "Unstarted discarded activities retain their flag until active activities finish and abort runs; project tests check this flag.",
        "AST cannot prove dynamic call completeness; finite cases do not prove all schedules or human usability."]
    model["questions"]=[]
    cfg=json.loads((ROOT/"sync.json").read_text(encoding="utf-8"))
    model["source_files"]=sorted(set(cfg["code_files"]+[
        "tooling/build_model.py","tooling/behavior_source.json","archive_app/__init__.py",
        "observer_runtime/semantic_probe.py","observer_runtime/behavior_model.py","observer_runtime/recording_session.py","observer_runtime/bo_stategraph.py","observer_runtime/observation_scope.py",
        "run.py","static/app.html","static/app.css","static/app.js",
        "static/graph/index.html","static/graph/viewer.js","static/graph/graph-core.js","static/graph/layout.js","static/graph/viewer.css",
        "static/graph/analysis.js","static/graph/recording.js","static/graph/glyphs.js","static/graph/replay-steps.js"]))
    model.setdefault('presentation', {})['recording']={'parameters': ['param_version', 'attempt', 'capacity', 'content_bytes', 'limit_bytes', 'limit_revision'], 'command_fields': ['document_id', 'operator_id', 'reviewer_id', 'approval_id', 'run_id', 'folder_id', 'project_id', 'capacity', 'seconds', 'limit_bytes', 'param_version', 'expected_version']}
    model['source_files']=sorted(set(model['source_files']+[p.relative_to(ROOT).as_posix() for p in (ROOT/'bo_stategraph').glob('*.py')]+['static/graph/preferences.js','static/graph/conversation.js','observer_runtime/bo_design.py','observer_runtime/bo_web.py','observer_runtime/view_preferences.py','observer_runtime/bo_retention.py']))
    for node in model['nodes']:
        if node['id'] in ['scope_check','approval_check','approval_candidate','commit_guard','folder_assignments','approval_target','project_limit','size_guard','authority_read']:
            node['basis_fields']=['param_version','epoch','clock']
        if node['id'] in ['scope_check', 'approval_check', 'approval_candidate', 'commit_guard', 'folder_assignments', 'approval_target']: node['semantic_roles']=['permission']
        if node.get('execution_role') in ('resource','join'): node['analysis_level']='advanced'
    model['implementation']=json.loads((ROOT/'implementation.json').read_text(encoding='utf-8'))
    model['source_files'] += ['implementation.json','bo_stategraph/machine.json']
    captures={
        'issue_approval':({'document_id':'string','operator_id':'string','reviewer_id':'string','deadline':'number'},{'approval_id':'string'}),
        'approval_revoked':({'approval_id':'string'},{'revoked':'boolean'}),
        'set_size_limit':({'project_id':'string','limit_bytes':'number'},{'project_id':'string','limit_bytes':'number','limit_revision':'number'}),
        'content_changed':({'document_id':'string','title_length':'number','number':'string','content_bytes':'number'},{'saved':'boolean'}),
        'move_folder':({'document_id':'string','folder_id':'string'},{'moved':'boolean'})}
    for n in model['nodes']:
        if n['id'] in captures:
            inputs,outputs=captures[n['id']];n['capture']={'in':inputs,'out':outputs};n['basis_fields']=['epoch']
    model['nodes'].extend(json.loads((ROOT/'tooling/frontend_nodes.json').read_text(encoding='utf-8')))
    model['graph_roots']+=['ui.command','ui.validate','ui.dirty']
    for target in ['archive_request','content_changed','move_folder','issue_approval','approval_revoked','resume_run','cancel_run','set_size_limit']:
        model['edges'].append({'id':'ui-to-'+target,'from':'ui.command','to':target,'type':'flow','label':"Submit the corresponding operation",'evidence':"Actual static/app.js request → LocalApplication.command dispatch"})
    model['edges'] += [{'id':'ui-validation','from':'ui.validate','to':'ui.command','type':'guard','label':"Submit positive integers only",'evidence':'submitLimit'},
                       {'id':'ui-dirty','from':'ui.dirty','to':'ui.command','type':'data','label':"Submit page input",'evidence':'DOM handlers'}]
    model['source_files'].extend(['tooling/frontend_nodes.json','integrations/bo_client.mjs'])
    model=enrich(model,scan(ROOT,cfg["code_files"]),depth=cfg.get("slice_depth",1))
    (ROOT/"behavior.json").write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
    return model


if __name__=="__main__":
    model=build()
    print(json.dumps({"revision":model["revision"],"nodes":len(model["nodes"]),"edges":len(model["edges"])}))
