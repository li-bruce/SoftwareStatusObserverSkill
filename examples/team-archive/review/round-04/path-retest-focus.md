# 当前关注的业务与实现

模型版本：discovery-r03
局部图：`focus:a12fa4939e9312593ce0`

```mermaid
flowchart LR
  n0["审批是否适用"]
  n1["撤销审批"]
  n2["项目 · 操作人 · 资料 · 版本"]
  n3["保存资料版本快照"]
  n4["修改资料内容"]
  n5["点击继续并重查资格"]
  n0 -->|"任一审批有效，提交时仍需适用"| n3
  n4 -->|"新版本不能沿用旧审批"| n0
  n1 -->|"撤销后重新判断全部候选"| n0
  n2 -->|"四个目标字段全部匹配"| n0
  n5 -->|"手动继续时重查"| n0
  b0["内容检查（范围外）"]
  b0 -.->|"内容检查通过"| n3
  b1["资料条目与内容版本（范围外）"]
  n4 -.->|"修改内容"| b1
  b2["运行身份与内容版本（范围外）"]
  n4 -.->|"旧运行保留；新版本另开"| b2
  b3["索引检查（范围外）"]
  b3 -.->|"索引检查通过"| n3
  b4["是否直接负责所在文件夹（范围外）"]
  n5 -.->|"重新检查资格"| b4
  b5["运行身份与内容版本（范围外）"]
  b5 -.->|"旧版本运行不能提交"| n3
  b6["是否直接负责所在文件夹（范围外）"]
  b6 -.->|"仅所在文件夹直接负责人"| n3
  b7["该资料版本是否已有归档（范围外）"]
  b7 -.->|"相同资料版本不重复建档"| n3
```

虚线保留范围外的原关系，不表示已经执行或获得许可。

| 节点 | 类型 | 源码 |
|---|---|---|
| 审批是否适用 | decision |   |
| 撤销审批 | action |   |
| 项目 · 操作人 · 资料 · 版本 | data |   |
| 保存资料版本快照 | effect |   |
| 修改资料内容 | action |   |
| 点击继续并重查资格 | action |   |

范围外或未显示的关系：8；未解析项：5；运行证据：not_selected。

| 未展开关系 | 类型 | 作用 |
|---|---|---|
| content_check → archive_commit | guard | 内容检查通过 |
| content_changed → document | data | 修改内容 |
| content_changed → run_identity | data | 旧运行保留；新版本另开 |
| index_check → archive_commit | guard | 索引检查通过 |
| resume_run → scope_check | flow | 重新检查资格 |
| run_identity → archive_commit | guard | 旧版本运行不能提交 |
| scope_check → archive_commit | guard | 仅所在文件夹直接负责人 |
| archive_unique → archive_commit | guard | 相同资料版本不重复建档 |
