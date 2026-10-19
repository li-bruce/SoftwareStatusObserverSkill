# Third-party components

The project's original code and documentation use the MIT license. Third-party
components keep their own copyright notices and licenses.

| Component | Version | License | Distribution |
|---|---|---|---|
| [PixiJS](https://github.com/pixijs/pixijs/tree/v8.22.0) | 8.22.0 | MIT | Browser bundle included with the Skill and example |
| [ELK.js](https://github.com/kieler/elkjs) | 0.12.0 | EPL-2.0 | Unmodified browser bundle and worker from the npm release; license retained as `ELK-LICENSE.md` |
| [transitions](https://github.com/pytransitions/transitions/tree/0.9.3) | 0.9.3 | MIT | Installed by pip; not vendored |
| [six](https://github.com/benjaminp/six/tree/1.17.0) | 1.17.0 | MIT | Installed by pip; not vendored |

PixiJS license text is retained next to each `pixi.min.js` bundle as
`PIXI-LICENSE.txt`. The installed Python distributions include their license
texts. Python's standard library supplies SQLite and the local HTTP server.
There is no npm install step, graph database, cloud service or model API key
required to run the example.

ELK.js supplies the layered and stress algorithms. Its source and build instructions
are available in the [upstream project](https://github.com/kieler/elkjs) and its
[0.12.0 npm source package](https://registry.npmjs.org/elkjs/-/elkjs-0.12.0.tgz).
The yWorks documentation informed the incremental interaction design; no yFiles
code is included and this project does not claim to implement yFiles algorithms.
