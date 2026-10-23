# GitHub publication acceptance — v0.6.0

This record supplements the [independent gallery trials](../english-gallery/README.md). It tests publication, installation, clean checkouts and the live bilingual introduction. It does not replace or rewrite earlier trial evidence.

## Publication results

- The [GitHub Pages introduction](https://li-bruce.github.io/SoftwareStatusObserverSkill/) is live. The account's existing custom domain redirects it to `liblog.vip/SoftwareStatusObserverSkill/`; no domain setting was changed.
- English/Chinese switching, retained language preference, mixed graph filters and the matching documentation link were tested on the deployed page. The product animation is illustrative, not connected to a user's application.
- [All four GitHub checks passed](23-ci-matrix-pass.json): Windows/Linux with Python 3.11/3.13 and Node 22. [Run 39952910697](https://github.com/li-bruce/SoftwareStatusObserverSkill/actions/runs/39952910697) validates code commit `4659b624e6cf895c52be21ea8d0eb3d2112262c3` from clean checkouts. Subsequent publication commits add receipts and documentation only.
- The [final local complete suite](26-local-final-suite-pass.log) also exits 0. The exact-byte [GitHub installation](21-published-github-install.json) and [installed project validation](22-published-installed-validation.json) pass.

![Published introduction in English](pages-en.png)
![Published introduction in Chinese](pages-zh.png)

## Failures, fixes and retests

| Finding | Repair | Evidence |
|---|---|---|
| Shared package markers changed bytes during Git checkout; working-directory checks had not exposed it. | Preserve their exact bytes consistently in canonical and installed copies. | [Ubuntu failure](01-ubuntu-clean-checkout-failure.log), [Windows failure](02-windows-clean-checkout-failure.log), [clean-export retest](03-clean-export-package-retest.json). |
| Original historical dialogue contained links to paths on the author's machine. | Preserve the original transcript; require its exact hash and an explicit archived target or external-only annotation. Reject unregistered absolute paths and invalid archive members. | [Ubuntu failure](04-ubuntu-historical-link-failure.log), [Windows failure](05-windows-historical-link-failure.log); six cases in `tests/test_document_links.py`. |
| The runnable example's dependency audit reported advisories. | Update Vue and Vite within their current majors; retain source-parser pins and rerun actual native cases. | Dependency and native-test receipts in this directory; the audit is not a security certification. |
| A deadlock regression tried to read an untracked runtime manifest on a fresh clone. | Read the shipped `.release/manifest.json`; retain the original lock-order assertions. | [Original failure](13-windows-fixture-manifest-failure.log). |
| Linux source analysis failed with `EAGAIN` when the JavaScript scanner synchronously read a nonblocking input pipe. | Consume the input stream to EOF before decoding JSON. Test delayed input, large fragmented UTF-8, truncated/empty JSON and malformed source. | [Initial failure](12-linux-architecture-failure.log), [diagnostic](14-linux-pipe-diagnostic.log); `tools/test_source_pipe.mjs`. |
| The archive example's reviewed working files used CRLF while Git stored five of them as LF. | Align current authored files with their committed LF bytes, then inspect, verify and accept a new candidate. Keep the previous accepted candidate unchanged. | [Windows failure](15-windows-archive-baseline-failure.log), [exact differences](16-archive-export-difference.json). |

No mapping, business, state or project assertion was removed to obtain a pass. The final acceptance remains tied to exact source and tool identities; missing evidence remains a failure.

## Review the records

Numbered JSON files contain command receipts and exact identities. Raw logs preserve failures as failures. `17-example-acceptance.json` records the new delivery/archive candidates and four separate reports. Both canonical and copied command entrypoints must accept the same candidate.

Installation is tested in an isolated project folder using the official Skill installer against GitHub. It does not overwrite the maintainer's globally installed Skill. The [published installation receipt](21-published-github-install.json) verifies all 144 Skill files against commit `4659b624e6cf895c52be21ea8d0eb3d2112262c3`. The [installed CLI result](22-published-installed-validation.json) validates the actual multilingual declaration, source inventory and mapping after independently installing parser dependencies. It uses the existing Python environment; this is not a fresh Python installation. Earlier installation receipts identify their own earlier commits and remain unchanged.

The [staged-input comparison](20-staged-input-byte-check.json) covers 404 accepted project inputs and shipped adapter files, with no byte differences. [Linux output](24-linux-full-suite-pass.log) and [Windows output](25-windows-full-suite-pass.log) include the real fragmented-input regression and complete repository verification. Original timestamped logs retain their whitespace; formatting checks apply to authored changes without rewriting these records.

## Commit record

| Commit | Purpose |
|---|---|
| `5a51ae9` | Publish the native/shared-service refactor, English maintenance, bilingual introduction and independent trials. |
| `1b1dc81` | Preserve shared runtime package bytes in clean Git checkouts. |
| `bafa95e` | Validate portable historical references and update the example's Vue/Vite dependencies. |
| `5ba0aa0` | Make clean-checkout regression fixtures self-contained and retain underlying command diagnostics. |
| `4659b62` | Fix fragmented parser input, add its regression and freeze new portable example acceptance with preserved evidence. |

## 中文说明

本目录补充 GitHub 发布验收，保留云端失败、具体修复和复测记录。原有试用对话与历史证据不改写；映射、状态约束、业务规则和项目测试仍分别验收。

最终 Windows／Linux 与 Python 3.11／3.13 四组云端完整检查均通过，本地完整复测也通过。从 GitHub 新下载的 144 个 Skill 文件与发布提交完全一致，使用该副本校验实际多语言项目成功。

介绍页已发布，支持中英文切换并记住选择。GitHub Pages 会沿用账号已有域名并自动跳转。真实测试请按 [版本说明](../../releases/v0.6.0.md) 安装完整 Skill，在目标项目新建对话使用 `$business-observer`。
