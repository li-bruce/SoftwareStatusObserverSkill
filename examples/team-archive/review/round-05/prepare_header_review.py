import json
from pathlib import Path

ROOT=Path(__file__).absolute().parents[2]
folder=ROOT/".stategraph/change-004"
impact=json.loads((folder/"impact.json").read_text(encoding="utf-8"))
assert not impact["errors"] and not impact["unmapped_changed_symbols"]
review={"candidate_id":impact["candidate_id"],"decisions":{
    "business":{"action":"unchanged","reason":"只修复 R16 当前值和历史判断的表达；大小阈值、提交、审批、等待、继续和快照语义不变。63 条独立业务预期全部保持。"},
    "state_machine":{"action":"unchanged","reason":"只改图形呈现与回归测试，实际生命周期/资源/汇合/事务代码未改。"},
    "abstraction":{"action":"updated","reason":"当前页面顶部取权威项目配置；历史场景显示保存时上限；历史帧没有记录时不借用未来参数。大小节点保留实际历史判断值并标记配置变化，稳定节点及布局身份不变。"},
    "probes":{"action":"unchanged","reason":"继续使用原实际读取、判断和版本依据；不补造完成运行的新判断事件。"}},
    "excluded_symbols":{},"requirement_changes":{},
    "failure_evidence":["review/v2/before-fix-stale-limit-header.png","review/v2/before-fix-stale-limit-header.ax.txt"]}
(folder/"review.json").write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
print(json.dumps({"candidate":impact["candidate_id"],"reviewed":True}))
