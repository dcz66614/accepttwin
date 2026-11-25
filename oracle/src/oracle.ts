/**
 * Independent verdict computation (P032 T007, PROJECT_BOOK §8, §9).
 *
 * Written from the spec text alone: the nine §8 diagnostic triggers
 * and the §9.6 verdict priority. No production code is imported, no
 * production verdict or diagnostic is read, and no shared decision
 * table is reused -- the Oracle recomputes every code from the raw
 * observations, the origin events and the reset records.
 *
 * Verdict priority (§9.6), applied literally:
 *   1. out of scope            -> INCONCLUSIVE
 *   2. origin baseline error   -> ORIGIN_NEGOTIATION_ERROR
 *   3. proven warm-cache bleed -> REPRESENTATION_BLEED
 *   4. other confirmed contract error -> CONTRACT_MISMATCH
 *   5. key evidence insufficient -> INCONCLUSIVE
 *   6. everything conforms     -> PASS_OBSERVED
 *
 * First error (§6.3): the smallest request number (001-008) carrying
 * a diagnostic other than the advisory VARY_ACCEPT_ABSENT; run-level
 * diagnostics (request_index null) never locate a first error.
 */

import type { OracleInput, RawObservation } from "./input.ts";
import {
  requiresRevalidation,
  varyAcceptPresent,
  varyIncludesStar,
  verifyCacheState,
} from "./evidence.ts";

export const DIAGNOSTIC_CODES = [
  "ORIGIN_NEGOTIATION_ERROR",
  "REPRESENTATION_BLEED",
  "CONTRACT_MISMATCH",
  "CACHE_STATE_UNKNOWN",
  "SENTINEL_MISMATCH",
  "INCONCLUSIVE_LIMIT",
  "VARY_ACCEPT_ABSENT",
  "CACHE_EVIDENCE_CONFLICT",
  "CACHE_POLICY_MISMATCH",
] as const;

export const CODE_SEVERITY: Record<string, string> = {
  ORIGIN_NEGOTIATION_ERROR: "CRITICAL",
  REPRESENTATION_BLEED: "CRITICAL",
  CONTRACT_MISMATCH: "CRITICAL",
  CACHE_STATE_UNKNOWN: "WARNING",
  SENTINEL_MISMATCH: "CRITICAL",
  INCONCLUSIVE_LIMIT: "WARNING",
  VARY_ACCEPT_ABSENT: "WARNING",
  CACHE_EVIDENCE_CONFLICT: "WARNING",
  CACHE_POLICY_MISMATCH: "CRITICAL",
};

export interface OracleDiagnostic {
  code: string;
  severity: string;
  message: string;
  experiment_id: string | null;
  request_index: number | null;
}

export interface VerifiedCacheState {
  request_index: number;
  /** The state this Oracle confirmed, or null (baselines, or the
   *  state could not be confirmed — T014, T013-F02). */
  state: string | null;
}

export interface OracleResult {
  verdict: string;
  diagnostics: OracleDiagnostic[];
  first_error: number | null;
  first_error_experiment_id: string | null;
  reasons: string[];
  /** Per-request verified cache states (T014, T013-F02): the parity
   *  check compares these against the production runner's verified
   *  states, so a state disagreement can no longer pass silently
   *  behind identical verdicts/diagnostics. */
  verified_cache_states: VerifiedCacheState[];
}

function contentTypeMatches(observed: string, expected: string): boolean {
  return observed.trim().toLowerCase() === expected.trim().toLowerCase();
}

function representationCorrect(
  status: number,
  contentType: string,
  sentinelMatch: boolean,
  expectedStatus: number,
  expectedContentType: string,
): boolean {
  return (
    status === expectedStatus &&
    contentTypeMatches(contentType, expectedContentType) &&
    sentinelMatch
  );
}

function diag(
  code: string,
  message: string,
  experimentId: string | null,
  requestIndex: number | null,
): OracleDiagnostic {
  return {
    code,
    severity: CODE_SEVERITY[code],
    message,
    experiment_id: experimentId,
    request_index: requestIndex,
  };
}

