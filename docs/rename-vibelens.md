# Business Observer is now VibeLens

VibeLens helps developers understand and debug AI-built software through state
graphs. The new Skill name is `vibelens`; invoke it with `$vibelens`.

| Item | New location |
| --- | --- |
| Repository | [li-bruce/VibeLens](https://github.com/li-bruce/VibeLens) |
| Skill | [`skills/vibelens`](../skills/vibelens/SKILL.md) |
| Introduction | [GitHub Pages](https://li-bruce.github.io/VibeLens/) |
| Project installation | `.agents/skills/vibelens` |

## Existing Git checkouts

GitHub redirects Git operations from the old repository name. Updating the remote
makes the configured location clear:

```bash
git remote set-url origin https://github.com/li-bruce/VibeLens.git
```

The local folder can retain its existing name. The Pages URL changes to
`https://li-bruce.github.io/VibeLens/`; GitHub does not provide the same automatic
redirect for project-site URLs. See [GitHub's rename documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).

## Existing Skill installations

Old installations continue to work with their installed files. To switch a project
to the new name, run this from the updated VibeLens checkout:

```bash
python tools/install_skill.py --project /path/to/your-project --migrate-legacy
```

For a global Codex installation:

```bash
python tools/install_skill.py --skills-dir ~/.codex/skills --migrate-legacy
```

The installer stages the complete new Skill first. It moves the entire old
`business-observer` directory, including local changes, to the sibling
`skill-backups/business-observer-TIMESTAMP-ID` folder and installs `vibelens`.
It restores the previous directory if the final installation move fails. An
existing `vibelens` directory is preserved and reported instead of overwritten.
Review any personal instruction changes in the backup before applying them to
the new installation. Start a new conversation to discover `$vibelens`.

Project runtime modules, application logic, recorded events and personal graph
settings are outside this migration. Internal `bo_` / `BO` names, JSON protocol
identifiers and `business-observer.layout.v2:` storage keys remain stable.
Application runtime upgrades continue to use the existing verified upgrade flow.

Version `v0.7.0` retains the previous name and folder. Original transcript JSON,
logs, screenshots and archived applications are retained. Source-navigation links
in rendered historical reports are pinned to the old paths in that fixed version.

## 中文速览

新名称是 **VibeLens**，新对话使用 `$vibelens`。当前本地文件夹可以保持原名；
其他机器的 Git 副本可以运行上面的 `git remote set-url` 命令更新地址。
旧 Git 地址仍会重定向，介绍页请使用新的 `/VibeLens/` 地址。

已有 Skill 使用 `--migrate-legacy` 显式迁移，旧目录完整保存在备份中。
项目的业务代码、状态网、运行模块、录制与个人布局由原有机制维护。
