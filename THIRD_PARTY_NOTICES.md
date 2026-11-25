# Third-Party Notices — P032 AcceptTwin (T012)

AcceptTwin's own code is MIT (see `LICENSE`). The project has **zero
runtime dependencies** (`pyproject.toml`: `dependencies = []`); the
entries below are development / build-time dependencies only, each
retaining its original license.

| Dependency | Version | License | Used for |
| --- | --- | --- | --- |
| pytest | 9.2.0 | MIT | test runner (`[project.optional-dependencies] dev`) |
| iniconfig | 2.3.1 | MIT | pytest transitive dependency |
| packaging | 26.4 | Apache-2.0 OR BSD-2-Clause | pytest transitive dependency |
| pluggy | (as installed with pytest 9.2.0) | MIT | pytest transitive dependency |
| Pygments | 2.21.0 | BSD-2-Clause | pytest transitive dependency |
| TypeScript | 5.9.3 | Apache-2.0 | `report-ui` build (`report-ui/package-lock.json` frozen; full license text at `report-ui/node_modules/typescript/LICENSE.txt`) |

License expressions above were read from the installed distributions'
metadata (`METADATA` `License-Expression` / `License` fields) and from
`report-ui/node_modules/typescript/package.json` on 2026-11-24. No other
third-party code is bundled: the Oracle and the report UI are project
sources, and no CDN, webfont, or remote asset is loaded at runtime
(verified by `tests/privacy/test_html_self_contained.py` and by the
`benchmark` HTML scan: 49 pages, 0 violations).

Node.js itself (24.22.1, MIT-licensed) is a runtime prerequisite for
the Oracle and for `npm run build`, not a bundled dependency.