export function evaluateScenario(input: OracleInput): OracleResult {
  const diagnostics: OracleDiagnostic[] = [];
  const reasons: string[] = [];
  const contract = input.contract;
  const mode = contract.cache_behavior.mode;
  const varyMode = contract.cache_behavior.vary_accept ?? "advisory";
  const varyRequired = varyMode === "required";
  const cacheable = mode === "variant_by_accept";
  const maxBody = Number(contract.limits["max_body_bytes"] ?? 1048576);

  const obsByIndex = new Map(input.observations.map((o) => [o.request_index, o]));
  const rawByIndex = new Map(
    input.raw_observations.map((r) => [r.request_index, r]),
  );

  // -- §9.6 step 1: input validity -------------------------------------
  const indices = [...obsByIndex.keys()].sort((a, b) => a - b);
  if (
    input.observations.length !== 8 ||
    indices.join(",") !== "1,2,3,4,5,6,7,8"
  ) {
    diagnostics.push(
      diag(
        "INCONCLUSIVE_LIMIT",
        "observations are incomplete: expected exactly requests 001-008 once each",
        null,
        null,
      ),
    );
    return finish("INCONCLUSIVE", diagnostics, ["observations are incomplete"], obsByIndex, []);
  }

  // -- per-request out-of-scope checks (§8.6) ---------------------------
  let outOfScope = false;
  for (const index of indices) {
    const obs = obsByIndex.get(index)!;
    const raw = rawByIndex.get(index);
    const bodySize = raw?.body_size ?? null;
    const transportError = raw?.transport_error ?? null;
    let limitCode = "";
    let detail = "";
    if (transportError !== null) {
      limitCode = "transport_error";
      detail = transportError;
    } else if (obs.response_status === 0) {
      limitCode = "transport_error";
      detail = "no HTTP response was received";
    } else if (obs.response_status >= 300 && obs.response_status < 400) {
      limitCode = "redirect";
      detail = `status ${obs.response_status} (redirects are not followed in this release)`;
    } else if (bodySize !== null && bodySize > maxBody) {
      limitCode = "body_too_large";
      detail = `body size ${bodySize} exceeds the ${maxBody} byte limit`;
    } else if (raw !== undefined && requiresRevalidation(raw)) {
      // §8.6 (T008, §11.3 E07/E08): no-cache / max-age=0 demands
      // revalidation this release does not implement.
      limitCode = "revalidation_required";
      detail = "response requires revalidation, which this release does not implement";
    }
    if (limitCode) {
      diagnostics.push(
        diag(
          "INCONCLUSIVE_LIMIT",
          `out of supported range (${limitCode})` + (detail ? `: ${detail}` : ""),
          obs.experiment_id,
          index,
        ),
      );
      outOfScope = true;
    }
  }

  // -- reset evidence (§8.4, §11.2 C23) ----------------------------------
  let resetConfirmed = true;
  if (input.resets.length === 0) {
    diagnostics.push(
      diag(
        "CACHE_STATE_UNKNOWN",
        "no cache reset was recorded, so no cold-cache claim can be confirmed",
        null,
        null,
      ),
    );
    resetConfirmed = false;
  } else {
    for (const reset of input.resets) {
      if (reset.success !== true || reset.entries_after !== 0) {
        diagnostics.push(
          diag(
            "CACHE_STATE_UNKNOWN",
            `a cache reset did not reach a confirmed empty state (namespace=${reset.namespace}, success=${reset.success}, entries_after=${reset.entries_after}), so cold-cache claims cannot be confirmed`,
            null,
            null,
          ),
        );
        resetConfirmed = false;
        break;
      }
    }
  }

  // -- cache-state verification per proxied request (§5.3, §8.4/§8.8) ---
  const confirmed = new Map<number, string | null>();
  for (const index of indices) {
    if (index <= 2) {
      confirmed.set(index, null); // direct-origin baselines: no cache evidence (ADR-001)
      continue;
    }
    const obs = obsByIndex.get(index)!;
    const raw = rawByIndex.get(index)!;
    // Each earlier request paired with the state this Oracle
    // confirmed for it (T014, T013-F05) — the HIT tie below must
    // not read the production runner's verified_cache_state.
    const earlier = input.raw_observations
      .filter((r) => r.request_index < index)
      .map((r) => ({ raw: r, confirmed: confirmed.get(r.request_index) ?? null }));
    const check = verifyCacheState(input, obs, raw, earlier);
    if (check.problem === "conflict") {
      diagnostics.push(
        diag(
          "CACHE_EVIDENCE_CONFLICT",
          `proxy reported ${raw.cache_status_header ?? "?"} for request ${String(index).padStart(3, "0")} but the origin counter moved by ${obs.origin_counter_delta >= 0 ? "+" : ""}${obs.origin_counter_delta}`,
          obs.experiment_id,
          index,
        ),
      );
      confirmed.set(index, null);
    } else if (check.problem === "unknown") {
      diagnostics.push(
        diag(
          "CACHE_STATE_UNKNOWN",
          `cache state for request ${String(index).padStart(3, "0")} could not be confirmed with dual evidence`,
          obs.experiment_id,
          index,
        ),
      );
      confirmed.set(index, null);
    } else {
      confirmed.set(index, check.confirmed);
    }
  }

  // -- origin baselines (§8.1, §9.1) --------------------------------------
  let baselineCorrect = true;
  let originError = false;
  for (const index of [1, 2]) {
    const obs = obsByIndex.get(index)!;
    const rep = contract.representations[obs.requested_representation];
    const correct = representationCorrect(
      obs.response_status,
      obs.response_content_type,
      obs.sentinel_match,
      rep.expected_status,
      rep.expected_content_type,
    );
    baselineCorrect = baselineCorrect && correct;
    if (obs.response_status === 0 || (obs.response_status >= 300 && obs.response_status < 400)) {
      baselineCorrect = false;
      continue;
    }
    if (!correct) {
      diagnostics.push(
        diag(
          "ORIGIN_NEGOTIATION_ERROR",
          `direct-origin baseline for ${obs.requested_representation} violates the contract: status ${obs.response_status} (expected ${rep.expected_status}), content-type ${obs.response_content_type} (expected ${rep.expected_content_type}), sentinel_match=${obs.sentinel_match}`,
          obs.experiment_id,
          index,
        ),
      );
      originError = true;
    }
  }

  // -- Sentinel (§8.5) and proxied contract responses (§8.3) -------------
  let contractError = false;
  for (const index of indices) {
    const obs = obsByIndex.get(index)!;
    const rep = contract.representations[obs.requested_representation];
    if (obs.response_status === 0 || (obs.response_status >= 300 && obs.response_status < 400)) {
      continue;
    }
    if (!obs.sentinel_match) {
      diagnostics.push(
        diag(
          "SENTINEL_MISMATCH",
          `response body for request ${String(index).padStart(3, "0")} lacks the exact Sentinel of the requested ${obs.requested_representation} representation`,
          obs.experiment_id,
          index,
        ),
      );
      contractError = true;
    }
    if (index <= 2) continue;
    const statusBad = obs.response_status !== rep.expected_status;
    const ctBad = !contentTypeMatches(obs.response_content_type, rep.expected_content_type);
    if (statusBad || ctBad) {
      diagnostics.push(
        diag(
          "CONTRACT_MISMATCH",
          `response for request ${String(index).padStart(3, "0")} violates the ${obs.requested_representation} contract`,
          obs.experiment_id,
          index,
        ),
      );
      contractError = true;
    }
  }

  // -- cache policy (§8.9) and unexpected HIT (§8.3) ----------------------
  let policyError = false;
  for (const index of indices) {
    if (index <= 2) continue;
    const obs = obsByIndex.get(index)!;
    const rep = contract.representations[obs.requested_representation];
    const state = confirmed.get(index) ?? null;
    if (mode === "no_store") {
      if (state === "MISS" || state === "HIT") {
        diagnostics.push(
          diag(
            "CACHE_POLICY_MISMATCH",
            `contract declares no_store but request ${String(index).padStart(3, "0")} was ${state} -- the proxy stored or reused a response`,
            obs.experiment_id,
            index,
          ),
        );
        policyError = true;
      }
    } else if (cacheable && state === "BYPASS") {
      // Vary: * exemption (T008, ADR-004, §11.3 E03): a response
      // that must never be reused is compliant when it is not
      // stored, so its BYPASS is not a policy violation.
      const raw = rawByIndex.get(index);
      if (raw === undefined || !varyIncludesStar(raw)) {
        diagnostics.push(
          diag(
            "CACHE_POLICY_MISMATCH",
            `contract declares variant_by_accept but request ${String(index).padStart(3, "0")} was BYPASS -- the proxy stored nothing, so per-representation cache isolation was never exercised`,
            obs.experiment_id,
            index,
          ),
        );
        policyError = true;
      }
    } else if (cacheable && state === "HIT" && resetConfirmed) {
      const correct = representationCorrect(
        obs.response_status,
        obs.response_content_type,
        obs.sentinel_match,
        rep.expected_status,
        rep.expected_content_type,
      );
      if (correct) {
        diagnostics.push(
          diag(
            "CONTRACT_MISMATCH",
            `request ${String(index).padStart(3, "0")} for ${obs.requested_representation} was a HIT immediately after a confirmed cache reset, but no entry for that representation could exist yet`,
            obs.experiment_id,
            index,
          ),
        );
        contractError = true;
      }
    }
  }

  // -- warm-cache bleed (§8.2, §9.2) ---------------------------------------
  let bleed = false;
  for (const [firstIndex, secondIndex] of [[5, 6], [7, 8]] as const) {
    const first = obsByIndex.get(firstIndex)!;
    const second = obsByIndex.get(secondIndex)!;
    const firstRep = contract.representations[first.requested_representation];
    const secondRep = contract.representations[second.requested_representation];
    const firstCorrect = representationCorrect(
      first.response_status,
      first.response_content_type,
      first.sentinel_match,
      firstRep.expected_status,
      firstRep.expected_content_type,
    );
    const isBleed =
      baselineCorrect &&
      firstCorrect &&
      confirmed.get(firstIndex) === "MISS" &&
      confirmed.get(secondIndex) === "HIT" &&
      second.origin_counter_delta === 0 &&
      first.cache_entry_id !== null &&
      second.cache_entry_id !== null &&
      first.cache_entry_id === second.cache_entry_id &&
      second.body_sha256 === first.body_sha256 &&
      contentTypeMatches(second.response_content_type, firstRep.expected_content_type) &&
      !second.sentinel_match;
    void secondRep;
    if (isBleed) {
      diagnostics.push(
        diag(
          "REPRESENTATION_BLEED",
          `warm-cache request ${String(secondIndex).padStart(3, "0")} for ${second.requested_representation} was served the other representation from a verified HIT of the entry stored by request ${String(firstIndex).padStart(3, "0")}`,
          second.experiment_id,
          secondIndex,
        ),
      );
      bleed = true;
    }
  }

  // -- Vary (§8.7, I-11) ----------------------------------------------------
  let varyUnknownRequired = false;
  for (const index of [1, 2]) {
    const obs = obsByIndex.get(index)!;
    const raw = rawByIndex.get(index);
    const present = raw === undefined ? null : varyAcceptPresent(raw);
    if (present === null) {
      if (varyRequired && cacheable) {
        diagnostics.push(
          diag(
            "INCONCLUSIVE_LIMIT",
            "contract requires Vary: Accept but no Vary header was supplied for this baseline; the required evidence is missing",
            obs.experiment_id,
            index,
          ),
        );
        varyUnknownRequired = true;
      }
      continue;
    }
    if (!cacheable || present) continue;
    if (varyRequired) {
      diagnostics.push(
        diag(
          "CONTRACT_MISMATCH",
          `contract requires Vary: Accept but the origin response for request ${String(index).padStart(3, "0")} does not declare it`,
          obs.experiment_id,
          index,
        ),
      );
      contractError = true;
    } else {
      diagnostics.push(
        diag(
          "VARY_ACCEPT_ABSENT",
          `origin response for request ${String(index).padStart(3, "0")} does not declare Vary: Accept; the cache must still be judged by its actual behaviour, not by this header alone (I-11)`,
          obs.experiment_id,
          index,
        ),
      );
    }
  }

  // -- verdict (§9.6 priority, applied literally) ---------------------------
  const evidenceInsufficient =
    diagnostics.some((d) => d.code === "CACHE_STATE_UNKNOWN" || d.code === "CACHE_EVIDENCE_CONFLICT") ||
    varyUnknownRequired;
  let verdict: string;
  if (outOfScope) {
    verdict = "INCONCLUSIVE";
    reasons.push("run left the supported range (redirect, transport failure, oversize body, revalidation required, or unknown representation)");
  } else if (originError) {
    verdict = "ORIGIN_NEGOTIATION_ERROR";
    reasons.push("a direct-origin baseline violates the contract");
  } else if (bleed) {
    verdict = "REPRESENTATION_BLEED";
    reasons.push("a warm-cache second request was served the other representation from a verified HIT");
  } else if (contractError || policyError) {
    verdict = "CONTRACT_MISMATCH";
    reasons.push("a response violates the contract but is neither a proven origin error nor a proven bleed");
  } else if (evidenceInsufficient) {
    verdict = "INCONCLUSIVE";
    reasons.push("key cache evidence is missing or conflicting");
  } else {
    verdict = "PASS_OBSERVED";
    reasons.push("baselines, cold requests and both warm orders are correct with complete cache evidence and no CRITICAL diagnostic");
  }
  const verifiedCacheStates: VerifiedCacheState[] = indices.map((index) => ({
    request_index: index,
    state: confirmed.get(index) ?? null,
  }));
  return finish(verdict, diagnostics, reasons, obsByIndex, verifiedCacheStates);
}

