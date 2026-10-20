"""Record semantic review for the current candidate; never modify expectations."""
import json
from pathlib import Path

ROOT=Path(__file__).absolute().parents[2]
impact=json.loads((ROOT/"review/round-04/inspect-final-candidate.json").read_text(encoding="utf-8-sig"))
reasons={}


def classify(path,symbols,reason):
    for symbol in symbols.split():
        reasons[path+"::"+symbol]=reason


classify("archive_app/ports.py","TracePort TracePort.__init__ TracePort.record no_trace",
         "中立可选输出端口，不作业务判定；关闭不构造载荷、接收器抛错不传播，规则测试及 on/off/fault 场景验证。类与方法作为观测边界分类，不冒充业务步骤。")
classify("archive_app/service.py","ArchiveService ArchiveService.__init__",
         "服务容器保存锁、时钟、真实线程及可选输出端口。具体业务由已映射命令和 evaluate/advance/worker/commit 节点承担；execution_version 仅记录创建构建，不参与权限。")
classify("archive_app/service.py","ArchiveService.close ArchiveService.start_scheduler ArchiveService.start_scheduler.loop",
         "调度与关停包装实际 advance/tick，不另造状态；关闭等待真实线程。核心场景通过受控真实线程检验，浏览器服务以实际定时调度执行。无限调度集合未证明。")
classify("archive_app/storage.py","ArchiveStore ArchiveStore.__init__ ArchiveStore.connect",
         "SQLite 连接和建表边界。唯一(document_id, content_version)约束承接 R13，try_commit 事务和并发重复用例验证真实记录。SQL 未伪装成 AST 全量数据流。")
classify("archive_app/storage.py","ArchiveStore.bump",
         "权威关系修订号更新，被审批/目录/内容命令在实际事务中调用；读取依据在 authority_read/evaluate 参数中显示。")
classify("archive_app/storage.py","ArchiveStore.get_run ArchiveStore.save_run",
         "按独立运行 ID 读写完整配置的持久化助手，包含版本/活动/资源/结果；在实际业务节点下折叠，edit_overlap/cancel_one_of_two/restart 和执行契约验证作用范围。")
classify("archive_app/storage.py","ArchiveStore.seed",
         "仅初始化明确标注的本地合成资料和人员；不是生产身份或真实权限来源，独立场景沿固定合成关系验证。")
classify("archive_app/workflow.py","Phase Workflow.__init__ definition",
         "真实 transitions.Machine 的枚举、装配与同源导出；graph.machine 与运行声明核对。状态节点来自这一声明，不另造观察状态机。")
classify("archive_app/workflow.py","Workflow.all_passed Workflow.approved Workflow.checks_failed Workflow.effect_saved Workflow.settled",
         "真实状态机 guard，分别读取同一调用交入的判定；lifecycle/commit_guard/checks_join 承载图上表达。独立未完成不能推进、资格失效、取消自然结束及事务提交场景覆盖相关门槛。")
classify("integrations/bo_observer.py","BOObserver BOObserver.__init__ BOObserver.close BOObserver.health BOObserver.snapshot BOObserver.trace BOObserver.write",
         "可剔除观测适配器：异步 sink、捕获白名单、构建/调用身份及 gap 健康信息；不提供权限判断。关闭/故障/队列满测试与独立核心包执行检验隔离。")
classify("integrations/bo_server.py","LocalApplication LocalApplication.__init__ LocalApplication.cases LocalApplication.command LocalApplication.graph_view LocalApplication.state",
         "本地合成演练的命令路由和只读视图，命令调用已映射服务；历史场景使用已保存权威快照，运行构建不匹配时禁用当前源码关联。HTTP/浏览器验证覆盖此适配层，非生产鉴权。")
classify("integrations/bo_server.py","serve serve.Handler serve.Handler.do_GET serve.Handler.do_POST serve.Handler.log_message serve.Handler.reply",
         "仅回环 HTTP 入口、同源命令限制、静态资源及载入源码服务；页面文件不作为业务效果证据。源码读取限加载清单，写命令仍经过核心事务保护。")
classify("run.py","main",
         "模块导入前 capture/check，加载后再次比对；默认要求已验收 manifest，开发候选显式标识未验收。保存的旧运行与当前构建不匹配时仅作历史状态。")
unmapped=set(impact["unmapped_changed_symbols"])
if unmapped-set(reasons):
    raise RuntimeError(sorted(unmapped-set(reasons)))
review={"candidate_id":impact["candidate_id"],"decisions":{
    "business":{"action":"updated","reason":"实现 U01-U04 / R01-R13 的当前目录直接负责人、另一审核员的完整目标版本审批、严格期限、独立运行、同次双检查、恢复/取消/改版及唯一快照事务。保留原始独立预期。"},
    "state_machine":{"action":"updated","reason":"应用自身 transitions 状态机与 activities/resources/join 事务记录作为唯一执行状态；每次实际线程开始和结束保存配置，旧新运行独立。"},
    "abstraction":{"action":"updated","reason":"保留原业务 ID，增加提交前权威读、实际 worker/恢复/目录/审批命令映射，并从 AST 生成局部函数参数；业务分组和静态结构/实际事实分开。"},
    "probes":{"action":"updated","reason":"记录真实候选判断、直接关系、检查输入摘要/结果及提交后效果；同 call 合并采集字段，历史帧首个精确边界，不借未来 disposition。仅捕获必要字段，观测故障隔离。"}},
    "excluded_symbols":{s:reasons[s] for s in sorted(unmapped)},"requirement_changes":{},
    "limits":["本地合成演练，不是生产身份系统或通用 ReBAC。","有限真实线程场景，不是全部交错证明；浏览器任务不是真人易用性研究。",
              "LF 格式调整已在验收前记录；固定上游文件保留字节，未改写测试期望。"]}
(ROOT/".stategraph/change-001/review.json").write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
