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
        ("flow.policy","action","核对归档资格","直接负责、有效审批和正文大小均满足当前条件。"),
        ("flow.checks","action","完成本次两项检查","每次运行独享名额；保留各活动实例与资源状态。"),
        ("flow.archive","action","复核并保存快照","同一事务核对当前关系、版本、审批、项目大小上限及本次检查结果。"),
        ("authority_read","function","读取当前权威关系","同一 SQLite 事务读取资料、直接负责人和完整审批候选。"),
        ("approval_candidate","decision","逐条判断审批","每条审批独立计算全部目标、身份、撤销与期限条件。"),
        ("commit_guard","decision","当前是否仍有资格","提交前重读当前版本与关系，不能沿用历史绿色结果。"),
        ("checks_join","data","本次两项均通过","ALL 汇合只使用同次运行同一内容版本的结果。"),
        ("cancel_run","action","取消本次运行","阻止尚未开始的检查，等待已启动检查实际结束再归还名额。"),
        ("lifecycle","data","本次流程状态","展开查看实际状态迁移；历史时刻使用该帧记录的状态。"),
        ("issue_approval","function","为当前版本审批","记录另一名审核员的版本绑定审批；既有等待运行仍需手动继续。"),
        ("move_folder","function","调整分类文件夹","更新当前目录及关系版本，当前直接负责人关系随之重查。"),
        ("recover_run","function","恢复中断记录","重启不复活已失去的工作线程；保留记录并释放其容量。"),
        ("worker_call","function","执行并保存检查结果","真实工作线程结束后更新同次运行，随后归还所占名额。"),
        ("project_limit","data","项目归档大小上限","每项目独立持久化，默认 8192 字节；改变上限不修改内容版本或审批。"),
        ("size_guard","decision","正文是否在当前上限内","只计算正文 UTF-8 字节数，等于上限允许；开始、继续、提交时重新读取当前上限。"),
        ("set_size_limit","function","调整项目大小上限","只接受正整数；超限等待，已开始检查自然结束，条件恢复仍需手动继续。"),
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
    for ident,label,symbol,parent in [('run.storage','保存运行状态','ArchiveStore.save_run','flow.checks'),
            ('run.lookup','读取指定运行','ArchiveStore.get_run','flow.checks'),
            ('relations.revision','更新关系修订号','ArchiveStore.bump','flow.policy')]:
        nodes[ident]={'id':ident,'label':label,'summary':label,'kind':'function','layer':'program',
            'parent':parent,'analysis_level':'advanced','source':{'path':'archive_app/storage.py','symbol':symbol}}
    nodes["processing_slots"]["execution_role"]="resource"
    for symbol,label,parent in [('schedule','安排等待、启动与汇合','flow.checks'),
            ('request_stop','停止启动新检查','cancel_run'),('settle','等待运行检查收尾','cancel_run'),
            ('checks_passed','核对同次检查结果','checks_join'),('interrupt','标记中断并归还名额','recover_run'),
            ('finish_activity','完成活动并记录结果','worker_call'),('resume','恢复本次运行','resume_run')]:
        ident='execution.'+symbol
        nodes[ident]={'id':ident,'label':label,'summary':label,'kind':'function','layer':'program',
            'parent':parent,'analysis_level':'advanced','source':{'path':'bo_stategraph/workflow.py','symbol':symbol}}
    nodes["checks_join"]["execution_role"]="join"
    nodes["processing_slots"]["summary"]="本次运行独享容量，创建时选 1 或 2；检查实际结束后归还。"
    nodes["content_changed"]["summary"]="旧运行不再提交；未开始检查作废，已开始自然结束，新版本另建独立运行。"
    nodes["content_check"]["summary"]="对本次固定输入检查 SECRET: 标记；不记录正文，只观察长度、摘要和实际判断。"
    nodes["index_check"]["summary"]="检查本次标题、项目和资料编号是否齐全。"
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
            "label":model["machine"]["labels"][value],"summary":"程序持久化状态 "+value,
            "parent":"lifecycle","source":model["machine"]["source"]}
    edges=[e for e in model["edges"] if e["id"] not in ("slots_content","slots_index","content_archive","index_archive")]
    for ident,node in nodes.items():
        if node.get("parent"):
            edges.append({"id":"contains:"+ident,"from":node["parent"],"to":ident,
                "type":"contains","label":"包含","evidence":"项目业务分组"})
    for activity in model["machine"]["execution"]["activities"]:
        for rid,units in activity["requires"].items():
            edges.append({"id":"resource:"+activity["id"],"from":rid,"to":activity["id"],
                "type":"resource","units":units,"label":"占用 1 个本运行名额","evidence":"实际执行声明 machine.execution"})
        edges.append({"id":"join:"+activity["id"],"from":activity["id"],"to":"checks_join",
            "type":"join","label":"本次检查结束","evidence":"实际 ALL 汇合声明"})
    edges += [
        {"id":"all-to-commit","from":"checks_join","to":"archive_commit","type":"guard","label":"同次两项通过","evidence":"U03-U04"},
        {"id":"policy-to-checks","from":"flow.policy","to":"flow.checks","type":"flow","label":"当前资格满足后开始","evidence":"U04"},
        {"id":"checks-to-archive","from":"flow.checks","to":"flow.archive","type":"flow","label":"两项通过再复核","evidence":"U03-U04"},
        {"id":"candidate-to-aggregate","from":"approval_candidate","to":"approval_check","type":"guard","label":"至少一条有效","evidence":"U03"},
        {"id":"limit-to-size","from":"project_limit","to":"size_guard","type":"data","label":"读取当前字节上限","evidence":"U05-U06"},
        {"id":"set-to-limit","from":"set_size_limit","to":"project_limit","type":"data","label":"保存项目配置","evidence":"U06"},
        {"id":"size-to-commit","from":"size_guard","to":"commit_guard","type":"guard","label":"当前正文不超限","evidence":"U05-U06"},
    ]
    model["nodes"],model["edges"]=list(nodes.values()),edges
    model["graph_roots"]=["flow.policy","flow.checks","flow.archive"]
    model["overview"]=[{"node":n,"x":80+i*400,"y":120} for i,n in enumerate(model["graph_roots"])]
    model["presentation"].update(default_expanded=[],
                                 title="团队资料归档 · 开发者运行图")
    model["presentation"]["replay_parameters"]={
        "content_bytes":{"node":"size_guard","direction":"in","field":"content_bytes"},
        "limit_bytes":{"node":"project_limit","direction":"out","field":"limit_bytes"},
        "limit_revision":{"node":"project_limit","direction":"out","field":"limit_revision"},
    }
    model['presentation']['context_fields']=[{'key':'content_bytes','label':'本次正文','unit':'字节'},
        {'key':'limit_bytes','label':'当前项目上限','saved_label':'保存时上限','unit':'字节'}]
    model["scope"]["unknowns"]=[
        "只覆盖本地合成资料、直接负责关系和内嵌审批规则，不是通用 ReBAC 引擎。",
        "正文不进入探针，仅记录内容摘要和长度；外部身份认证、文件系统归档及外部服务不在首版范围。",
        "未启动且已作废的活动保留 discarded 标识，直到已启动活动结束后执行 abort；该标识由项目测试检查。",
        "AST 不能证明动态调用完整性；图和有限场景不构成所有调度或真人易用性证明。"]
    model["questions"]=[]
    cfg=json.loads((ROOT/"sync.json").read_text(encoding="utf-8"))
    model["source_files"]=sorted(set(cfg["code_files"]+[
        "tooling/build_model.py","tooling/behavior_source.json","archive_app/__init__.py",
        "observer_runtime/semantic_probe.py","observer_runtime/behavior_model.py","observer_runtime/recording_session.py","observer_runtime/bo_stategraph.py",
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
    model=enrich(model,scan(ROOT,cfg["code_files"]),depth=cfg.get("slice_depth",1))
    (ROOT/"behavior.json").write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
    return model


if __name__=="__main__":
    model=build()
    print(json.dumps({"revision":model["revision"],"nodes":len(model["nodes"]),"edges":len(model["edges"])}))
