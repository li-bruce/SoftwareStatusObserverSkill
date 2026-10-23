# Third-party components

The project's original code and documentation use the MIT license. Third-party
components keep their own copyright notices and licenses.

The optional database feature installs SQLAlchemy (MIT), pg8000 (BSD-3-Clause),
PyMongo (Apache-2.0), redis-py (MIT), the Neo4j Python driver (Apache-2.0 AND Python-2.0), SQLGlot
(MIT), and Pygments (BSD-2-Clause). Versions are pinned in
[requirements-database.txt](skills/business-observer/requirements-database.txt).
Native acceptance uses pg, Mongoose and redis (MIT), mongodb and neo4j-driver
(Apache-2.0), with versions and transitive dependencies in
[the native lockfile](tools/database-native/package-lock.json). These packages
are installed rather than vendored; their distributions retain license notices.

The optional Compose acceptance fixture downloads database server images under
their own licenses. In particular, MongoDB Community uses SSPL; it is not
represented here as an OSI-approved open-source license. Server images are test
dependencies, not bundled with the Skill.

| Component | Version | License | Distribution |
|---|---|---|---|
| [PixiJS](https://github.com/pixijs/pixijs/tree/v8.22.0) | 8.22.0 | MIT | Browser bundle included with the Skill and example |
| [ELK.js](https://github.com/kieler/elkjs) | 0.12.0 | EPL-2.0 | Unmodified browser bundle and worker from the npm release; license retained as `ELK-LICENSE.md` |
| [transitions](https://github.com/pytransitions/transitions/tree/0.9.3) | 0.9.3 | MIT | Installed by pip; not vendored |
| [six](https://github.com/benjaminp/six/tree/1.17.0) | 1.17.0 | MIT | Installed by pip; not vendored |

| [jsonschema](https://github.com/python-jsonschema/jsonschema) | 4.25.1 | MIT | Installed by pip for protocol validation |
| [TypeScript](https://github.com/microsoft/TypeScript) | 5.9.3 | Apache-2.0 | Locked npm source parser; not vendored |
| [Vue / compiler-sfc](https://github.com/vuejs/core) | 3.5.22 | MIT | Locked parser and example dependencies |
| [React / React DOM](https://github.com/facebook/react) | 19.2.0 | MIT | Example dependencies |
| [Vite](https://github.com/vitejs/vite) | 7.1.12 | MIT | Example development and build tool |
| [jsdom](https://github.com/jsdom/jsdom) | 26.1.0 | MIT | Real component / DOM handler tests |

PixiJS license text is retained next to each `pixi.min.js` bundle as
`PIXI-LICENSE.txt`. The installed Python distributions include their license
texts. Python's standard library supplies SQLite and the local HTTP server.
The JS/TS/SFC parser and frontend example use locked npm dependencies. No graph database, cloud service or model API key is required.

ELK.js supplies the layered and stress algorithms. Its source and build instructions
are available in the [upstream project](https://github.com/kieler/elkjs) and its
[0.12.0 npm source package](https://registry.npmjs.org/elkjs/-/elkjs-0.12.0.tgz).
The yWorks documentation informed the incremental interaction design; no yFiles
code is included and this project does not claim to implement yFiles algorithms.

The active viewer's `viewer.js`, `graph-core.js`, `layout.js` and `viewer.css` are
original project code under MIT. There is no proprietary styling library or remote
font dependency. `tools/check_package.py` checks the reviewed browser bundle hashes,
license files and script entrypoints so a dependency change requires another review.
