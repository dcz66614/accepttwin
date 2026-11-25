# How to Reproduce AcceptTwin v1.0.1 (P032, FIX-R1 refreeze)

This file reproduces the release from the frozen source, and
reproduces the T014-H independent unpack verification. All
commands assume a Linux/macOS machine with Python 3.12 and
Node ≥ 24.

## 1. Get the frozen source

```bash
# Option A — from the release package:
python3 -m zipfile -t 08_release/source.zip   # must say "Test of source.zip OK"
mkdir -p /tmp/accepttwin-verify && cd /tmp/accepttwin-verify
unzip /path/to/08_release/source.zip
cd accepttwin-1.0.1

# Option B — from git (same content, same commit):
git clone <repo> accepttwin && cd accepttwin
git checkout 221f902798a245b7a2672f3a53a9a63ab176e014   # tag P032-v1.0.1
git status --short   # must be empty
```

## 2. Verify the package hashes (T014-G)

From inside `08_release/`:

```bash
sha256sum -c SHA256SUMS.txt
# source.zip: OK
# RELEASE_MANIFEST.json: OK
```

Per-file hashes for the 165 files inside `source.zip` are in
`RELEASE_MANIFEST.json` under `files[]` (each entry: in-zip
`path`, `sha256`, `size_bytes`, `role`). After unpacking, verify
every extracted file against the manifest, e.g.:

```bash
python3 - << 'EOF'
import hashlib, json, zipfile
from pathlib import Path
man = json.loads(Path("08_release/RELEASE_MANIFEST.json").read_text())
root = Path("/tmp/accepttwin-verify/accepttwin-1.0.1")
bad = []
for f in man["files"]:
    p = root / f["path"].removeprefix("accepttwin-1.0.1/")
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != f["sha256"] or p.stat().st_size != f["size_bytes"]:
        bad.append(f["path"])
print("files checked:", len(man["files"]), "mismatches:", bad)
# also check the zip itself:
z = hashlib.sha256(Path("08_release/source.zip").read_bytes()).hexdigest()
assert z == man["source_zip"]["sha256"], "source.zip hash mismatch"
assert man["git_commit"] == "221f902798a245b7a2672f3a53a9a63ab176e014"
print("source.zip hash OK, commit OK")
EOF
```

Expected: 165 files checked, 0 mismatches. The 48 report JSON
samples and 49 HTML pages are hashed in the manifest under
`samples` (repo paths `evidence/Reports/...` at the freeze
commit); they are **not** inside `source.zip` — they are
Drive-archived evidence, verified separately in T014-I.

## 3. Rebuild the environment

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e . "pytest==9.2.0"
.venv/bin/python -m accepttwin --version   # accepttwin 1.0.0
```

Report UI (clean checkout rebuild path, T013-F03 — two ways):

```bash
# (a) with registry access (verified in T014-D):
cd report-ui && npm ci && npm run build   # tsc 5.9.3, exit 0
# (b) offline: reuse an installed node_modules/ with pinned tsc 5.9.3,
# then npm run build. The rebuilt report-ui.js must be byte-identical
# to the committed file:
sha256sum report-ui.js
# 784e3106f7a380845559690dfa04aa4f8549f0d044bf5edea66ee2aefec9c84d
```

## 4. Re-run the full gate (FIX-R1 refreeze)

```bash
.venv/bin/python -m pytest -q
# expected: 1026 passed, 0 failed, 0 skipped

.venv/bin/python -m accepttwin verify --suite s0
# expected: S0_STATUS: PASS (24/24 golden, parity 24/24),
# C11 bleed 3/3, repeat-100 distinct_hashes=1,
# C01 report hash 67e69e68e128441b67fae155ac1af8dbb4e7992b4dfe70db7dcef1f04e62acde

