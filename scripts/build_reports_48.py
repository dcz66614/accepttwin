"""Build the 48 formal ``accepttwin.report/v1`` samples (P032 T009).

Reads the real recorded results of the 48 Golden scenarios under
``evidence/Golden/<sid>/`` — the frozen contract, the raw
observations, the production classification and the independent
Oracle result — and builds one formal report per scenario with
:func:`accepttwin.report_builder.build_report`. Nothing here
re-runs an experiment or invents evidence: the samples are the
recorded outcomes, re-expressed in the formal report format.

Each sample is then checked with the *independent* Schema
validator (``tests/unit/independent_schema_validator.py``), which
reads only the Schema file and shares no code with the generator.
The run fails (exit code 1) unless all 48 samples validate, every
sample's verdict matches the recorded production verdict, and
every sample's Oracle parity holds.

Outputs (``evidence/Reports/``):

* ``<sid>.json`` — one formal report per scenario (C01–C24, E01–E24);
* ``REPORTS_SUMMARY.json`` — per-scenario verdict / parity / hash
  plus the 48/48 counts;
* ``T009_NOTES.md`` is maintained by hand, not by this script.

Usage: ``.venv/bin/python scripts/build_reports_48.py`` (run from
the repository root; ``src`` is added to ``sys.path`` here).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "unit"))

from accepttwin.report_builder import build_report  # noqa: E402
from independent_schema_validator import validate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "evidence" / "Golden"
REPORTS_DIR = ROOT / "evidence" / "Reports"

SCENARIO_IDS: tuple[str, ...] = tuple(
    [f"C{i:02d}" for i in range(1, 25)] + [f"E{i:02d}" for i in range(1, 25)]
)

#: RawObservation keys projected onto the frozen §5.5 observation.
#: ``verified_cache_state`` is the dual-evidence state (None on the
#: two direct-origin baselines, ADR-001); the raw header claim is
#: never used as the verified state.
_OBSERVATION_KEYS = (
    "request_index",
    "experiment_id",
    "requested_representation",
    "response_status",
    "response_content_type",
    "body_sha256",
    "sentinel_match",
    "cache_key_sha256",
    "cache_entry_id",
    "origin_counter_delta",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _observations_from_raw(raw_path: Path) -> list[dict]:
    raw = _load_json(raw_path)
    observations = []
    for record in raw["observations"]:
        obs = {key: record.get(key) for key in _OBSERVATION_KEYS}
        obs["cache_status"] = record.get("verified_cache_state")
        observations.append(obs)
    return observations


def build_all() -> dict:
    """Build and independently validate all 48 report samples."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    samples: dict[str, dict] = {}
    for sid in SCENARIO_IDS:
        sdir = GOLDEN_DIR / sid
        contract = _load_json(sdir / "contract.json")
        observations = _observations_from_raw(sdir / "raw-observations.json")
        production = _load_json(sdir / "production.json")
        oracle = _load_json(sdir / "oracle.json")
        expected = _load_json(sdir / "scenario.json")
        report = build_report(
            contract,
            production,
            oracle,
            observations=observations,
            scenario_id=sid,
        )
        errors = validate(report)
        verdict_ok = report["verdict"] == expected["verdict"] == production["verdict"]
        parity_ok = report["oracle_parity"] is True and report["final"] is True
        samples[sid] = {
            "scenario_id": sid,
            "verdict": report["verdict"],
            "expected_verdict": expected["verdict"],
            "verdict_matches_record": verdict_ok,
            "first_error": report["first_error"],
            "oracle_parity": report["oracle_parity"],
            "final": report["final"],
            "report_hash": report["report_hash"],
            "schema_errors": errors,
            "schema_valid": not errors,
        }
        out_path = REPORTS_DIR / f"{sid}.json"
        out_path.write_text(
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        status = (
            "OK"
            if (not errors and verdict_ok and parity_ok)
            else "FAIL"
        )
        print(
            f"{sid}: {status} verdict={report['verdict']} "
            f"parity={report['oracle_parity']} "
            f"hash={report['report_hash'][:12]}"
            + (f" errors={errors}" if errors else "")
        )
    valid = sum(1 for s in samples.values() if s["schema_valid"])
    matching = sum(1 for s in samples.values() if s["verdict_matches_record"])
    parity = sum(1 for s in samples.values() if s["oracle_parity"] is True)
    summary = {
        "generator": "scripts/build_reports_48.py (P032 T009)",
        "source": "evidence/Golden/<sid>/ recorded results (contract, raw-observations, production, oracle)",
        "REPORTS_STATUS": (
            "PASS"
            if valid == 48 and matching == 48 and parity == 48
            else "FAIL"
        ),
        "SCHEMA_VALID": f"{valid}/48",
        "VERDICT_MATCHES_RECORD": f"{matching}/48",
        "ORACLE_PARITY": f"{parity}/48",
        "samples": samples,
    }
    (REPORTS_DIR / "REPORTS_SUMMARY.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"REPORTS_STATUS: {summary['REPORTS_STATUS']} "
        f"(schema {valid}/48, verdict {matching}/48, parity {parity}/48)"
    )
    return summary


if __name__ == "__main__":
    summary = build_all()
    sys.exit(0 if summary["REPORTS_STATUS"] == "PASS" else 1)