function finish(
  verdict: string,
  diagnostics: OracleDiagnostic[],
  reasons: string[],
  obsByIndex: Map<number, { experiment_id: string }>,
  verifiedCacheStates: VerifiedCacheState[],
): OracleResult {
  const codeOrder = (code: string): number => DIAGNOSTIC_CODES.indexOf(code as never);
  const ordered = [...diagnostics].sort((a, b) => {
    const aNull = a.request_index === null ? 1 : 0;
    const bNull = b.request_index === null ? 1 : 0;
    if (aNull !== bNull) return aNull - bNull;
    const ai = a.request_index ?? 0;
    const bi = b.request_index ?? 0;
    if (ai !== bi) return ai - bi;
    const ao = codeOrder(a.code);
    const bo = codeOrder(b.code);
    if (ao !== bo) return ao - bo;
    return a.message.localeCompare(b.message);
  });
  let firstError: number | null = null;
  let firstErrorExperimentId: string | null = null;
  for (const d of ordered) {
    if (d.code === "VARY_ACCEPT_ABSENT") continue;
    if (d.request_index !== null) {
      firstError = d.request_index;
      const obs = obsByIndex.get(d.request_index);
      firstErrorExperimentId = obs !== undefined ? obs.experiment_id : d.experiment_id;
      break;
    }
  }
  return {
    verdict,
    diagnostics: ordered,
    first_error: firstError,
    first_error_experiment_id: firstErrorExperimentId,
    reasons,
    verified_cache_states: verifiedCacheStates,
  };
}
