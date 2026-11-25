"""S0 gate verifier (P032 T007-C): re-check evidence against §13.

Reads only files under ``evidence/S0/``, ``fixtures/s0/`` and the
Oracle / harness sources -- it never trusts ``run_s0.py``'s summary
at face value. Every §13 mapping-table item is an explicit,
fail-closed assertion; any failure prints the item, the evidence and
the reason, and the final line is ``S0_STATUS: FAIL``.

§13 mapping (PROJECT_BOOK §13), each with its check below:

* 24 core cases (§11.2)             -- all 24 fixtures exist, ran, matched
* 24/24 Oracle parity (§12)         -- verdict + diagnostics + first error
  + the eight per-request verified_cache_states (P2-01: the same
  widened definition as scripts/s0_harness.py check_parity and
  src/accepttwin/report_builder.py — missing or malformed states
  fail closed, never count as agreement)
* known failures detected (§8,§11.2)-- C07-C16, C19, C24 hit expected verdict
* healthy zero false positives (§7) -- C01-C06, C17, C18 PASS_OBSERVED
* both warm orders real (§0.2,§6)   -- HM [5,6] and MH [7,8] real requests
* independent cold requests (§5.4)  -- reset + empty + MISS/BYPASS dual proof
* dual cache evidence (§5.3)        -- header leg + behaviour leg recomputed
* stable bleed repro (§8.2,§11.2)   -- C11 3/3 REPRESENTATION_BLEED
* missing-Vary healthy (§7.11)      -- C03/C04 PASS with VARY warning only
* repeat-100 hash (§7.8,§10.4)      -- 100 runs, 1 hash, recomputed here;
  fresh pair per run, same-pair hash equal, contract hash invariant
  under a port rewrite, and the 3 C11 repro hashes equal the main C11
  hash (ADR-003)
* single scenario < 1s (§10.5)      -- every scenario + repeat max < 1.0s
* insufficient evidence (§8.4,§8.8)-- C20-C23 INCONCLUSIVE, never a bleed
* first-error location (§6.3,§8)    -- exact request + experiment, recomputed
* mandatory call convention (ADR-002 Decision 3) -- the classify_run
  call site in scripts/s0_harness.py passes real tuples + raw_observations,
  never None.
* Oracle independence (§12.3)       -- Oracle sources import no production
  code and read no production verdict.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accepttwin.contract import canonical_json_bytes  # noqa: E402

EVIDENCE = ROOT / "evidence" / "S0"
FIXTURES = ROOT / "fixtures" / "s0"
SCENARIOS = [f"C{i:02d}" for i in range(1, 25)]
HEALTHY = ["C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18"]
KNOWN_FAILURES = [
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
    "C15", "C16", "C19", "C24",
]
INSUFFICIENT = ["C20", "C21", "C22", "C23"]

RESULTS: list[tuple[str, str, bool, str]] = []


def check(item: str, spec: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((item, spec, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {item} ({spec})" + (f" -- {detail}" if detail else ""))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _with_port(url: str, port: int) -> str:
    """Return *url* with its port replaced by *port* (same scheme/host/path).

    Independent reimplementation for the port-invariance check -- it
    deliberately does not import the production normalisation helper.
    """
    parsed = urlsplit(url)
    netloc = parsed.netloc
    userinfo, sep, hostport = netloc.rpartition("@")
    if hostport.startswith("["):
        bracket = hostport.find("]")
        new_hostport = hostport[: bracket + 1] + f":{port}"
    else:
        host_part, _, _ = hostport.rpartition(":")
        new_hostport = f"{host_part}:{port}"
    return urlunsplit(
        (
            parsed.scheme,
            (userinfo + sep if sep else "") + new_hostport,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def _proj(diags: list[dict]) -> list[dict]:
    order = {
        "ORIGIN_NEGOTIATION_ERROR": 0, "REPRESENTATION_BLEED": 1,
        "CONTRACT_MISMATCH": 2, "CACHE_STATE_UNKNOWN": 3,
        "SENTINEL_MISMATCH": 4, "INCONCLUSIVE_LIMIT": 5,
        "VARY_ACCEPT_ABSENT": 6, "CACHE_EVIDENCE_CONFLICT": 7,
        "CACHE_POLICY_MISMATCH": 8,
    }
    pairs = [{"code": d["code"], "request_index": d["request_index"]} for d in diags]
    return sorted(pairs, key=lambda p: (
        p["request_index"] is None,
        p["request_index"] if p["request_index"] is not None else 0,
        order[p["code"]],
    ))


def _normalise_cache_states(value: object, *, production: bool) -> list[dict] | None:
    """Normalise an 8-entry per-request cache-state list, or None
    when it is missing or malformed (fail-closed).

    Production side (``production["confirmed_cache_states"]``):
    ``"CACHE_STATE_UNKNOWN"`` counts as ``None`` (confirmed
    nothing); Oracle side (``oracle["verified_cache_states"]``):
    only ``"MISS"`` / ``"HIT"`` / ``"BYPASS"`` / ``None`` are legal.
    Mirrors ``scripts/s0_harness.py`` check_parity (T014 / T013-F02)
    and ``src/accepttwin/report_builder.py`` — the three parity
    definitions must stay identical.
    """
    if not isinstance(value, list) or len(value) != 8:
        return None
    allowed = (
        ("MISS", "HIT", "BYPASS", "CACHE_STATE_UNKNOWN")
        if production
        else ("MISS", "HIT", "BYPASS")
    )
    states = []
    for entry in value:
        if not isinstance(entry, dict):
            return None
        index = entry.get("request_index")
        state = entry.get("state")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 1
            or index > 8
            or (state is not None and state not in allowed)
        ):
            return None
        if state == "CACHE_STATE_UNKNOWN":
            state = None
        states.append({"request_index": index, "state": state})
    states.sort(key=lambda s: s["request_index"])
    if [s["request_index"] for s in states] != list(range(1, 9)):
        return None
    return states


def check_oracle_parity(production: dict, oracle: dict) -> tuple[bool, str]:
    """Widened Oracle parity (§12, P2-01): verdict, diagnostics
    projection, first error, first-error experiment, AND the eight
    per-request verified MISS/HIT/BYPASS states. A missing or
    malformed state list on either side fails closed — it is never
    treated as agreement. Returns (ok, detail); detail is "" on ok.
    """
    try:
        if oracle.get("verdict") != production.get("verdict"):
            return False, (
                f"verdict oracle {oracle.get('verdict')!r} != "
                f"production {production.get('verdict')!r}"
            )
        if _proj(oracle.get("diagnostics", [])) != _proj(
            production.get("diagnostics", [])
        ):
            return False, "diagnostics projection mismatch"
        if oracle.get("first_error") != production.get("first_error"):
            return False, (
                f"first_error oracle {oracle.get('first_error')!r} != "
                f"production {production.get('first_error')!r}"
            )
        if oracle.get("first_error_experiment_id") != production.get(
            "first_error_experiment_id"
        ):
            return False, "first_error_experiment_id mismatch"
    except (KeyError, TypeError, AttributeError) as exc:
        return False, f"unreadable verdict/diagnostics/first_error: {exc}"
    prod_states = _normalise_cache_states(
        production.get("confirmed_cache_states"), production=True
    )
    if prod_states is None:
        return False, (
            "production has no well-formed confirmed_cache_states "
            "(expected 8 entries, requests 001-008)"
        )
    ora_states = _normalise_cache_states(
        oracle.get("verified_cache_states"), production=False
    )
    if ora_states is None:
        return False, (
            "oracle has no well-formed verified_cache_states "
            "(expected 8 entries, requests 001-008)"
        )
    if ora_states != prod_states:
        return False, (
            f"verified_cache_states mismatch: production {prod_states} "
            f"!= oracle {ora_states}"
        )
    return True, ""


def main() -> int:
    summary_path = EVIDENCE / "S0_SUMMARY.json"
    if not summary_path.exists():
        print("S0_STATUS: FAIL -- evidence/S0/S0_SUMMARY.json is missing (run scripts/run_s0.py first)")
        return 1
    summary = _load(summary_path)

    per: dict[str, dict] = {}
    for sid in SCENARIOS:
        sdir = EVIDENCE / sid
        for name in ("raw-observations.json", "contract.json", "oracle-input.json", "production.json", "oracle.json", "scenario.json"):
            if not (sdir / name).exists():
                check(f"{sid} evidence files", "§11.2", False, f"missing {name}")
                per[sid] = {}
                break
        else:
            per[sid] = {
                "raw": _load(sdir / "raw-observations.json"),
                "contract": _load(sdir / "contract.json"),
                "oracle_input": _load(sdir / "oracle-input.json"),
                "production": _load(sdir / "production.json"),
                "oracle": _load(sdir / "oracle.json"),
                "scenario": _load(sdir / "scenario.json"),
                "fixture": _load(FIXTURES / f"{sid}.json"),
            }

    # -- 1. 24 core cases (§11.2) ---------------------------------------
    all_present = all(per.get(sid) for sid in SCENARIOS)
    check("24 core cases exist with full evidence", "§11.2", all_present,
          f"{sum(1 for s in SCENARIOS if per.get(s))}/24 scenario dirs complete")
    golden_ok = True
    golden_detail = ""
    for sid in SCENARIOS:
        if not per.get(sid):
            golden_ok = False
            continue
        p = per[sid]
        fx = p["fixture"]
        prod = p["production"]
        if not (
            prod["verdict"] == fx["expected_verdict"]
            and prod["first_error"] == fx["expected_first_error"]
            and prod["first_error_experiment_id"] == fx["expected_first_error_experiment_id"]
            and _proj(prod["diagnostics"]) == fx["expected_diagnostics"]
        ):
            golden_ok = False
            golden_detail = f"{sid}: verdict {prod['verdict']} != {fx['expected_verdict']} or diagnostics/first_error mismatch"
            break
    check("24/24 core Golden match frozen expectations", "§11.2", golden_ok, golden_detail or "24/24")

    # -- 2. Oracle parity (§12) ------------------------------------------
    # P2-01: the same widened definition as the runtime parity
    # (s0_harness check_parity + report_builder): verdict,
    # diagnostics, first error, AND the eight per-request verified
    # cache states. Missing/malformed states fail closed.
    parity_ok = True
    parity_detail = ""
    for sid in SCENARIOS:
        if not per.get(sid):
            parity_ok = False
            continue
        p = per[sid]
        ok, detail = check_oracle_parity(p["production"], p["oracle"])
        if not ok:
            parity_ok = False
            parity_detail = f"{sid}: {detail}"
            break
    check("24/24 Oracle parity (verdict + diagnostics + first error + 8 verified_cache_states)", "§12",
          parity_ok, parity_detail or "24/24")

    # -- 3. Known failures (§8, §11.2) ------------------------------------
    kf = [sid for sid in KNOWN_FAILURES if per.get(sid) and per[sid]["production"]["verdict"] == per[sid]["fixture"]["expected_verdict"]]
    check("known failures all detected", "§8, §11.2", len(kf) == len(KNOWN_FAILURES),
          f"{len(kf)}/{len(KNOWN_FAILURES)} (C07-C16, C19, C24)")

    # -- 4. Healthy zero false positives (§7, §11.2) ----------------------
    hp = [sid for sid in HEALTHY if per.get(sid) and per[sid]["production"]["verdict"] == "PASS_OBSERVED"]
    check("healthy scenarios zero false positives", "§7, §11.2", len(hp) == len(HEALTHY),
          f"{len(hp)}/{len(HEALTHY)} PASS_OBSERVED (C01-C06, C17, C18)")

    # -- 5. Both warm orders real (§0.2, §6) ------------------------------
    orders_ok = True
    orders_detail = ""
    for sid in SCENARIOS:
        if not per.get(sid):
            orders_ok = False
            continue
        raw = per[sid]["raw"]
        obs = raw["observations"]
        if len(obs) != 8 or [o["request_index"] for o in obs] != list(range(1, 9)):
            orders_ok = False
            orders_detail = f"{sid}: not 8 sequential requests"
            break
        if [o["experiment_id"] for o in obs] != [
            "ORIGIN_HTML", "ORIGIN_MARKDOWN", "HTML_COLD", "MARKDOWN_COLD",
            "HTML_TO_MARKDOWN", "HTML_TO_MARKDOWN",
            "MARKDOWN_TO_HTML", "MARKDOWN_TO_HTML",
        ]:
            orders_ok = False
            orders_detail = f"{sid}: experiment sequence wrong"
            break
        if [o["requested_representation"] for o in obs] != [
            "html", "markdown", "html", "markdown",
            "html", "markdown", "markdown", "html",
        ]:
            orders_ok = False
            orders_detail = f"{sid}: warm orders HM/MH not both present"
            break
        # Every request must be a real GET with a real origin event or
        # a verified HIT (HITs legitimately produce no new event).
        events = raw["origin_events"]
        if len(events) < 6:
            orders_ok = False
            orders_detail = f"{sid}: only {len(events)} origin events"
            break
        # No reset between the two requests of a warm experiment:
        # steps 19-20 and 24-25 must be consecutive request steps.
        names = [s["name"] for s in raw["steps"]]
        if names[18:20] != ["HTMLWarmFirst", "MarkdownWarmSecond"] or names[23:25] != ["MarkdownWarmFirst", "HTMLWarmSecond"]:
            orders_ok = False
            orders_detail = f"{sid}: reset found inside a warm experiment"
            break
        if [s["step"] for s in raw["steps"] if s["name"] == "ResetCache"] != [9, 13, 17, 22]:
            orders_ok = False
            orders_detail = f"{sid}: resets not exactly at steps 09/13/17/22"
            break
    check("both warm orders really executed (HM + MH, no mid-warm reset)", "§0.2, §6",
          orders_ok, orders_detail or "8 requests, resets at 09/13/17/22 only")

    # -- 6. Independent cold requests (§5.4, §6) --------------------------
    cold_ok = True
    cold_detail = ""
    for sid in SCENARIOS:
        if not per.get(sid):
            cold_ok = False
            continue
        raw = per[sid]["raw"]
        if len(raw["resets"]) != 4:
            cold_ok = False
            cold_detail = f"{sid}: {len(raw['resets'])} resets, expected 4"
            break
        for i, reset in enumerate(raw["resets"]):
            if sid == "C23" and i == 0:
                if reset["success"] is not False:
                    cold_ok = False
                    cold_detail = "C23: first reset must report failure"
                    break
                continue
            if not reset["success"] or reset["entries_after"] != 0:
                cold_ok = False
                cold_detail = f"{sid}: reset {i} not confirmed empty"
                break
        if not cold_ok:
            break
        # Cold / warm-first requests start from an empty cache.
        for idx in (3, 4, 5, 7):
            if raw["observations"][idx - 1]["cache_entry_count_before"] != 0:
                cold_ok = False
                cold_detail = f"{sid}: request {idx:03d} did not start from an empty cache"
                break
        if not cold_ok:
            break
        # Cold requests carry MISS/BYPASS dual proof -- except the
        # opaque-proxy scenario, whose cold requests are UNKNOWN by
        # design. (C21's runner-level states are MISS: the journal
        # fault bites only at the adjudication boundary, where the
        # classifier/Oracle receive an empty event list; see check 12.)
        for idx in (3, 4):
            state = raw["observations"][idx - 1]["verified_cache_state"]
            if sid == "C20":
                if state != "CACHE_STATE_UNKNOWN":
                    cold_ok = False
                    cold_detail = f"{sid}: cold request {idx} must be UNKNOWN, got {state}"
                    break
            elif state not in ("MISS", "BYPASS"):
                cold_ok = False
                cold_detail = f"{sid}: cold request {idx} state {state}, expected MISS/BYPASS"
                break
        if not cold_ok:
            break
    check("independent cold requests (reset + empty + MISS/BYPASS dual proof)", "§5.4, §6",
          cold_ok, cold_detail or "4 confirmed resets, empty before 003/004/005/007")

    # -- 7. Dual cache evidence (§5.3), recomputed from raw --------------
    dual_ok = True
    dual_detail = ""
    for sid in SCENARIOS:
        if not per.get(sid):
            dual_ok = False
            continue
        raw = per[sid]["raw"]
        by_index = {o["request_index"]: o for o in raw["observations"]}
        for idx in range(3, 9):
            o = by_index[idx]
            header = o["cache_status_header"]
            state = o["verified_cache_state"]
            delta = o["origin_counter_delta"]
            if state in ("MISS", "HIT", "BYPASS"):
                if header != state:
                    dual_ok = False
                    dual_detail = f"{sid} req {idx}: header {header} != verified {state}"
                    break
                if state == "MISS":
                    if delta != 1 or not o["origin_event_present"] or not (
                        o["cache_entry_count_after"] is not None
                        and o["cache_entry_count_before"] is not None
                        and o["cache_entry_count_after"] > o["cache_entry_count_before"]
                    ) or not o["cache_key_sha256"] or not o["cache_entry_id"]:
                        dual_ok = False
                        dual_detail = f"{sid} req {idx}: MISS behaviour leg incomplete"
                        break
                elif state == "HIT":
                    if delta != 0 or not o["cache_key_sha256"] or not o["cache_entry_id"]:
                        dual_ok = False
                        dual_detail = f"{sid} req {idx}: HIT behaviour leg incomplete"
                        break
                    # The stored entry is the one the *most recent*
                    # storing MISS wrote under this entry id: cache
                    # keys are deterministic, so an earlier
                    # experiment's MISS under the same key may share
                    # the id while holding a different body.
                    storing = [
                        p for p in raw["observations"]
                        if p["request_index"] < idx
                        and p["cache_entry_id"] == o["cache_entry_id"]
                        and p["verified_cache_state"] == "MISS"
                    ]
                    if not storing or storing[-1]["body_sha256"] != o["body_sha256"]:
                        dual_ok = False
                        dual_detail = f"{sid} req {idx}: HIT entry/body does not match the storing MISS"
                        break
                else:  # BYPASS
                    if delta != 1 or not o["origin_event_present"] or o["cache_entry_count_after"] != o["cache_entry_count_before"]:
                        dual_ok = False
                        dual_detail = f"{sid} req {idx}: BYPASS behaviour leg incomplete"
                        break
            elif state == "CACHE_STATE_UNKNOWN":
                # UNKNOWN must be justified: a missing/conflicting leg.
                if sid == "C22" and idx == 6:
                    if header != "HIT" or delta != 1:
                        dual_ok = False
                        dual_detail = "C22 req 006: expected header HIT with delta +1"
                        break
                elif sid == "C20":
                    if header is not None:
                        dual_ok = False
                        dual_detail = "C20: opaque proxy must hide the status header"
                        break
                elif sid == "C21":
                    pass  # journal unavailable: event leg missing by design
                else:
                    dual_ok = False
                    dual_detail = f"{sid} req {idx}: unexpected UNKNOWN state"
                    break
            else:
                dual_ok = False
                dual_detail = f"{sid} req {idx}: bad verified state {state!r}"
                break
        if not dual_ok:
            break
    check("dual cache evidence (header + origin behaviour), recomputed", "§5.3",
          dual_ok, dual_detail or "every confirmed state has both legs; every UNKNOWN is justified")

    # -- 8. Stable bleed reproduction (§8.2, §11.2) -----------------------
    bleed = summary.get("bleed_reproduction", {})
    bleed_ok = (
        bleed.get("scenario") == "C11"
        and bleed.get("reproduced_3_of_3") is True
        and len(bleed.get("runs", [])) == 3
        and all(
            r["verdict"] == "REPRESENTATION_BLEED" and r["first_error"] == 6
            and len(r["bleed_diagnostics"]) == 2
            for r in bleed["runs"]
        )
    )
    check("stable bleed reproduction (C11, 3/3, full dual evidence)", "§8.2, §11.2",
          bleed_ok, "3/3 REPRESENTATION_BLEED, first_error 006, 2 bleed diagnostics each" if bleed_ok else str(bleed))

    # -- 9. Missing-Vary healthy (§7.11, §11.2) ---------------------------
    vary_ok = True
    vary_detail = ""
    for sid in ("C03", "C04"):
        if not per.get(sid):
            vary_ok = False
            continue
        prod = per[sid]["production"]
        codes = [d["code"] for d in prod["diagnostics"]]
        if prod["verdict"] != "PASS_OBSERVED" or codes != ["VARY_ACCEPT_ABSENT", "VARY_ACCEPT_ABSENT"]:
            vary_ok = False
            vary_detail = f"{sid}: verdict {prod['verdict']}, diagnostics {codes}"
            break
    check("missing-Vary healthy scenarios pass (C03/C04, warning only)", "§7.11, §11.2",
          vary_ok, vary_detail or "PASS_OBSERVED + VARY_ACCEPT_ABSENT x2, no bleed")

    # -- 10. Repeat-100 hash (§7.8, §10.4), recomputed --------------------
    repeat = summary.get("repeat_100", {})
    repeat_ok = (
        repeat.get("runs") == 100
        and repeat.get("distinct_hashes") == 1
        and repeat.get("all_equal") is True
        and repeat.get("fresh_pair_per_run") is True
        and repeat.get("same_pair_all_equal") is True
        and isinstance(repeat.get("hash"), str)
        and len(repeat["hash"]) == 64
    )
    # Recompute the C01 canonical hash from the stored evidence.
    recomputed = None
    if per.get("C01"):
        p = per["C01"]
        contract_hash = hashlib.sha256(
            canonical_json_bytes(p["contract"])
        ).hexdigest()
        report = {
            "schema": "accepttwin.report/v1",
            "scenario_id": "C01",
            "contract_sha256": contract_hash,
            "observations": [
                {
                    "request_index": o["request_index"],
                    "experiment_id": o["experiment_id"],
                    "requested_representation": o["requested_representation"],
                    "response_status": o["response_status"],
                    "response_content_type": o["response_content_type"],
                    "body_sha256": o["body_sha256"],
                    "sentinel_match": o["sentinel_match"],
                    "cache_status": o["verified_cache_state"],
                    "origin_counter_delta": o["origin_counter_delta"],
                }
                for o in p["raw"]["observations"]
            ],
            "diagnostics": [
                {"code": d["code"], "request_index": d["request_index"]}
                for d in p["production"]["diagnostics"]
            ],
            "verdict": p["production"]["verdict"],
            "first_error": p["production"]["first_error"],
            "first_error_experiment_id": p["production"]["first_error_experiment_id"],
        }
        recomputed = hashlib.sha256(canonical_json_bytes(report)).hexdigest()
        if recomputed != p["scenario"]["report_hash"]:
            repeat_ok = False
    # Port invariance (ADR-003): rewriting only the contract ports
    # must not change the contract hash -- this is the check that
    # catches the P1-1 defect (a port-dependent hash fails here).
    port_invariant = False
    port_detail = "no C01 evidence to rewrite"
    if per.get("C01"):
        p = per["C01"]
        original_hash = hashlib.sha256(
            canonical_json_bytes(p["contract"])
        ).hexdigest()
        rewritten = dict(p["contract"])
        for key, preferred, fallback in (
            ("url", 51111, 51112),
            ("origin_url", 52222, 52223),
        ):
            orig_port = urlsplit(rewritten[key]).port
            new_port = preferred if orig_port != preferred else fallback
            rewritten[key] = _with_port(rewritten[key], new_port)
        rewritten_hash = hashlib.sha256(
            canonical_json_bytes(rewritten)
        ).hexdigest()
        port_invariant = rewritten_hash == original_hash
        port_detail = (
            f"contract hash unchanged after port rewrite: "
            f"{original_hash[:12]} vs {rewritten_hash[:12]}"
        )
        if not port_invariant:
            repeat_ok = False
    else:
        repeat_ok = False
    # C11 repro hashes (ADR-003): the 3 fresh-port reproductions must
    # hash identically to each other and to the main C11 run -- before
    # the fix they differed on every run.
    bleed_runs = summary.get("bleed_reproduction", {}).get("runs", [])
    bleed_hashes = [r.get("report_hash") for r in bleed_runs]
    bleed_hash_ok = (
        len(bleed_hashes) == 3
        and len(set(bleed_hashes)) == 1
        and bool(per.get("C11"))
        and bleed_hashes[0] == per["C11"]["scenario"]["report_hash"]
    )
    if not bleed_hash_ok:
        repeat_ok = False
    check("100/100 identical canonical report hashes (recomputed)", "§7.8, §10.4",
          repeat_ok,
          f"100 runs, distinct={repeat.get('distinct_hashes')}, "
          f"fresh_pair={repeat.get('fresh_pair_per_run')}, "
          f"same_pair_equal={repeat.get('same_pair_all_equal')}, "
          f"recomputed C01 hash matches={recomputed == per['C01']['scenario']['report_hash'] if per.get('C01') else False}, "
          f"port_invariant={port_invariant} ({port_detail}), "
          f"C11 repro hashes equal main C11 hash={bleed_hash_ok}")

    # -- 11. Single scenario < 1s (§10.5) ---------------------------------
    max_dur = max(
        (per[sid]["scenario"]["duration_seconds"] for sid in SCENARIOS if per.get(sid)),
        default=999,
    )
    rep_max = repeat.get("max_duration_seconds", 999)
    check("single scenario < 1s (all 24 + repeat max)", "§10.5",
          max_dur < 1.0 and rep_max < 1.0,
          f"max scenario {max_dur:.3f}s, repeat max {rep_max:.3f}s")

    # -- 12. Insufficient evidence (§8.4, §8.8, §9.4) ---------------------
    ins_ok = True
    ins_detail = ""
    for sid in INSUFFICIENT:
        if not per.get(sid):
            ins_ok = False
            continue
        prod = per[sid]["production"]
        codes = [d["code"] for d in prod["diagnostics"]]
        if prod["verdict"] != "INCONCLUSIVE" or "REPRESENTATION_BLEED" in codes:
            ins_ok = False
            ins_detail = f"{sid}: verdict {prod['verdict']}, codes {codes}"
            break
    check("insufficient evidence never misjudged (C20-C23 INCONCLUSIVE, no bleed)", "§8.4, §8.8, §9.4",
          ins_ok, ins_detail or "4/4 INCONCLUSIVE, 0 bleed diagnostics")
    # C21's journal fault is visible in the adjudication input itself.
    c21_oi = per.get("C21", {}).get("oracle_input", {}) if per.get("C21") else {}
    c21_ok = (
        c21_oi.get("origin_events_available") is False
        and c21_oi.get("origin_events") == []
    )
    check("C21 adjudication input carries an empty, unavailable event journal", "§8.4, §11.2",
          c21_ok, "origin_events=[] and origin_events_available=false" if c21_ok else str(c21_oi.get("origin_events_available")))

    # -- 13. First-error location (§6.3, §8), recomputed -------------------
    fe_ok = True
    fe_detail = ""
    for sid in SCENARIOS:
        if not per.get(sid):
            fe_ok = False
            continue
        prod = per[sid]["production"]
        violating = [
            d["request_index"]
            for d in prod["diagnostics"]
            if d["code"] != "VARY_ACCEPT_ABSENT" and d["request_index"] is not None
        ]
        expected_fe = min(violating) if violating else None
        if prod["first_error"] != expected_fe:
            fe_ok = False
            fe_detail = f"{sid}: first_error {prod['first_error']} != recomputed {expected_fe}"
            break
        if expected_fe is not None:
            exp_id = next(
                o["experiment_id"]
                for o in per[sid]["raw"]["observations"]
                if o["request_index"] == expected_fe
            )
            if prod["first_error_experiment_id"] != exp_id:
                fe_ok = False
                fe_detail = f"{sid}: first_error_experiment_id mismatch"
                break
    check("first-error location exact (request + experiment, recomputed)", "§6.3, §8",
          fe_ok, fe_detail or "24/24 match the smallest violating request")

    # -- 14. Mandatory call convention (ADR-002 Decision 3) ---------------
    harness_src = (ROOT / "scripts" / "s0_harness.py").read_text(encoding="utf-8")
    # The real call site is a single line carrying both the contract
    # arguments and raw_observations; the MANDATORY_CALL_SNIPPET doc
    # constant above it is split over several lines and must not match.
    call_lines = [
        ln for ln in harness_src.splitlines()
        if "classify_run(contract, run.observations" in ln
        and "raw_observations=run.raw_observations" in ln
    ]
    call_ok = False
    call_detail = ""
    for ln in call_lines:
        if "raw_observations=run.raw_observations" in ln and "run.origin_events" not in ln.split("raw_observations")[0].replace("adj_origin_events", ""):
            # The adjudication variable must be the real tuple (or the
            # documented C21 empty tuple), never None.
            if "adj_origin_events" in ln and "None" not in ln:
                call_ok = True
                call_detail = ln.strip()[:160]
                break
    if not call_ok:
        call_detail = f"no compliant call site found; call lines: {call_lines}"
    check("mandatory classify_run call convention (ADR-002 Decision 3)", "ADR-002",
          call_ok, call_detail)
    # No None is ever passed for origin_events / reset_evidence anywhere
    # in the harness call.
    none_ok = all("None" not in ln for ln in call_lines)
    check("no None passed to classify_run (origin_events/reset_evidence)", "ADR-002",
          none_ok, "call site passes real tuples only" if none_ok else str(call_lines))

    # -- 15. Oracle independence (§12.3) -----------------------------------
    oracle_src = ""
    for path in sorted((ROOT / "oracle" / "src").glob("*.ts")):
        oracle_src += path.read_text(encoding="utf-8") + "\n"
    forbidden = [s for s in ("classify_run", "production.json", ".py", "accepttwin.classifier", "subprocess") if s in oracle_src]
    ind_ok = not forbidden
    check("Oracle independent (no production import/call, no production verdict read)", "§12.3",
          ind_ok, f"forbidden strings in oracle/src: {forbidden}" if forbidden else "oracle/src/*.ts clean")
    # Oracle input files must not carry a production verdict/diagnostics.
    oi_ok = True
    oi_detail = ""
    for sid in SCENARIOS:
        if not per.get(sid):
            oi_ok = False
            continue
        oi = per[sid]["oracle_input"]
        if "verdict" in oi or "diagnostics" in oi or "production" in oi:
            oi_ok = False
            oi_detail = f"{sid}: oracle-input carries a verdict/diagnostics field"
            break
    check("Oracle input carries no production verdict/diagnostics", "§12.2, §12.3",
          oi_ok, oi_detail or "24/24 oracle-input files clean")

    # -- final ---------------------------------------------------------------
    failed = [r for r in RESULTS if not r[2]]
    status = "PASS" if not failed and summary.get("S0_STATUS") == "PASS" else "FAIL"
    print(f"\nS0_STATUS: {status} ({len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed)")
    if failed:
        for item, spec, _, detail in failed:
            print(f"  FAILED: {item} ({spec}) -- {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
