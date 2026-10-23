# Redacted source reproduction

| Package | Actual isolated execution | Normal gate |
| --- | --- | --- |
| [v1 source](gallery-v1-source.zip) | App and observer initialize; current source binding; JPEG accepted; PNG approval becomes public | Exit 0 |
| [v2 source](gallery-v2-source.zip) | App and observer initialize; current source binding; JPEG rejected with zero rows/messages; PNG approval becomes public | Exit 0 |

Each archive was extracted into a separate work/.validation directory and executed
using the installed local Python 3.12 environment. Both CLI normal gates and actual
application effects were checked. This is actual fresh-source execution, not a
fresh network dependency installation. The complete original v1/v2 validation
reports retain their original root and scope. Raw reproduction argv, paths, exit
codes, stdout and stderr are in review/source-reproduction in the evidence ZIP.

Exact files, sizes and SHA256:
[v1 manifest](gallery-v1-source.zip.manifest.json),
[v2 manifest](gallery-v2-source.zip.manifest.json).
Both contain the same 144 byte-verified candidate-3 Skill files and locked
dependencies. Requirements lock is the actual installed environment snapshot;
JavaScript adapter package-lock.json files are retained. Synthetic PNG/JPEG
images are under work/browser-fixtures. No node_modules, virtual environment,
Git data, runtime database, runtime session/collector token state, personal view
configuration or raw personal-preference payload is included. No frozen Skill
file is changed to redact a runtime secret; runtime private state is excluded.

From a separate extracted directory on Windows:

```powershell
New-Item -ItemType Directory -Force work/tmp | Out-Null
$env:TMP = (Resolve-Path work/tmp).Path
$env:TEMP = $env:TMP
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -B run.py --port 8845 --database work/reproduced.sqlite
```

The launcher prints both actual URLs. Use another free port if needed; the
delivered instance already uses 8842. Demo accounts are documented in README.md.
The extracted source starts with fresh local runtime data. Existing personal
configuration is not required. `test_app.py` runs project tests;
`validate.py` executes the ordinary synchronization gate.

To repeat the old cookie collision independently, the evidence ZIP contains the
byte-verified gallery-core-v2-before-cookie.zip and current probe source/argv.
The bounded before/after records contain statuses and paths, never cookie values.
Historical F06 remains unproven as a specific occurrence of this mechanism.

Final archive app/observer/acceptance/Skill inputs are compared byte for byte
with the already executed isolated extractions. Packaging/report helper snapshots
and ZIP metadata were finalized afterward. No business tests were rerun for
the final documentation correction. See evidence/final-artifact-equivalence.json.
