"""Review this dynamic-limit change after inspect; preserve independent expectations."""
import json
from pathlib import Path

ROOT=Path(__file__).absolute().parents[2]
impact=json.loads((ROOT/".stategraph/change-003/impact.json").read_text(encoding="utf-8"))
reasons={}
def classify(path,symbols,reason):
    for symbol in symbols.split():
        reasons[path+"::"+symbol]=reason

classify("archive_app/service.py","ArchiveService",
         "服务容器包含新增的项目上限命令。该命令、实际读取和大小判断分别映射 set_size_limit/project_limit/size_guard；类整体不单独作为业务动作。")
classify("archive_app/storage.py","ArchiveStore ArchiveStore.__init__ ArchiveStore.seed",
         "新增项目上限和配置修订号的幂等迁移，种子采用明确列名保留旧行。迁移及重启持久化测试覆盖旧表；closing 显式关闭连接修复 Windows 文件锁，未改变原有记录和快照语义。")
classify("integrations/bo_server.py",
         "LocalApplication LocalApplication.__init__ LocalApplication.cases LocalApplication.command LocalApplication.graph_view LocalApplication.version_sources",
         "本地演练的适配层：大小命令仍由核心事务执行；当前场景与首版冻结模型、源码、意图及运行记录分开加载，按所选版本验证绑定。只读版本测试防止旧图指向新源码。")
classify("integrations/bo_server.py","serve serve.Handler serve.Handler.do_GET",
         "回环 HTTP 适配器按版本提供已加载源码和场景清单。首版文件来自冻结清单，不依赖任意客户端路径；业务限制由核心执行。")
unmapped=set(impact["unmapped_changed_symbols"])
if unmapped-set(reasons):
    raise RuntimeError(sorted(unmapped-set(reasons)))
review={"candidate_id":impact["candidate_id"],"decisions":{
    "business":{"action":"updated","reason":"按 U05/U06 与直接用户回答实现 R14-R16：每项目正整数上限，默认 8192 字节、UTF-8 正文、包含等值边界；运行中超限等待、自然收尾、手动继续复用同版本结果。原 41 项预期未改。"},
    "state_machine":{"action":"unchanged","reason":"沿用原 transitions 生命周期及运行独享资源/汇合。size_allowed 作为同一个权威资格 allowed 的新增合取条件；复用既有 waiting/resume_required 和提交事务，不引入另一套状态。"},
    "abstraction":{"action":"updated","reason":"保留原业务 ID、项目与布局 ID；增加 project_limit/size_guard/set_size_limit 和当前大小参数，更新提交判断；局部 AST 自动反映新增函数调用。冻结 v1 与当前 v2 可切换比较。"},
    "probes":{"action":"updated","reason":"同一事务记录项目上限读取、UTF-8 字节数、配置修订、实际允许/超限量；提交事件仍只在效果保存后。上限/判断参数随 epoch 变化变为历史；历史帧不借最终资格。"}},
    "excluded_symbols":{s:reasons[s] for s in sorted(unmapped)},
    "requirement_changes":{},
    "limits":["本地合成数据，未加入生产身份和配置权限系统。",
              "有限线程场景及 agent 浏览器任务，不代表全部并发交错或真人易用性证明。",
              "首版文件和压缩包未改写；为只读完整绑定，在其 source-snapshot 补入同一冻结版 intent.json。"]}
(ROOT/".stategraph/change-003/review.json").write_text(
    json.dumps(review,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
print(json.dumps({"reviewed_candidate":impact["candidate_id"],"excluded":len(unmapped)}))