.venv/bin/python -m accepttwin verify --suite all
# expected: VERIFY_STATUS: PASS (ALL48 48/48 golden, parity 48/48;
# S0 24/24 golden, parity 24/24, repeat-100 distinct_hashes=1)

.venv/bin/python -m accepttwin benchmark --suite all
# expected: BENCHMARK_STATUS: PASS (max single-scenario < 1s,
# repeat-100 distinct=1, schema 48/48, HTML 49 pages clean)

bash evidence/Performance/offline_verify.sh
# expected: OFFLINE_VERIFY: PASS
```

Notes:

- `verify` / `benchmark` rewrite derived files under `evidence/`
  (recorded results, summaries, HTML). After a re-run, restore
  the committed state with `git checkout -- evidence/` and
  confirm `git status --short` is empty — or, when re-running
  inside an unpacked copy, compare the regenerated summaries
  instead: verdicts, parities, and all 48 report hashes must be
  identical to the frozen ones (only ephemeral ports, port-derived
  cache keys, and durations change).
- Single-scenario time must stay under 1 second; repeat-100 must
  yield exactly one distinct normalised hash.

## 5. FIX-R1 unpack verification (T014-H procedure, re-run at the v1.0.1 freeze)

1. New temporary directory `/tmp/t014-unpack/` (fresh, not the
   worktree, not the repo).
2. `python3 -m zipfile -t source.zip` → OK; extracted.
3. File count: 165 files (+ 26 directory entries), structure
   checked (src/, oracle/, schemas/, tests/, fixtures/ with
   s0 C01–C24 + extended E01–E24, contracts/, scripts/,
   report-ui/, 01_project_book/, 02_implementation_plan/,
   00_control/ADR-001–009, docs/, README.md, LICENSE,
   THIRD_PARTY_NOTICES.md, pyproject.toml).
4. Every extracted file's SHA-256 + size checked against
   `RELEASE_MANIFEST.json` `files[]` (procedure in §2 above).
5. Dependency lock files checked: `report-ui/package-lock.json`
   (TypeScript 5.9.3 pinned); Python `pyproject.toml`
   (`dependencies = []`, dev `pytest==9.2.0`); Oracle
   `oracle/package.json` declares no dependencies.
6. LICENSE is MIT; THIRD_PARTY_NOTICES.md present.
7. Fresh venv built from the unpacked content; full pytest +
   `verify --suite s0` re-run; results compared with the frozen
gate (1026 passed; S0 24/24; C01 hash `67e69e68…`).
8. Result: manifest `files[]` was built from the zip bytes and cross-checked 165/165 against `git show P032-v1.0.1:<path>` (builder `/tmp/p032_freeze/build_manifest.py`); `sha256sum -c SHA256SUMS.txt` passes. See the FIX-R1 refreeze report to the parent agent.

## 6. T014-C independent probe re-verification (summary)

Each fix was re-checked with a probe independent of the fix's
own tests (25 checks, all PASS; script
`~/workspace/t014-scratch/t014c_check.py`, log
`~/workspace/t014-scratch/t014c_checks.log`):

- F01: swap still collides (accepted, ADR-007) + `contract.py`
  production code unchanged + pinning test passes.
- F-01/F04: both read sites retain exactly `limit + 1` bytes
  (1048577, not 2 MiB); no `resp.read()` remains in either site.
- T008 P2-2: 10/10 revalidation forms (production) + 15/15
  (Oracle mirror).
- T003: q=0 → 406 and q-tie probes 10/10.
- F02: state-disagreement and missing-field parity tests pass.
- F05: no Oracle code reads production `verified_cache_state`.
- T006 P3, T012 P2-1/P2-2, T011 P2 (script refuses files outside
  `evidence/`, exit 2; still deletes inside it), T010 P2-1/P2-2,
  T013-F03 (rebuild path documented; `npm run build` exit 0,
  committed `report-ui.js` unchanged), ADR-005/006/007 present
  and cited, LIMITATIONS residual table has no OPEN items.
