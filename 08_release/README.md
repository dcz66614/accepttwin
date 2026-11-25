# AcceptTwin v1.0.1 — Release Package (P032)

**Status: READY_FOR_FINAL_REVIEW — not yet ACCEPTED.** T014
(construction + release evidence) is complete; GPT final review R1
returned FAIL and FIX-R1 closed all 3 P1 + 4 P2 (see
`RELEASE_NOTES.md`); R2 is pending. The project becomes ACCEPTED
only when ChatGPT gives an explicit `FINAL_VERDICT: PASS` in the
establishment conversation. Do not treat this release as finally
approved.

## What this is

AcceptTwin verifies that the same URL serving HTML to browsers and
Markdown to AI agents never mixes the two up through a shared
cache: dual-representation contract, cold baselines for both
representations, both warm-cache orders, dual cache evidence,
first-error attribution, and an independent TypeScript Oracle.
Local, synthetic, loopback-only; it proves nothing about real CDNs
(see the honest-boundary clause in `00_control/ADR-006.md` inside
`source.zip`, and `docs/LIMITATIONS.md`).

## Contents of `08_release/`

| File | What it is |
| --- | --- |
| `source.zip` | The frozen source package: production code, Oracle, schemas, 48 Golden fixtures, tests, specs (md + docx), ADRs, docs, MIT LICENSE. Built by `git archive` from commit `221f902` (tag `P032-v1.0.1`). 165 files. Excludes `.venv`, `node_modules`, `evidence/` (regenerated artifacts, Drive-archived separately), and `00_control/competitive_gate/`. |
| `RELEASE_MANIFEST.json` | Release identity: commit, tag, per-file SHA-256 for all 165 zip files (with roles, cross-checked 165/165 against `git show P032-v1.0.1:<path>`), hashes of the 48 report JSON samples + 49 HTML pages, gate results, all 16 T013 findings with dispositions, FIX-R1 (R1 FAIL → all P1/P2 fixed), T001 gate evidence, remaining P2 list. |
| `SHA256SUMS.txt` | Top-level hashes (`source.zip`, `RELEASE_MANIFEST.json`). Verify from inside `08_release/`: `sha256sum -c SHA256SUMS.txt`. Per-file hashes live in the manifest. |
| `RELEASE_NOTES.md` | What changed in T014, gate results, known limitations. |
| `HOW_TO_REPRODUCE.md` | Rebuild, re-verify, and unpack-verify this release from scratch. |
| `LICENSE`, `THIRD_PARTY_NOTICES.md` | MIT license and third-party notices (copies of the files in `source.zip`). |

## Quick verification

```bash
cd 08_release
sha256sum -c SHA256SUMS.txt        # must say OK for both lines
python3 -m zipfile -t source.zip   # must say "Test of source.zip OK"
```

Then follow `HOW_TO_REPRODUCE.md` for the full unpack + re-test
verification (T014-H).

## Gate results (T014-D, clean worktree, fresh venv + `npm ci`)

- `pytest`: **1026 passed, 0 failed**
- `verify --suite s0`: PASS — 24/24 golden, parity 24/24, C11 bleed 3/3, repeat-100 distinct hash = 1
- `verify --suite all`: PASS — ALL48 48/48 golden, parity 48/48
- `benchmark --suite all`: PASS — max single-scenario 0.0408s, repeat-100 distinct = 1, schema 48/48, HTML 49 pages clean
- Offline verification: PASS
- `npm run build`: exit 0, `report-ui.js` byte-identical to the committed file

## Known limitations (see `RELEASE_NOTES.md` for the full list)

- T013-F01 port-swap contract-hash collision: **accepted by design**
  (§10.4 forces it; see ADR-007). No verdict impact.
- §4.1 CLI commands: **implemented in FIX-R1** (`run`, `demo`,
  `verify --report`, report preview/export/delete, `clean`,
  `contract delete`); ADR-008 supersedes the ADR-005 deferral.
- D-01, D-04–D-08: spec-verification annotations, recorded, no action.
