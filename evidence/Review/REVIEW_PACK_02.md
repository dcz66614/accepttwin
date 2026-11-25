# FIX-R1 审查包 02 — Oracle、S0/运行脚本、报告 UI、Schema、契约、配置与 ADR-001–009

审查对象 commit：`221f902798a245b7a2672f3a53a9a63ab176e014`（tag `P032-v1.0.1`，P032 FIX-R1 重冻结，规格 v1.0.1）。
本包全部内容取自该 tag 的 git 对象（`git show <tag>:<path>`），非工作区副本；
每节标题下均给出该文件在该 tag 下的 SHA-256（对内容字节计算）。
核对方法：`git show 221f902798a245b7a2672f3a53a9a63ab176e014:<path> | sha256sum`。

## oracle/src/evidence.ts

- SHA-256：`ac69388b0ff15389b757e884a386426f47961ab715f611785b427783c62e308b`
- 字节数：8833

```
/**
 * Dual-evidence cache-state verification (P032 T007, PROJECT_BOOK §5.3).
 *
 * Independent re-implementation of the §5.3 contract: a cache state
 * counts as confirmed only when its response-header leg and its
 * origin-behaviour leg both hold. Any conflict, or any missing leg,
 * yields CACHE_STATE_UNKNOWN -- never a guessed state.
 *
 * Header leg (from the raw observation's response headers):
 *   MISS/HIT need X-AcceptTwin-Cache-Status plus key and entry id;
 *   BYPASS needs the status header alone.
 * Behaviour leg (recomputed here from the raw observation and the
 * origin event list -- never trusted from a single header):
 *   MISS: origin counter +1, a matching origin event exists, and a
 *     cache entry was created (entry count grew);
 *   HIT:  origin counter unchanged, the entry id is the id of an
 *     entry stored by an earlier MISS in this run, and the body
 *     hash equals that stored entry's body hash;
 *   BYPASS: origin counter +1, a matching origin event exists, and
 *     the entry count did not grow.
 *
 * A header state contradicted by the behaviour leg is a conflict
 * (§8.8 CACHE_EVIDENCE_CONFLICT), not a confirmation and not a
 * bleed. When the origin journal is unavailable
 * (`origin_events_available` false), no origin event can be found,
 * so every MISS/BYPASS loses its behaviour leg (§8.4).
 */

import type { Observation, OracleInput, RawObservation } from "./input.ts";

export type VerifiedState = "MISS" | "HIT" | "BYPASS" | "CACHE_STATE_UNKNOWN";

export interface CacheCheck {
  /** The state this Oracle is willing to trust downstream, or null. */
  confirmed: VerifiedState | null;
  /** "conflict" | "unknown" | null -- which §8 diagnostic, if any. */
  problem: "conflict" | "unknown" | null;
  /** True when a matching origin event was found for this request. */
  eventFound: boolean;
}

const CONFIRMED: ReadonlySet<string> = new Set(["MISS", "HIT", "BYPASS"]);

function headerOf(raw: RawObservation, name: string): string | null {
  const wanted = name.toLowerCase();
  for (const [key, value] of Object.entries(raw.response_headers)) {
    if (key.trim().toLowerCase() === wanted) return value;
  }
  return null;
}

/** Case-insensitive response-header lookup (T008: used by the
 *  Oracle's own revalidation and Vary:* rules in oracle.ts). */
export function responseHeader(raw: RawObservation, name: string): string | null {
  return headerOf(raw, name);
}

/** True when the response's Vary contains the `*` token (RFC 9111
 *  §4.1: the stored response must never be reused — T008, §11.3 E03). */
export function varyIncludesStar(raw: RawObservation): boolean {
  const vary = headerOf(raw, "vary");
  if (vary === null) return false;
  return vary.split(",").map((t) => t.trim()).includes("*");
}

/** True when the response demands revalidation this release does
 *  not implement: `Cache-Control: no-cache` or `max-age=0`
 *  (§8.6, T008, §11.3 E07/E08). */
export function requiresRevalidation(raw: RawObservation): boolean {
  const cacheControl = headerOf(raw, "cache-control");
  if (cacheControl === null) return false;
  for (const token of cacheControl.split(",")) {
    const directive = token.trim().toLowerCase();
    if (!directive) continue;
    // RFC 9111-tolerant parsing (T014, T008 P2-2 — mirrors the
    // production classifier): strip whitespace around '=' and any
    // quoted-string parameter, so `max-age = 0`, `max-age="0"` and
    // `no-cache="field"` trigger exactly like their compact forms.
    const eq = directive.indexOf("=");
    const name = (eq === -1 ? directive : directive.slice(0, eq)).trim();
    const value =
      eq === -1
        ? ""
        : directive
            .slice(eq + 1)
            .trim()
            .replace(/^["']|["']$/g, "")
            .trim();
    if (name === "no-cache") return true;
    if (name === "max-age" && eq !== -1) {
      // Integer-only, like the production classifier's int(value):
      // `max-age=0.0` is not a valid delta-seconds value and must
      // not trigger (parity with production).
      if (/^[+-]?\d+$/.test(value) && parseInt(value, 10) === 0) return true;
    }
  }
  return false;
}

export function varyAcceptPresent(raw: RawObservation): boolean | null {
  const vary = headerOf(raw, "vary");
  if (vary === null) return false;
  const tokens = vary.split(",").map((t) => t.trim().toLowerCase());
  return tokens.includes("accept") || tokens.includes("*");
}

export function eventPresent(
  input: OracleInput,
  obs: Observation,
  expectedAccept: string,
): boolean {
  if (!input.origin_events_available) return false;
  return input.origin_events.some(
    (ev) =>
      ev.index > obs.origin_counter_before &&
      ev.index <= obs.origin_counter_after &&
      ev.accept === expectedAccept &&
      ev.status === obs.response_status,
  );
}

/**
 * Verify one proxied observation's cache state from both legs.
 * `earlier` is the list of raw observations with a smaller request
 * index, each paired with the state *this* Oracle confirmed for it
 * (null when it confirmed none) — used to tie a HIT to the MISS
 * that stored its entry. The Oracle never reads the production
 * runner's `verified_cache_state` (T014, T013-F05): the claimed
 * state is the raw cache-status header, and a storing MISS is one
 * this Oracle confirmed itself. Either coupling could otherwise
 * inherit a production verification error as an input.
 */
export function verifyCacheState(
  input: OracleInput,
  obs: Observation,
  raw: RawObservation,
  earlier: Array<{ raw: RawObservation; confirmed: string | null }>,
): CacheCheck {
  const headerStatus = raw.cache_status_header;
  // T014 (T013-F05): the claim is the raw header the proxy sent,
  // exactly like the production verifier (cache_evidence module), whose
  // claim is `header.status` — never the production runner's
  // `verified_cache_state`.
  const claimed = headerStatus;
  const delta = obs.origin_counter_delta;
  const rep = input.contract.representations[obs.requested_representation];
  const eventFound = eventPresent(input, obs, rep.accept);

  const conflict = (): CacheCheck => ({
    confirmed: null,
    problem: "conflict",
    eventFound,
  });
  const unknown = (): CacheCheck => ({
    confirmed: null,
    problem: "unknown",
    eventFound,
  });

  // A header state contradicted by the counter is a conflict (§8.8),
  // whether the claimed state is that header state or UNKNOWN.
  if (
    headerStatus !== null &&
    CONFIRMED.has(headerStatus) &&
    ((headerStatus === "HIT" && delta !== 0) ||
      ((headerStatus === "MISS" || headerStatus === "BYPASS") && delta !== 1))
  ) {
    return conflict();
  }
  if (claimed === null) return unknown();
  if (!CONFIRMED.has(claimed)) return unknown();
  // A confirmed state whose legs disagree is a conflict.
  if (claimed === "HIT" && delta !== 0) return conflict();
  if ((claimed === "MISS" || claimed === "BYPASS") && delta !== 1) {
    return conflict();
  }

  if (claimed === "MISS") {
    if (!raw.cache_key_sha256 || !raw.cache_entry_id) return unknown();
    if (!eventFound) return unknown();
    const created =
      raw.cache_entry_count_before !== null &&
      raw.cache_entry_count_after !== null &&
      raw.cache_entry_count_after > raw.cache_entry_count_before;
    if (!created) return unknown();
    return { confirmed: "MISS", problem: null, eventFound };
  }
  if (claimed === "HIT") {
    if (!raw.cache_key_sha256 || !raw.cache_entry_id) return unknown();
    // The stored entry is the one the *most recent* storing MISS
    // wrote under this entry id: cache keys are deterministic, so
    // an earlier experiment's MISS under the same key may share the
    // id while holding a different body (e.g. a URI-only key reused
    // across experiments). Only the latest storing MISS is the entry
    // this HIT can be serving. The storing MISS must be one this
    // Oracle confirmed itself (T014, T013-F05) — never the
    // production runner's `verified_cache_state`.
    const storing = earlier.filter(
      (prev) =>
        prev.raw.cache_entry_id !== null &&
        prev.raw.cache_entry_id === raw.cache_entry_id &&
        prev.confirmed === "MISS",
    );
    const stored = storing.length > 0 ? storing[storing.length - 1] : undefined;
    if (stored === undefined) return unknown();
    if (stored.raw.body_sha256 !== raw.body_sha256) return unknown();
    return { confirmed: "HIT", problem: null, eventFound };
  }
  // BYPASS
  if (!eventFound) return unknown();
  const countUnchanged =
    raw.cache_entry_count_before !== null &&
    raw.cache_entry_count_after !== null &&
    raw.cache_entry_count_after === raw.cache_entry_count_before;
  if (!countUnchanged) return unknown();
  return { confirmed: "BYPASS", problem: null, eventFound };
}
```

## oracle/src/index.ts

- SHA-256：`ca5d1464f40d53544ee7a35d59442f0515ee5960b47feb63345cf87e082cfde2`
- 字节数：1264

```
/**
 * Oracle CLI (P032 T007, PROJECT_BOOK §12).
 *
 * Usage:
 *   node oracle/src/index.ts --input <oracle-input.json> --output <result.json>
 *
 * Reads only the contract + raw observations in the input file and
 * writes the independently computed verdict, diagnostics and first
 * error. It never imports production Python code and never reads a
 * production verdict (§12.3).
 */

import { readFileSync, writeFileSync } from "node:fs";
import { parseOracleInput } from "./input.ts";
import { evaluateScenario } from "./oracle.ts";

function parseArgs(argv: string[]): { input: string; output: string } {
  let input = "";
  let output = "";
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--input" && i + 1 < argv.length) input = argv[i + 1];
    if (argv[i] === "--output" && i + 1 < argv.length) output = argv[i + 1];
  }
  if (!input || !output) {
    throw new Error("usage: node oracle/src/index.ts --input <oracle-input.json> --output <result.json>");
  }
  return { input, output };
}

const { input, output } = parseArgs(process.argv.slice(2));
const oracleInput = parseOracleInput(readFileSync(input, "utf-8"));
const result = evaluateScenario(oracleInput);
writeFileSync(output, JSON.stringify(result, null, 2) + "\n", "utf-8");
```

## oracle/src/input.ts

- SHA-256：`1d665587cd8e9706eb897827133890a1bb4e60ee653cf54d8e243df2b34a2d43`
- 字节数：2888

```
/**
 * Oracle input types and loading (P032 T007, PROJECT_BOOK §12.2).
 *
 * The Oracle reads exactly three things: the frozen contract JSON, the
 * raw per-request observations, and the origin-event / reset evidence.
 * It never reads a production verdict or a production diagnostic
 * (§12.3). The input file is `accepttwin.oracle-input/v1`, written by
 * the S0 harness from the same adjudication inputs the production
 * classifier received -- the Oracle judges the same evidence, with
 * its own logic.
 */

export interface Representation {
  accept: string;
  expected_status: number;
  expected_content_type: string;
  sentinel: string;
}

export interface ContractInput {
  schema: string;
  contract_id: string;
  name: string;
  url: string;
  origin_url: string;
  representations: Record<string, Representation>;
  request_headers: Record<string, unknown>;
  cache_behavior: {
    mode: string;
    vary_accept: string;
    max_age_seconds: number | null;
  };
  limits: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface Observation {
  request_index: number;
  experiment_id: string;
  requested_representation: string;
  response_status: number;
  response_content_type: string;
  body_sha256: string;
  sentinel_match: boolean;
  cache_status: string | null;
  cache_key_sha256: string | null;
  cache_entry_id: string | null;
  origin_counter_before: number;
  origin_counter_after: number;
  origin_counter_delta: number;
}

export interface RawObservation extends Observation {
  method: string;
  url: string;
  accept: string;
  body_size: number;
  sentinel_sha256: string;
  response_headers: Record<string, string>;
  cache_status_header: string | null;
  verified_cache_state: string | null;
  cache_verification_reasons: string[];
  cache_entry_count_before: number | null;
  cache_entry_count_after: number | null;
  origin_event_present: boolean | null;
  transport_error: string | null;
}

export interface OriginEventInput {
  index: number;
  method: string;
  path: string;
  accept: string;
  status: number;
}

export interface ResetInput {
  namespace: string;
  success: boolean;
  entries_before: number;
  entries_after: number;
  entries_removed: number;
}

export interface OracleInput {
  format: string;
  contract: ContractInput;
  observations: Observation[];
  raw_observations: RawObservation[];
  origin_events: OriginEventInput[];
  origin_events_available: boolean;
  resets: ResetInput[];
}

export function parseOracleInput(text: string): OracleInput {
  const data: unknown = JSON.parse(text);
  if (typeof data !== "object" || data === null) {
    throw new Error("oracle input must be a JSON object");
  }
  const input = data as OracleInput;
  if (input.format !== "accepttwin.oracle-input/v1") {
    throw new Error(`unexpected oracle input format: ${String(input.format)}`);
  }
  return input;
}
```

## oracle/src/oracle.ts

- SHA-256：`5587b79f0632c0e1d78b2cd1fc9385e97e4107cc509f4e0dbaed0563327e30a4`
- 字节数：19132

```
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
```

## oracle/package.json

- SHA-256：`67b49fbfc1f91be49ded322b5dd9fb6cea3bbaf4c38162b90937e58b670222e6`
- 字节数：391

```
{"description":"AcceptTwin independent Oracle (P032 T007): TypeScript re-implementation of PROJECT_BOOK §5.3/§8/§9. Reads only the frozen contract and raw observations; never imports production Python code and never reads a production verdict.","engines":{"node":">=24"},"name":"accepttwin-oracle","private":true,"scripts":{"oracle":"node src/index.ts"},"type":"module","version":"1.0.0"}
```

## oracle/tsconfig.json

- SHA-256：`6c2990eca5e66ed9f274661ac81bf156b6a3487d58141b9be2c5dc73bcda3a12`
- 字节数：291

```
{
  "compilerOptions": {
    "erasableSyntaxOnly": true,
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "noEmit": true,
    "skipLibCheck": true,
    "strict": true,
    "target": "ES2024",
    "allowImportingTsExtensions": true
  },
  "include": [
    "src/**/*.ts"
  ]
}
```

## scripts/build_reports_48.py

- SHA-256：`89713259380c475aa371d8a1f576a3e03c3280dcba650c906f20317f919af30a`
- 字节数：5946

```
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
```

## scripts/clean_evidence.py

- SHA-256：`764f71f2531fb282dd11b256ac12056fb14f80f926346fcd63e8c9fd2e28f082`
- 字节数：3302

```
#!/usr/bin/env python3
"""Minimal workspace-bounded cleanup command (P032 T011, §17.3).

Deletes only the evidence / temporary files the caller names, and
only when each one resolves to a regular file *inside the
``evidence/`` subtree* of the workspace root (T014, T011 P2: the
default deletable subtree is narrowed to ``evidence/`` — an
operator explicitly naming a file can no longer delete source
files, or any other file outside ``evidence/``, by mistake).
Anything else is refused and nothing is deleted.

Usage::

    python scripts/clean_evidence.py [--root DIR] [--dry-run] FILE [FILE ...]

* ``--root`` defaults to the project root (the parent of ``scripts/``).
* Paths may be relative to the root or absolute; absolute paths
  outside the root, ``..`` escapes, symlinks, directories, the
  root itself, and any file outside ``evidence/`` are all refused.
* All targets are validated before anything is deleted, so one bad
  target blocks the whole batch — there are no partial deletions.
* ``--dry-run`` prints what would be deleted and deletes nothing.

Exit codes: 0 = all named files deleted (or, with ``--dry-run``,
listed); 2 = refused (bad target, nothing deleted); 1 = unexpected
error. This command never runs a shell, never takes a glob, and
never deletes anything it was not explicitly given.

See :mod:`accepttwin.privacy` for the enforced rules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/clean_evidence.py` from the repo root
# as well as `python -m` from anywhere: make `src/` importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accepttwin.privacy import PrivacyError, delete_evidence_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Delete named files under evidence/ inside the workspace "
            "(P032 T011, PROJECT_BOOK §17.3; T014 narrows the default "
            "deletable subtree to evidence/ — files outside evidence/ "
            "are refused even when explicitly named). Refuses anything "
            "outside the workspace root."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="file(s) to delete, relative to --root or absolute; "
        "must resolve under evidence/",
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="workspace root; targets must resolve inside it "
        "(default: project root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be deleted and delete nothing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        deleted = delete_evidence_files(
            args.root,
            args.paths,
            dry_run=args.dry_run,
            allowed_subtrees=("evidence",),
        )
    except PrivacyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    verb = "would delete" if args.dry_run else "deleted"
    for path in deleted:
        print(f"{verb}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## scripts/embed_report.py

- SHA-256：`bb6f7a7325bf745ab738759bd74e8c67945cfdee2a35195e1032dedba3da856a`
- 字节数：21947

```
"""Embed an ``accepttwin.report/v1`` JSON report into a single
self-contained HTML page (P032 T010).

Reads one formal report (``evidence/Reports/<sid>.json``, built by
T009), validates it fail-closed, prints a privacy preview, and
writes one HTML file that opens fully offline: the stylesheet
(``report-ui/styles.css``) and the compiled UI bundle
(``report-ui/report-ui.js``, built from ``report-ui/src/*.ts``)
are inlined, the report JSON is embedded as a
``<script type="application/json">`` payload, and the page
contains no remote reference of any kind (no CDN, no webfont, no
image, no iframe, no external link).

Privacy (PROJECT_BOOK §7.12 I-12, §17.2, §4.2 constraint 7):

* the report itself never carries raw body text or a sensitive
  request header (T009 enforces this at build time); this script
  re-scans for forbidden keys (case-insensitive) and for the
  Sentinel literals before writing anything;
* the privacy preview is printed to stdout *before* any file is
  written, and the generated page repeats the same checklist as
  its §4.3 area F (item 10 of the T010 interface);
* the finished HTML is scanned again (Sentinel literals, remote
  references) — a single hit fails the run with exit code 1 and
  writes nothing.

Determinism: the embedded payload is ``json.dumps(sort_keys=True,
indent=2)`` of the report as loaded; the template, CSS and JS
bundle are fixed inputs, so re-running the script on the same
report produces byte-identical HTML. No timestamp, duration or
random value is ever added.

Hash check: the stored ``report_hash`` is recomputed with
:func:`accepttwin.report_builder.compute_report_hash` (the single
canonical implementation — this script never re-implements
canonical JSON) and must match, otherwise the run fails.

Baseline expectations (§4.3 area B): the "expected" column comes
from the run's contract (``--contract`` — only the three safe
fields per representation are copied: ``accept``,
``expected_status``, ``expected_content_type``; Sentinel values
are never copied) or, when no contract is given, from the frozen
§5.1.2 constants (identical across all 48 contracts, verified in
T010). The baseline block is embedded as a second, separate JSON
payload — the report JSON itself is never modified.

Usage (run from the repository root)::

    .venv/bin/python scripts/embed_report.py evidence/Reports/C11.json \\
        --contract evidence/Golden/C11/contract.json -o evidence/Reports/html/C11.html
    .venv/bin/python scripts/embed_report.py --all-48
    .venv/bin/python scripts/embed_report.py evidence/Reports/C11.json --check-only

``--all-48`` builds all 48 single-report pages plus
``index.html`` (the 48-scenario summary) from the existing report
samples — it never re-runs an experiment (live re-runs belong to
T012). The summary is derived from the 48 report JSONs and
cross-checked field by field against
``evidence/Reports/REPORTS_SUMMARY.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "unit"))

from accepttwin.contract import parse_contract  # noqa: E402
from accepttwin.report_builder import compute_report_hash  # noqa: E402
from accepttwin.url_guard import URLGuardError, validate_loopback_url  # noqa: E402
from independent_schema_validator import validate as validate_schema  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORT_UI_DIR = ROOT / "report-ui"
REPORTS_DIR = ROOT / "evidence" / "Reports"
GOLDEN_DIR = ROOT / "evidence" / "Golden"

SCENARIO_IDS: tuple[str, ...] = tuple(
    [f"C{i:02d}" for i in range(1, 25)] + [f"E{i:02d}" for i in range(1, 25)]
)

VERDICTS: tuple[str, ...] = (
    "PASS_OBSERVED",
    "ORIGIN_NEGOTIATION_ERROR",
    "REPRESENTATION_BLEED",
    "CONTRACT_MISMATCH",
    "INCONCLUSIVE",
)

#: Frozen §5.1.2 baseline expectations (identical in all 48
#: contracts — verified by T010 against evidence/Golden/*/contract.json).
FROZEN_BASELINE: dict[str, dict[str, object]] = {
    "html": {
        "accept": "text/html",
        "expected_status": 200,
        "expected_content_type": "text/html; charset=utf-8",
    },
    "markdown": {
        "accept": "text/markdown",
        "expected_status": 200,
        "expected_content_type": "text/markdown; charset=utf-8",
    },
}

#: Keys that must never appear in a report or in generated HTML,
#: matched case-insensitively (§7.12 I-12, §5.1.3, §17.2).
_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "body",
        "body_text",
        "response_body",
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
    }
)

#: Sentinel literals — must never appear in generated HTML (§5.3).
_SENTINELS: tuple[str, ...] = ("AT_HTML_SENTINEL_001", "AT_MARKDOWN_SENTINEL_001")

def _is_loopback_host(host: str) -> bool:
    host = host.strip("[]").lower()
    if host == "localhost":
        return True
    if host.startswith("127."):
        parts = host.split(".")
        return (
            len(parts) == 4
            and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
        )
    return host == "::1"


class EmbedError(ValueError):
    """Raised when a report cannot be embedded fail-closed."""


# ---------------------------------------------------------------------------
# Fail-closed input checks
# ---------------------------------------------------------------------------


def _reject_forbidden_keys(value: object, where: str = "report") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise EmbedError(f"forbidden key {key!r} in {where}")
            _reject_forbidden_keys(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, f"{where}[{index}]")


def _check_no_sentinels(text: str, where: str) -> None:
    for sentinel in _SENTINELS:
        if sentinel in text:
            raise EmbedError(f"Sentinel literal {sentinel} found in {where}")


def _check_report_structure(report: dict) -> None:
    required = (
        "schema",
        "project",
        "scenario_id",
        "input",
        "observations",
        "diagnostics",
        "verdict",
        "first_error",
        "first_error_experiment_id",
        "critical_count",
        "warning_count",
        "reasons",
        "oracle",
        "oracle_parity",
        "final",
        "report_hash",
    )
    missing = [key for key in required if key not in report]
    if missing:
        raise EmbedError(f"report is missing top-level fields: {missing}")
    if report["schema"] != "accepttwin.report/v1":
        raise EmbedError(f"unexpected report schema: {report['schema']!r}")
    if report["verdict"] not in VERDICTS:
        raise EmbedError(f"unknown verdict: {report['verdict']!r}")
    observations = report["observations"]
    if not isinstance(observations, list) or len(observations) != 8:
        raise EmbedError(
            f"exactly 8 observations are required, got {len(observations) if isinstance(observations, list) else type(observations).__name__}"
        )
    indices = sorted(obs["request_index"] for obs in observations)
    if indices != list(range(1, 9)):
        raise EmbedError(f"observations must cover requests 001-008, got {indices}")
    diagnostics = report["diagnostics"]
    critical = sum(1 for d in diagnostics if d["severity"] == "CRITICAL")
    warning = sum(1 for d in diagnostics if d["severity"] == "WARNING")
    if critical != report["critical_count"] or warning != report["warning_count"]:
        raise EmbedError(
            "diagnostic counts disagree with the report: "
            f"critical {critical}!={report['critical_count']} or "
            f"warning {warning}!={report['warning_count']}"
        )
    for key in ("url", "origin_url"):
        url = report["input"][key]
        try:
            validate_loopback_url(url)
        except (URLGuardError, ValueError) as exc:
            raise EmbedError(f"input.{key} is not a loopback URL: {exc}") from exc


def load_report(path: Path) -> dict:
    """Load and fully validate one report JSON (fail-closed)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EmbedError(f"cannot read report {path}: {exc}") from exc
    _check_no_sentinels(text, f"report file {path}")
    try:
        report = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EmbedError(f"report {path} is not valid JSON: {exc}") from exc
    if not isinstance(report, dict):
        raise EmbedError(f"report {path} is not a JSON object")
    errors = validate_schema(report)
    if errors:
        raise EmbedError(f"report {path} fails the independent Schema check: {errors}")
    _reject_forbidden_keys(report)
    _check_report_structure(report)
    recomputed = compute_report_hash(report)
    if recomputed != report["report_hash"]:
        raise EmbedError(
            f"report_hash mismatch for {report.get('scenario_id')}: "
            f"stored {report['report_hash']}, recomputed {recomputed}"
        )
    return report


def load_baseline(contract_path: Path | None) -> dict:
    """Baseline expectations from a contract, or §5.1.2 constants.

    Only the three safe fields per representation are copied —
    Sentinel values are never read into the baseline block.
    """
    if contract_path is None:
        return json.loads(json.dumps(FROZEN_BASELINE))
    try:
        contract = parse_contract(json.loads(contract_path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise EmbedError(f"cannot load contract {contract_path}: {exc}") from exc
    baseline: dict[str, dict[str, object]] = {}
    for rep in ("html", "markdown"):
        entry = contract.representations[rep]
        baseline[rep] = {
            "accept": entry.accept,
            "expected_status": entry.expected_status,
            "expected_content_type": entry.expected_content_type,
        }
    return baseline


# ---------------------------------------------------------------------------
# HTML assembly and output scanning
# ---------------------------------------------------------------------------


def _load_template_assets() -> tuple[str, str, str]:
    template = (REPORT_UI_DIR / "index.html").read_text(encoding="utf-8")
    styles = (REPORT_UI_DIR / "styles.css").read_text(encoding="utf-8")
    script = (REPORT_UI_DIR / "report-ui.js").read_text(encoding="utf-8")
    for name, asset in (("index.html", template), ("styles.css", styles), ("report-ui.js", script)):
        _check_no_sentinels(asset, name)
    return template, styles, script


def _embed_json(payload: object) -> str:
    """Serialise a payload for a ``<script type="application/json">``
    block. ``</`` is escaped as ``<\\/`` (valid JSON, identical
    value on parse) so no payload string can close the script tag.
    """
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
    return text.replace("</", "<\\/")


def _scan_finished_html(html: str, *, allow_relative_links: bool) -> None:
    """Fail-closed scan of finished HTML: no Sentinel literal, no
    remote reference, no external-resource tag of any kind."""
    _check_no_sentinels(html, "generated HTML")
    if "<link" in html or "<iframe" in html or "<img" in html:
        raise EmbedError("generated HTML contains <link>, <iframe> or <img>")
    # Exactly four <script> tags: three application/json payloads
    # plus the one inline UI bundle. Any other script tag (in
    # particular one with a src) fails.
    if html.count("<script") != 4 or "<script src" in html:
        raise EmbedError("generated HTML does not contain exactly the four expected inline <script> tags")
    if "@import" in html or "url(" in html:
        raise EmbedError("generated HTML contains @import or url()")
    if "http://" in html or "https://" in html:
        # Only loopback http(s) URLs may appear (report evidence
        # request_url / redirect_target values, e.g. E12/E22).
        # Protocol-relative URLs cannot occur: href values are
        # validated strictly below, there is no src attribute, and
        # the CSS/JS contain no protocol-relative reference.
        for match in re.finditer(r"https?://([^\s\"'<>/:]+)", html):
            if not _is_loopback_host(match.group(1)):
                raise EmbedError(
                    f"generated HTML contains a non-loopback URL host: {match.group(0)}"
                )
    hrefs = re.findall(r'href="([^"]*)"', html)
    for href in hrefs:
        if not allow_relative_links:
            raise EmbedError(f"generated HTML contains a link href={href!r}")
        if not re.fullmatch(r"[A-Za-z0-9_.\-]+\.html", href):
            raise EmbedError(f"generated HTML contains a non-relative href={href!r}")
    if "data:" in html:
        raise EmbedError("generated HTML contains a data: URI")


def _render(
    template: str,
    styles: str,
    script: str,
    *,
    report: dict | None,
    baseline: dict | None,
    summary: dict | None,
    allow_relative_links: bool,
) -> str:
    html = template
    html = html.replace("<!--ACCEPTTWIN:STYLES-->", styles, 1)
    html = html.replace("<!--ACCEPTTWIN:SCRIPT-->", script, 1)
    html = html.replace(
        "<!--ACCEPTTWIN:REPORT_JSON-->",
        _embed_json(report) if report is not None else "",
        1,
    )
    html = html.replace(
        "<!--ACCEPTTWIN:BASELINE_JSON-->",
        _embed_json(baseline) if baseline is not None else "",
        1,
    )
    html = html.replace(
        "<!--ACCEPTTWIN:SUMMARY_JSON-->",
        _embed_json(summary) if summary is not None else "",
        1,
    )
    for token in ("ACCEPTTWIN:STYLES", "ACCEPTTWIN:SCRIPT", "ACCEPTTWIN:REPORT_JSON", "ACCEPTTWIN:BASELINE_JSON", "ACCEPTTWIN:SUMMARY_JSON"):
        if token in html:
            raise EmbedError(f"template placeholder {token} was not replaced")
    _scan_finished_html(html, allow_relative_links=allow_relative_links)
    return html


# ---------------------------------------------------------------------------
# Privacy preview (printed before any file is written)
# ---------------------------------------------------------------------------


def print_privacy_preview(report: dict, out_name: str, baseline_source: str) -> None:
    print("PRIVACY PREVIEW — export happens only after this preview")
    print(f"  report:        {report['scenario_id']} ({report['verdict']})")
    print(f"  report_hash:   {report['report_hash']}")
    print(f"  output file:   {out_name}")
    print(f"  baseline from: {baseline_source}")
    print("  contains raw body text:        false")
    print("  contains sensitive headers:    false (no Authorization / Cookie)")
    print("  contains allow-listed headers: true (Accept, User-Agent, Accept-Encoding, Accept-Language)")
    print("  contains raw body content:     false")
    print("  contains body hashes:          true (SHA-256 + Sentinel match flags only)")
    print("  body text displayed:           never — hashes and match flags only")
    print("  remote references in output:   none (scan passed)")
    print("  Sentinel literals in output:   none (scan passed)")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def build_single(
    report_path: Path,
    contract_path: Path | None,
    template: str,
    styles: str,
    script: str,
) -> tuple[str, dict, str]:
    """Return (html, report, out_name) for one report file."""
    report = load_report(report_path)
    baseline = load_baseline(contract_path)
    baseline_source = (
        f"contract {contract_path}" if contract_path is not None else "frozen §5.1.2 constants"
    )
    html = _render(
        template,
        styles,
        script,
        report=report,
        baseline=baseline,
        summary=None,
        allow_relative_links=False,
    )
    return html, report, baseline_source


def cmd_single(args: argparse.Namespace) -> int:
    template, styles, script = _load_template_assets()
    html, report, baseline_source = build_single(
        args.report, args.contract, template, styles, script
    )
    out_name = str(args.out) if args.out is not None else f"{report['scenario_id']}.html"
    print_privacy_preview(report, out_name, baseline_source)
    if args.check_only:
        print(f"CHECK ONLY: {report['scenario_id']} OK (nothing written)")
        return 0
    if args.out is None:
        raise EmbedError("--out is required (no default output path)")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"WROTE {args.out} ({len(html.encode('utf-8'))} bytes)")
    return 0


def cmd_all_48(args: argparse.Namespace) -> int:
    template, styles, script = _load_template_assets()
    summary_path = REPORTS_DIR / "REPORTS_SUMMARY.json"
    try:
        recorded = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EmbedError(f"cannot read {summary_path}: {exc}") from exc
    recorded_samples = recorded.get("samples", {})

    pages: dict[str, str] = {}
    rows: list[dict] = []
    counts: dict[str, int] = {verdict: 0 for verdict in VERDICTS}
    for sid in SCENARIO_IDS:
        report_path = REPORTS_DIR / f"{sid}.json"
        contract_path = GOLDEN_DIR / sid / "contract.json"
        html, report, _baseline_source = build_single(
            report_path, contract_path, template, styles, script
        )
        recorded_row = recorded_samples.get(sid)
        if recorded_row is None:
            raise EmbedError(f"REPORTS_SUMMARY.json has no row for {sid}")
        for field in ("verdict", "first_error", "oracle_parity", "report_hash"):
            if recorded_row[field] != report[field]:
                raise EmbedError(
                    f"{sid}: {field} disagrees with REPORTS_SUMMARY.json "
                    f"({recorded_row[field]!r} != {report[field]!r})"
                )
        pages[sid] = html
        counts[report["verdict"]] += 1
        rows.append(
            {
                "scenario_id": sid,
                "verdict": report["verdict"],
                "first_error": report["first_error"],
                "critical_count": report["critical_count"],
                "warning_count": report["warning_count"],
                "oracle_parity": report["oracle_parity"],
                "final": report["final"],
                "report_hash": report["report_hash"],
            }
        )
    summary = {
        "generated_from": "evidence/Reports/<sid>.json (48 report samples, no experiment re-run)",
        "total": len(rows),
        "counts": counts,
        "rows": rows,
    }
    index_html = _render(
        template,
        styles,
        script,
        report=None,
        baseline=None,
        summary=summary,
        allow_relative_links=True,
    )

    out_dir = args.out_dir
    print("PRIVACY PREVIEW — 48 pages (export happens only after this preview)")
    print(f"  pages:         48 single-report pages + index.html -> {out_dir}")
    print(f"  verdicts:      {counts}")
    print(f"  oracle parity: {sum(1 for r in rows if r['oracle_parity'] is True)}/48")
    print("  contains raw body text:        false (all 48 reports scanned)")
    print("  contains sensitive headers:    false (all 48 reports scanned)")
    print("  contains body hashes:          true (SHA-256 + Sentinel match flags only)")
    print("  remote references in output:   none (all 49 pages scanned)")
    print("  Sentinel literals in output:   none (all 49 pages scanned)")
    if args.check_only:
        print("CHECK ONLY: 48/48 + index OK (nothing written)")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for sid in SCENARIO_IDS:
        (out_dir / f"{sid}.html").write_text(pages[sid], encoding="utf-8")
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    total_bytes = sum(len(p.encode("utf-8")) for p in pages.values()) + len(
        index_html.encode("utf-8")
    )
    print(f"WROTE 49 files to {out_dir} ({total_bytes} bytes total)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Embed an accepttwin.report/v1 JSON report into a self-contained offline HTML page."
    )
    parser.add_argument("report", nargs="?", type=Path, help="report JSON file (single mode)")
    parser.add_argument("--contract", type=Path, default=None, help="run contract JSON (baseline expectations; default: frozen §5.1.2 constants)")
    parser.add_argument("-o", "--out", type=Path, default=None, help="output HTML file (single mode)")
    parser.add_argument("--all-48", action="store_true", help="build all 48 pages + index.html summary")
    parser.add_argument("--out-dir", type=Path, default=REPORTS_DIR / "html", help="output directory for --all-48 (default: evidence/Reports/html)")
    parser.add_argument("--check-only", action="store_true", help="validate + print the privacy preview, write nothing")
    args = parser.parse_args(argv)
    try:
        if args.all_48:
            if args.report is not None:
                raise EmbedError("do not pass a report file together with --all-48")
            return cmd_all_48(args)
        if args.report is None:
            parser.error("a report file is required (or --all-48)")
        return cmd_single(args)
    except EmbedError as exc:
        print(f"EMBED_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

## scripts/run_all_48.py

- SHA-256：`a6b3347845909bda9a43d1323e6bf528e23277e6682f1c13c623cddaa6142fec`
- 字节数：10225

```
"""48-scenario Golden runner (P032 T008): execute C01-C24 + E01-E24.

Writes per-scenario evidence under ``evidence/Golden/<sid>/`` (same
file set as ``evidence/S0/``: ``raw-observations.json``,
``contract.json``, ``oracle-input.json``, ``production.json``,
``oracle.json``, ``scenario.json``) and the suite summary to
``evidence/Golden/ALL48_SUMMARY.json``.

Also performs the two multi-run checks that extend the S0 gate:

* stable bleed reproduction (§8.2, §11.3): E13 re-executed 3 times
  on fresh services (independent cache clears), each must yield
  REPRESENTATION_BLEED with the full dual-evidence chain;
* determinism spot check (§7.8, §10.4): E01 re-executed 3 times,
  each on a fresh pair with fresh OS-assigned ports, the canonical
  report hash must be identical all 3 times (the full 100-run check
  lives in scripts/run_s0.py for C01).

Exit code 0 only when every §11 item passes. This script never
declares the suite PASS on its own say-so: ``tests/golden/``
re-executes every scenario live and re-checks the same expectations.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from s0_harness import (  # noqa: E402
    ALL_SCENARIO_IDS,
    EXTENDED_FIXTURE_DIR,
    EXTENDED_SCENARIO_IDS,
    FIXTURE_DIR,
    ROOT,
    SCENARIO_IDS,
    check_parity,
    oracle_input_dict,
    run_oracle,
    run_scenario,
)

EVIDENCE_DIR = ROOT / "evidence" / "Golden"

HEALTHY_48 = [
    "C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18",
    "E01", "E02", "E03", "E04", "E05", "E06", "E15", "E16",
]
KNOWN_FAILURES_48 = [
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
    "C15", "C16", "C19", "C24",
    "E09", "E10", "E11", "E13", "E14", "E23", "E24",
]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _suite_of(scenario_id: str) -> tuple[Path, str]:
    """(fixture dir, contract prefix) for one scenario id."""
    if scenario_id in SCENARIO_IDS:
        return FIXTURE_DIR, "s0"
    return EXTENDED_FIXTURE_DIR, "ext"


def run_all() -> dict:
    """Execute the full 48-scenario suite and return the summary dict."""
    started = time.perf_counter()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    scenarios: dict[str, dict] = {}
    for sid in ALL_SCENARIO_IDS:
        fixture_dir, prefix = _suite_of(sid)
        outcome = run_scenario(
            sid,
            fixture_dir=fixture_dir,
            contract_prefix=prefix,
            namespace_prefix=f"all48-{sid}",
        )
        sdir = EVIDENCE_DIR / sid
        sdir.mkdir(parents=True, exist_ok=True)
        outcome.run.write_evidence(sdir / "raw-observations.json")
        _write_json(sdir / "contract.json", outcome.contract.as_dict())
        injection = outcome.fixture.get("injection") or {}
        oracle_input = oracle_input_dict(
            outcome.contract,
            outcome.run,
            outcome.adj_origin_events,
            origin_events_available=(
                injection.get("kind") != "origin_events_unavailable"
            ),
        )
        _write_json(sdir / "oracle-input.json", oracle_input)
        _write_json(sdir / "production.json", outcome.production.as_dict())
        oracle_result = run_oracle(
            sdir / "oracle-input.json", sdir / "oracle.json"
        )
        parity = check_parity(outcome, oracle_result)
        fixture = outcome.fixture
        expected_ok = (
            outcome.production.verdict == fixture["expected_verdict"]
            and outcome.production.first_error == fixture["expected_first_error"]
            and outcome.production.first_error_experiment_id
            == fixture["expected_first_error_experiment_id"]
            and outcome.diagnostics_projection == fixture["expected_diagnostics"]
        )
        scenarios[sid] = {
            "scenario_id": sid,
            "suite": "S0" if sid in SCENARIO_IDS else "extended",
            "expected_verdict": fixture["expected_verdict"],
            "verdict": outcome.production.verdict,
            "expected_first_error": fixture["expected_first_error"],
            "first_error": outcome.production.first_error,
            "first_error_experiment_id": outcome.production.first_error_experiment_id,
            "expected_diagnostics": fixture["expected_diagnostics"],
            "diagnostics": outcome.diagnostics_projection,
            "oracle_verdict": oracle_result["verdict"],
            "oracle_first_error": oracle_result["first_error"],
            "oracle_parity": parity["parity"],
            "oracle_mismatches": parity["mismatches"],
            "expected_ok": expected_ok,
            "duration_seconds": round(outcome.duration_seconds, 4),
            "report_hash": outcome.report_hash,
            "origin_counter_delta_total": sum(
                obs.origin_counter_delta for obs in outcome.run.observations
            ),
            "request_count": len(outcome.run.observations),
            "reset_count": len(outcome.run.reset_evidence),
            "step_count": len(outcome.run.step_log),
            "warm_hm_requests": [
                obs.request_index
                for obs in outcome.run.observations
                if obs.experiment_id == "HTML_TO_MARKDOWN"
            ],
            "warm_mh_requests": [
                obs.request_index
                for obs in outcome.run.observations
                if obs.experiment_id == "MARKDOWN_TO_HTML"
            ],
        }
        _write_json(sdir / "scenario.json", scenarios[sid])
        print(
            f"{sid}: {outcome.production.verdict} "
            f"(expected {fixture['expected_verdict']}) "
            f"first_error={outcome.production.first_error} "
            f"parity={'OK' if parity['parity'] else 'MISMATCH'} "
            f"{outcome.duration_seconds:.3f}s hash={outcome.report_hash[:12]}"
        )

    # -- stable bleed reproduction (§8.2, §11.3): E13, 3/3 ---------------
    bleed_runs = []
    for attempt in range(1, 4):
        outcome = run_scenario(
            "E13",
            fixture_dir=EXTENDED_FIXTURE_DIR,
            contract_prefix="ext",
            namespace_prefix=f"all48-E13-repro-{attempt}",
        )
        bleed_runs.append(
            {
                "attempt": attempt,
                "verdict": outcome.production.verdict,
                "first_error": outcome.production.first_error,
                "report_hash": outcome.report_hash,
                "bleed_diagnostics": [
                    d for d in outcome.diagnostics_projection
                    if d["code"] == "REPRESENTATION_BLEED"
                ],
            }
        )
        print(
            f"E13 repro {attempt}/3: {outcome.production.verdict} "
            f"first_error={outcome.production.first_error}"
        )
    bleed_ok = all(
        r["verdict"] == "REPRESENTATION_BLEED"
        and r["first_error"] == 6
        and len(r["bleed_diagnostics"]) == 2
        for r in bleed_runs
    )

    # -- determinism spot check (§7.8, §10.4): E01, fresh pair per run --
    det_hashes: list[str] = []
    for i in range(3):
        outcome = run_scenario(
            "E01",
            fixture_dir=EXTENDED_FIXTURE_DIR,
            contract_prefix="ext",
            namespace_prefix=f"all48-E01-det-{i+1}",
        )
        det_hashes.append(outcome.report_hash)
        if outcome.production.verdict != "PASS_OBSERVED":
            print(f"E01 determinism {i+1}: unexpected verdict {outcome.production.verdict}")
    det_ok = len(set(det_hashes)) == 1
    print(
        f"determinism E01: distinct_hashes={len(set(det_hashes))} "
        f"all_equal={det_ok}"
    )

    total_seconds = time.perf_counter() - started
    passed = sum(
        1
        for s in scenarios.values()
        if s["expected_ok"] and s["oracle_parity"]
    )
    parity_count = sum(1 for s in scenarios.values() if s["oracle_parity"])
    max_duration = max(s["duration_seconds"] for s in scenarios.values())
    summary = {
        "gate": "ALL48",
        "spec": "PROJECT_BOOK.md §11",
        "ALL48_STATUS": (
            "PASS"
            if passed == 48
            and parity_count == 48
            and bleed_ok
            and det_ok
            and max_duration < 1.0
            else "FAIL"
        ),
        "ALL48_GOLDEN": f"{passed}/48",
        "ALL48_ORACLE_PARITY": f"{parity_count}/48",
        "S0_GOLDEN": (
            f"{sum(1 for sid in SCENARIO_IDS if scenarios[sid]['expected_ok'] and scenarios[sid]['oracle_parity'])}/24"
        ),
        "EXTENDED_GOLDEN": (
            f"{sum(1 for sid in EXTENDED_SCENARIO_IDS if scenarios[sid]['expected_ok'] and scenarios[sid]['oracle_parity'])}/24"
        ),
        "FALSE_POSITIVE": sum(
            1
            for sid in HEALTHY_48
            if scenarios[sid]["verdict"] != "PASS_OBSERVED"
        ),
        "KNOWN_FAILURE_DETECTED": sum(
            1
            for sid in KNOWN_FAILURES_48
            if scenarios[sid]["verdict"] == scenarios[sid]["expected_verdict"]
        ),
        "KNOWN_FAILURE_TOTAL": len(KNOWN_FAILURES_48),
        "bleed_reproduction": {
            "scenario": "E13",
            "runs": bleed_runs,
            "reproduced_3_of_3": bleed_ok,
        },
        "determinism_spot_check": {
            "scenario": "E01",
            "runs": 3,
            "distinct_hashes": len(set(det_hashes)),
            "hash": det_hashes[0] if det_hashes else None,
            "all_equal": det_ok,
            "fresh_pair_per_run": True,
        },
        "max_scenario_duration_seconds": max_duration,
        "total_seconds": round(total_seconds, 2),
        "scenarios": scenarios,
    }
    _write_json(EVIDENCE_DIR / "ALL48_SUMMARY.json", summary)
    print(
        f"ALL48_STATUS: {summary['ALL48_STATUS']} "
        f"({passed}/48 golden, parity {parity_count}/48)"
    )
    return summary


if __name__ == "__main__":
    summary = run_all()
    sys.exit(0 if summary["ALL48_STATUS"] == "PASS" else 1)
```

## scripts/run_s0.py

- SHA-256：`a02e341b71b63670b6c628cb87aa754c619889e7fa20945b3fee0ebe56e7d2c7`
- 字节数：10973

```
"""S0 gate runner (P032 T007-C): execute C01-C24 + Oracle parity.

Writes per-scenario evidence under ``evidence/S0/<sid>/`` and the
gate summary to ``evidence/S0/S0_SUMMARY.json``:

* ``raw-observations.json`` -- the runner's raw-observations file
  (``accepttwin.raw-observations/v1``), 8 real HTTP requests;
* ``contract.json`` -- the contract actually used (live ports);
* ``oracle-input.json`` -- the exact adjudication input both the
  production classifier and the Oracle judged (§12.2);
* ``production.json`` -- the production classification result;
* ``oracle.json`` -- the independent Oracle result;
* ``scenario.json`` -- fixture + duration + report hash + parity.

Also performs the two multi-run checks of §13 / §11.4:

* stable bleed reproduction (§8.2, §11.2): C11 re-executed 3 times
  on fresh services (independent cache clears), each must yield
  REPRESENTATION_BLEED with the full dual-evidence chain;
* repeat-100 (§7.8, §10.4): C01 re-executed 100 times, each run on
  a fresh pair with fresh OS-assigned ports (same logical input, real
  requests every time), the canonical report hash must be identical
  all 100 times (ADR-003: the old single-pair form passed by
  construction, since 100 runs shared one pair of ports). A
  supplementary 3-run same-pair check must give the same hash as
  the fresh-pair runs.

Exit code 0 only when every §13 item passes; the verdict itself is
in S0_SUMMARY.json (``S0_STATUS``). ``scripts/verify_s0.py`` re-checks
the evidence independently -- this script never declares S0 PASS on
its own say-so.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from s0_harness import (  # noqa: E402
    ROOT,
    SCENARIO_IDS,
    check_parity,
    make_pair,
    oracle_input_dict,
    run_oracle,
    run_scenario,
)

EVIDENCE_DIR = ROOT / "evidence" / "S0"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_all() -> dict:
    """Execute the full S0 gate and return the summary dict."""
    started = time.perf_counter()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    scenarios: dict[str, dict] = {}
    for sid in SCENARIO_IDS:
        outcome = run_scenario(sid)
        sdir = EVIDENCE_DIR / sid
        sdir.mkdir(parents=True, exist_ok=True)
        # Raw evidence file (runner format) + contract + oracle input.
        outcome.run.write_evidence(sdir / "raw-observations.json")
        _write_json(sdir / "contract.json", outcome.contract.as_dict())
        injection = outcome.fixture.get("injection") or {}
        oracle_input = oracle_input_dict(
            outcome.contract,
            outcome.run,
            outcome.adj_origin_events,
            origin_events_available=(
                injection.get("kind") != "origin_events_unavailable"
            ),
        )
        _write_json(sdir / "oracle-input.json", oracle_input)
        _write_json(sdir / "production.json", outcome.production.as_dict())
        oracle_result = run_oracle(
            sdir / "oracle-input.json", sdir / "oracle.json"
        )
        parity = check_parity(outcome, oracle_result)
        fixture = outcome.fixture
        expected_ok = (
            outcome.production.verdict == fixture["expected_verdict"]
            and outcome.production.first_error == fixture["expected_first_error"]
            and outcome.production.first_error_experiment_id
            == fixture["expected_first_error_experiment_id"]
            and outcome.diagnostics_projection == fixture["expected_diagnostics"]
        )
        scenarios[sid] = {
            "scenario_id": sid,
            "expected_verdict": fixture["expected_verdict"],
            "verdict": outcome.production.verdict,
            "expected_first_error": fixture["expected_first_error"],
            "first_error": outcome.production.first_error,
            "first_error_experiment_id": outcome.production.first_error_experiment_id,
            "expected_diagnostics": fixture["expected_diagnostics"],
            "diagnostics": outcome.diagnostics_projection,
            "oracle_verdict": oracle_result["verdict"],
            "oracle_first_error": oracle_result["first_error"],
            "oracle_parity": parity["parity"],
            "oracle_mismatches": parity["mismatches"],
            "expected_ok": expected_ok,
            "duration_seconds": round(outcome.duration_seconds, 4),
            "report_hash": outcome.report_hash,
            "origin_counter_delta_total": sum(
                obs.origin_counter_delta for obs in outcome.run.observations
            ),
            "request_count": len(outcome.run.observations),
            "reset_count": len(outcome.run.reset_evidence),
            "step_count": len(outcome.run.step_log),
            "warm_hm_requests": [
                obs.request_index
                for obs in outcome.run.observations
                if obs.experiment_id == "HTML_TO_MARKDOWN"
            ],
            "warm_mh_requests": [
                obs.request_index
                for obs in outcome.run.observations
                if obs.experiment_id == "MARKDOWN_TO_HTML"
            ],
        }
        _write_json(sdir / "scenario.json", scenarios[sid])
        print(
            f"{sid}: {outcome.production.verdict} "
            f"(expected {fixture['expected_verdict']}) "
            f"first_error={outcome.production.first_error} "
            f"parity={'OK' if parity['parity'] else 'MISMATCH'} "
            f"{outcome.duration_seconds:.3f}s hash={outcome.report_hash[:12]}"
        )

    # -- stable bleed reproduction (§8.2, §11.2): C11, 3/3 ---------------
    bleed_runs = []
    for attempt in range(1, 4):
        outcome = run_scenario("C11", namespace_prefix=f"s0-C11-repro-{attempt}")
        bleed_runs.append(
            {
                "attempt": attempt,
                "verdict": outcome.production.verdict,
                "first_error": outcome.production.first_error,
                "report_hash": outcome.report_hash,
                "bleed_diagnostics": [
                    d for d in outcome.diagnostics_projection
                    if d["code"] == "REPRESENTATION_BLEED"
                ],
            }
        )
        print(
            f"C11 repro {attempt}/3: {outcome.production.verdict} "
            f"first_error={outcome.production.first_error}"
        )
    bleed_ok = all(
        r["verdict"] == "REPRESENTATION_BLEED"
        and r["first_error"] == 6
        and len(r["bleed_diagnostics"]) == 2
        for r in bleed_runs
    )

    # -- repeat-100 (§7.8, §10.4): C01, fresh pair per run ------------
    # ADR-003: every iteration starts fresh services on fresh
    # OS-assigned ports, so a port-dependent hash cannot pass this
    # gate (the old single-pair form passed by construction). The
    # supplementary same-pair check pins the other direction:
    # re-running on one fixed pair must give the same hash as the
    # fresh-pair runs.
    repeat_hashes: list[str] = []
    repeat_durations: list[float] = []
    for i in range(100):
        outcome = run_scenario("C01", namespace_prefix=f"s0-C01-repeat-{i+1}")
        repeat_hashes.append(outcome.report_hash)
        repeat_durations.append(outcome.duration_seconds)
        if outcome.production.verdict != "PASS_OBSERVED":
            print(f"C01 repeat {i+1}: unexpected verdict {outcome.production.verdict}")
    repeat_ok = len(set(repeat_hashes)) == 1 and all(
        h == repeat_hashes[0] for h in repeat_hashes
    )
    same_pair_hashes: list[str] = []
    with make_pair("C01") as pair:
        for i in range(3):
            outcome = run_scenario(
                "C01", pair=pair, namespace_prefix=f"s0-C01-samepair-{i+1}"
            )
            same_pair_hashes.append(outcome.report_hash)
            if outcome.production.verdict != "PASS_OBSERVED":
                print(f"C01 same-pair {i+1}: unexpected verdict {outcome.production.verdict}")
    same_pair_ok = (
        len(set(same_pair_hashes)) == 1
        and same_pair_hashes
        and same_pair_hashes[0] == repeat_hashes[0]
    )
    repeat_ok = repeat_ok and same_pair_ok
    print(
        f"repeat-100 C01: distinct_hashes={len(set(repeat_hashes))} "
        f"all_equal={repeat_ok} max_duration={max(repeat_durations):.3f}s "
        f"same_pair_equal={same_pair_ok}"
    )

    total_seconds = time.perf_counter() - started
    passed = sum(
        1
        for s in scenarios.values()
        if s["expected_ok"] and s["oracle_parity"]
    )
    parity_count = sum(1 for s in scenarios.values() if s["oracle_parity"])
    max_duration = max(s["duration_seconds"] for s in scenarios.values())
    summary = {
        "gate": "S0",
        "spec": "PROJECT_BOOK.md §13",
        "S0_STATUS": (
            "PASS"
            if passed == 24
            and parity_count == 24
            and bleed_ok
            and repeat_ok
            and max_duration < 1.0
            else "FAIL"
        ),
        "S0_CORE_GOLDEN": f"{passed}/24",
        "S0_ORACLE_PARITY": f"{parity_count}/24",
        "S0_FALSE_POSITIVE": sum(
            1
            for sid in ("C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18")
            if scenarios[sid]["verdict"] != "PASS_OBSERVED"
        ),
        "S0_KNOWN_FAILURE_DETECTED": sum(
            1
            for sid in (
                "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
                "C15", "C16", "C19", "C24",
            )
            if scenarios[sid]["verdict"] == scenarios[sid]["expected_verdict"]
        ),
        "S0_KNOWN_FAILURE_TOTAL": 12,
        "bleed_reproduction": {
            "scenario": "C11",
            "runs": bleed_runs,
            "reproduced_3_of_3": bleed_ok,
        },
        "repeat_100": {
            "scenario": "C01",
            "runs": 100,
            "distinct_hashes": len(set(repeat_hashes)),
            "hash": repeat_hashes[0] if repeat_hashes else None,
            "all_equal": repeat_ok,
            "max_duration_seconds": round(max(repeat_durations), 4),
            "fresh_pair_per_run": True,
            "same_pair_runs": len(same_pair_hashes),
            "same_pair_hash": same_pair_hashes[0] if same_pair_hashes else None,
            "same_pair_all_equal": same_pair_ok,
        },
        "max_scenario_duration_seconds": max_duration,
        "total_seconds": round(total_seconds, 2),
        "scenarios": scenarios,
    }
    _write_json(EVIDENCE_DIR / "S0_SUMMARY.json", summary)
    print(f"S0_STATUS: {summary['S0_STATUS']} ({passed}/24 golden, parity {parity_count}/24)")
    return summary


if __name__ == "__main__":
    summary = run_all()
    sys.exit(0 if summary["S0_STATUS"] == "PASS" else 1)
```

## scripts/s0_harness.py

- SHA-256：`9ee1614c26701aba9e19c03eedf50786de3b0d3725fcc35d85d9237aef84e610`
- 字节数：30326

```
"""S0 harness (P032 T007): run one C01-C24 Golden end to end.

Shared by ``scripts/run_s0.py`` and ``tests/golden/test_s0.py`` so the
gate script and the test suite execute exactly the same scenarios.

Per scenario (PROJECT_BOOK §11.2, §6, §10.2):

* a real synthetic origin + a real controlled cache proxy are started
  on OS-assigned loopback ports (``port=0``), a contract is built for
  those URLs, and :func:`accepttwin.experiment_runner.run_experiments`
  performs the frozen 25 steps / 8 real HTTP GETs (001-008). Nothing
  here simulates a request.
* the production classifier is called under the mandatory calling
  convention of ADR-002 Decision 3 (verbatim)::

      classify_run(contract, run.observations, run.origin_events,
                   run.reset_evidence, raw_observations=run.raw_observations)

  with exactly one documented deviation: scenario C21
  (``origin_events_unavailable``) passes ``()`` -- the empty tuple,
  meaning "the journal was checked and found nothing" -- instead of
  ``run.origin_events``. ``None`` is never passed for any of the
  four arguments. The deviation is recorded in the scenario fixture
  and in the per-scenario evidence, and the Oracle receives the same
  empty event list, so production and Oracle judge the same input.

Fault-injection proxies (harness-only subclasses of
:class:`~accepttwin.cache_proxy.ControlledCacheProxy`; production
code in ``src/`` is untouched -- T007 must not modify T002-T006):

* C22 ``proxy_lies_hit_on_warm_second`` -- the 4th proxied GET
  (request 006, HM-2) is served a real HTTP response whose
  ``X-AcceptTwin-Cache-Status`` header says HIT while the origin
  counter moved +1 (the proxy fetched from the origin). Header leg
  and behaviour leg conflict (§8.8).
* C23 ``reset_reports_failure`` -- the first cache reset reports
  ``success=False`` (the store is genuinely empty at that point, so
  ``entries_after`` is honestly 0); no cold-cache claim can then be
  confirmed (§8.4, §11.2 C23).
* C24 ``proxy_rewrites_markdown_content_type`` -- proxied responses
  to Markdown requests return ``Content-Type: text/html`` while the
  body is unchanged; the direct-origin baselines stay correct, so
  the fault is a proxy contract violation, not an origin error
  (§8.3, §11.2 C24).

Extended-Golden injections (P032 T008, same harness-only rule --
production code in ``src/`` is untouched except for the ADR-004
classifier/origin changes the §11.3 shapes themselves require):

* E12 ``proxy_returns_local_redirect`` -- every proxied GET is
  answered ``301`` with ``Location`` pointing at the origin URL
  (loopback); the proxy never contacts the origin. The first release
  does not follow redirects (§8.6, §11.3 E12).
* E22 ``proxy_returns_external_redirect`` -- as E12, but the
  ``Location`` points at ``http://example.com/doc`` (non-loopback);
  following it is forbidden (§8.6, §11.3 E22). The target is a
  synthetic fixture address, never a real user URL.
* E20 ``proxy_lies_miss_with_stash_replay`` -- the 4th proxied GET
  (request 006, HM-2) is served the Markdown body the proxy observed
  at request 004 (kept in a harness-side stash, not the cache store,
  so resets stay honest) without contacting the origin (counter
  delta 0), while the header claims MISS. Header leg and behaviour
  leg conflict (§8.8, §11.3 E20).
* E21 ``proxy_returns_oversize_body`` -- every proxied response body
  is padded past the 1 MiB contract limit (sentinel intact, so the
  only fault is size); the stored entry keeps the original body
  (§8.6, §11.3 E21).
* E23 ``proxy_rewrites_html_content_type`` -- the C24 mirror for
  HTML: proxied responses to HTML requests return ``Content-Type:
  text/markdown`` while the body is unchanged (§8.3, §11.3 E23).
* E24 ``proxy_corrupts_warm_second_sentinel`` -- the warm-second
  responses (requests 006, 008) are returned with their Sentinel
  bytes replaced by a wrong Sentinel; the stored entries keep the
  correct bodies (§8.5, §11.3 E24).
* E17 reuses the ``opaque`` proxy mode (as C20) and E18 reuses the
  ``origin_events_unavailable`` adjudication-input shape (as C21);
  E19 reuses ``proxy_lies_hit_on_warm_second`` (as C22).

Canonical report hash (§10.4): the hashed payload carries only
deterministic fields -- contract hash, scenario id, per-request
(experiment, requested representation, status, Content-Type, body
SHA-256, Sentinel match, verified cache state, origin counter
*delta*), diagnostics (code + request), verdict and first error.
Absolute origin counters, cache keys / entry ids, timestamps,
durations and process ids never enter it. Ports never enter it
either, but only because of an explicit normalisation step, not by
omission: the contract's ``url`` / ``origin_url`` carry OS-assigned
loopback ports (services start with ``port=0``), and
``canonical_contract_hash`` normalises those ports to 0 before
hashing (ADR-003, §10.4 "不包含动态端口"), so two runs of the same
logical contract on different ports hash identically. Execution
still uses the real ports; only the hash input is normalised.
``canonical_json_bytes`` from ``accepttwin.contract`` is the single
canonicalisation implementation (T009 will reuse it; T007 does not
write a second one).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from accepttwin.cache_proxy import (
    ControlledCacheProxy,
    ResetEvidence,
    _entry_id_for,
    cache_key_for,
)
from accepttwin.classifier import ClassificationResult, classify_run
from accepttwin.contract import (
    canonical_json_bytes,
    parse_contract,
)
from accepttwin.experiment_runner import ExperimentRun, run_experiments
from accepttwin.origin_server import SyntheticOrigin

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "s0"
EXTENDED_FIXTURE_DIR = ROOT / "fixtures" / "extended"
CONTRACT_TEMPLATE = ROOT / "contracts" / "site.json"
ORACLE_ENTRY = ROOT / "oracle" / "src" / "index.ts"

SCENARIO_IDS: tuple[str, ...] = tuple(f"C{i:02d}" for i in range(1, 25))
EXTENDED_SCENARIO_IDS: tuple[str, ...] = tuple(f"E{i:02d}" for i in range(1, 25))
ALL_SCENARIO_IDS: tuple[str, ...] = SCENARIO_IDS + EXTENDED_SCENARIO_IDS

#: The mandatory production-classifier call (ADR-002 Decision 3).
#: Kept as a literal string so scripts/verify_s0.py can assert the
#: call site in this file matches it.
MANDATORY_CALL_SNIPPET = (
    "classify_run(contract, run.observations, "
    "adj_origin_events, run.reset_evidence, "
    "raw_observations=run.raw_observations)"
)


# ---------------------------------------------------------------------------
# Fault-injection proxies (harness only, see module docstring)
# ---------------------------------------------------------------------------


class _LyingHitProxy(ControlledCacheProxy):
    """C22: the 4th proxied GET claims HIT while fetching from origin."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._proxied_gets = 0

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        self._proxied_gets += 1
        status, headers, body = super()._serve_once(path_and_query, accept)
        if self._proxied_gets == 4:  # request 006, HM-2
            headers = [
                (name, "HIT") if name.lower() == "x-accepttwin-cache-status"
                else (name, value)
                for name, value in headers
            ]
        return status, headers, body


class _FailingResetProxy(ControlledCacheProxy):
    """C23: the first reset reports failure (store genuinely empty)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._resets = 0

    def reset_cache(self, namespace: str) -> ResetEvidence:
        self._resets += 1
        if self._resets == 1:
            before = self.cache_snapshot().entry_count
            return ResetEvidence(
                namespace=namespace,
                success=False,
                entries_before=before,
                entries_after=before,
                entries_removed=0,
            )
        return super().reset_cache(namespace)


class _RewriteMarkdownContentTypeProxy(ControlledCacheProxy):
    """C24: proxied Markdown responses claim Content-Type text/html."""

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        status, headers, body = super()._serve_once(path_and_query, accept)
        if accept.strip().lower() == "text/markdown":
            headers = [
                (name, "text/html; charset=utf-8")
                if name.lower() == "content-type"
                else (name, value)
                for name, value in headers
            ]
        return status, headers, body


class _LocalRedirectProxy(ControlledCacheProxy):
    """E12: every proxied GET is a 301 to the (loopback) origin URL.

    The origin is never contacted, so the counter does not move; no
    cache headers are emitted, so no cache state can be confirmed.
    """

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        return (
            301,
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Location", str(self.origin_url)),
            ],
            b"301 Moved Permanently\n",
        )


class _ExternalRedirectProxy(ControlledCacheProxy):
    """E22: every proxied GET is a 301 to a non-loopback address.

    The target is a synthetic fixture address (``example.com``), never
    a real user URL; following it is forbidden (§8.6).
    """

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        return (
            301,
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Location", "http://example.com/doc"),
            ],
            b"301 Moved Permanently\n",
        )


class _LyingMissProxy(ControlledCacheProxy):
    """E20: the 4th proxied GET (006, HM-2) claims MISS with delta 0.

    The proxy replays the Markdown body it observed at request 004
    (kept in a harness-side stash, not the cache store, so the reset
    evidence stays honest) without contacting the origin, while the
    header claims MISS. The body is the genuine origin body, so no
    Sentinel or contract diagnostic fires — only the §8.8 conflict.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._proxied_gets = 0
        self._stashed_markdown: bytes | None = None

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        self._proxied_gets += 1
        if self._proxied_gets == 4 and self._stashed_markdown is not None:
            _material, key_sha = cache_key_for(
                self._origin_url_for(path_and_query), accept
            )
            headers = [
                ("Content-Type", "text/markdown; charset=utf-8"),
                ("Vary", "Accept"),
                ("X-AcceptTwin-Cache-Status", "MISS"),
                ("X-AcceptTwin-Cache-Key", key_sha),
                ("X-AcceptTwin-Entry-Id", _entry_id_for(key_sha)),
            ]
            return 200, headers, self._stashed_markdown
        status, headers, body = super()._serve_once(path_and_query, accept)
        if self._proxied_gets == 2 and accept.strip().lower() == "text/markdown":
            self._stashed_markdown = body
        return status, headers, body


class _OversizeBodyProxy(ControlledCacheProxy):
    """E21: every proxied body is padded past the 1 MiB limit.

    The padding is appended after the original body, so the Sentinel
    stays intact and the only fault is size (§8.6 ``body_too_large``).
    The stored entry keeps the original body.
    """

    _TARGET_SIZE = 1048577  # contract max_body_bytes (1 MiB) + 1

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        status, headers, body = super()._serve_once(path_and_query, accept)
        if len(body) < self._TARGET_SIZE:
            body = body + b"x" * (self._TARGET_SIZE - len(body))
        return status, headers, body


class _RewriteHtmlContentTypeProxy(ControlledCacheProxy):
    """E23: proxied HTML responses claim Content-Type text/markdown."""

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        status, headers, body = super()._serve_once(path_and_query, accept)
        if accept.strip().lower() == "text/html":
            headers = [
                (name, "text/markdown; charset=utf-8")
                if name.lower() == "content-type"
                else (name, value)
                for name, value in headers
            ]
        return status, headers, body


class _CorruptWarmSentinelProxy(ControlledCacheProxy):
    """E24: warm-second responses (006, 008) carry a wrong Sentinel.

    The Sentinel bytes in the returned body are replaced; the stored
    entries keep the correct bodies, so the fault is a proxy response
    fault (§8.5), not a bleed (body hashes differ from the first
    requests') and not an origin error (baselines stay correct).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._proxied_gets = 0

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        self._proxied_gets += 1
        status, headers, body = super()._serve_once(path_and_query, accept)
        if self._proxied_gets in (4, 6):  # requests 006, 008
            body = body.replace(
                b"AT_HTML_SENTINEL_001", b"AT_HTML_SENTINEL_999"
            ).replace(
                b"AT_MARKDOWN_SENTINEL_001", b"AT_MARKDOWN_SENTINEL_999"
            )
        return status, headers, body


_INJECTION_PROXIES = {
    "proxy_lies_hit_on_warm_second": _LyingHitProxy,
    "reset_reports_failure": _FailingResetProxy,
    "proxy_rewrites_markdown_content_type": _RewriteMarkdownContentTypeProxy,
    "proxy_returns_local_redirect": _LocalRedirectProxy,
    "proxy_returns_external_redirect": _ExternalRedirectProxy,
    "proxy_lies_miss_with_stash_replay": _LyingMissProxy,
    "proxy_returns_oversize_body": _OversizeBodyProxy,
    "proxy_rewrites_html_content_type": _RewriteHtmlContentTypeProxy,
    "proxy_corrupts_warm_second_sentinel": _CorruptWarmSentinelProxy,
}


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def load_scenario(
    scenario_id: str, fixture_dir: str | Path | None = None
) -> dict[str, Any]:
    """Load and return the fixture JSON for *scenario_id*.

    *fixture_dir* defaults to the S0 directory (C01-C24); the
    extended Golden (E01-E24, T008) pass ``EXTENDED_FIXTURE_DIR``.
    """
    path = Path(fixture_dir or FIXTURE_DIR) / f"{scenario_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["scenario_id"] != scenario_id:
        raise ValueError(f"fixture {path} carries id {data['scenario_id']!r}")
    return data


def build_contract(
    proxy_url: str,
    origin_url: str,
    fixture: dict[str, Any],
    contract_prefix: str = "s0",
):
    """Build a validated contract for the live service URLs."""
    data = json.loads(CONTRACT_TEMPLATE.read_text(encoding="utf-8"))
    data["contract_id"] = f"{contract_prefix}-{fixture['scenario_id']}"
    data["name"] = (
        f"{contract_prefix.upper()} {fixture['scenario_id']} "
        f"({fixture['origin_scenario']})"
    )
    data["url"] = proxy_url
    data["origin_url"] = origin_url
    cb = fixture["contract"]
    data["cache_behavior"] = {
        "mode": cb["mode"],
        "vary_accept": cb["vary_accept"],
        "max_age_seconds": cb["max_age_seconds"],
    }
    return parse_contract(data)


@dataclass
class ScenarioOutcome:
    """Everything one scenario execution produced, for gate + tests."""

    scenario_id: str
    fixture: dict[str, Any]
    contract: Any
    run: ExperimentRun
    duration_seconds: float
    production: ClassificationResult
    # Adjudication inputs actually passed to the classifier (C21:
    # origin_events is () by fixture design, never None).
    adj_origin_events: tuple = ()
    report: dict[str, Any] = field(default_factory=dict)
    report_hash: str = ""

    @property
    def diagnostics_projection(self) -> list[dict[str, Any]]:
        """Production diagnostics as sorted {code, request_index} pairs."""
        from accepttwin.diagnostics import diagnostic_order

        pairs = [
            {"code": d.code, "request_index": d.request_index}
            for d in self.production.diagnostics
        ]
        return sorted(
            pairs,
            key=lambda p: (
                p["request_index"] is None,
                p["request_index"] if p["request_index"] is not None else 0,
                diagnostic_order(p["code"]),
            ),
        )


def canonical_report(contract: Any, run: ExperimentRun, result: ClassificationResult, scenario_id: str) -> dict[str, Any]:
    """Deterministic report payload for the §10.4 hash (see docstring)."""
    from accepttwin.contract import canonical_contract_hash

    return {
        "schema": "accepttwin.report/v1",
        "scenario_id": scenario_id,
        "contract_sha256": canonical_contract_hash(contract),
        "observations": [
            {
                "request_index": obs.request_index,
                "experiment_id": obs.experiment_id,
                "requested_representation": obs.requested_representation,
                "response_status": obs.response_status,
                "response_content_type": obs.response_content_type,
                "body_sha256": obs.body_sha256,
                "sentinel_match": obs.sentinel_match,
                "cache_status": obs.cache_status,
                "origin_counter_delta": obs.origin_counter_delta,
            }
            for obs in run.observations
        ],
        "diagnostics": [
            {"code": d.code, "request_index": d.request_index}
            for d in result.diagnostics
        ],
        "verdict": result.verdict,
        "first_error": result.first_error,
        "first_error_experiment_id": result.first_error_experiment_id,
    }


def report_hash(report: dict[str, Any]) -> str:
    """SHA-256 of the Canonical JSON of *report* (§10.4)."""
    return hashlib.sha256(canonical_json_bytes(report)).hexdigest()


def oracle_input_dict(contract: Any, run: ExperimentRun, adj_origin_events: tuple, *, origin_events_available: bool) -> dict[str, Any]:
    """The exact adjudication input the independent Oracle reads.

    Same observations / raw observations / resets as the production
    classifier received; the origin event list is the adjudication
    list (empty for C21, with ``origin_events_available`` false).
    No production verdict or diagnostic ever enters this file (§12.2).
    """
    return {
        "format": "accepttwin.oracle-input/v1",
        "contract": contract.as_dict(),
        "observations": [obs.as_dict() for obs in run.observations],
        "raw_observations": [raw.as_dict() for raw in run.raw_observations],
        "origin_events": [
            {
                "index": ev.index,
                "method": ev.method,
                "path": ev.path,
                "accept": ev.accept,
                "status": ev.status,
            }
            for ev in adj_origin_events
        ],
        "origin_events_available": origin_events_available,
        "resets": [
            {
                "namespace": ev.namespace,
                "success": ev.success,
                "entries_before": ev.entries_before,
                "entries_after": ev.entries_after,
                "entries_removed": ev.entries_removed,
            }
            for ev in run.reset_evidence
        ],
    }


class _Pair:
    """A running (origin, proxy, contract) triple for one scenario."""

    def __init__(
        self, fixture: dict[str, Any], contract_prefix: str = "s0"
    ) -> None:
        self.fixture = fixture
        self.origin = SyntheticOrigin(
            port=0, scenario=fixture["origin_scenario"]
        )
        self.origin.start()
        proxy_cls = ControlledCacheProxy
        injection = fixture.get("injection") or {}
        if injection.get("kind") in _INJECTION_PROXIES:
            proxy_cls = _INJECTION_PROXIES[injection["kind"]]
        self.proxy: ControlledCacheProxy = proxy_cls(
            port=0,
            mode=fixture["proxy_mode"],
            origin_url=self.origin.url,
        )
        self.proxy.start()
        self.contract = build_contract(
            self.proxy.url, self.origin.url, fixture, contract_prefix
        )
        if fixture["contract"]["mode"] == "no_store":
            # The proxy needs the contract to know storage is
            # forbidden; rebuild it bound to the contract (new port).
            self.proxy.stop()
            self.proxy = proxy_cls(
                port=0,
                mode=fixture["proxy_mode"],
                contract=self.contract,
            )
            self.proxy.start()
            self.contract = build_contract(
                self.proxy.url, self.origin.url, fixture, contract_prefix
            )

    def __enter__(self) -> "_Pair":
        return self

    def __exit__(self, *exc: object) -> bool:
        self.proxy.stop()
        self.origin.stop()
        return False


def run_scenario(
    scenario_id: str,
    *,
    pair: _Pair | None = None,
    namespace_prefix: str | None = None,
    fixture_dir: str | Path | None = None,
    contract_prefix: str = "s0",
) -> ScenarioOutcome:
    """Execute one S0/extended scenario end to end (real HTTP) and classify it.

    *fixture_dir* / *contract_prefix* default to the S0 Golden
    (``fixtures/s0/``, ``"s0"``); the extended Golden (T008) pass
    ``EXTENDED_FIXTURE_DIR`` / ``"ext"``. When *pair* is supplied,
    the run reuses those live services (used by the supplementary
    same-pair determinism check); otherwise a fresh pair is started
    for this scenario only -- the repeat-100 gate runs each iteration
    on a fresh pair with fresh OS-assigned ports, so a port-dependent
    hash cannot pass it (ADR-003).
    """
    fixture = load_scenario(scenario_id, fixture_dir)
    own_pair = pair is None
    if pair is None:
        pair = _Pair(fixture, contract_prefix)
    try:
        contract = pair.contract
        injection = fixture.get("injection") or {}
        started = time.perf_counter()
        run = run_experiments(
            contract,
            origin=pair.origin,
            proxy=pair.proxy,
            scenario=fixture["origin_scenario"],
            proxy_mode=fixture["proxy_mode"],
            namespace_prefix=namespace_prefix or f"s0-{scenario_id}",
        )
        duration = time.perf_counter() - started
        # Adjudication inputs (ADR-002 Decision 3). C21 passes the
        # empty tuple -- checked, found nothing -- never None.
        adj_origin_events: tuple = (
            () if injection.get("kind") == "origin_events_unavailable"
            else run.origin_events
        )
        # Mandatory call (ADR-002 Decision 3, verbatim argument
        # roles): real tuples, never None; raw_observations always.
        production = classify_run(contract, run.observations, adj_origin_events, run.reset_evidence, raw_observations=run.raw_observations)
        report = canonical_report(contract, run, production, scenario_id)
        return ScenarioOutcome(
            scenario_id=scenario_id,
            fixture=fixture,
            contract=contract,
            run=run,
            duration_seconds=duration,
            production=production,
            adj_origin_events=adj_origin_events,
            report=report,
            report_hash=report_hash(report),
        )
    finally:
        if own_pair:
            pair.proxy.stop()
            pair.origin.stop()


def make_pair(
    scenario_id: str,
    fixture_dir: str | Path | None = None,
    contract_prefix: str = "s0",
) -> _Pair:
    """Start a reusable (origin, proxy, contract) pair for *scenario_id*."""
    return _Pair(load_scenario(scenario_id, fixture_dir), contract_prefix)


# ---------------------------------------------------------------------------
# Independent Oracle invocation + parity (§12.4)
# ---------------------------------------------------------------------------


def run_oracle(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Run the independent TypeScript Oracle on *input_path*.

    The Oracle is a separate Node.js process reading only the
    oracle-input file; it never sees a production verdict (§12.3).
    Returns the Oracle result dict it wrote to *output_path*.
    """
    import subprocess

    proc = subprocess.run(
        [
            "node",
            str(ORACLE_ENTRY),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"oracle failed (exit {proc.returncode}): "
            f"{proc.stdout.strip()} {proc.stderr.strip()}"
        )
    return json.loads(Path(output_path).read_text(encoding="utf-8"))


def oracle_projection(oracle_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Oracle diagnostics as sorted {code, request_index} pairs."""
    from accepttwin.diagnostics import diagnostic_order

    pairs = [
        {"code": d["code"], "request_index": d["request_index"]}
        for d in oracle_result["diagnostics"]
    ]
    return sorted(
        pairs,
        key=lambda p: (
            p["request_index"] is None,
            p["request_index"] if p["request_index"] is not None else 0,
            diagnostic_order(p["code"]),
        ),
    )


def production_cache_states(outcome: ScenarioOutcome) -> list[dict[str, Any]]:
    """Per-request verified cache states, normalised for parity.

    These are the states the production *classifier* was willing to
    trust (``ClassificationResult.confirmed_cache_states``, T014 /
    T013-F02) — NOT the runner's observation-layer states: the
    classifier downgrades observation states it cannot confirm
    (e.g. C21, where the adjudication origin-event list is empty,
    so every proxied state is unconfirmed even though the runner
    verified them against its own live event log). ``None`` means
    "confirmed nothing" (baselines per ADR-001, or unconfirmed).
    """
    states = []
    for entry in sorted(
        outcome.production.confirmed_cache_states,
        key=lambda e: e["request_index"],
    ):
        state = entry.get("state")
        if state == "CACHE_STATE_UNKNOWN":
            state = None
        states.append({"request_index": entry["request_index"], "state": state})
    return states


def _normalise_oracle_cache_states(value: Any) -> list[dict[str, Any]] | None:
    """Normalise an Oracle ``verified_cache_states`` value, or None
    when it is not a well-formed 8-entry list (fail-closed: the
    caller treats None as a mismatch)."""
    if not isinstance(value, list) or len(value) != 8:
        return None
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
            or (state is not None and state not in ("MISS", "HIT", "BYPASS"))
        ):
            return None
        states.append({"request_index": index, "state": state})
    states.sort(key=lambda s: s["request_index"])
    if [s["request_index"] for s in states] != list(range(1, 9)):
        return None
    return states


def check_parity(outcome: ScenarioOutcome, oracle_result: dict[str, Any]) -> dict[str, Any]:
    """Compare production vs Oracle per §12.4 (verdict, diagnostics,
    first error, and — since T014 / T013-F02 — the per-request
    verified MISS/HIT/BYPASS states). Returns {"parity": bool,
    "mismatches": [...]}."""
    mismatches: list[str] = []
    if oracle_result["verdict"] != outcome.production.verdict:
        mismatches.append(
            f"verdict: production={outcome.production.verdict} "
            f"oracle={oracle_result['verdict']}"
        )
    if oracle_projection(oracle_result) != outcome.diagnostics_projection:
        mismatches.append(
            "diagnostics: production="
            f"{json.dumps(outcome.diagnostics_projection)} oracle="
            f"{json.dumps(oracle_projection(oracle_result))}"
        )
    if oracle_result["first_error"] != outcome.production.first_error:
        mismatches.append(
            f"first_error: production={outcome.production.first_error} "
            f"oracle={oracle_result['first_error']}"
        )
    if (
        oracle_result["first_error_experiment_id"]
        != outcome.production.first_error_experiment_id
    ):
        mismatches.append(
            "first_error_experiment_id: production="
            f"{outcome.production.first_error_experiment_id} oracle="
            f"{oracle_result['first_error_experiment_id']}"
        )
    oracle_states = _normalise_oracle_cache_states(
        oracle_result.get("verified_cache_states")
    )
    production_states = production_cache_states(outcome)
    if oracle_states is None:
        mismatches.append(
            "verified_cache_states: oracle result has no well-formed "
            "per-request cache states (expected 8 entries, requests "
            "001-008)"
        )
    elif oracle_states != production_states:
        mismatches.append(
            "verified_cache_states: production="
            f"{json.dumps(production_states)} oracle="
            f"{json.dumps(oracle_states)}"
        )
    return {"parity": not mismatches, "mismatches": mismatches}
```

## scripts/verify_s0.py

- SHA-256：`688c317f3dab2b157447bac981c43a5d91ff8b48ade3f3b0c382c6adad267bd2`
- 字节数：32956

```
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
```

## report-ui/src/app.ts

- SHA-256：`292c6b22b63c877f971e46d1ce5db4dc200d20979500f630e507eb18028e785e`
- 字节数：30496

```
/**
 * DOM rendering for the AcceptTwin self-contained HTML report
 * (P032 T010).
 *
 * Renders the ten required interface items (T010 task card) from
 * the embedded ``accepttwin.report/v1`` JSON payload:
 *
 *   1. final verdict            (§4.3 area A)
 *   2. HTML / Markdown baselines (§4.3 area B)
 *   3. four experiment states   (§6)
 *   4. dual-direction timeline  (§4.3 area C)
 *   5. cache evidence           (§5.3, §4.3 area C)
 *   6. first-error location     (§4.3 area D, §6.3)
 *   7. diagnostic codes         (§4.3 area E, §8)
 *   8. Oracle parity            (§12.4)
 *   9. report hash              (§10.4)
 *  10. privacy preview          (§4.3 area F, §17.3)
 *
 * Safety rules (fail-closed by construction):
 * - All report data is inserted via ``textContent`` only — never
 *   ``innerHTML`` — so no report string can become markup.
 * - No remote fetch, no link, no image, no iframe: the only
 *   network-adjacent action is the JSON download button, which
 *   builds a Blob from the already-embedded payload at click time.
 * - No body text is ever displayed: only hashes (truncated to a
 *   16-hex summary in the visible UI, full value in the embedded
 *   JSON) and Sentinel match flags.
 * - This module never recomputes a verdict or a diagnostic; it
 *   only renders what the report contains.
 */

/// <reference path="./types.ts" />
/// <reference path="./timeline.ts" />
/// <reference path="./diagnostics.ts" />

namespace AcceptTwinUI {
  // ------------------------------------------------------------------
  // DOM helpers (textContent only — no innerHTML anywhere)
  // ------------------------------------------------------------------

  function el(
    tag: string,
    className?: string,
    text?: string,
  ): HTMLElement {
    const node = document.createElement(tag);
    if (className !== undefined && className !== "") {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function show(id: string): HTMLElement | null {
    return document.getElementById(id);
  }

  function clear(node: HTMLElement): void {
    while (node.firstChild !== null) {
      node.removeChild(node.firstChild);
    }
  }

  /** Two-column key/value table. Values are always plain text. */
  function kvTable(rows: Array<[string, string]>): HTMLTableElement {
    const table = document.createElement("table");
    table.className = "kv";
    const body = document.createElement("tbody");
    for (const [key, value] of rows) {
      const tr = document.createElement("tr");
      tr.appendChild(el("th", "", key));
      tr.appendChild(el("td", "mono", value));
      body.appendChild(tr);
    }
    table.appendChild(body);
    return table;
  }

  function hashSummary(hash: string): string {
    return hash.length > 16 ? hash.slice(0, 16) + "…" : hash;
  }

  function verdictBadge(verdict: Verdict): HTMLElement {
    const badge = el(
      "span",
      "verdict-badge verdict-" + verdict,
      verdict + " · " + VERDICT_LABELS[verdict],
    );
    return badge;
  }

  function severityBadge(severity: Severity): HTMLElement {
    return el("span", "severity severity-" + severity, severity);
  }

  // ------------------------------------------------------------------
  // 1. Final verdict (§4.3 area A)
  // ------------------------------------------------------------------

  function renderVerdict(report: Report): void {
    const section = show("section-verdict");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "1 · 最终裁决"));
    const badgeRow = el("p", "verdict-row");
    badgeRow.appendChild(verdictBadge(report.verdict));
    const finalText = report.final
      ? "最终有效报告（Oracle parity 通过）"
      : "非最终报告（未提供 Oracle 结果，或 Oracle parity 未通过）";
    badgeRow.appendChild(el("span", "final-flag", finalText));
    section.appendChild(badgeRow);
    section.appendChild(
      kvTable([
        ["场景 ID", report.scenario_id],
        ["诊断总数", String(report.diagnostics.length)],
        ["CRITICAL 数量", String(report.critical_count)],
        ["WARNING 数量", String(report.warning_count)],
        [
          "首次错误请求",
          report.first_error === null
            ? "无"
            : `请求 ${String(report.first_error).padStart(3, "0")}` +
              (report.first_error_experiment_id !== null
                ? `（${report.first_error_experiment_id}）`
                : ""),
        ],
        ["输入契约 SHA-256", report.input.contract_sha256],
        ["报告 Schema", report.schema],
      ]),
    );
    if (report.reasons.length > 0) {
      section.appendChild(el("h3", "", "裁决理由"));
      const list = document.createElement("ul");
      for (const reason of report.reasons) {
        list.appendChild(el("li", "", reason));
      }
      section.appendChild(list);
    }
  }

  // ------------------------------------------------------------------
  // 2. HTML / Markdown baselines (§4.3 area B)
  // ------------------------------------------------------------------

  function renderBaselines(report: Report, baseline: Baseline): void {
    const section = show("section-baseline");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "2 · HTML / Markdown 基线"));
    section.appendChild(
      el(
        "p",
        "note",
        "源站直连基线（请求 001 / 002，不经过缓存代理）。预期值来自运行契约 " +
          "（无契约时取冻结 §5.1.2 常量）；正文原文不显示，只显示 Sentinel 匹配标志与正文哈希。",
      ),
    );
    const grid = el("div", "baseline-grid");
    const columns: Array<{
      rep: "html" | "markdown";
      obsIndex: number;
      title: string;
    }> = [
      { rep: "html", obsIndex: 1, title: "HTML 基线（请求 001）" },
      { rep: "markdown", obsIndex: 2, title: "Markdown 基线（请求 002）" },
    ];
    for (const column of columns) {
      const expected = baseline[column.rep];
      const obs = report.observations.find(
        (o) => o.request_index === column.obsIndex,
      );
      const card = el("div", "baseline-card");
      card.appendChild(el("h3", "", column.title));
      if (obs === undefined) {
        card.appendChild(el("p", "", "无观测记录"));
        grid.appendChild(card);
        continue;
      }
      const passed =
        obs.response_status === expected.expected_status &&
        obs.response_content_type === expected.expected_content_type &&
        obs.sentinel_match;
      card.appendChild(
        kvTable([
          ["Accept 请求值", expected.accept],
          ["预期状态码", String(expected.expected_status)],
          ["实际状态码", String(obs.response_status)],
          ["预期 Content-Type", expected.expected_content_type],
          ["实际 Content-Type", obs.response_content_type],
          ["Sentinel 匹配", obs.sentinel_match ? "匹配" : "不匹配"],
          ["正文 SHA-256（摘要）", hashSummary(obs.body_sha256)],
          ["源站基线结果", passed ? "通过" : "失败"],
        ]),
      );
      grid.appendChild(card);
    }
    section.appendChild(grid);
  }

  // ------------------------------------------------------------------
  // 3. Four experiment states (§6)
  // ------------------------------------------------------------------

  function renderExperiments(report: Report): void {
    const section = show("section-experiments");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "3 · 四种实验状态"));
    section.appendChild(
      el(
        "p",
        "note",
        "四种实验按 §6.1 固定顺序执行，缺一不可；每个实验独立清空缓存 " +
          "（§6.2），暖缓存实验的两次请求之间不清缓存。点击可展开查看每次请求的完整记录。",
      ),
    );
    const cacheMode = report.input.cache_behavior.mode;
    for (const meta of FOUR_EXPERIMENTS) {
      const details = document.createElement("details");
      details.className = "experiment";
      const summary = document.createElement("summary");
      summary.appendChild(el("span", "", meta.label + " — "));
      summary.appendChild(
        el("span", "", experimentStatus(meta, report.observations)),
      );
      details.appendChild(summary);
      const table = document.createElement("table");
      table.className = "requests";
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      for (const label of [
        "请求",
        "请求表示",
        "响应表示",
        "状态码",
        "Content-Type",
        "缓存状态（预期 / 实际）",
        "源站计数变化",
        "Sentinel",
      ]) {
        headRow.appendChild(el("th", "", label));
      }
      head.appendChild(headRow);
      table.appendChild(head);
      const body = document.createElement("tbody");
      for (const index of meta.indices) {
        const obs = report.observations.find(
          (o) => o.request_index === index,
        );
        if (obs === undefined) {
          continue;
        }
        const row = document.createElement("tr");
        row.appendChild(
          el("td", "mono", String(obs.request_index).padStart(3, "0")),
        );
        row.appendChild(el("td", "", representationLabel(obs.requested_representation)));
        row.appendChild(el("td", "", representationLabel(observedRepresentation(obs))));
        row.appendChild(el("td", "mono", String(obs.response_status)));
        row.appendChild(el("td", "mono", obs.response_content_type));
        row.appendChild(
          el(
            "td",
            "",
            expectedCacheState(obs.experiment_id, obs.request_index, cacheMode) +
              " / " +
              (obs.cache_status === null ? "直连" : obs.cache_status),
          ),
        );
        row.appendChild(
          el("td", "mono", obs.origin_counter_delta >= 0 ? `+${obs.origin_counter_delta}` : String(obs.origin_counter_delta)),
        );
        row.appendChild(el("td", "", obs.sentinel_match ? "匹配" : "不匹配"));
        body.appendChild(row);
      }
      table.appendChild(body);
      details.appendChild(table);
      section.appendChild(details);
    }
  }

  // ------------------------------------------------------------------
  // 4. Dual-direction timeline (§4.3 area C)
  // ------------------------------------------------------------------

  function renderTimeline(report: Report): void {
    const section = show("section-timeline");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "4 · 双向缓存时间线"));
    section.appendChild(
      el(
        "p",
        "note",
        "每条时间线以 RESET 开头（§6.2：每个实验独立清空缓存；报告 JSON " +
          "不含重置记录，RESET 在此仅表示实验边界，不是对重置事件的观测断言）。" +
          "暖缓存实验的第一次请求是“存入”步骤，第二次请求是被判定的步骤。",
      ),
    );
    for (const lane of buildLanes(report.observations)) {
      section.appendChild(el("h3", "", lane.title));
      const list = el("ol", "lane");
      for (const step of lane.steps) {
        const item = document.createElement("li");
        if (step.kind === "reset") {
          item.className = "lane-reset";
          item.appendChild(el("span", "", step.label));
          list.appendChild(item);
          continue;
        }
        const obs = step.observation;
        item.className = "lane-request";
        const line = el("span", "");
        line.appendChild(
          el("strong", "", `请求 ${String(obs.request_index).padStart(3, "0")} `),
        );
        line.appendChild(
          document.createTextNode(
            `${representationLabel(obs.requested_representation)} → ` +
              `${representationLabel(observedRepresentation(obs))} · ` +
              `缓存 ${obs.cache_status ?? "直连"} · ` +
              `键摘要 ${cacheKeySummary(obs.cache_key_sha256)} · ` +
              `条目 ${obs.cache_entry_id ?? "—"} · ` +
              `源站计数 ${obs.origin_counter_delta >= 0 ? "+" : ""}${obs.origin_counter_delta} · ` +
              `Sentinel ${obs.sentinel_match ? "匹配" : "不匹配"}`,
          ),
        );
        item.appendChild(line);
        list.appendChild(item);
      }
      section.appendChild(list);
    }
  }

  // ------------------------------------------------------------------
  // 5. Cache evidence (§5.3 dual evidence)
  // ------------------------------------------------------------------

  function renderCacheEvidence(report: Report): void {
    const section = show("section-cache");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "5 · 缓存证据"));
    section.appendChild(
      el(
        "p",
        "note",
        "每个缓存状态必须同时具备响应头证据与源站行为证据（§5.3 / §7.7 I-07），" +
          "两者缺一不可：MISS / BYPASS 要求源站计数 +1，HIT 要求源站计数不变。基线请求 " +
          "001 / 002 直连源站，不经过缓存，无缓存证据。",
      ),
    );
    const table = document.createElement("table");
    table.className = "requests";
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const label of [
      "请求",
      "实验",
      "响应头证据（缓存状态）",
      "行为证据（源站计数变化）",
      "双重证据",
      "缓存键摘要",
      "缓存条目 ID",
    ]) {
      headRow.appendChild(el("th", "", label));
    }
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement("tbody");
    for (const obs of report.observations) {
      const row = document.createElement("tr");
      row.appendChild(el("td", "mono", String(obs.request_index).padStart(3, "0")));
      row.appendChild(el("td", "", obs.experiment_id));
      row.appendChild(el("td", "", obs.cache_status ?? "直连（无）"));
      row.appendChild(
        el("td", "mono", obs.origin_counter_delta >= 0 ? `+${obs.origin_counter_delta}` : String(obs.origin_counter_delta)),
      );
      row.appendChild(
        el("td", "", DUAL_EVIDENCE_LABELS[dualEvidenceAgreement(obs)] ?? "—"),
      );
      row.appendChild(el("td", "mono", cacheKeySummary(obs.cache_key_sha256)));
      row.appendChild(el("td", "mono", obs.cache_entry_id ?? "—"));
      body.appendChild(row);
    }
    table.appendChild(body);
    section.appendChild(table);
  }

  // ------------------------------------------------------------------
  // 6. First-error location (§4.3 area D, §6.3)
  // ------------------------------------------------------------------

  function renderFirstError(report: Report): void {
    const section = show("section-first-error");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "6 · 首次错误定位"));
    section.appendChild(
      el(
        "p",
        "note",
        "first_error 是整个运行中第一个违反冻结契约的请求（§6.3），按实际执行顺序编号，" +
          "不按诊断严重程度重排；首次错误与最终裁决分别存储，后续更严重的错误不改写历史请求顺序。",
      ),
    );
    const obs = firstErrorObservation(report);
    if (obs === null || report.first_error === null) {
      section.appendChild(el("p", "", "无首次错误：全部 8 个请求均符合冻结契约。"));
      return;
    }
    section.appendChild(
      kvTable([
        ["请求序号", String(report.first_error).padStart(3, "0")],
        ["实验", report.first_error_experiment_id ?? "—"],
        ["请求表示", representationLabel(obs.requested_representation)],
        ["响应表示", representationLabel(observedRepresentation(obs))],
        ["响应状态码", String(obs.response_status)],
        ["响应 Content-Type", obs.response_content_type],
        ["缓存状态", obs.cache_status ?? "直连（无）"],
        ["Sentinel 匹配", obs.sentinel_match ? "匹配" : "不匹配"],
        ["正文 SHA-256（摘要）", hashSummary(obs.body_sha256)],
        ["源站计数变化", obs.origin_counter_delta >= 0 ? `+${obs.origin_counter_delta}` : String(obs.origin_counter_delta)],
      ]),
    );
  }

  // ------------------------------------------------------------------
  // 7. Diagnostic codes (§4.3 area E, §8)
  // ------------------------------------------------------------------

  function renderDiagnostics(report: Report): void {
    const section = show("section-diagnostics");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "7 · 诊断代码"));
    if (report.diagnostics.length === 0) {
      section.appendChild(el("p", "", "无诊断：运行未触发任何诊断代码。"));
      return;
    }
    for (const diag of diagnosticsInOrder(report)) {
      const article = el("article", "diagnostic");
      const head = el("p", "diagnostic-head");
      head.appendChild(el("strong", "mono", diag.code));
      head.appendChild(document.createTextNode(" "));
      head.appendChild(severityBadge(diag.severity));
      const description = DIAGNOSTIC_DESCRIPTIONS[diag.code];
      if (description !== undefined) {
        head.appendChild(document.createTextNode(" — " + description));
      }
      article.appendChild(head);
      article.appendChild(el("p", "", diag.message));
      article.appendChild(
        kvTable([
          ["实验", diag.experiment_id ?? "—"],
          [
            "请求序号",
            diag.request_index === null
              ? "—"
              : String(diag.request_index).padStart(3, "0"),
          ],
        ]),
      );
      const evidence = diag.evidence;
      const keys = Object.keys(evidence);
      if (keys.length > 0) {
        const details = document.createElement("details");
        details.className = "evidence";
        details.appendChild(el("summary", "", "证据引用（" + String(keys.length) + " 项）"));
        const rows: Array<[string, string]> = keys.map((key) => [
          evidenceLabel(key),
          formatEvidenceValue(evidence[key]),
        ]);
        details.appendChild(kvTable(rows));
        article.appendChild(details);
      }
      section.appendChild(article);
    }
  }

  // ------------------------------------------------------------------
  // 8. Oracle parity (§12.4)
  // ------------------------------------------------------------------

  function renderOracle(report: Report): void {
    const section = show("section-oracle");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "8 · Oracle parity"));
    section.appendChild(
      el(
        "p",
        "note",
        "独立 TypeScript Oracle 与生产实现逐场景对账（§12.4）：比较最终裁决、" +
          "诊断投影（code + request_index）与首次错误位置。三项全部一致时 parity 通过，" +
          "报告方可标记最终有效（§4.2 约束 6）。",
      ),
    );
    const table = document.createElement("table");
    table.className = "requests";
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const label of ["", "生产实现", "独立 Oracle"]) {
      headRow.appendChild(el("th", "", label));
    }
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement("tbody");
    const rows: Array<[string, string, string]> = [
      [
        "最终裁决",
        report.verdict,
        report.oracle === null ? "—" : report.oracle.verdict,
      ],
      [
        "首次错误",
        report.first_error === null ? "无" : String(report.first_error),
        report.oracle === null
          ? "—"
          : report.oracle.first_error === null
            ? "无"
            : String(report.oracle.first_error),
      ],
      [
        "首次错误实验",
        report.first_error_experiment_id ?? "—",
        report.oracle === null
          ? "—"
          : report.oracle.first_error_experiment_id ?? "—",
      ],
    ];
    for (const [label, prod, oracle] of rows) {
      const row = document.createElement("tr");
      row.appendChild(el("td", "", label));
      row.appendChild(el("td", "mono", prod));
      row.appendChild(el("td", "mono", oracle));
      body.appendChild(row);
    }
    table.appendChild(body);
    section.appendChild(table);
    section.appendChild(
      kvTable([
        [
          "Oracle parity",
          report.oracle_parity === null
            ? "未提供 Oracle 结果"
            : report.oracle_parity
              ? "一致"
              : "不一致",
        ],
        ["最终有效", report.final ? "是" : "否"],
      ]),
    );
  }

  // ------------------------------------------------------------------
  // 9. Report hash (§10.4)
  // ------------------------------------------------------------------

  function renderHash(report: Report): void {
    const section = show("section-hash");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "9 · 报告哈希"));
    section.appendChild(
      el(
        "p",
        "note",
        "report_hash = SHA-256（规范化 JSON 哈希载荷）（§10.4）：载荷去掉 report_hash 本身与 " +
          "cache_key_sha256 / cache_entry_id / origin_counter_before / origin_counter_after / " +
          "request_url / redirect_target；url 与 origin_url 的临时端口在规范化时归一化为 0（ADR-003）。",
      ),
    );
    section.appendChild(
      kvTable([
        ["报告哈希", report.report_hash],
        ["输入契约 SHA-256", report.input.contract_sha256],
        ["场景 ID", report.scenario_id],
      ]),
    );
    section.appendChild(
      el(
        "p",
        "note",
        "核对：embed_report.py 在生成本页前已用 report_builder.compute_report_hash " +
          "对报告 JSON 重算并比对一致；也可对下载的 JSON 报告重新计算核对。",
      ),
    );
  }

  // ------------------------------------------------------------------
  // 10. Privacy preview (§4.3 area F, §17.3)
  // ------------------------------------------------------------------

  function renderPrivacy(report: Report, exportName: string): void {
    const section = show("section-privacy");
    if (section === null) {
      return;
    }
    clear(section);
    section.appendChild(el("h2", "", "10 · 隐私预览"));
    section.appendChild(
      el(
        "p",
        "note",
        "导出 HTML 之前必须完成隐私预览（§4.2 约束 7、§17.3）：本页在生成时已由 " +
          "embed_report.py 打印预览并通过正文泄漏扫描；以下为本报告的预览结果。",
      ),
    );
    const headers = Object.entries(report.input.request_headers)
      .map(([key, value]) => `${key}=${value}`)
      .join(", ");
    section.appendChild(
      kvTable([
        ["是否包含原始正文", "否"],
        ["是否包含敏感请求头（Authorization / Cookie）", "否"],
        ["是否包含允许展示的请求头", "是（Accept、User-Agent、Accept-Encoding、Accept-Language）"],
        ["允许展示的请求头（实际值）", headers],
        ["是否包含正文原始内容", "否"],
        ["是否包含正文哈希", "是（SHA-256 与 Sentinel 匹配标志）"],
        ["正文原文显示", "不显示 — 本页只显示哈希与匹配标志"],
        ["导出文件", exportName],
        ["导出前预览状态", "已完成"],
      ]),
    );
    const download = el("button", "download-button", "下载 JSON 报告（" + report.scenario_id + ".json）");
    download.setAttribute("type", "button");
    download.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(report, null, 2) + "\n"], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = report.scenario_id + ".json";
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    });
    section.appendChild(download);
    section.appendChild(
      el(
        "p",
        "note",
        "下载内容与本页嵌入的 JSON 报告完全一致（同一份 report JSON），不经过任何网络请求。",
      ),
    );
  }

  // ------------------------------------------------------------------
  // 48-scenario summary (index.html)
  // ------------------------------------------------------------------

  function renderSummary(summary: Summary): void {
    const view = show("summary-view");
    const reportView = show("report-view");
    if (view === null) {
      return;
    }
    if (reportView !== null) {
      reportView.setAttribute("hidden", "");
    }
    view.removeAttribute("hidden");
    clear(view);
    view.appendChild(el("h2", "", "48 场景汇总"));
    view.appendChild(
      el(
        "p",
        "note",
        "由 48 份 JSON 报告样本直接生成（未重跑实验），并与 REPORTS_SUMMARY.json 逐项核对一致。" +
          "点击“查看报告”打开对应场景的自包含 HTML 报告（相对链接，不访问外部网址）。",
      ),
    );
    const chips = el("p", "summary-chips");
    for (const verdict of VERDICTS) {
      const count = summary.counts[verdict] ?? 0;
      chips.appendChild(
        el("span", "summary-chip verdict-" + verdict, `${verdict} ${count}`),
      );
    }
    chips.appendChild(el("span", "summary-chip", `共 ${summary.total} 场景`));
    view.appendChild(chips);
    const table = document.createElement("table");
    table.className = "requests";
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const label of [
      "场景",
      "最终裁决",
      "首次错误",
      "CRITICAL",
      "WARNING",
      "Oracle parity",
      "最终",
      "报告哈希（前 12 位）",
      "",
    ]) {
      headRow.appendChild(el("th", "", label));
    }
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement("tbody");
    for (const row of summary.rows) {
      const tr = document.createElement("tr");
      tr.appendChild(el("td", "mono", row.scenario_id));
      const verdictCell = document.createElement("td");
      verdictCell.appendChild(verdictBadge(row.verdict));
      tr.appendChild(verdictCell);
      tr.appendChild(
        el("td", "mono", row.first_error === null ? "—" : String(row.first_error)),
      );
      tr.appendChild(el("td", "mono", String(row.critical_count)));
      tr.appendChild(el("td", "mono", String(row.warning_count)));
      tr.appendChild(
        el("td", "", row.oracle_parity === null ? "未提供" : row.oracle_parity ? "一致" : "不一致"),
      );
      tr.appendChild(el("td", "", row.final ? "是" : "否"));
      tr.appendChild(el("td", "mono", row.report_hash.slice(0, 12)));
      const linkCell = document.createElement("td");
      const link = document.createElement("a");
      link.href = row.scenario_id + ".html";
      link.textContent = "查看报告";
      linkCell.appendChild(link);
      tr.appendChild(linkCell);
      body.appendChild(tr);
    }
    table.appendChild(body);
    view.appendChild(table);
  }

  // ------------------------------------------------------------------
  // Bootstrap
  // ------------------------------------------------------------------

  function readPayload<T>(id: string): T | null {
    const node = document.getElementById(id);
    if (node === null || node.textContent === null) {
      return null;
    }
    const text = node.textContent.trim();
    if (text === "") {
      return null;
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      return null;
    }
  }

  export function init(): void {
    const report = readPayload<Report>("accepttwin-report");
    const baseline = readPayload<Baseline>("accepttwin-baseline");
    const summary = readPayload<Summary>("accepttwin-summary");
    const notice = show("no-payload");
    if (report !== null) {
      if (notice !== null) {
        notice.setAttribute("hidden", "");
      }
      document.title = `AcceptTwin 报告 — ${report.scenario_id} · ${report.verdict}`;
      const heading = show("report-title");
      if (heading !== null) {
        heading.textContent = `AcceptTwin 报告 — ${report.scenario_id}`;
      }
      const fallback: Baseline = {
        html: {
          accept: "text/html",
          expected_status: 200,
          expected_content_type: "text/html; charset=utf-8",
        },
        markdown: {
          accept: "text/markdown",
          expected_status: 200,
          expected_content_type: "text/markdown; charset=utf-8",
        },
      };
      renderVerdict(report);
      renderBaselines(report, baseline ?? fallback);
      renderExperiments(report);
      renderTimeline(report);
      renderCacheEvidence(report);
      renderFirstError(report);
      renderDiagnostics(report);
      renderOracle(report);
      renderHash(report);
      renderPrivacy(report, report.scenario_id + ".html");
      return;
    }
    if (summary !== null) {
      if (notice !== null) {
        notice.setAttribute("hidden", "");
      }
      document.title = "AcceptTwin 报告 — 48 场景汇总";
      const heading = show("report-title");
      if (heading !== null) {
        heading.textContent = "AcceptTwin 报告 — 48 场景汇总";
      }
      renderSummary(summary);
      return;
    }
    // No payload embedded: this is the bare template. The static
    // notice in the template stays visible and explains how to
    // generate a real report page.
  }
}

AcceptTwinUI.init();
```

## report-ui/src/diagnostics.ts

- SHA-256：`591542a5aca51db9798f48cae15a4f6dcbbc8d8160f42c2bede9f23aeb1c7c63`
- 字节数：5474

```
/**
 * Diagnostics and first-error presentation (P032 T010).
 *
 * Pure functions over the frozen §8 diagnostics and the §6.3
 * first-error location — no DOM here. Nothing in this module
 * re-derives a verdict or a diagnostic: it only formats what the
 * report already contains. Evidence values are rendered
 * generically (hashes, flags, counters, loopback URLs, the fixed
 * ``redacted:non-loopback`` marker); raw body text can never
 * appear because the report itself never carries it (§7.12 I-12),
 * and ``scripts/embed_report.py`` additionally scans the finished
 * HTML for the Sentinel literals before writing it.
 */

/// <reference path="./types.ts" />

namespace AcceptTwinUI {
  /** One-line §8 descriptions (presentation labels only). */
  export const DIAGNOSTIC_DESCRIPTIONS: Record<string, string> = {
    ORIGIN_NEGOTIATION_ERROR: "源站基线未按表示契约返回正确内容",
    REPRESENTATION_BLEED: "暖缓存第二请求得到了另一种表示（已证实串版）",
    CONTRACT_MISMATCH: "响应不符合声明契约",
    CACHE_STATE_UNKNOWN: "无法用双重证据确认缓存状态",
    SENTINEL_MISMATCH: "响应正文缺少请求表示应有的精确 Sentinel",
    INCONCLUSIVE_LIMIT: "超出首版支持范围，无法形成可靠判断",
    VARY_ACCEPT_ABSENT: "源站响应未声明 Vary: Accept",
    CACHE_EVIDENCE_CONFLICT: "代理报告的缓存状态与源站行为证据不一致",
    CACHE_POLICY_MISMATCH: "代理实际行为与契约声明的缓存模式冲突",
  };

  /**
   * Chinese labels for evidence keys seen in §8 diagnostics.
   * Unknown keys fall back to the key itself — the value is still
   * shown, never dropped silently.
   */
  export function evidenceLabel(key: string): string {
    const labels: Record<string, string> = {
      body_sha256: "正文 SHA-256",
      body_size: "正文大小（字节）",
      cache_control: "Cache-Control",
      cache_entry_count_after: "缓存条目数（后）",
      cache_entry_count_before: "缓存条目数（前）",
      cache_entry_id: "缓存条目 ID",
      cache_key_sha256: "缓存键 SHA-256",
      cache_reset_confirmed: "缓存重置已确认",
      cache_status: "缓存状态",
      declared_cache_mode: "契约声明的缓存模式",
      evidence_conflict: "证据冲突",
      evidence_consistent: "证据一致",
      expected: "预期",
      expected_content_type: "预期 Content-Type",
      expected_sentinel_sha256: "预期 Sentinel SHA-256",
      expected_status: "预期状态码",
      experiment_id: "实验",
      first_request_index: "首次请求序号",
      limit_code: "超出范围原因",
      observed: "实际",
      observed_content_type: "实际 Content-Type",
      observed_representation: "实际表示",
      observed_status: "实际状态码",
      observed_cache_status: "实际缓存状态",
      origin_counter_after: "源站计数（后）",
      origin_counter_before: "源站计数（前）",
      origin_counter_delta: "源站计数变化",
      origin_direct: "直连源站",
      origin_journal_available: "源站事件日志可用",
      proxy_cache_header_present: "代理缓存状态头存在",
      proxy_reported_status: "代理报告的状态",
      redirect_target: "重定向目标",
      request_index: "请求序号",
      request_url: "请求 URL",
      requested_representation: "请求表示",
      response_content_type: "响应 Content-Type",
      response_status: "响应状态码",
      sentinel_match: "Sentinel 匹配",
      stage: "阶段",
      supported_limit: "支持上限",
      vary_accept: "Vary 要求",
    };
    return labels[key] ?? key;
  }

  /**
   * Render one evidence value as plain text. Nested ``expected`` /
   * ``observed`` objects flatten one level (``status=200,
   * content_type=…``). Booleans render as 是/否; null renders as
   * an em dash. No value is ever interpreted as HTML — callers
   * must assign the result via ``textContent``.
   */
  export function formatEvidenceValue(value: unknown): string {
    if (value === null || value === undefined) {
      return "—";
    }
    if (typeof value === "boolean") {
      return value ? "是" : "否";
    }
    if (typeof value === "number") {
      return String(value);
    }
    if (typeof value === "string") {
      return value;
    }
    if (Array.isArray(value)) {
      return value.map((item) => formatEvidenceValue(item)).join(", ");
    }
    if (typeof value === "object") {
      return Object.entries(value as Record<string, unknown>)
        .map(([key, item]) => `${key}=${formatEvidenceValue(item)}`)
        .join(", ");
    }
    return String(value);
  }

  /** The observation the first error points at, or null. */
  export function firstErrorObservation(
    report: Report,
  ): ReportObservation | null {
    if (report.first_error === null) {
      return null;
    }
    return (
      report.observations.find(
        (obs) => obs.request_index === report.first_error,
      ) ?? null
    );
  }

  /** Diagnostics sorted by request order (§6.3: never re-sorted by
   * severity — the report's order is the execution order). */
  export function diagnosticsInOrder(report: Report): ReportDiagnostic[] {
    return [...report.diagnostics].sort((a, b) => {
      const ra = a.request_index ?? Number.MAX_SAFE_INTEGER;
      const rb = b.request_index ?? Number.MAX_SAFE_INTEGER;
      return ra - rb;
    });
  }
}
```

## report-ui/src/timeline.ts

- SHA-256：`dd137172d4859cb8241d901d391372df1108bded198d504fa07b8d673ba65cc2`
- 字节数：7040

```
/**
 * Dual-direction cache timeline (P032 T010).
 *
 * Pure functions over the eight frozen §5.5 observations — no DOM
 * here, so this logic is independently checkable. The timeline
 * follows PROJECT_BOOK §4.3 area C:
 *
 *   lane 1: RESET → HTML MISS → Markdown MISS / HIT / BYPASS
 *   lane 2: RESET → Markdown MISS → HTML MISS / HIT / BYPASS
 *
 * The §6.3 fixed sequence has eight requests, so each lane shows
 * the warm experiment's *store* request explicitly between the cold
 * request and the warm second request (005 between 003 and 006;
 * 007 between 004 and 008): hiding the store request would drop
 * evidence, and the lane headline is still the second warm
 * request's cache state, exactly as §4.3 area C specifies.
 *
 * The RESET markers are structural: §6.2 requires each experiment
 * to reset the cache independently, but the frozen report JSON
 * carries no reset records, so a marker means "experiment boundary
 * — cache reset per §6.2", not an observed reset event. The UI
 * labels it as such; nothing here invents reset evidence.
 */

/// <reference path="./types.ts" />

namespace AcceptTwinUI {
  /**
   * The representation actually observed, derived only from the
   * response Content-Type (§5.1.2 frozen values). "unknown" when
   * the Content-Type matches neither representation — the raw
   * Content-Type string is shown alongside, never body text.
   */
  export function observedRepresentation(
    obs: ReportObservation,
  ): "html" | "markdown" | "unknown" {
    const ct = obs.response_content_type.toLowerCase();
    if (ct.startsWith("text/html")) {
      return "html";
    }
    if (ct.startsWith("text/markdown")) {
      return "markdown";
    }
    return "unknown";
  }

  /** Chinese label for a requested / observed representation. */
  export function representationLabel(
    rep: "html" | "markdown" | "unknown",
  ): string {
    if (rep === "html") {
      return "HTML";
    }
    if (rep === "markdown") {
      return "Markdown";
    }
    return "无法识别";
  }

  /**
   * Dual-evidence agreement for one proxied observation (§5.3 /
   * §7.7 I-07): the header state and the origin-counter behaviour
   * must agree — MISS / BYPASS expect the origin counter to rise
   * by 1, HIT expects it to stay flat.
   */
  export function dualEvidenceAgreement(
    obs: ReportObservation,
  ): "agree" | "conflict" | "unknown" | "direct" {
    if (obs.cache_status === null) {
      // Direct-origin baseline (ADR-001): no cache evidence exists.
      return "direct";
    }
    if (obs.cache_status === "CACHE_STATE_UNKNOWN") {
      return "unknown";
    }
    if (obs.cache_status === "HIT") {
      return obs.origin_counter_delta === 0 ? "agree" : "conflict";
    }
    // MISS and BYPASS both require the request to reach the origin.
    return obs.origin_counter_delta === 1 ? "agree" : "conflict";
  }

  export const DUAL_EVIDENCE_LABELS: Record<string, string> = {
    agree: "双重证据一致",
    conflict: "双重证据冲突",
    unknown: "缓存状态无法确认",
    direct: "直连源站，不经过缓存",
  };

  /**
   * Cache-key summary (§4.3 area C: "缓存键摘要"): the first 16
   * hex characters of the key hash plus an ellipsis. The full hash
   * stays in the embedded report JSON (and in the downloadable
   * JSON); the UI shows only the summary. Null when no key exists
   * (origin baselines, unconfirmed states).
   */
  export function cacheKeySummary(
    cacheKeySha256: string | null,
  ): string {
    if (cacheKeySha256 === null || cacheKeySha256 === "") {
      return "—";
    }
    return cacheKeySha256.slice(0, 16) + "…";
  }

  /** One step of a timeline lane. */
  export type TimelineStep =
    | { kind: "reset"; label: string }
    | { kind: "request"; observation: ReportObservation };

  export interface TimelineLane {
    id: "HTML_TO_MARKDOWN" | "MARKDOWN_TO_HTML";
    title: string;
    steps: TimelineStep[];
  }

  const RESET_STEP: TimelineStep = {
    kind: "reset",
    label: "RESET — 按 §6.2 独立清空缓存（实验边界标记）",
  };

  /**
   * Build the two §4.3 area C lanes from the eight observations.
   * Lane 1 covers requests 003 (HTML cold) → 005 (warm store) →
   * 006 (warm second); lane 2 covers 004 → 007 → 008.
   */
  export function buildLanes(
    observations: ReportObservation[],
  ): TimelineLane[] {
    const byIndex = new Map<number, ReportObservation>();
    for (const obs of observations) {
      byIndex.set(obs.request_index, obs);
    }
    const pick = (indices: number[]): TimelineStep[] => {
      const steps: TimelineStep[] = [RESET_STEP];
      for (const index of indices) {
        const obs = byIndex.get(index);
        if (obs !== undefined) {
          steps.push({ kind: "request", observation: obs });
        }
      }
      return steps;
    };
    return [
      {
        id: "HTML_TO_MARKDOWN",
        title: "方向一：HTML → Markdown（实验 3）",
        steps: pick([3, 5, 6]),
      },
      {
        id: "MARKDOWN_TO_HTML",
        title: "方向二：Markdown → HTML（实验 4）",
        steps: pick([4, 7, 8]),
      },
    ];
  }

  /**
   * One-line status for one of the four §6 experiments, derived
   * from its observations: request count, cache-state chain,
   * Sentinel match rate. Never claims more than the observations
   * show.
   */
  export function experimentStatus(
    meta: ExperimentMeta,
    observations: ReportObservation[],
  ): string {
    const obs = meta.indices
      .map((index) => observations.find((o) => o.request_index === index))
      .filter((o): o is ReportObservation => o !== undefined);
    if (obs.length === 0) {
      return "无观测记录";
    }
    const states = obs.map((o) =>
      o.cache_status === null ? "直连" : o.cache_status,
    );
    const matched = obs.filter((o) => o.sentinel_match).length;
    const chain = states.join(" → ");
    return (
      `完成 · ${obs.length} 个请求 · 缓存 ${chain} · ` +
      `Sentinel 匹配 ${matched}/${obs.length}`
    );
  }

  /**
   * Expected cache state for one request under §6.1, given the
   * contract's cache mode. Used only as a *label* ("预期") next to
   * the observed state — the verdict itself is never recomputed
   * here.
   */
  export function expectedCacheState(
    experimentId: ExperimentId,
    requestIndex: number,
    cacheMode: string,
  ): string {
    const bypass = cacheMode === "no_store";
    if (experimentId === "ORIGIN_HTML" || experimentId === "ORIGIN_MARKDOWN") {
      return "直连源站，无缓存状态";
    }
    if (experimentId === "HTML_COLD" || experimentId === "MARKDOWN_COLD") {
      return bypass ? "BYPASS" : "MISS";
    }
    // Warm experiments: first request stores, second is judged.
    const isFirst = requestIndex === 5 || requestIndex === 7;
    if (isFirst) {
      return bypass ? "BYPASS" : "MISS";
    }
    return bypass ? "BYPASS" : "MISS（正确隔离）/ HIT（串版证据）";
  }
}
```

## report-ui/src/types.ts

- SHA-256：`8cbe1a1694fda7bbfc01bd6c9d37b2c97e1505038bcfb3cf06137ba4f131fd18`
- 字节数：6823

```
/**
 * Report data types for the AcceptTwin self-contained HTML report
 * (P032 T010).
 *
 * These types mirror the frozen ``accepttwin.report/v1`` JSON shape
 * built by ``src/accepttwin/report_builder.py`` (PROJECT_BOOK §14,
 * §5.8) — they describe data, they never re-decide a verdict. The
 * UI only renders what the report already contains: no raw response
 * body text and no sensitive request header ever appears here
 * (§7.12 I-12, §17.2), and the Sentinel *values* are never carried
 * in any field below (only ``sentinel_match`` booleans and
 * ``body_sha256`` / ``expected_sentinel_sha256`` hashes).
 *
 * The four modules of this directory follow PROJECT_BOOK §15.3
 * (frontend module tree — the full list was truncated in the frozen
 * extraction, D-04; the surviving names are app / types / timeline /
 * diagnostics): types (this file), timeline (dual-direction cache
 * lanes), diagnostics (diagnostic + first-error presentation) and
 * app (DOM rendering + bootstrap).
 */

namespace AcceptTwinUI {
  /** The five frozen final verdicts (PROJECT_BOOK §9). */
  export type Verdict =
    | "PASS_OBSERVED"
    | "ORIGIN_NEGOTIATION_ERROR"
    | "REPRESENTATION_BLEED"
    | "CONTRACT_MISMATCH"
    | "INCONCLUSIVE";

  export const VERDICTS: readonly Verdict[] = [
    "PASS_OBSERVED",
    "ORIGIN_NEGOTIATION_ERROR",
    "REPRESENTATION_BLEED",
    "CONTRACT_MISMATCH",
    "INCONCLUSIVE",
  ];

  /** Chinese labels for the five verdicts (presentation only). */
  export const VERDICT_LABELS: Record<Verdict, string> = {
    PASS_OBSERVED: "通过（已观测）",
    ORIGIN_NEGOTIATION_ERROR: "源站协商错误",
    REPRESENTATION_BLEED: "表示串版",
    CONTRACT_MISMATCH: "契约不符",
    INCONCLUSIVE: "证据不足",
  };

  /** Diagnostic severity — only CRITICAL / WARNING exist (§8). */
  export type Severity = "CRITICAL" | "WARNING";

  /** Verified dual-evidence cache state (§5.3); null only on the two
   * direct-origin baselines, which never pass through the cache
   * (ADR-001). */
  export type CacheStatus =
    | "MISS"
    | "HIT"
    | "BYPASS"
    | "CACHE_STATE_UNKNOWN"
    | null;

  /** The six frozen experiment ids (§6.3). */
  export type ExperimentId =
    | "ORIGIN_HTML"
    | "ORIGIN_MARKDOWN"
    | "HTML_COLD"
    | "MARKDOWN_COLD"
    | "HTML_TO_MARKDOWN"
    | "MARKDOWN_TO_HTML";

  export const EXPERIMENT_IDS: readonly ExperimentId[] = [
    "ORIGIN_HTML",
    "ORIGIN_MARKDOWN",
    "HTML_COLD",
    "MARKDOWN_COLD",
    "HTML_TO_MARKDOWN",
    "MARKDOWN_TO_HTML",
  ];

  /** One frozen §5.5 observation, as carried by the report. */
  export interface ReportObservation {
    request_index: number;
    experiment_id: ExperimentId;
    requested_representation: "html" | "markdown";
    response_status: number;
    response_content_type: string;
    body_sha256: string;
    sentinel_match: boolean;
    cache_status: CacheStatus;
    cache_key_sha256: string | null;
    cache_entry_id: string | null;
    origin_counter_delta: number;
  }

  /** One frozen §8 diagnostic, as carried by the report. */
  export interface ReportDiagnostic {
    code: string;
    severity: Severity;
    message: string;
    experiment_id: ExperimentId | null;
    request_index: number | null;
    evidence: Record<string, unknown>;
  }

  export interface ReportInput {
    contract_id: string;
    contract_sha256: string;
    url: string;
    origin_url: string;
    cache_behavior: {
      mode: string;
      vary_accept: string;
      max_age_seconds: number | null;
    };
    request_headers: Record<string, string>;
  }

  /** The full ``accepttwin.report/v1`` report (§14.3). */
  export interface Report {
    schema: string;
    project: { project_id: string; version: string };
    scenario_id: string;
    input: ReportInput;
    observations: ReportObservation[];
    diagnostics: ReportDiagnostic[];
    verdict: Verdict;
    first_error: number | null;
    first_error_experiment_id: ExperimentId | null;
    critical_count: number;
    warning_count: number;
    reasons: string[];
    oracle: {
      verdict: Verdict;
      first_error: number | null;
      first_error_experiment_id: ExperimentId | null;
    } | null;
    oracle_parity: boolean | null;
    final: boolean;
    report_hash: string;
  }

  /**
   * Baseline expectations for the two representations (§5.1.2).
   * This block is supplied by ``scripts/embed_report.py`` from the
   * run's contract (or, when no contract is given, from the frozen
   * §5.1.2 constants) and contains only Accept / expected status /
   * expected Content-Type — never a Sentinel value.
   */
  export interface BaselineRepresentation {
    accept: string;
    expected_status: number;
    expected_content_type: string;
  }

  export interface Baseline {
    html: BaselineRepresentation;
    markdown: BaselineRepresentation;
  }

  /** One row of the 48-scenario summary (derived from the reports). */
  export interface SummaryRow {
    scenario_id: string;
    verdict: Verdict;
    first_error: number | null;
    critical_count: number;
    warning_count: number;
    oracle_parity: boolean | null;
    final: boolean;
    report_hash: string;
  }

  /** The 48-scenario summary payload embedded in index.html. */
  export interface Summary {
    generated_from: string;
    total: number;
    counts: Record<Verdict, number>;
    rows: SummaryRow[];
  }

  /** Fixed experiment metadata (§6.1, §6.3): order, request indices. */
  export interface ExperimentMeta {
    id: ExperimentId;
    /** Short label, e.g. "实验 3：HTML → Markdown 暖缓存". */
    label: string;
    kind: "baseline" | "cold" | "warm";
    /** Request indices belonging to this experiment (§6.3). */
    indices: number[];
  }

  export const EXPERIMENTS: readonly ExperimentMeta[] = [
    {
      id: "ORIGIN_HTML",
      label: "源站 HTML 基线（O-H）",
      kind: "baseline",
      indices: [1],
    },
    {
      id: "ORIGIN_MARKDOWN",
      label: "源站 Markdown 基线（O-M）",
      kind: "baseline",
      indices: [2],
    },
    {
      id: "HTML_COLD",
      label: "实验 1：HTML 独立冷请求",
      kind: "cold",
      indices: [3],
    },
    {
      id: "MARKDOWN_COLD",
      label: "实验 2：Markdown 独立冷请求",
      kind: "cold",
      indices: [4],
    },
    {
      id: "HTML_TO_MARKDOWN",
      label: "实验 3：HTML → Markdown 暖缓存",
      kind: "warm",
      indices: [5, 6],
    },
    {
      id: "MARKDOWN_TO_HTML",
      label: "实验 4：Markdown → HTML 暖缓存",
      kind: "warm",
      indices: [7, 8],
    },
  ];

  /** The four experiments of §6 (the two baselines excluded). */
  export const FOUR_EXPERIMENTS: readonly ExperimentMeta[] = EXPERIMENTS.filter(
    (meta) => meta.kind !== "baseline",
  );
}
```

## report-ui/T010_NOTES.md

- SHA-256：`6772b6a187949bba5b8df7f8b32c0ec321e11588b61f6a855845e156efa459ee`
- 字节数：7732

```
# T010 — 自包含 HTML 报告（P032）

## 交付物

- `report-ui/src/types.ts` — 报告 JSON 类型与冻结实验元数据（§6.1/§6.3）。
- `report-ui/src/timeline.ts` — 双向缓存时间线纯函数（§4.3 区域 C）与双重证据一致性判定（§5.3）。
- `report-ui/src/diagnostics.ts` — 诊断展示与首次错误定位纯函数（§8/§6.3）。
- `report-ui/src/app.ts` — DOM 渲染（十项界面）与启动；全部数据经 `textContent` 插入，绝无 `innerHTML`。
- `report-ui/tsconfig.json` / `report-ui/package.json` / `report-ui/package-lock.json` — TypeScript 5.9.3 精确锁定（离线可装，见下）；`npm run build` 生成 `report-ui/report-ui.js`。
- `report-ui/report-ui.js` — 已提交的编译产物（tsc 单文件输出，无打包器、无运行时依赖）。
- `report-ui/index.html` — 模板：静态页眉/页脚 + 十个空章节 + 三个 JSON 载荷槽 + 内嵌脚本槽；直接打开显示“未嵌入报告数据”说明。
- `report-ui/styles.css` — 全部样式（系统字体栈，无任何外部引用）。
- `scripts/embed_report.py` — 生成器：校验 → 隐私预览（先于写入）→ 扫描 → 写入；`--all-48` 生成 48 页 + 汇总。
- `tests/integration/test_report_ui.py` — 21 个测试（全量 761 passed，基线 740 + 新增 21）。
- `evidence/Reports/html/<sid>.html`（48）+ `evidence/Reports/html/index.html` — 生成的 HTML 报告样本与 48 场景汇总。

## 界面十项与规格映射

| # | 界面项 | 位置 | 规格依据 |
| --- | --- | --- | --- |
| 1 | 最终裁决 | section-verdict | §4.3 区域 A |
| 2 | HTML/Markdown 基线 | section-baseline | §4.3 区域 B |
| 3 | 四种实验状态 | section-experiments | §6（可展开/折叠，§14.4） |
| 4 | 双向时间线 | section-timeline | §4.3 区域 C |
| 5 | 缓存证据 | section-cache | §5.3 双重证据 |
| 6 | 首次错误定位 | section-first-error | §4.3 区域 D、§6.3 |
| 7 | 诊断代码 | section-diagnostics | §4.3 区域 E、§8 |
| 8 | Oracle parity | section-oracle | §12.4 |
| 9 | 报告哈希 | section-hash | §10.4、ADR-003 |
| 10 | 隐私预览 | section-privacy | §4.3 区域 F、§17.3 |

## 设计决定（与规格的张力，如实记录）

1. **TypeScript 而非手写 JS**：§15.3/§16.3 要求前端用 TypeScript。§15.3 的前端模块树在冻结提取中被截断（D-04），只存活了 app.ts / types.ts / timeline.ts / diagnostics.ts 四个名字——本实现恰好采用这四个模块，不补编不存在的模块名。编译用 `tsc --outFile` + `namespace`（无打包器），因为冻结环境中无 bundler；`erasableSyntaxOnly` 未启用（namespace 不是可擦除语法）。TypeScript 5.9.3 已验证可从本机 npm 缓存完全离线安装（`npm install --offline`，731ms），`package-lock.json` 已锁定；`node_modules/` 不提交（见 `.gitignore` 追加）。
2. **基线“预期”值的来源**：报告 JSON（T009 设计）不含 `representations`，因此基线表的预期状态码/Content-Type/Accept 来自 `--contract` 传入的运行契约（只复制 accept / expected_status / expected_content_type 三个安全字段，绝不复制 Sentinel 值），或无契约时取冻结 §5.1.2 常量。已核实 48 份契约的 representations 完全相同，故两种来源结果一致。基线块以独立的第二个 JSON 载荷嵌入，报告 JSON 本身绝不改动。
3. **时间线 RESET 标记**：§4.3 区域 C 的两条时间线以 RESET 开头；报告 JSON 不含重置记录，因此 RESET 在此仅表示“§6.2 实验边界”，页面与 `timeline.ts` 注释中均明确说明，不伪装成观测到的重置事件。
4. **暖缓存“存入”请求不隐藏**：§4.3 区域 C 的 lane 简写只画了冷请求与暖缓存第二请求，但 §6.3 固定序列有 8 个请求；时间线把暖缓存第一次请求（005/007）明确画在冷请求与第二请求之间，lane 标题仍以第二请求的缓存状态为准。不隐藏证据。
5. **缓存键与正文哈希的显示粒度**：时间线/基线/缓存表显示缓存键 SHA-256 与 `body_sha256` 的前 16 位摘要 + `…`（§4.3 区域 C 称“缓存键摘要”）；诊断“证据引用”详情显示完整 64 位哈希。完整哈希同时保留在嵌入的 JSON 与可下载的 JSON 报告中。哈希不是正文（§4.3 区域 F 要求报告含正文哈希，§17.2 允许记录正文哈希），显示完整哈希不构成泄漏。`body_sha256` 同理。
6. **汇总页链接是相对链接**：`index.html` 的 48 个“查看报告”链接为 `C11.html` 形式的相对路径（非远程）；单报告页不含任何链接。下载 JSON 按钮在点击时用 Blob 就地生成，不经过网络。
7. **生成物位置**：生成的 48 页 + 汇总放在 `evidence/Reports/html/`（与 T009 的 JSON 样本同目录），因 T013/T014 预期在此找“HTML 报告样本”。`report-ui/` 只放模板与源码，不放生成物。
8. **诚实边界脚注**：页脚引用 VERIFY_LOG.md D-03 中记录的集中表述（分散在 §3.2/§3.3/§7.11 的实质内容），仅作展示，不替代 D-03 终审前集中成条款的要求。

## 隐私与泄漏控制

- 生成器在写入前做：独立 Schema 校验（复用 T009 的 `independent_schema_validator`，不 import 生成器）、禁 key 大小写不敏感扫描（与 `report_builder._FORBIDDEN_KEYS` 同集合）、Sentinel 原文扫描、输入 URL 回环校验、报告哈希用 `report_builder.compute_report_hash` 重算比对（复用唯一规范化实现，不另写）。
- 成品 HTML 再扫一遍：Sentinel 原文、非回环 http(s) URL、`<link>`/`<iframe>`/`<img>`/`<script src>`/`@import`/`url(`/`data:`；`<script>` 恰好 4 个（3 个 JSON 载荷 + 1 个内嵌 bundle）。
- 报告中唯一的 http(s) URL 是诊断证据里的回环 `request_url` / `redirect_target`（E12/E22 形，后者已脱敏为 `redacted:non-loopback`），扫描按回环 host 白名单放行。
- 诊断消息只含 `'` 特殊字符；即便如此，UI 仍只用 `textContent` 插入数据。

## 重建方法

```bash
cd report-ui && npm install --offline && npm run build   # 生成 report-ui.js
cd .. && .venv/bin/python scripts/embed_report.py --all-48  # 生成 48 页 + 汇总
```

## 验收（2026-11-24）

- `.venv/bin/python -m pytest -q` — **761 passed**（基线 740 + T010 新增 21），0 失败。
- `.venv/bin/python scripts/embed_report.py --all-48` — 49 文件，分布 PASS 16 / ORIGIN 7 / BLEED 8 / CONTRACT 4 / INCONCLUSIVE 13，Oracle parity 48/48；两次运行字节一致（`git status` 干净）。
- 无头 Chromium（Playwright 缓存的 chromium-1255，`--host-resolver-rules` 封锁非回环解析）离线渲染：C11 等五种裁决页十个章节均有内容，首次错误“请求 006”、双重证据、下载按钮均已渲染；汇总页 48 行 + 分布 chips 均已渲染。
- 泄漏扫描：48 页 + 汇总均无 Sentinel 原文、无远程引用（grep 与生成器扫描双重确认）。
- HTML↔JSON 一致性抽查：C11（串版）与 C01（PASS）的嵌入 JSON 与源报告逐字段相等（verdict、诊断、首错、哈希、Oracle parity、观测、输入、理由）。

## 未解决的疑问

- 无。§14.2 报告 JSON 示例截断（D-04）不影响本任务：界面以 §14.3 + §5.8 + T009 的 `report_builder` 实现为准，报告字段均来自实际样本而非截断示例。
- 提醒复核员：`report-ui.js` 是已提交的编译产物，`test_compiled_bundle_matches_typescript_sources` 在本地有 `tsc` 时重编译比对字节；无 `tsc` 的环境只断言内容标记（验收时已亲自重编译比对通过）。
```

## report-ui/index.html

- SHA-256：`05f0d1f3211cc9d794da08ceb3c47c28de523b62f9bf33dfb63f0a3fdbc7c061`
- 字节数：3041

```
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AcceptTwin 报告</title>
<!--
  AcceptTwin self-contained report template (P032 T010).
  scripts/embed_report.py replaces the three ACCEPTTWIN placeholders
  below with the inline stylesheet, the compiled report-ui.js bundle
  and the embedded report JSON. The finished page has no remote
  reference of any kind: no CDN, no webfont, no image, no iframe,
  no external link — it opens fully offline.
-->
<style>
<!--ACCEPTTWIN:STYLES-->
</style>
</head>
<body>
<header>
<h1 id="report-title">AcceptTwin 报告</h1>
<p>同一网址，两种表示，验证交付是否正确。Your website serves humans and AI. Make sure it never mixes them up.</p>
<p>项目 P032 · 规格 v1.0.0 · 报告 Schema accepttwin.report/v1</p>
</header>

<div id="no-payload">
<p><strong>未嵌入报告数据。</strong>这是报告模板本身，不是已生成的报告页。</p>
<p>生成方法：<span class="mono">.venv/bin/python scripts/embed_report.py evidence/Reports/C11.json -o evidence/Reports/html/C11.html</span>（需先用 <span class="mono">--contract</span> 传入运行契约，或不传则使用冻结 §5.1.2 常量作基线预期值）。48 场景汇总：<span class="mono">.venv/bin/python scripts/embed_report.py --all-48</span>。</p>
<p>本页不显示正文原文：报告只包含正文 SHA-256 与 Sentinel 匹配标志。</p>
</div>

<noscript>
<p><strong>本报告页需要 JavaScript 渲染。</strong>脚本是内嵌的自包含代码，不访问任何网络；启用 JavaScript 后重新打开即可查看全部十个章节。</p>
</noscript>

<main id="report-view">
<section id="section-verdict"></section>
<section id="section-baseline"></section>
<section id="section-experiments"></section>
<section id="section-timeline"></section>
<section id="section-cache"></section>
<section id="section-first-error"></section>
<section id="section-diagnostics"></section>
<section id="section-oracle"></section>
<section id="section-hash"></section>
<section id="section-privacy"></section>
</main>

<main id="summary-view" hidden></main>

<footer>
<p>诚实边界：本工具只证明“在给定双表示契约、受控缓存与有界场景内，网站按声明交付了正确的表示”，不证明真实 CDN 行为、不修复缓存、不认证网站的 AI 友好度、不保证任何真实网站的交付正确；没有 Vary: Accept 本身不是故障证据。</p>
<p>隐私：本页不包含原始响应正文、Authorization、Cookie 或其他敏感请求头；不上传报告，不自动打开外部网址。</p>
</footer>

<script type="application/json" id="accepttwin-report">
<!--ACCEPTTWIN:REPORT_JSON-->
</script>
<script type="application/json" id="accepttwin-baseline">
<!--ACCEPTTWIN:BASELINE_JSON-->
</script>
<script type="application/json" id="accepttwin-summary">
<!--ACCEPTTWIN:SUMMARY_JSON-->
</script>
<script>
<!--ACCEPTTWIN:SCRIPT-->
</script>
</body>
</html>
```

## report-ui/styles.css

- SHA-256：`6bf873eb24ef318ff6587db6765be0995e7ade7e34a3d06914890208c15c44e2`
- 字节数：4819

```
/* AcceptTwin self-contained report styles (P032 T010).
 *
 * Inlined verbatim by scripts/embed_report.py into every generated
 * HTML page. No external references of any kind: no style imports,
 * no resource references, no webfont, no image, no icon font —
 * system font stack only, so the page renders identically with the
 * network off.
 */

* { box-sizing: border-box; }

body {
  margin: 0 auto;
  max-width: 1020px;
  padding: 24px 20px 64px;
  background: #ffffff;
  color: #1a1a1a;
  font-family: system-ui, -apple-system, "Segoe UI", "Helvetica Neue", sans-serif;
  font-size: 15px;
  line-height: 1.55;
}

header { border-bottom: 3px solid #1a1a1a; margin-bottom: 8px; padding-bottom: 12px; }
header h1 { font-size: 24px; margin: 0 0 4px; }
header p { margin: 2px 0; color: #555555; }

main section {
  border: 1px solid #cccccc;
  border-radius: 6px;
  margin: 18px 0;
  padding: 14px 16px;
}

h2 { font-size: 19px; margin: 0 0 10px; }
h3 { font-size: 16px; margin: 14px 0 6px; }

.note {
  background: #f2f2f2;
  border-left: 4px solid #888888;
  color: #444444;
  font-size: 13px;
  margin: 8px 0 12px;
  padding: 8px 10px;
}

.mono { font-family: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace; font-size: 13px; overflow-wrap: anywhere; }

table { border-collapse: collapse; margin: 8px 0; width: 100%; }
th, td { border: 1px solid #dddddd; padding: 6px 8px; text-align: left; vertical-align: top; }
thead th { background: #f2f2f2; }
table.kv th { background: #f7f7f7; width: 220px; }

.verdict-row { align-items: center; display: flex; flex-wrap: wrap; gap: 12px; }
.verdict-badge {
  border-radius: 4px;
  color: #ffffff;
  display: inline-block;
  font-weight: 700;
  padding: 6px 12px;
}
.verdict-PASS_OBSERVED { background: #1e7d32; }
.verdict-ORIGIN_NEGOTIATION_ERROR { background: #b26a00; }
.verdict-REPRESENTATION_BLEED { background: #b00020; }
.verdict-CONTRACT_MISMATCH { background: #8e24aa; }
.verdict-INCONCLUSIVE { background: #455a64; }
.final-flag { color: #444444; font-size: 14px; }

.severity {
  border-radius: 3px;
  color: #ffffff;
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 7px;
}
.severity-CRITICAL { background: #b00020; }
.severity-WARNING { background: #b26a00; }

.baseline-grid { display: grid; gap: 14px; grid-template-columns: 1fr 1fr; }
.baseline-card { border: 1px solid #dddddd; border-radius: 4px; padding: 10px 12px; }
.baseline-card h3 { margin-top: 0; }

details.experiment { border: 1px solid #dddddd; border-radius: 4px; margin: 10px 0; padding: 8px 12px; }
details.experiment summary { cursor: pointer; font-weight: 700; }
details.evidence { margin-top: 8px; }
details.evidence summary { cursor: pointer; color: #444444; }

table.requests { font-size: 13px; }
table.requests td, table.requests th { padding: 5px 7px; }

ol.lane { list-style: none; margin: 6px 0; padding: 0; }
ol.lane li {
  border-left: 4px solid #888888;
  margin: 6px 0;
  padding: 6px 10px;
}
ol.lane li.lane-reset { background: #f2f2f2; border-left-color: #1a1a1a; font-weight: 700; }
ol.lane li.lane-request { background: #fbfbfb; }

article.diagnostic { border-top: 1px solid #dddddd; margin-top: 12px; padding-top: 10px; }
article.diagnostic:first-of-type { border-top: none; margin-top: 0; padding-top: 0; }
.diagnostic-head { margin: 0 0 6px; }

.summary-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.summary-chip {
  background: #f2f2f2;
  border: 1px solid #cccccc;
  border-radius: 4px;
  display: inline-block;
  font-weight: 700;
  padding: 4px 10px;
}
.summary-chip.verdict-PASS_OBSERVED { background: #e6f2e8; border-color: #1e7d32; color: #1e7d32; }
.summary-chip.verdict-ORIGIN_NEGOTIATION_ERROR { background: #fdf3e0; border-color: #b26a00; color: #7a4a00; }
.summary-chip.verdict-REPRESENTATION_BLEED { background: #fdecea; border-color: #b00020; color: #b00020; }
.summary-chip.verdict-CONTRACT_MISMATCH { background: #f6e8fa; border-color: #8e24aa; color: #8e24aa; }
.summary-chip.verdict-INCONCLUSIVE { background: #eceff1; border-color: #455a64; color: #455a64; }

button.download-button {
  background: #1a1a1a;
  border: none;
  border-radius: 4px;
  color: #ffffff;
  cursor: pointer;
  font-size: 15px;
  margin: 10px 0;
  padding: 10px 16px;
}
button.download-button:hover { background: #444444; }

footer { border-top: 3px solid #1a1a1a; color: #555555; font-size: 13px; margin-top: 28px; padding-top: 12px; }

#no-payload {
  background: #fdf3e0;
  border: 1px solid #b26a00;
  border-radius: 6px;
  margin: 18px 0;
  padding: 14px 16px;
}

@media (max-width: 720px) {
  .baseline-grid { grid-template-columns: 1fr; }
  table.kv th { width: 150px; }
}

@media print {
  body { max-width: none; padding: 0; }
  main section { break-inside: avoid; }
  button.download-button { display: none; }
}
```

## report-ui/package.json

- SHA-256：`5053662d73f3af0d52e9bf309073f4898ccaa5b2f20ab984e709a9f1983e5717`
- 字节数：393

```
{"description":"AcceptTwin (P032 T010): self-contained HTML report UI. TypeScript sources compile to a single report-ui.js bundle (no bundler, no runtime dependency), inlined by scripts/embed_report.py.","devDependencies":{"typescript":"5.9.3"},"engines":{"node":">=24"},"license":"MIT","name":"accepttwin-report-ui","private":true,"scripts":{"build":"tsc -p tsconfig.json"},"version":"1.0.0"}
```

## report-ui/package-lock.json

- SHA-256：`b83b414a3961c7ca7217ac303966b7da01a381c5b84394bb891a3c8fbafd6e16`
- 字节数：798

```
{
  "name": "accepttwin-report-ui",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "accepttwin-report-ui",
      "version": "1.0.0",
      "license": "MIT",
      "devDependencies": {
        "typescript": "5.9.3"
      },
      "engines": {
        "node": ">=24"
      }
    },
    "node_modules/typescript": {
      "version": "5.9.3",
      "resolved": "https://registry.npmjs.org/typescript/-/typescript-5.9.3.tgz",
      "integrity": "sha512-jl1vZzPDinLr9eUt3J/t7V6FgNEw9QjvBPdysz9KfQDD41fQrC2Y4vKQdiaUpFT4bXlb1RHhLpp8wtm6M5TgSw==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "tsc": "bin/tsc",
        "tsserver": "bin/tsserver"
      },
      "engines": {
        "node": ">=14.17"
      }
    }
  }
}
```

## report-ui/tsconfig.json

- SHA-256：`f345f6b8808903dd584d3b24213c8437dd096210893f4add010d138a4ebb54da`
- 字节数：259

```
{"compilerOptions":{"declaration":false,"forceConsistentCasingInFileNames":true,"module":"none","noEmitOnError":true,"outFile":"./report-ui.js","rootDir":"./src","skipLibCheck":true,"sourceMap":false,"strict":true,"target":"ES2024"},"include":["src/**/*.ts"]}
```

## schemas/accepttwin.contract.v1.schema.json

- SHA-256：`ff70c577b0b6cff035ed0f944b9d7f8a586113762799cffaaaf5a92fa15d5987`
- 字节数：3105

```
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://accepttwin.local/schemas/accepttwin.contract.v1.schema.json",
  "title": "AcceptTwin contract",
  "type": "object",
  "required": [
    "schema",
    "contract_id",
    "name",
    "url",
    "origin_url",
    "representations",
    "request_headers",
    "cache_behavior",
    "limits",
    "metadata"
  ],
  "additionalProperties": false,
  "properties": {
    "schema": {
      "const": "accepttwin.contract/v1"
    },
    "contract_id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "url": {
      "type": "string",
      "minLength": 1
    },
    "origin_url": {
      "type": "string",
      "minLength": 1
    },
    "representations": {
      "type": "object",
      "required": [
        "html",
        "markdown"
      ],
      "additionalProperties": false,
      "properties": {
        "html": {
          "$ref": "#/$defs/representation"
        },
        "markdown": {
          "$ref": "#/$defs/representation"
        }
      }
    },
    "request_headers": {
      "type": "object",
      "required": [
        "accept_encoding",
        "user_agent",
        "accept_language"
      ],
      "additionalProperties": false,
      "properties": {
        "accept_encoding": {
          "const": "identity"
        },
        "user_agent": {
          "const": "AcceptTwin/1.0.0"
        },
        "accept_language": {
          "const": "en"
        }
      }
    },
    "cache_behavior": {
      "type": "object",
      "required": [
        "mode"
      ],
      "additionalProperties": false,
      "properties": {
        "mode": {
          "enum": [
            "variant_by_accept",
            "no_store"
          ]
        },
        "vary_accept": {
          "enum": [
            "required",
            "advisory",
            "not_required"
          ]
        },
        "max_age_seconds": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        }
      }
    },
    "limits": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "max_body_bytes": {
          "type": "integer",
          "minimum": 1,
          "maximum": 1048576
        },
        "request_timeout_seconds": {
          "type": "number",
          "exclusiveMinimum": 0
        }
      }
    },
    "metadata": {
      "type": "object"
    }
  },
  "$defs": {
    "representation": {
      "type": "object",
      "required": [
        "accept",
        "expected_status",
        "expected_content_type",
        "sentinel"
      ],
      "additionalProperties": false,
      "properties": {
        "accept": {
          "type": "string",
          "minLength": 1
        },
        "expected_status": {
          "type": "integer"
        },
        "expected_content_type": {
          "type": "string",
          "minLength": 1
        },
        "sentinel": {
          "type": "string",
          "minLength": 1
        }
      }
    }
  }
}
```

## schemas/accepttwin.report.v1.schema.json

- SHA-256：`a7adb7823f629d2da19806f52ccbed03b0f6349899ab8c87cab337d5116ed725`
- 字节数：5859

```
{"$defs":{"diagnostic":{"additionalProperties":false,"properties":{"code":{"enum":["ORIGIN_NEGOTIATION_ERROR","REPRESENTATION_BLEED","CONTRACT_MISMATCH","CACHE_STATE_UNKNOWN","SENTINEL_MISMATCH","INCONCLUSIVE_LIMIT","VARY_ACCEPT_ABSENT","CACHE_EVIDENCE_CONFLICT","CACHE_POLICY_MISMATCH"]},"evidence":{"propertyNames":{"pattern":"^(?!(?i:authorization|cookie|proxy-authorization|set-cookie|body|body_text|response_body)$).*$"},"type":"object"},"experiment_id":{"enum":["ORIGIN_HTML","ORIGIN_MARKDOWN","HTML_COLD","MARKDOWN_COLD","HTML_TO_MARKDOWN","MARKDOWN_TO_HTML",null],"type":["string","null"]},"message":{"minLength":1,"type":"string"},"request_index":{"minimum":1,"type":["integer","null"]},"severity":{"enum":["CRITICAL","WARNING"]}},"required":["code","severity","message","experiment_id","request_index","evidence"],"type":"object"},"observation":{"additionalProperties":false,"properties":{"body_sha256":{"pattern":"^[0-9a-f]{64}$","type":"string"},"cache_entry_id":{"pattern":"^entry-[0-9a-f]{16}$","type":["string","null"]},"cache_key_sha256":{"pattern":"^[0-9a-f]{64}$","type":["string","null"]},"cache_status":{"enum":["MISS","HIT","BYPASS","CACHE_STATE_UNKNOWN",null],"type":["string","null"]},"experiment_id":{"enum":["ORIGIN_HTML","ORIGIN_MARKDOWN","HTML_COLD","MARKDOWN_COLD","HTML_TO_MARKDOWN","MARKDOWN_TO_HTML"]},"origin_counter_delta":{"type":"integer"},"request_index":{"minimum":1,"type":"integer"},"requested_representation":{"enum":["html","markdown"]},"response_content_type":{"minLength":1,"type":"string"},"response_status":{"maximum":599,"minimum":0,"type":"integer"},"sentinel_match":{"type":"boolean"}},"required":["request_index","experiment_id","requested_representation","response_status","response_content_type","body_sha256","sentinel_match","cache_status","cache_key_sha256","cache_entry_id","origin_counter_delta"],"type":"object"}},"$id":"https://accepttwin.local/schemas/accepttwin.report.v1.schema.json","$schema":"https://json-schema.org/draft/2020-12/schema","additionalProperties":false,"description":"Formal machine report accepttwin.report/v1 (PROJECT_BOOK §14.3, P032 T009). No raw response body text, no sensitive request headers, and no non-loopback URL may appear in a report. report_hash is the SHA-256 of the Canonical JSON (§10.4) of the report with the port-bearing / absolute-counter fields of report_builder.REPORT_HASH_EXCLUDED_FIELDS removed (see that module: cache keys are SHA-256s of ephemeral-port URLs, so they cannot be port-normalised and are excluded from the hash input, as are absolute origin counters and port-bearing request/redirect URLs).","properties":{"critical_count":{"minimum":0,"type":"integer"},"diagnostics":{"items":{"$ref":"#/$defs/diagnostic"},"type":"array"},"final":{"type":"boolean"},"first_error":{"minimum":1,"type":["integer","null"]},"first_error_experiment_id":{"enum":["ORIGIN_HTML","ORIGIN_MARKDOWN","HTML_COLD","MARKDOWN_COLD","HTML_TO_MARKDOWN","MARKDOWN_TO_HTML",null],"type":["string","null"]},"input":{"additionalProperties":false,"properties":{"cache_behavior":{"additionalProperties":false,"properties":{"max_age_seconds":{"minimum":0,"type":["integer","null"]},"mode":{"enum":["variant_by_accept","no_store"]},"vary_accept":{"enum":["required","advisory","not_required"]}},"required":["mode"],"type":"object"},"contract_id":{"minLength":1,"type":"string"},"contract_sha256":{"pattern":"^[0-9a-f]{64}$","type":"string"},"origin_url":{"pattern":"^http://(127\\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])|\\[::1\\]|localhost)(:(6553[0-5]|655[0-2][0-9]|65[0-4][0-9]{2}|6[0-4][0-9]{3}|[1-5][0-9]{4}|[1-9][0-9]{0,3}))?(/.*)?$","type":"string"},"request_headers":{"additionalProperties":false,"properties":{"accept_encoding":{"const":"identity"},"accept_language":{"const":"en"},"user_agent":{"const":"AcceptTwin/1.0.0"}},"required":["accept_encoding","user_agent","accept_language"],"type":"object"},"url":{"pattern":"^http://(127\\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])|\\[::1\\]|localhost)(:(6553[0-5]|655[0-2][0-9]|65[0-4][0-9]{2}|6[0-4][0-9]{3}|[1-5][0-9]{4}|[1-9][0-9]{0,3}))?(/.*)?$","type":"string"}},"required":["contract_id","contract_sha256","url","origin_url","cache_behavior","request_headers"],"type":"object"},"observations":{"items":{"$ref":"#/$defs/observation"},"maxItems":8,"minItems":8,"type":"array"},"oracle":{"additionalProperties":false,"properties":{"first_error":{"minimum":1,"type":["integer","null"]},"first_error_experiment_id":{"enum":["ORIGIN_HTML","ORIGIN_MARKDOWN","HTML_COLD","MARKDOWN_COLD","HTML_TO_MARKDOWN","MARKDOWN_TO_HTML",null],"type":["string","null"]},"verdict":{"enum":["INCONCLUSIVE","ORIGIN_NEGOTIATION_ERROR","REPRESENTATION_BLEED","CONTRACT_MISMATCH","PASS_OBSERVED"]}},"required":["verdict","first_error","first_error_experiment_id"],"type":["object","null"]},"oracle_parity":{"type":["boolean","null"]},"project":{"additionalProperties":false,"properties":{"project_id":{"const":"P032"},"version":{"const":"1.0.1"}},"required":["project_id","version"],"type":"object"},"reasons":{"items":{"type":"string"},"type":"array"},"report_hash":{"pattern":"^[0-9a-f]{64}$","type":"string"},"scenario_id":{"pattern":"^[CE][0-9]{2}$","type":"string"},"schema":{"const":"accepttwin.report/v1"},"verdict":{"enum":["INCONCLUSIVE","ORIGIN_NEGOTIATION_ERROR","REPRESENTATION_BLEED","CONTRACT_MISMATCH","PASS_OBSERVED"]},"warning_count":{"minimum":0,"type":"integer"}},"required":["schema","project","scenario_id","input","observations","diagnostics","verdict","first_error","first_error_experiment_id","critical_count","warning_count","reasons","oracle","oracle_parity","final","report_hash"],"title":"AcceptTwin report","type":"object"}
```

## contracts/site.json

- SHA-256：`1022cc43f5c71b296bb3b8d6bd5c74a7b046f169f62b1b3df300c468a2792857`
- 字节数：958

```
{"cache_behavior":{"max_age_seconds":60,"mode":"variant_by_accept","vary_accept":"advisory"},"contract_id":"site-example-001","limits":{"max_body_bytes":1048576,"request_timeout_seconds":5.0},"metadata":{"note":"Example contract for local synthetic origin (port 18766) behind the controlled cache proxy (port 18765). Same path, different ports, per PROJECT_BOOK §5.1.1."},"name":"Example site (synthetic origin + controlled proxy)","origin_url":"http://127.0.0.1:18766/doc","representations":{"html":{"accept":"text/html","expected_content_type":"text/html; charset=utf-8","expected_status":200,"sentinel":"AT_HTML_SENTINEL_001"},"markdown":{"accept":"text/markdown","expected_content_type":"text/markdown; charset=utf-8","expected_status":200,"sentinel":"AT_MARKDOWN_SENTINEL_001"}},"request_headers":{"accept_encoding":"identity","accept_language":"en","user_agent":"AcceptTwin/1.0.0"},"schema":"accepttwin.contract/v1","url":"http://127.0.0.1:18765/doc"}
```

## pyproject.toml

- SHA-256：`cba02ad97fa635e1d5ebf5740cfb3a6e40bb672aaa10d055faa6d7b22e5865ad`
- 字节数：759

```
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "accepttwin"
version = "1.0.0"
description = "AcceptTwin (P032): same URL, two representations — verify delivery is never mixed up."
readme = "README.md"
# NOTE (T012): README.md now exists (T012 wrote it from the real CLI
# --help output), so the readme pointer is restored; the console
# entry point below is the T012 CLI (verify + benchmark).
license = { text = "MIT" }
requires-python = ">=3.12,<3.13"
dependencies = []

[project.scripts]
accepttwin = "accepttwin.cli:main"

[project.optional-dependencies]
dev = ["pytest==9.2.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

## LICENSE

- SHA-256：`db22e0c9e0d1017ef44fd60a90eb197d41ff22c306d7ce11d1e7bba87a64f28c`
- 字节数：1063

```
MIT License

Copyright (c) 2026 Sam Du

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## THIRD_PARTY_NOTICES.md

- SHA-256：`363c5e53ce857a44a2aeb1b7e9292be80f696e8006055847b848098510d19d2f`
- 字节数：1494

```
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
```

## README.md

- SHA-256：`6b213e79c54c5c35a13ae3f17ed83d741911986770598e34ad50780aeded6445`
- 字节数：7142

```
# AcceptTwin — 网页双态镜 (P032)

> Your website serves humans and AI. Make sure it never mixes them up.

同一 URL 对浏览器返回 HTML、对 AI 返回 Markdown。AcceptTwin 在本地验证：
网站是否**从不把两种表示混淆**——用真实本地 HTTP 请求、四种实验
（两个独立冷请求 + HTML→Markdown、Markdown→HTML 两个暖缓存实验）、
缓存 MISS/HIT/BYPASS 双重证据、五种确定性裁决、48 组固定 Golden，
并用独立 TypeScript Oracle 逐场景对账。

- 规格：`01_project_book/PROJECT_BOOK.md` v1.0.1（冻结）
- 实施计划：`02_implementation_plan/IMPLEMENTATION_PLAN.md`
- 许可证：MIT（见 `LICENSE`；第三方依赖见 `THIRD_PARTY_NOTICES.md`）

## 快速开始

```bash
# 1. 安装（需要 Python 3.12；见 docs/INSTALL.md）
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .            # 生产包，零运行时依赖
.venv/bin/python -m pip install -e ".[dev]"     # 再加 pytest（测试用）

# 2. 验收命令（全部为真实本地运行，无网络、无真人、无收费 API）
.venv/bin/python -m accepttwin verify --suite all
.venv/bin/python -m accepttwin benchmark --suite all
.venv/bin/python -m pytest -q

# 3. 跑你自己的契约（P1-01 已落地，见 docs/USAGE.md）
.venv/bin/python -m accepttwin demo   # 健康 + 故意串版，各跑一次并导出 HTML
.venv/bin/python -m accepttwin run --contract contracts/site.json
.venv/bin/python -m accepttwin verify --report output/runs/demo-healthy/report.json
```

## CLI

```text
usage: accepttwin [-h] [--version] COMMAND ...

AcceptTwin (P032): same URL, two representations — verify delivery is never
mixed up. Local-only, offline, no real users.

positional arguments:
  COMMAND
    run       run one user contract end to end (real experiments + Oracle
              parity + formal report)
    demo      run the bundled example contract twice: healthy (PASS) then a
              deliberate bleed (REPRESENTATION_BLEED), with HTML export
    verify    re-run the Golden gate live (48 scenarios + Oracle parity;
              --suite all also re-runs S0 24/24), or verify one formal report
              file (--report)
    report    preview, export or delete a formal report JSON file
    clean     delete one run's output files under output/runs/<RUN_ID>
    contract  manage stored contracts
    benchmark
              measure per-scenario time (<1s), repeat-100 determinism, and re-
              validate reports + self-contained HTML

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit
```

子命令帮助（逐字引自实际 `--help` 输出，见 `docs/USAGE.md`）：

```text
usage: accepttwin run [-h] --contract CONTRACT [--scenario SCENARIO]
                      [--proxy-mode {respect_vary,force_uri_only,manual_accept_key,disabled,opaque,ignore_no_store}]
                      [--scenario-id SCENARIO_ID] [--run-id RUN_ID]
                      [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --contract CONTRACT   contract JSON file (accepttwin.contract/v1, loopback
                        URLs only)
  --scenario SCENARIO   synthetic origin scenario: a name under
                        fixtures/origin/ or a path to a scenario JSON file
                        (default: healthy)
  --proxy-mode {respect_vary,force_uri_only,manual_accept_key,disabled,opaque,ignore_no_store}
                        controlled proxy mode (§10.3); default follows the
                        contract: variant_by_accept -> respect_vary, no_store
                        -> disabled
  --scenario-id SCENARIO_ID
                        report scenario_id label (C01-C24 / E01-E24); default
                        follows the S0 configuration table for a known
                        (origin scenario, proxy mode) pair
  --run-id RUN_ID       run id (output directory under output/runs/; default:
                        the contract_id)
  --output OUTPUT       report JSON path (default: output/runs/<run-id>/
                        report.json; sibling evidence files land next to it)
```

```text
usage: accepttwin verify [-h] [--suite {s0,all}] [--report REPORT]
                         [--contract CONTRACT]

options:
  -h, --help           show this help message and exit
  --suite {s0,all}     suite to verify: s0 (C01-C24 + repeat-100) or all (48
                       scenarios + S0 re-run) (default: all)
  --report REPORT      verify one formal report JSON file instead of re-
                       running a suite (Schema + hash + privacy + Oracle
                       parity/final)
  --contract CONTRACT  with --report: also check the report's contract_sha256
                       against this contract file
```

```text
usage: accepttwin benchmark [-h] [--suite {all}]

options:
  -h, --help     show this help message and exit
  --suite {all}  suite to benchmark (default: all)
```

其余子命令：`accepttwin demo`（无参数）、`accepttwin report preview <报告>`、
`accepttwin report export <报告>`、`accepttwin report delete <报告>`、
`accepttwin clean --run-id <RUN_ID>`、`accepttwin contract delete <契约>`，用法与示例见
`docs/USAGE.md`。退出码：0 = 命令成功（`run`/`demo` 要求 Oracle parity 成立且报告
`final=true`；报告裁决本身是数据，不决定退出码）；1 = 门禁/核验失败；2 = 输入错误或
拒绝删除。

## 验收命令

| 命令 | 通过标准 |
| --- | --- |
| `.venv/bin/python -m accepttwin verify --suite all` | 48/48 Golden、48/48 Oracle parity、S0 24/24 重跑通过（含 repeat-100） |
| `.venv/bin/python -m accepttwin verify --suite s0` | S0 24/24、parity 24/24、串版 3/3 复现、repeat-100 唯一哈希 |
| `.venv/bin/python -m accepttwin demo` | 健康 `PASS_OBSERVED` + 故意串版 `REPRESENTATION_BLEED`，两份报告均 Oracle parity 且均已导出 HTML |
| `.venv/bin/python -m accepttwin run --contract contracts/site.json` | 真实四实验 + Oracle parity + 正式报告写到 `output/runs/<contract_id>/` |
| `.venv/bin/python -m accepttwin benchmark --suite all` | 单场景 < 1 秒、100 次重复唯一规范化报告哈希、48/48 Schema 有效、49 页 HTML 自包含且与 JSON 一致 |
| `.venv/bin/python -m pytest -q` | 全量测试通过（见 `docs/USAGE.md` 的实测数） |

## 文档

- 安装：`docs/INSTALL.md`
- 使用：`docs/USAGE.md`
- 限制与未测试环境：`docs/LIMITATIONS.md`（未测试的环境一律标 `NOT_TESTED`，不推断为通过）

## 诚实边界

本工具只证明“在给定双表示契约、受控缓存与有界场景内，网站按声明
交付了正确的表示”。它**不**证明真实 CDN 行为、**不**修复缓存、**不**
认证网站的 AI 友好度、**不**保证任何真实网站的交付正确；没有
`Vary: Accept` 本身不是故障证据。完整限制见 `docs/LIMITATIONS.md`。
集中条款见 `00_control/ADR-006.md`（D-03，终审前已集中成单一条款；
规格原文仍分散在 §3.2/§3.3/§7.11，ADR-006 为唯一集中表述）。
```

## docs/INSTALL.md

- SHA-256：`68860ed4bae18803e561b92fe05a7445fea62b7a6b622f5d2eaa8c9500e7237c`
- 字节数：3914

```
# 安装指南 (INSTALL.md) — P032 AcceptTwin，T012

## 已验证的安装环境（实测）

| 项目 | 实测值 |
| --- | --- |
| 操作系统 | Linux（`Linux htch-runtime 7.0.0-44-generic x86_64`） |
| Python | 3.12.3 |
| Node.js | 24.22.1（独立 Oracle 与报告界面构建用） |
| npm | 10.9.4 |
| pytest | 9.2.0（dev 依赖） |
| TypeScript | 5.9.3（`report-ui`，已冻结于 `report-ui/package-lock.json`） |

其他操作系统、Python/Node 版本一律 `NOT_TESTED`（见 `docs/LIMITATIONS.md`）。

## 安装步骤

```bash
git clone <repo>              # 或解包源码
cd p032-accepttwin

python3.12 -m venv .venv
.venv/bin/python -m pip install -e .            # 生产包：零运行时依赖
.venv/bin/python -m pip install -e ".[dev]"     # 测试：pytest==9.2.0
```

`pip install -e .` 会按 `pyproject.toml` 安装可编辑包并注册
`accepttwin` 控制台命令（`accepttwin = "accepttwin.cli:main"`）。
不安装也可以运行：pytest 通过 `pyproject.toml` 的
`pythonpath = ["src"]` 直接用源码；`python -m accepttwin` 在已安装
包时无需额外 `PYTHONPATH`。

## 报告界面构建

```bash
cd report-ui
npm run build    # tsc -p tsconfig.json，用已冻结的 package-lock.json
```

构建只用本地 `report-ui/node_modules/` 中的 TypeScript 5.9.3，
不访问网络。`npm ci`（全新安装依赖）需要访问 npm registry，
**不是**离线步骤；离线复现只需已存在的 `node_modules/`（见
`docs/LIMITATIONS.md` 与 `evidence/Performance/OFFLINE_LOG.txt`）。

冻结重建路径（T014，T013-F03，见 `00_control/ADR-007.md` 决定 8）：
干净检出后 `npm run build` 会失败（`tsc: not found`，
`node_modules/` 未提交）；重建有两条路——(a) 能访问 registry 时
`npm ci`（`package-lock.json` 已锁定 TypeScript 5.9.3）再
`npm run build`；(b) 离线时复用已装 `node_modules/`（钉死 tsc
5.9.3）再 `npm run build`，T013 已验证该重建与已提交
`report-ui.js` 字节一致（SHA-256 `784e3106…`）。已提交的
`report-ui.js` 本身就是冻结产物；无法访问 registry 的干净检出
不能从零重建它，该限制如实记录，不隐藏。

## 离线安装说明

- 生产包 `accepttwin` 本身零运行时依赖（`pyproject.toml` 的
  `dependencies = []`），安装不需要网络下载任何运行库。
- 构建后端为 `setuptools>=69`：`pip install -e .` 默认用构建隔离，
  首次构建会从 PyPI 下载 setuptools；若构建机完全离线，需事先
  在环境中备好 `setuptools>=69` 再用
  `pip install --no-build-isolation --no-index -e .`
  （离线验证实录见 `evidence/Performance/OFFLINE_LOG.txt`）。
- 测试依赖只有 `pytest==9.2.0`（及传递依赖），须事先装好；
  离线时无法现场下载。
- 安装后验证：

```bash
.venv/bin/python -m accepttwin --help
.venv/bin/python -m accepttwin --version   # accepttwin 1.0.0
.venv/bin/python -m accepttwin demo        # 健康 + 故意串版，各跑一次并导出 HTML
.venv/bin/python -m pytest -q
```

`demo` 是最快的端到端自检：两次真实运行（各 8 个真实 HTTP
请求）+ 两次 Oracle 对账 + 两份正式报告 + 两页 HTML，全部在
`output/runs/demo-healthy/` 与 `output/runs/demo-bleed/`。运行
输出（`output/`）是生成文件，已加入 `.gitignore`，不提交。

## 常见问题

- `No module named accepttwin`：包未安装进当前 Python 环境。
  在仓库根目录执行 `.venv/bin/python -m pip install -e .`，
  或用 `PYTHONPATH=src .venv/bin/python -m accepttwin …` 临时运行。
- `node: command not found`：Oracle 对账与 `npm run build` 需要
  Node.js ≥ 24；只跑 Python 单元测试不需要 Node。
- 端口冲突：源站与代理均用 OS 分配的临时回环端口（`port=0`），
  不占用固定端口；报告哈希已把临时端口归一化为 0（ADR-003）。
```

## docs/LIMITATIONS.md

- SHA-256：`f044ef3100b8254d1bd58c72c293e5b00eaee00c25cf7104e61d594516d54f81`
- 字节数：8299

```
# 限制与已知问题 (LIMITATIONS.md) — P032 AcceptTwin，T014

本文档如实列出已知限制。**凡未测试的环境一律标 `NOT_TESTED`，
不得推断为通过。**

## 未测试的环境（NOT_TESTED）

| 环境 | 状态 |
| --- | --- |
| Windows（任意版本） | NOT_TESTED |
| macOS（任意版本） | NOT_TESTED |
| Linux（除实测环境外的发行版/内核） | NOT_TESTED |
| Python ≠ 3.12.3 | NOT_TESTED |
| Node.js ≠ 24.22.1 | NOT_TESTED |
| CPU ≠ x86_64 | NOT_TESTED |
| 真实 CDN / 真实网站 / 公网 | NOT_TESTED（且按设计禁止：产品只接受回环地址，见 §0.2） |
| HTTPS 被测资源 | 不支持（§0.2 第 3 条；首版只支持 HTTP） |

实测环境：Linux `7.0.0-44-generic x86_64`、Python 3.12.3、
Node.js 24.22.1、npm 10.9.4、pytest 9.2.0、TypeScript 5.9.3。

## 已知限制（产品行为）

- 只支持本地回环地址（`127.0.0.0/8`、`::1`、`localhost`）与 HTTP
  GET；不跟随重定向；不读取环境代理变量；不发送 Cookie /
  Authorization；请求头集合固定。
- 不实现缓存重新验证（`no-cache` / `max-age=0` 的响应判
  `INCONCLUSIVE`，`limit_code == "revalidation_required"`，ADR-004）。
- `Vary: *` 下代理不存储（BYPASS）是合规行为，不触发 variant
  策略分句（ADR-004，RFC 9111 §4.1）。
- 正文限制 1 MiB：超限正文判 `INCONCLUSIVE_LIMIT`
  （`body_too_large`）；执行层读取自 T014 起有界（两处读取点只
  保留前 `limit + 1` 字节，见 ADR-007 决定 2），精确大小与整段
  哈希仍被测量。
- CLI 提供全部九条 §4.1 命令（`run` / `demo` / `verify --suite` /
  `verify --report` / `report preview` / `report export` /
  `report delete` / `clean --run-id` / `contract delete`，加
  `--help` / `--version` 与 `benchmark`；P1-01 FIX-R1，见
  `00_control/ADR-008.md`，ADR-005 的延期已被取代）。删除命令
  只接受工作区内显式指定的常规文件：`report delete` 限
  `output/` 或 `evidence/Reports/` 下的报告文件，`contract
  delete` 限 `contracts/` 或 `output/` 下的契约文件，`clean`
  限 `output/runs/<RUN_ID>/` 内的平铺文件；工作区外、符号链接、
  目录一律拒绝。清理脚本 `scripts/clean_evidence.py` 仍只接受
  `evidence/` 子树内的目标（见 ADR-007）。
- `npm ci`（全新安装 `report-ui` 依赖）需要访问 npm registry，
  不是离线步骤；干净检出 `npm run build` 会失败（`tsc: not
  found`），离线重建复用已存在的 `node_modules/`（钉死 tsc
  5.9.3，已验证与已提交 `report-ui.js` 字节一致）；冻结重建
  路径见 `docs/INSTALL.md` 与 ADR-007 决定 8。
- 性能门槛（单场景 < 1 秒）在参考 VM 上实测通过；其他机器上
  的耗时未测量，不得直接套用。

## 残留项（来自各任务复核，全部非阻断，留待 T013/T014）

| ID | 内容 | 状态 |
| --- | --- | --- |
| T003 P2-01 | 源站 `Accept` 的 `q=0` 未返回 406 | CLOSED（T014：`_parse_accept` 跳过 q≤0，RFC 9110 §12.5.1；实况测试已补） |
| T003 P2-02 | q 平局规则无测试 | CLOSED（T014：平局“先列出者胜”实况测试已补） |
| T006 P3 | 分类器 `event_support is False` 分支中 `origin_journal_available` 写为 `(origin_events is not None)` 恒为 True | CLOSED（T014：改为字面 True 加注释，无行为变化） |
| T008 P2-2 | revalidation token 解析为精确匹配，`max-age = 0` 与 `no-cache="field"` 双侧均不触发 | CLOSED（T014：RFC 9111 宽容解析，生产与 Oracle 同步；参数化测试已补） |
| T010 P2-1 | `report-ui/T010_NOTES.md` 称 UI 只显示前 16 位哈希摘要，与实现不符（诊断证据详情显示完整 64 位哈希；行为合规，仅措辞） | CLOSED（T014：措辞已修正） |
| T010 P2-2 | `tests/integration/test_report_ui.py:465,492` 两处条件性 `pytest.skip`（无 Chromium 时跳过离线渲染测试） | CLOSED（T014：改为硬失败 `pytest.fail`，CI 须提供 Chromium） |
| T011 F-01 | `experiment_runner.py:301` 的 `_http_get` 用无界 `resp.read()`；`_max_body` 只赋值从未被读取。超限正文只在进程内存中短暂存在、随即丢弃，哈希与大小是唯一持久化物，无泄漏路径；但故障源站可迫使单次超限分配。**不在 T012 范围内**（`experiment_runner.py` 禁止 T012 修改，修复属 T013/T014） | CLOSED（T014：有界流式读取，见 ADR-007 决定 2） |
| T011 P2 | 清理命令可删子树未收窄：实现为“工作区内 + 显式指定 + 常规文件 + 非符号链接”，满足 §17.3 字面要求，但未收窄到 `evidence/` 等子目录；操作者显式点名即可删除工作区内任意常规文件（含源码） | CLOSED（T014：脚本默认只接受 `evidence/` 子树，CLI 帮助与文档明示；见 ADR-007 决定 7） |
| T012 P2-1 | 项目书 §4.1 其余 CLI 命令未落地（`demo`/`run`/`report preview/export/delete`/`clean`/`contract delete`，`verify --report` 形式亦无） | CLOSED（FIX-R1 P1-01：九条命令全部落地并真实执行，见 ADR-008；ADR-005 延期作废） |
| T012 P2-2 | `docs/USAGE.md` 引用 `/tmp/t012_verify.log`（构建者本机临时日志） | CLOSED（T014：改引已提交 `evidence/Performance/VERIFY_LOG.txt`） |
| T013-F01 | 端口交换契约哈希碰撞：`url`/`origin_url` 互换端口的两份契约哈希相同 | ACCEPTED（T014：见 ADR-007 决定 1——角色占位经实测证明无效，碰撞为 §10.4 所强制；钉住测试已加。**该哈希表示的是忽略端口值后的语义契约身份，不是完整的实际端点身份。**） |
| T013-F02 | Oracle parity 只比 verdict+诊断投影+first_error，未直接比对逐请求 verified MISS/HIT/BYPASS 状态 | CLOSED（T014：parity 加宽至逐请求状态；生产侧为分类器确认态，见 ADR-007 决定 3） |
| T013-F03 | 干净检出 `npm run build` 失败（`tsc: not found`，`node_modules` 未提交，`npm ci` 需 registry） | CLOSED（T014：冻结重建路径写入 `docs/INSTALL.md` 与 ADR-007 决定 8） |
| T013-F04 | F-01 无界读取不止一处：`cache_proxy.py:761` 的 `_fetch_origin` 同样无界 `resp.read()` | CLOSED（T014：与 F-01 同一有界读取 helper，见 ADR-007 决定 2） |
| T013-F05 | Oracle 以生产 runner 的 `verified_cache_state` 为声称状态（双腿均重算，fail-closed，但存在耦合） | CLOSED（T014：声称改取原始状态头，HIT 系缚改用 Oracle 自身确认态；见 ADR-007 决定 4） |
| D-03 | 诚实边界未集中成单一条款（实质分散在 §3.2/§3.3/§7.11） | CLOSED（T014：集中条款见 `00_control/ADR-006.md`） |
| D-01 | GPT 称 §19–§21“此前已存在”与交付记录不符（内容已补齐，仅供终审知悉） | 已登记，无行动 |
| D-04–D-08 | 规格长代码块/图表提取截断标注、frontmatter 不完整、§5.1.2 JSON 按字段表写出等 | 已标注，随规格移交 |
| T007 重审残留 | T007 修复重审 PASS，未登记新的残留项；已知张力为 ADR-003 的端口归一化解释（§10.4“不包含动态端口”不限于 `ephemeral_port` 字段，`url`/`origin_url` 的回环端口同样归一化为 0） | 已裁决（ADR-003），无 OPEN 项 |

## 规格引用张力（T012 发现，如实标注）

- 项目书 §4.1 冻结的 CLI 命令契约包含 `demo` / `run` /
  `report preview` 等命令，实施计划 T012 任务卡只要求落地
  `verify --suite all` 与 `benchmark --suite all`；T014 按任务卡
  交付两条命令、其余按 ADR-005 延期。FIX-R1 P1-01 已按 §4.1
  把其余命令全部补齐（见 ADR-008），本张力已消除。
- T012 任务卡引用的 `npm run oracle:parity` 在补全回复中被截断，
  无法确认其完整命令串；本版本不虚构该命令，Oracle parity 由
  `verify`/`benchmark` 内的 `run_oracle`（Node 直接执行
  `oracle/src/index.ts`）覆盖，`oracle/package.json` 本身也未定义
  `oracle:parity` 脚本。
- 实施计划 §6 的 T012 输出列表在页面提取中截断（VERIFY_LOG D-06）；
  本版本按任务卡正文与 §18 验收标准交付
  `tests/performance/`、`docs/`、`evidence/Performance/` 及 CLI，
  未补写截断的输出项。
```

## docs/USAGE.md

- SHA-256：`3256fb1c969da893ea8d8097323a5eb74c143c8fccb3ff9d7b37748431079981`
- 字节数：14865

```
# 使用指南 (USAGE.md) — P032 AcceptTwin，T012

本文档的命令与实际 CLI `--help` 输出逐字一致（`tests/performance/test_cli.py`
逐项断言）。凡与 `--help` 不符处，以 `--help` 为准。

## 验收命令

```bash
.venv/bin/python -m accepttwin verify --suite all
.venv/bin/python -m accepttwin verify --suite s0
.venv/bin/python -m accepttwin demo
.venv/bin/python -m accepttwin run --contract contracts/site.json
.venv/bin/python -m accepttwin verify --report output/runs/demo-healthy/report.json
.venv/bin/python -m accepttwin benchmark --suite all
.venv/bin/python -m pytest -q
```

## `run`

```text
usage: accepttwin run [-h] --contract CONTRACT [--scenario SCENARIO]
                      [--proxy-mode {respect_vary,force_uri_only,manual_accept_key,disabled,opaque,ignore_no_store}]
                      [--scenario-id SCENARIO_ID] [--run-id RUN_ID]
                      [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --contract CONTRACT   contract JSON file (accepttwin.contract/v1, loopback
                        URLs only)
  --scenario SCENARIO   synthetic origin scenario: a name under
                        fixtures/origin/ or a path to a scenario JSON file
                        (default: healthy)
  --proxy-mode {respect_vary,force_uri_only,manual_accept_key,disabled,opaque,ignore_no_store}
                        controlled proxy mode (§10.3); default follows the
                        contract: variant_by_accept -> respect_vary, no_store
                        -> disabled
  --scenario-id SCENARIO_ID
                        report scenario_id label (C01-C24 / E01-E24); default
                        follows the S0 configuration table for a known
                        (origin scenario, proxy mode) pair
  --run-id RUN_ID       run id (output directory under output/runs/; default:
                        the contract_id)
  --output OUTPUT       report JSON path (default: output/runs/<run-id>/
                        report.json; sibling evidence files land next to it)
```

跑一份用户自己的双表示契约：真实执行冻结四实验（8 个真实 HTTP
请求）、生产分类、独立 Oracle 对账、正式 `accepttwin.report/v1`
报告。Oracle parity 在 harness 与 report builder 两处各算一次，
两处不一致时 fail-closed，不出报告。输出默认写到
`output/runs/<run-id>/`（`run-id` 默认 = `contract_id`）：
`report.json`、`raw-observations.json`、`contract.json`、
`production.json`、`oracle-input.json`、`oracle.json`、
`run-summary.json`。`--output` 可改报告路径，兄弟证据文件随之
落在其旁。

- 契约端口用契约文件写明的端口（须为空闲回环端口；被占用时
  报错退出 1，不静默换端口）。`demo` 用临时端口，无此要求。
- `--scenario` 是合成源站场景（`fixtures/origin/` 下的名字，
  如 `healthy`、`no_vary`、`html_404`，或场景 JSON 文件路径），
  不是 Golden 编号；`--proxy-mode` 是受控代理模式（§10.3）。
  健康契约 + `force_uri_only` 代理就是故意复现串版的办法。
- 报告的 `scenario_id` 标签：冻结的 v1 报告 Schema 只接受
  `C01–C24 / E01–E24`，因此用户运行按其复现的 Golden **配置**
  标注（映射表：healthy+respect_vary → C01、healthy+disabled →
  C05、healthy+force_uri_only → C11、healthy+ignore_no_store →
  C19、healthy+opaque → C20、no_vary+manual_accept_key → C03、
  no_vary+respect_vary → C13、no_vary+force_uri_only → C15、
  no_vary+disabled → C17、html_404 → C07、markdown_404 → C08、
  html_wrong_content_type → C09、markdown_sentinel_missing →
  C10；未列入映射表的配置必须显式传 `--scenario-id`）。该标签
  记录的是配置，不是 Golden 身份；运行的真实身份是
  `contract_id` + `contract_sha256` + run-id，见同目录的
  `run-summary.json`（见 `00_control/ADR-008.md`）。
- 退出码：0 = 运行完成且 Oracle parity 成立、报告 `final=true`
  （裁决本身是数据：真实的 `REPRESENTATION_BLEED` 发现仍退出
  0）；1 = parity 不一致或基础设施失败；2 = 输入错误（文件缺
  失、契约非法、非回环 URL、未知场景、非法 `--scenario-id` /
  `--run-id`）。

示例（两个自定义契约，见 `tests/fixtures/contracts/`，均非 Golden
重放——自有 contract_id 与自有回环端口，真实跑通全流程）：

```bash
# 健康：PASS_OBSERVED，8 条观测全 MISS，Oracle parity，final=true
.venv/bin/python -m accepttwin run --contract tests/fixtures/contracts/custom-healthy.json
# 串版：同一份健康契约改走 URI-only 代理 → REPRESENTATION_BLEED，first_error=6
.venv/bin/python -m accepttwin run --contract tests/fixtures/contracts/custom-bleed.json --proxy-mode force_uri_only
```

## `demo`

```text
usage: accepttwin demo [-h]

options:
  -h, --help  show this help message and exit
```

用自带的 `contracts/site.json` 模板跑两次（均用临时回环端口，
不占用固定端口）：健康（C01 配置，`respect_vary`，期望
`PASS_OBSERVED`）与故意串版（C11 配置，同一份契约改走
`force_uri_only` 代理，期望 `REPRESENTATION_BLEED`、
first_error=6）。两次都做 Oracle parity 并导出 HTML，输出在
`output/runs/demo-healthy/` 与 `output/runs/demo-bleed/`。
`DEMO_STATUS: PASS` 当且仅当两边裁决都符合预期、两边 parity 都
成立、两份 HTML 都已导出；否则退出 1。

## `verify --report`

```text
usage: accepttwin verify [-h] [--suite {s0,all}] [--report REPORT]
                         [--contract CONTRACT]

options:
  -h, --help           show this help message and exit
  --suite {s0,all}     suite to verify: s0 (C01-C24 + repeat-100) or all (48
                       scenarios + S0 re-run) (default: all)
  --report REPORT      verify one formal report JSON file instead of re-
                       running a suite (Schema + hash + privacy + Oracle
                       parity/final)
  --contract CONTRACT  with --report: also check the report's contract_sha256
                       against this contract file
```

`--suite` 与 `--report` 互斥。`verify --report` 核验一份正式报告
文件（独立 Schema 校验 + 报告哈希重算 + 隐私扫描 + Oracle
parity/final），不重新跑实验；`--contract` 可再核对报告的
`contract_sha256`。退出 0 = 报告已验证为真实一致（裁决本身不
决定退出码：一份有效的 `REPRESENTATION_BLEED` 报告仍退出 0）；
退出 1 = 报告无效、哈希不符或 parity 不成立；退出 2 = 文件缺失
或契约非法。

## `report preview` / `report export` / `report delete`

```text
usage: accepttwin report preview [-h] [--contract CONTRACT] report
usage: accepttwin report export [-h] [--contract CONTRACT] [--out OUT]
                                [--check-only]
                                report
usage: accepttwin report delete [-h] report
```

- `preview`：打印隐私预览（§4.2 约束 7：预览先于导出）与人类可读
  摘要（裁决、首次错误、诊断、8 条请求、缓存状态、报告哈希），
  **不写任何文件**。
- `export`：先打印隐私预览，再导出自包含离线 HTML（§14.4；
  默认写到报告旁的 `<report-stem>.html`，`--out` 可改）；
  `--check-only` 只校验与预览，不写文件。导出的页面经远程引用
  与 Sentinel 字面值扫描，任一命中即失败。
- `delete`：只删 `output/` 或 `evidence/Reports/` 下、JSON
  `schema` 为 `accepttwin.report/v1` 的文件；其他文件、工作区外、
  符号链接、目录一律拒绝（退出 2，什么都不删）。

## `clean`

```text
usage: accepttwin clean [-h] --run-id RUN_ID [--dry-run]
```

删除一次运行的输出文件（`output/runs/<RUN_ID>/` 内的平铺常规
文件，删完移除空目录）。目录不存在、是符号链接、或内含符号链
接/子目录时整批拒绝（退出 2，什么都不删）；`--dry-run` 只列出、
不删除。`scripts/clean_evidence.py` 仍是 `evidence/` 子树的脚本
清理入口，两者边界不同，不互相替代。

```bash
.venv/bin/python -m accepttwin clean --run-id demo-bleed --dry-run
.venv/bin/python -m accepttwin clean --run-id demo-bleed
```

## `contract delete`

```text
usage: accepttwin contract delete [-h] contract
```

只删 `contracts/` 或 `output/` 下、JSON `schema` 为
`accepttwin.contract/v1` 的文件；其他文件、工作区外、符号链接、
目录一律拒绝（退出 2，什么都不删）。

## 退出码总表

| 退出码 | 含义 |
| --- | --- |
| 0 | 命令成功（`run`/`demo` 要求 Oracle parity 成立且报告 `final=true`；`verify --report` 要求报告有效且 parity 成立） |
| 1 | 门禁/核验失败（parity 不一致、报告无效、基础设施失败、demo 预期不符） |
| 2 | 输入错误或拒绝删除（参数错误、文件缺失、契约非法、非回环 URL、越权删除） |

## `verify`

```text
usage: accepttwin verify [-h] [--suite {s0,all}]

options:
  -h, --help        show this help message and exit
  --suite {s0,all}  suite to verify: s0 (C01-C24 + repeat-100) or all (48
                    scenarios + S0 re-run) (default: all)
```

- `--suite s0`：重跑 S0 门禁——C01–C24 全部真实执行、Oracle parity
  24/24、串版 C11 独立复现 3/3、repeat-100（C01，每次全新服务与端口）
  唯一哈希。证据写到 `evidence/S0/`（`S0_SUMMARY.json`）。
- `--suite all`（默认）：先跑 48 场景全套（`evidence/Golden/`，
  `ALL48_SUMMARY.json`），再重跑 S0 全套。退出码 0 当且仅当两边
  均为 PASS。
- 每次运行都重新启动源站与代理、重新发送全部 8 个真实 HTTP 请求；
  不读缓存的历史报告。

## `benchmark`

```text
usage: accepttwin benchmark [-h] [--suite {all}]

options:
  -h, --help     show this help message and exit
  --suite {all}  suite to benchmark (default: all)
```

依次做四件事，全部为本次调用内的真实运行：

1. 跑 48 场景，记录每场景实验耗时（限值 1 秒，见 §10.5；报告生成
   时间不计入单场景时间）。
2. C01 重复 100 次（每次全新服务与端口），核对规范化报告哈希唯一，
   并扫描首份规范化 JSON 是否含时间戳、临时目录、进程 ID、随机
   UUID、动态端口、耗时等非确定性字段（§10.4）。
3. 用 `scripts/build_reports_48.py` 从新鲜 Golden 证据重建 48 份
   `accepttwin.report/v1` 报告并独立校验 Schema。
4. 用 `scripts/embed_report.py --all-48` 导出 49 页自包含 HTML，
   再用 `accepttwin.privacy` 扫描全目录，并逐页核对裁决、首次错误
   与报告哈希与 JSON 一致。

汇总写到 `evidence/Performance/BENCHMARK_SUMMARY.json`。

## 实测结果（本机，2026-11-24，见证据文件）

| 项目 | 实测 |
| --- | --- |
| `verify --suite all` | 48/48 Golden、48/48 Oracle parity、S0 24/24 重跑通过（日志 `evidence/Performance/VERIFY_LOG.txt`，证据 `evidence/Golden/ALL48_SUMMARY.json`、`evidence/S0/S0_SUMMARY.json`） |
| `benchmark --suite all` | `BENCHMARK_STATUS: PASS`，总耗时 20.57s |
| 单场景耗时 | 最大 0.041s，中位 0.0146s，最小 0.0080s（限值 1.000s） |
| repeat-100 | C01 哈希唯一：`67e69e68e128441b67fae155ac1af8dbb4e7992b4dfe70db7dcef1f04e62acde`（与 T007 修复后记录的 C01 哈希一致），最大单次 0.0266s |
| 报告 Schema | 48/48 有效，裁决 48/48 一致，parity 48/48 |
| HTML | 49 页，0 违规；裁决/首次错误/哈希与 JSON 逐页一致 |
| 全量测试 | `.venv/bin/python -m pytest -q`（见下） |

## 测试

```bash
.venv/bin/python -m pytest -q                    # 全量
.venv/bin/python -m pytest -q tests/performance/ # 仅 T012 性能与 CLI 测试
.venv/bin/python -m pytest -q tests/golden/      # 仅 48 Golden
.venv/bin/python -m pytest -q tests/privacy/     # 仅隐私与安全回归
```

全量测试数以实际运行输出为准：T012 交付时 **936 passed、0 failed**
（T011 基线 921 + T012 新增 15），日志见
`evidence/Performance/T012_TEST_LOG.txt`；离线复核同样 936 passed，
见 `evidence/Performance/OFFLINE_LOG.txt`。FIX-R1 P1-01 + P2-01
交付时全量 **1026 项：1024 passed、2 failed**（2026-11-24 实测，
84 秒）；新增 59 项全部通过（`tests/integration/
test_cli_commands.py` 48 项 + `tests/unit/test_verify_s0_parity.py`
11 项）。2 项失败是既存环境原因，与本次改动无关：
`test_default_ports_from_site_contract` 与
`test_default_port_matches_contract_origin_url` 绑定契约默认端口
18765/18766，而当时该端口正被并行通道的进程占用。**重冻结时已
复核通过**：端口空闲后重跑这两项，2 passed（0.24s）；另跑
`accepttwin run --contract contracts/site.json` 默认端口运行，
exit 0，`RUN_STATUS: COMPLETE`（PASS_OBSERVED，parity True）；
随后全量重跑 **1026 passed、0 failed、0 skipped**（84.54s），
两项端口测试均在内（基线 967 的口径不变）。

## 其他脚本（不在 CLI 内，按原路径使用）

```bash
.venv/bin/python scripts/run_s0.py          # S0 门禁（verify --suite s0 的实现）
.venv/bin/python scripts/run_all_48.py      # 48 场景（verify --suite all 的实现）
.venv/bin/python scripts/build_reports_48.py # 48 份正式 JSON 报告
.venv/bin/python scripts/embed_report.py --all-48   # 49 页 HTML 导出
.venv/bin/python scripts/embed_report.py evidence/Reports/C11.json --check-only  # 导出前隐私预览
.venv/bin/python scripts/clean_evidence.py --dry-run evidence/Privacy/PRIVACY_TEST_LOG.txt  # 清理（见 §17.3）
```

## 证据同步说明

`verify --suite all`（及 `scripts/run_all_48.py`）会用新端口重跑
全部 48 场景并重写 `evidence/Golden/`；而 `evidence/Reports/`
是派生文件，只在 `build_reports_48.py` 运行时才与当前 Golden
同步。因此**单独跑完 `verify` 后，须再跑一次
`build_reports_48.py` + `embed_report.py --all-48`**，否则
`test_committed_samples_match_generator` 会因端口不同而失败——
这是派生证据的固有次序，不是产品缺陷。`benchmark` 内部已包含
重建与导出两步，跑完即同步。

项目书 §4.1 冻结的九条 CLI 命令已全部落地（P1-01 FIX-R1，见
`00_control/ADR-008.md`）：`run`、`demo`、`verify --report`、
`report preview/export/delete`、`clean`、`contract delete`，外加
原有的 `verify --suite` 与 `benchmark`。ADR-005 的延期决定已被
ADR-008 取代，不再有效。删除命令的安全边界见上文各节与
`docs/LIMITATIONS.md`；`scripts/clean_evidence.py` 仍只接受
`evidence/` 子树内的目标（见 ADR-007）。
```

## 00_control/ADR-001.md

- SHA-256：`593bd0a1237532871eaee711bf2a66c87190aeb42234b325d5cfa664a1163a46`
- 字节数：1582

```
# ADR-001 — `RequestObservation.cache_status` is `str | None`

- **Status:** Accepted (clarification, not a semantic change).
- **Date:** 2026-11-24 (P032 T005 independent-review fix, P2-1).
- **Context:** IMPLEMENTATION_PLAN §5.5 freezes `RequestObservation`
  with `cache_status: str`. The T005 implementation declares
  `cache_status: str | None`, and the two direct-origin baseline
  requests — 001 O-H and 002 O-M — take `None`, because they are
  sent straight to the origin and never pass through the cache, so
  no cache state exists for them at all.

## Decision

- The type is widened to `str | None`. This is a clarification of
  the frozen interface, not a semantic change: the frozen §5.5
  specification text is **not** amended.
- Only the two direct-origin baseline requests (001, 002) take
  `None`. Every proxied request (003–008) carries a verified state
  string from the dual evidence (§5.3): `"MISS"`, `"HIT"`,
  `"BYPASS"`, or `"CACHE_STATE_UNKNOWN"`.
- `None` means "direct-origin request, no cache evidence exists".
  It is distinct from `"CACHE_STATE_UNKNOWN"`, which means "the
  request went through the proxy but the cache state could not be
  verified".

## Consequences

- T006 (classifier) and T007 (independent Oracle) **must** treat
  `cache_status is None` as a direct-origin request and must never
  read it as a cache state, infer a state from it, or conflate it
  with `"CACHE_STATE_UNKNOWN"`.
- The `RequestObservation` docstring in
  `src/accepttwin/evidence.py` references this ADR.
- No other field, verdict, or step is affected.
```

## 00_control/ADR-002.md

- SHA-256：`84aa577b60e39a4033aab1c50b2c78259eaf1e27a6e3b525d304c1ba384098f4`
- 字节数：8362

```
# ADR-002 — T006 复核修复：variant BYPASS 策略分句、Vary fail-closed、None 调用约定、§8 证据字段

- **Status:** Accepted.
- **Date:** 2026-11-24 (P032 T006 复核修复，P1-1 / P2-1 / P2-2 / P2-3 / P2-4).
- **Context:** T006 独立复核结论 FAIL（0 P0 / 1 P1 / 4 P2），复核员亲自重跑
  47/68/358 全部通过、核心逻辑无问题；Muse 用 `/tmp/p1_probe.py` 亲自复现
  P1-1 与 P2-2 现象，确认真实。本 ADR 记录修复中需要跨任务约定的部分。
  冻结规格（PROJECT_BOOK v1.0.0）本身未修改。

## Decision 1 — P1-1：variant_by_accept 下已确认 BYPASS 是 CACHE_POLICY_MISMATCH

- PROJECT_BOOK §5.4 / §6.1 规定 variant 契约下冷、暖请求预期为 MISS；
  §8.9 variant 分句规定“契约声明 variant_by_accept，实际代理行为与契约
  明确规定的缓存模式冲突”即触发 CACHE_POLICY_MISMATCH。
- 旧实现中该分句无任何触发路径：`disabled` 代理模式（缓存从未工作）
  配 variant 契约时，分类器静默判 `PASS_OBSERVED`、零诊断——隔离性从未
  被检验却被认证为 PASS。
- 修复：`diagnostics.check_variant_by_accept_policy`（§8.9 variant 分句）
  + 分类器策略核对处：仅当 BYPASS 已通过双重证据确认（`confirmed_state`
  为 `"BYPASS"`）时触发，裁决 CONTRACT_MISMATCH（§9.6 步骤 4）。未确认
  的 BYPASS（`CACHE_STATE_UNKNOWN` / 冲突 / `None`）仍是 §8.4 证据问题，
  不得升级为已证实策略违反。
- `no_store` 下 BYPASS 仍为 PASS（C05/C06 形），不受影响；冻结 S0
  Golden C01–C24 中没有 variant+disabled 场景，修复不改变任何冻结
  Golden 的预期 verdict（全量回归通过，见下）。

## Decision 2 — P2-1：vary_accept == "required" 且 Vary 是否存在未知时 fail-closed

- `vary_accept == "required"` 且分类器从未见过任何 Vary 头（未传
  `raw_observations` 且未传 `vary_accept_present`，或两者对某条基线均
  无值）时，判 `INCONCLUSIVE`（§9.6 步骤 5“关键证据不足”），诊断为
  `INCONCLUSIVE_LIMIT`（`limit_code == "vary_accept_unknown"`）。
  §5.2 明文：required 下“缺少 Vary: Accept 构成契约违反”——没看过头就
  既不能确认违反、也不能排除违反，故不得 PASS。
- Vary 已知缺失时仍为 CONTRACT_MISMATCH（违反已证实）；Vary 已知存在时
  正常 PASS。显式 map 有值时优先，raw 头为后备（map 对某请求沉默时回落
  到 raw 头）。
- **正文超大检查（§8.6，§17.4 1 MiB 限制）仍依赖 `raw_observations`
  才能核查**：冻结 `RequestObservation` 没有 body-size 字段，没有其他
  来源可推导正文大小。**T007 调用分类器时必须传 `run.raw_observations`，
  否则该项检查无法执行**——分类器对此不猜测、不补默认值。同一要求已写
  入分类器模块 docstring 与 `classify_run` docstring。

## Decision 3 — P2-2：None 与 `[]` 的不对称，选路线 B（强制调用约定）

- 现象：`origin_events=None` / `reset_evidence=None` 被当作“已确认”而跳
  过检查（→ PASS），`[]` 却判 INCONCLUSIVE；调用方误传 None 即可得假 PASS。
- **选路线 B，不改代码语义**，理由：
  1. 现有测试大量用 `events=None` / `resets=None` 默认值；路线 A（None
     与 `[]` 同等 fail-closed）会把大批健康 PASS 夹具翻成
     INCONCLUSIVE，改动面覆盖分类器与诊断两组测试的默认值与断言，
     回归风险高于其收益，且与冻结 Golden 的预期 verdict 无关的夹具
     也要重写；
  2. None-skip 已有先例（ADR-001：基线请求的 `cache_status is None`
     表示“无缓存证据”，而非“已确认”）；
  3. 真正的风险是生产调用方悄悄传 None——用书面、可审计的调用约定
     + 测试钉住（`test_none_means_skip_cross_check_not_confirmed`）
     来堵，比改单元测试的人体工学更对症。
- 约定（已写入分类器模块 docstring、`classify_run` docstring，并由
  下列测试钉住）：
  - `None` = 调用方声明不做该项交叉核对，**仅限单元测试使用**；
  - `[]` / `()` = 调用方已执行检查、结果为空，fail-closed
    （无源站事件 → `CACHE_STATE_UNKNOWN`；无重置记录 →
    `CACHE_STATE_UNKNOWN`）；
  - **生产调用（T007）永不传 None**。
- **T007 任务卡必须写入的调用约定文字**（逐字采用）：
  > 调用 `classify_run` 时，`origin_events` 必须传
  > `run.origin_events`、 `reset_evidence` 必须传
  > `run.reset_evidence` 的真实元组，永不传 `None`；同时必须传
  > `run.raw_observations`（否则 §8.6 正文超大检查无法执行，
  > 且 `vary_accept == "required"` 时 Vary 未知会 fail-closed 判
  > INCONCLUSIVE）。`None` 仅限单元测试使用，表示“声明不做该项
  > 交叉核对”，不表示“已确认”。

## Decision 4 — P2-3：§8 证据字段补齐情况

已补（能从冻结输入推导的）：

- §8.1：`stage`（= experiment_id）。
- §8.3（`check_contract_response`、`check_unexpected_hit`、Vary 的
  CONTRACT_MISMATCH 分支）：`stage`、`expected` / `observed`（结构化
  `{status, content_type}`）、`response_status` /
  `response_content_type`（与既有 `observed_*` 并存，未删旧键）。
- §8.4 / §8.8（`check_cache_state`）：`proxy_cache_header_present`、
  `origin_journal_available`、`cache_reset_confirmed`（分类器传入运行
  级重置结论；直接调用检查函数而不传时为 `None`）、
  `evidence_conflict`（UNKNOWN 为 `False`，CONFLICT 为 `True`）。
  未提供的证据腿一律记 `None`（未知），绝不猜一个 `False`。
  分类器自建的“无匹配源站事件”`CACHE_STATE_UNKNOWN` 诊断同样补齐
  上述四字段。
- §8.6（`check_inconclusive_limit`）：新增可选参数 `request_url` /
  `redirect_target`，有 raw 记录时分类器传入（`request_url` 取
  `RawObservation.url`；`redirect_target` 取 raw 响应头的 `Location`，
  仅当 limit 为 redirect 时）；无 raw 记录时字段缺席，不猜测。
- §8.9 两分支：`cache_control` 由分类器从 raw 响应头传入（无 raw 时
  为 `None`）；其余字段（`declared_cache_mode`、
  `observed_cache_status`、`cache_entry_count_before/after`、
  `cache_entry_id`）此前已齐。

客观上无法从冻结输入得到的字段（由 T009 报告层处理）：

- `request_url`（§8.6）：冻结 `RequestObservation` 无 URL 字段；只有
  持有 `RawObservation` 的调用路径才能提供。无 raw 记录的诊断（如契约
  无效、观测不完整等运行级诊断）仍无此字段，T009 不得编造 URL。
- `redirect_target`（§8.6）：同上，仅当 raw 响应头含 `Location` 时可
  得；§8.6 要求“仅记录已验证的脱敏地址”，T009 对非回环目标不得原样
  记录。
- `cache_control`（§8.9）：冻结观测无此字段，仅 raw 响应头可供；无 raw
  时为 `None`。
- 其余 §8 字段（`request_index` 等）已由 `Diagnostic` 自身字段承载，
  不再在 evidence 内重复。

## Consequences

- T007（独立 Oracle）必须遵守 Decision 3 的调用约定文字；T009 报告层
  负责 Decision 4 列出的、冻结输入无法提供的字段，不得在分类器层编造。
- `check_cache_state` 新增可选参数 `cache_reset_confirmed`（默认
  `None`）；`check_inconclusive_limit` 新增可选参数 `request_url` /
  `redirect_target`（默认 `None`）。均为向后兼容的扩展，旧调用不受影响。
- 新增 `check_variant_by_accept_policy`，已导出；§8.9 variant 分句自此
  有触发路径（P1-1 修复前无）。

## Verification

- `tests/unit/test_classifier.py`：47 → 55 通过（新增 8：P1-1 冷/暖
  BYPASS ×2、未确认 BYPASS 不触发策略违反 ×1、P2-4 串版无策略诊断
  ×1、P2-1 未知 Vary ×2 + 已知存在对照 ×1、P2-2 None 约定钉住 ×1）。
- `tests/unit/test_diagnostics.py`：68 → 75 通过（新增 7：variant 分句
  ×3、§8.4 证据字段 ×3、§8.6 request_url ×1）。
- 全量：`.venv/bin/python -m pytest -q` —— 373 通过（358 + 15 新增），
  0 失败。冻结 S0 Golden 预期 verdict 未变。
```

## 00_control/ADR-003.md

- SHA-256：`fde9ae2840d3f77f6100afefab53f14a48baa908f573c706e9493ed22fda7c67`
- 字节数：6854

```
# ADR-003 — §10.4 解释：临时端口排除在契约哈希之外

- **Status:** Accepted (clarification of the frozen spec, not a semantic change).
- **Date:** 2026-11-24 (P032 T007 复核修复，P1-1).
- **Context:** T007 独立复核结论 FAIL（1 P1）：报告哈希含临时端口，
  repeat-100 门禁被缩窄。冻结规格（PROJECT_BOOK v1.0.0）本身未修改。
  复核员与 Muse 各自独立证实：同一份 C01 契约只改端口 → 哈希变化；
  三次独立全运行同一场景三个不同哈希；提交版证据内同一 C11 的 3 次
  复现（每次 fresh pair、新端口）哈希各不相同；`scripts/run_s0.py`
  的 repeat-100 用单个固定 pair，100 次共用同一对端口，distinct=1
  按构造必然通过。

## 规格依据

- PROJECT_BOOK §10.4：规范化 JSON“不包含动态端口”，以下字段不进入
  规范化报告哈希：`generated_at`、`duration_ms`、`process_id`、
  `temporary_path`、`ephemeral_port`；“100 次运行必须得到完全相同的
  结果”。
- PROJECT_BOOK §7.8 (I-08)：相同契约、相同场景、相同代理配置和相同
  输入，100 次运行的规范化报告哈希必须完全相同。
- §10.4 的“动态端口”不限于名为 `ephemeral_port` 的字段：`url` /
  `origin_url` 的端口同样是 OS 分配的临时端口（harness 以 `port=0`
  启动服务），经由契约哈希间接进入报告哈希，与以 `ephemeral_port`
  字段直接进入在熵上毫无区别。本 ADR 把这一点写明为 §10.4 的解释，
  而不是新增规则。

## Decision — 归一化方式：固定占位符端口 0，仅回环 http URL

- `canonical_json_bytes`（唯一的规范化实现，T009 将复用）在规范化
  时，对键名恰为 `url` / `origin_url` 且值为字符串的字段，把其中
  **回环 `http` URL 的显式端口替换为 `0`**；scheme、host、path、
  query 原样保留。`canonical_contract_hash` 经由
  `canonical_json_bytes` 自动获得该语义，无需第二份实现。
- 选占位符 `0` 而不是去掉端口（只取 scheme+host+path），理由：
  1. 保留 URL 形状（scheme/host/端口槽/path 都在），规范化后的
     JSON 仍能看出原来有一个端口；
  2. `0` 在本代码库中已有“请 OS 分配端口”的约定含义（harness
     以 `port=0` 启动 origin 与 proxy），规范化形式字面意思就是
     “某个 OS 分配的端口”；
  3. 保留的信息严格更多：去掉端口会把“有显式端口的 URL”与“无端口
     的 URL”（隐含 :80）合并成同一个哈希，而占位符 `0` 让两者保持
     不同——只有显式端口值之间才互相坍缩，而这正是 §10.4 要求的。
- 只归一化回环 URL，不归一化非回环 URL：非回环主机的端口是服务身
  份的一部分（`example.com:8080` 与 `:9090` 是不同服务），而回环
  端口在本系统中是运行时 OS 分配的。回环判定不做 DNS（规范化必须
  是纯函数、确定性的）：字面 IP 用 `ipaddress` 判 `is_loopback`
  （覆盖整个 127/8 与 `::1`），名字只认 `localhost`；其他名字不
  猜，留原样。
- 只归一化 `url` / `origin_url` 两个键，不归一化其他 URL 值字段：
  其他字段的端口可能是语义性的，本次不碰，避免过度抹掉语义差异。
- 归一化失败时（不可解析的字符串）原样返回：规范化永不抛错；
  校验是另一层，仍在真实值上运行。

## 不变的部分（本修复明确不改）

- **执行仍用真实端口**：origin / proxy 仍以 OS 分配的真实端口启动
  并真实通信；只改哈希输入。
- **语义校验不动**：`url` 与 `origin_url` 仍须同 path、不同端口
  （`contract.py::_semantic_errors` 未改），且仍在真实值上校验。
  规范化后的两个 URL 在哈希内变得相同，不影响“不同端口”的校验——
  校验与哈希是两个不同的函数，前者读真实契约，后者读规范化形式。
- **归一化不改变契约的其他语义区分**：换 path、换 host、换 scheme、
  换表示 / sentinel、换 contract_id，哈希仍然不同（单测钉住）。
- **报告载荷本身不变**：`canonical_report` 的字段集合未变；它经由
  `contract_sha256` 间接携带的端口熵被消除后，报告哈希才真正只含
  §10.4 列出的确定性字段。

## 为什么归一化放在 `canonical_json_bytes` 而不是只放在 `canonical_contract_hash`

- §10.4 是对规范化 JSON 本身的要求，不是某一个哈希函数的要求；
  唯一的规范化实现就应当实现它，否则同一份契约经两条路径会得到
  两个哈希。
- `scripts/verify_s0.py` 第 10 项独立重算契约哈希时直接调用
  `canonical_json_bytes`（不经过 `canonical_contract_hash`）：
  归一化只放进后者会使验证器的重算与被验证的哈希系统性不一致，
  反而破坏独立复核。本次不改验证器的重算路径，只在其上增加
  端口不变性断言（见下）。

## Consequences

- `scripts/run_s0.py` 的 repeat-100 改为每次迭代 fresh pair（新
  端口），真正检验端口无关性；另保留 3 次同 pair 运行作补充，
  且要求同 pair 哈希等于 fresh-pair 哈希。
- `scripts/verify_s0.py` 第 10 项新增：改写 C01 契约端口重算哈希
  要求相等；并要求 3 次 C11 复现的报告哈希彼此相等且等于主场景
  C11 的报告哈希（修复前该断言会失败，正是应有的检出能力）。
- `tests/golden/test_s0.py` 的确定性测试同步改为 fresh pair，并删
  除“同一字节串纯重算 SHA-256 100 次”的同义反复断言（它只证明
  SHA-256 自洽，对运行间确定性证明力为零）。
- `scripts/s0_harness.py` docstring 中“ports … never enter it”的失
  实宣称已修正为如实描述归一化机制。
- T009 报告层复用同一实现（`canonical_json_bytes` /
  `canonical_contract_hash`），不得另写一份规范化；复用时同样只
  得到端口归一化后的哈希，执行层仍用真实端口。

## Verification

- 同一逻辑契约换两对端口 ⇒ `canonical_contract_hash` 相同；换
  path / host / sentinel / contract_id ⇒ 哈希不同；非回环 URL
  端口不归一化；无端口 URL 不变；IPv6 回环 `[::1]` 归一化；
  不可解析字符串原样保留（`tests/unit/test_canonical_json.py`
  新增测试）。
- 验收：`tests/golden/test_s0.py`、`.venv/bin/python
  scripts/run_s0.py`（S0_STATUS: PASS，24/24 golden，parity 24/24，
  C11 复现 3/3，repeat-100 distinct_hashes=1）、
  `.venv/bin/python scripts/verify_s0.py`（19 项以上全部通过）、
  全量 `.venv/bin/python -m pytest -q`（432 个已有测试全部通过，
  另新增测试全部通过）。
```

## 00_control/ADR-004.md

- SHA-256：`3065b9a94a8fce33768cb3481074905d78c3b8b103f1241ea81b194001fa658d`
- 字节数：4621

```
# ADR-004 — T008 扩展 Golden 所需的三处行为澄清与两处延期

- **Status:** Accepted (clarifications of the frozen spec, not semantic changes).
- **Date:** 2026-11-24 (P032 T008).
- **Context:** PROJECT_BOOK §11.3 冻结了 E01–E24 的 verdict，但三处
  形状在 T002–T007 的实现中没有可达的触发路径：E03（`Vary: *`）
  的 BYPASS 会被 §8.9 variant 分句判为策略违反；E07/E08
  （`max-age=0` / `no-cache`）在分类器中没有任何重新验证检查；
  E01/E02/E03/E07/E08/E10/E11 需要源站发出 T003 场景语言表达
  不了的响应头/状态。冻结规格（PROJECT_BOOK v1.0.0）本身未修改。

## Decision 1 — E03：`Vary: *` 下的 BYPASS 是合规行为，不触发 variant 分句

- RFC 9111 §4.1：`Vary: *` 的存储响应永远不得复用；代理不存
  储它（BYPASS）是唯一合规的做法。§5.3 的 MISS 定义要求“缓存
  条目在本次响应后被建立”——`Vary: *` 下没有条目被建立，所以
  §11.3 E03 所写的“第二请求 MISS”是宽松说法，诚实的 §5.3 标
  签是 BYPASS；两种说法下的裁决都是 PASS_OBSERVED。
- `check_variant_by_accept_policy` 新增可选参数 `vary`：响应
  Vary 含 `*` token 时该请求豁免 variant 分句；`vary=None`
  （未知/未提供）不豁免。分类器与独立 Oracle 各自独立实现
  同一规则（Oracle 读原始响应头，不读生产结论）。
- 豁免只针对 BYPASS 的存储行为：每个响应仍按自身状态码 /
  Content-Type / Sentinel 逐一判定；E03 全程 BYPASS、条目数
  恒为 0（证据见 `evidence/Golden/E03/`）。

## Decision 2 — E07/E08：`no-cache` / `max-age=0` 触发 §8.6 `revalidation_required`

- §8.6 的触发条件原文包含“需要未实现的缓存重新验证语义”。
  分类器与独立 Oracle 在逐请求越界检查中新增一档：原始响应
  的 `Cache-Control` 含 `no-cache` 或 `max-age=0` 时，该请求产
  生 `INCONCLUSIVE_LIMIT`（`limit_code == "revalidation_required"`），
  整轮裁决 INCONCLUSIVE（§9.6 步骤 1）。`max-age>0` 不触发。
- 该检查只读原始响应头；无 raw 记录时跳过、不猜测（与 §8.6
  正文超大检查同一原则）。首错位置为首个携带该指令的响应
  （E07/E08 的源站每个响应都带指令，故首错为 001）。

## Decision 3 — 源站场景语言扩展（E01/E02/E03/E07/E08/E10/E11）

- 每表示 `vary` 允许的字面值扩展为 `"accept"`（ legacy 简写，
  仍等于 `"Accept"`）、`"Accept"`、`"Accept, Accept-Encoding"`、
  `"*"`、null；新增可选字段 `vary_header_name`（`"Vary"` /
  `"vary"`，E01：字段名小写发出）与 `cache_control`（字面
  `Cache-Control` 值，如 `"max-age=0"` / `"no-cache"`）。
- 既有夹具不受影响（`"accept"` 归一化为 `"Accept"`，null 仍为
  无头）。新增 7 个源站夹具：`vary_lowercase`、`vary_multi`、
  `vary_star`、`cache_max_age_0`、`cache_no_cache`、
  `html_markdown_content_type`（E10）、`markdown_406`（E11）。
- E09 复用既有 `markdown_wrong_content_type` 夹具：T003 以
  “对方表示的 Content-Type”作为“返回另一表示”的既定替身
  （C09 同款），夹具内已注明。

## Deferred — T003 遗留 P2-01 / P2-02 留待 T014（本次不做）

- P2-01（源站 `Accept` 的 `q=0` 未返回 406）、P2-02（q 平局
  规则无测试）与 E01–E24 无关：四实验执行器只发不带 q 值的
  固定 Accept 头，E09–E11 也不涉及 q 值处理。按 T008 任务卡
  “若与 E01–E24 无关，明确记录留待 T014，不得为做而做”，
  两项均不实现、不加测试，留待 T014 处理。本 ADR 仅记录该决定。

## Verification

- 生产分类器单测新增 5 项（`tests/unit/test_classifier.py`：
  no-cache / max-age=0 → INCONCLUSIVE 首错 001；
  max-age=60 对照 PASS；`Vary: *` BYPASS → PASS；
  `Vary: Accept` BYPASS → CONTRACT_MISMATCH 对照）；
  诊断单测新增 2 项（`tests/unit/test_diagnostics.py`：
  variant 分句的 `Vary: *` 豁免与非豁免对照）。
- 源站集成测试新增 7 项（`tests/integration/test_origin_server.py`：
  Vary 多字段 / `Vary: *` / 字段名小写（原始头列表断言）/
  两种 Cache-Control 指令 / markdown 406 / HTML 返回 Markdown
  Content-Type / 非法 vary 值拒绝）。
- 扩展 Golden E01–E24 全部通过且 Oracle parity 24/24；
  48 场景全套 48/48；S0 24 条重跑仍 PASS（`scripts/run_s0.py` +
  `scripts/verify_s0.py` 19/19）；全量测试见 T008 交接报告。
```

## 00_control/ADR-005.md

- SHA-256：`2c8ed2fecd04bddb52d9835ee6886b693cc28159757306fdb75832be42d2ed51`
- 字节数：4081

```
# ADR-005 — PROJECT_BOOK §4.1 其余 CLI 命令延期至 v1.0.0 之后（T012 P2-1）

- **Status:** Accepted (deferral / revision of the frozen §4.1 contract for v1.0.0).
- **Date:** 2026-11-24 (P032 T014).
- **Context:** PROJECT_BOOK §4.1 freezes nine CLI commands:
  `accepttwin --help`, `demo`, `run --contract contracts/site.json`,
  `verify --report output/report.json`, `report preview`,
  `report export`, `clean --run-id <RUN_ID>`, `report delete`,
  `contract delete`. The delivered v1.0.0 CLI provides only
  `verify --suite s0|all` and `benchmark --suite all` (plus
  `--help` / `--version`); even the `verify --report` form is
  absent — `verify` takes `--suite`, a different interface.
  T012 recorded the gap as P2-1 (honestly disclosed in
  docs/USAGE.md and docs/LIMITATIONS.md, no placeholder commands);
  T013 carried it and required T014 to decide explicitly before
  freeze: implement per §4.1, or record an ADR deferring/amending
  §4.1. Silent omission is not acceptable. The frozen spec text
  itself (01_project_book/PROJECT_BOOK.md) is **not** edited; this
  ADR is the written decision that revises §4.1 for v1.0.0.

## Decision

- **Defer, do not implement in v1.0.0.** The deferred commands are
  `demo`, `run`, `verify --report`, `report preview`,
  `report export`, `clean`, `report delete`, `contract delete`.
  They are deferred to post-v1.0.0 work, to be implemented per
  §4.1 when a later version revisits the CLI surface.
- **v1.0.0 CLI surface is exactly:** `accepttwin verify --suite
  s0|all`, `accepttwin benchmark --suite all`, `accepttwin --help`,
  `accepttwin --version`. Nothing else is advertised; no deferred
  command exists as a placeholder, stub, or unimplemented help
  entry.
- **Cleanup stays available as a script, not a CLI subcommand:**
  `scripts/clean_evidence.py` (workspace-bounded; since T014 its
  default deletable subtree is narrowed to `evidence/` — see
  ADR-007). The `--run-id` form of `accepttwin clean` is not
  implemented in v1.0.0.
- **Documentation is updated to cite this ADR:** docs/USAGE.md
  §"未实现的命令" and docs/LIMITATIONS.md record the deferral and
  point here; the §4.1 gap is no longer "OPEN, to be decided".

## Rationale

1. **Zero effect on any verdict or gate.** The deferred commands
   are entry-point conveniences (demo run, report preview/export/
   delete, cleanup, contract deletion). No Golden scenario, no S0
   gate item, no Oracle parity comparison, and no acceptance
   criterion in §18 depends on them. The complete verification
   workflow (verify / benchmark / reports / HTML export) is
   already covered by the two implemented commands plus the
   `scripts/` entry points (`run_s0.py`, `run_all_48.py`,
   `build_reports_48.py`, `embed_report.py`,
   `clean_evidence.py`).
2. **Scope risk at freeze.** Implementing seven commands plus a
   new `verify --report` interface inside T014 (the freeze task)
   would be a feature build, not a fix: new argument parsing,
   new file-management semantics (delete commands), and new tests
   — all without a dedicated task card, review round, or Golden
   coverage. That is the wrong place to grow the CLI surface.
3. **Honesty is preserved.** The gap was disclosed from T012
   onward; this ADR converts the disclosure into a decision with
   a named disposition (deferred, not dropped) and a pointer for
   future work.

## Consequences

- Final (GPT) review must judge this deferral on its merits: a
  reviewer who considers the §4.1 surface essential to v1.0.0
  may still FAIL the release on this point. This ADR does not
  claim the deferral is cost-free — only that it is explicit,
  reasoned, and does not touch any verdict, gate, or evidence.
- Post-v1.0.0 work that implements the deferred commands must
  follow §4.1 (including the `verify --report` form) and must
  not silently change the v1.0.0 `verify --suite` / `benchmark
  --suite` interfaces.
- T012 P2-1 is CLOSED by this ADR (disposition: deferred, not
  implemented). It is not "fixed by code", and must not be
  reported as such.
```

## 00_control/ADR-006.md

- SHA-256：`027b49d0e8bb970229ff3b2562ca04606ff6264310992cd90a4b371cc8d4998b`
- 字节数：5205

```
# ADR-006 — 诚实边界集中条款（D-03）

- **Status:** Accepted (centralised honest-boundary clause).
- **Date:** 2026-11-24 (P032 T014).
- **Context:** The honest boundary of this project was dispersed
  across PROJECT_BOOK §3.2 (non-goals), §3.3 (two-layer success
  definition), §7.11 (I-11, Vary), §2.1–§2.4 (evidence boundaries
  and competition), §1.3 (planning assumptions), and the README's
  honest-boundary section. T013 (D-03, carried since spec
  verification) required a single centralised clause before final
  review. The frozen spec text itself
  (01_project_book/PROJECT_BOOK.md) is **not** edited; this ADR
  is the single clause. Where README.md, docs/LIMITATIONS.md, or
  the report-UI footer state part of the boundary, they point
  here. D-03 is CLOSED by this ADR.

## The central clause (v1.0.0)

AcceptTwin v1.0.0 is a **local, synthetic, deterministic
experiment harness** for one narrow question — whether the HTML
and Markdown representations of the same URL survive a shared
cache in both warm-cache orders — and every claim about it is
bounded as follows:

1. **Local and synthetic only (§3.2).** All origins, proxies,
   contracts, and fixtures are synthetic and loopback-only. The
   product does not certify real CDNs (Cloudflare, Fastly,
   Akamai, or any other), does not scan public websites, does
   not listen to production traffic, does not collect real user
   data, and does not perform penetration testing, vulnerability
   scanning, readiness scoring, SEO checks, or Markdown
   conversion. Anything outside that list is a non-goal, not a
   future promise.
2. **Evidence is bounded by its sources (§2.1–§2.3).** E01 (RFC
   9110/9111) supplies the protocol semantics. E02 (Firecrawl
   issue #5956) proves only that a real origin can negotiate
   content incorrectly — it is a content-negotiation anomaly,
   **not** a proven cache-bleed incident: it proves no cache HIT,
   no wrong-representation reuse, and no Vary causation. E03
   (Cloudflare Markdown for Agents) is an example of a correct
   implementation, **not** a test conclusion about all CDNs.
   No evidence in this project proves that cache bleed is common
   in production.
3. **No single signal decides a verdict (§7.11, §2.1).** A missing
   `Vary: Accept` is never, by itself, a cache fault; a present
   `Vary: Accept` never, by itself, proves correct isolation.
   Every verdict requires the dual evidence of §5.3 (response
   header leg + origin-behaviour leg), and insufficient evidence
   yields INCONCLUSIVE, never a guessed PASS or BLEED.
4. **Success is two-layer, and only the first layer is measured
   (§3.3).** Engineering success — 24/24 S0, 48/48 Golden, 48/48
   Oracle parity, zero false positives on healthy scenarios, all
   known faults detected, single-scenario time under 1 second,
   repeat-100 identical normalised hash, JSON Schema valid,
   HTML self-contained, offline run passes — is measured on this
   machine with the frozen fixtures and is reported with its
   logs. Product value is **USER_VALUE_NOT_MEASURED**: there were
   no human participants, so the project must not claim that
   users are willing to use it, that it saves any measured
   amount of time, that it has real customers, that anyone would
   pay for it, or that any acquirer is interested. GitHub spread
   and commercial potential are product hypotheses, not
   engineering acceptance facts.
5. **Planning numbers are assumptions, not measurements (§1.3).**
   The frequencies (2–3 checks per week), pain intensity (5/5),
   and per-incident cost (20–60 minutes) in §1.3 are planning
   assumptions from the establishment phase. They must not be
   quoted in release notes, READMEs, or any public material as
   measured user benefit.
6. **No invention claim (§2.4).** AcceptTwin does not claim to
   have invented HTTP cache testing. Hurl, cache-tests,
   acceptmarkdown.com, and readiness-audit already cover large
   parts of this space. The claimed difference is only the narrow
   combination: same URL, two representations, independent cold
   baselines, both warm-cache orders, dual cache evidence,
   first-error attribution, and an independent Oracle — and that
   difference was tested by the T001 competitive gate
   (CONTINUE), not asserted.
7. **What a PASS means.** A PASS_OBSERVED verdict means: on this
   synthetic fixture, with this contract, the observed behaviour
   conformed and the evidence was complete. It does not mean the
   tested site is safe in production, that the configuration is
   correct for other sites, or that no bleed exists outside the
   eight frozen requests of the scenario.

## Consequences

- README.md's honest-boundary section and docs/LIMITATIONS.md
  cite this ADR as the single source; the report-UI footer
  footnote is display only and does not replace this clause.
- Any future public claim about AcceptTwin (README, release
  notes, GitHub description) must be checked against this
  clause; a claim that contradicts any of its seven points is a
  release defect, not a marketing choice.
- D-03 is CLOSED. D-01 and D-04–D-08 remain recorded with the
  frozen spec (no action), as before.
```

## 00_control/ADR-007.md

- SHA-256：`dce2d7d1cbdfb573f795a806f21bd6af41cfc1ad841cae8ad6d1af3684609525`
- 字节数：13209

```
# ADR-007 — T014 修复记录（T013 审查发现的逐项处置）

- **Status:** Accepted (fix record for the T014 freeze).
- **Date:** 2026-11-24 (P032 T014).
- **Context:** T013 independent review found 0 P0 / 0 P1 / 15 P2 /
  1 P3 (FINDINGS.json, reviewed commit `c02387c`). T014 disposed
  of all 16 items. This ADR records the technical decisions that
  are not visible from the diffs alone — above all the two places
  where the review's suggested fix was tried and *not* taken
  (T013-F01), and the one place where the first implementation
  was wrong and had to be corrected (T013-F02 production side).
  §4.1 CLI and the honest boundary are recorded separately in
  ADR-005 and ADR-006. The frozen spec text itself
  (01_project_book/PROJECT_BOOK.md,
  02_implementation_plan/IMPLEMENTATION_PLAN.md) is **not**
  edited. No Golden expected value was changed in T014.

## Decision 1 — T013-F01 (port-swap contract-hash collision): ACCEPTED, with proof that the suggested fix cannot work

- The finding: two contracts differing only by swapping the
  `url` / `origin_url` ports hash identically (review probe:
  `82686a3e6dc62a53…`; T014 probe
  `~/workspace/t014-scratch/probe_f01.py`: `a313e039…`).
- The review's first suggested fix — role-distinct placeholders
  (`url` → `:0`, `origin_url` → `:1`) — was **implemented and
  probed in T014 and does not fix the collision**: the
  placeholder is a per-key constant, so the swapped contract
  normalises to the very same bytes (`url` `:0`, `origin_url`
  `:1`). The implementation was reverted (zero production
  change); the existing test
  `test_contract_hash_ignores_loopback_port_change` failed under
  it, confirming the attempt changed behaviour without fixing
  the finding.
- The collision is forced by §10.4, not by an implementation
  bug: the hash must be invariant to OS-assigned loopback port
  values (repeat-100 with fresh pairs must give one hash, §7.8
  I-08), and the port values are the *only* difference between
  the two contracts. Any hash satisfying §10.4 therefore
  collides them.
- An order-based placeholder (smaller port → `:0`) would
  distinguish the swap but would make the hash depend on OS
  allocation order and break repeat-100 determinism, so it is
  rejected on spec grounds (§7.8 I-08: the same logical input
  must hash identically across runs).
- **Accepted residual:** contract identity is modulo ephemeral
  ports, exactly as §10.4 specifies. Execution and validation
  still use the real ports (the runner connects proxy vs origin
  by role, never by hash; `contract.py::_semantic_errors`
  still enforces same path / different ports on real values).
  No Golden scenario distinguishes the pair; no verdict,
  parity, or Golden outcome is affected.
- **口径澄清（P1-03 / R1 P2-02）：该哈希表示的是忽略端口值后的语义契约身份，不是完整的实际端点身份。**
- A pinning test records the acceptance:
  `test_contract_hash_port_swap_collides_by_design_t013_f01`
  asserts the swap collides *by design*, with this proof in
  its docstring, so a future "fix" that breaks repeat-100 is
  caught. The C01 report hash `67e69e68…` is unchanged.

## Decision 2 — T011 F-01 + T013-F04 (unbounded reads): bounded streaming read at both sites

- Both production read sites used unbounded `resp.read()`:
  `experiment_runner.py:301` (`_http_get`) and
  `cache_proxy.py:761` (`_fetch_origin`). T014 probes confirmed
  a 2 MiB origin body was returned whole at both sites.
- Fix: a single shared helper,
  `privacy.read_http_body_bounded(response, limit, sentinel=)`,
  reads in 64 KiB chunks, retains only the first `limit + 1`
  bytes, and still measures the exact total size, the exact
  whole-stream SHA-256, and Sentinel presence (with a
  one-sentinel overlap between chunks, so a Sentinel past the
  retained prefix or straddling a chunk boundary is still
  found) over the full stream. The only allocation is the
  retained prefix plus one chunk and a short overlap buffer.
- `_http_get` now returns `HttpGetResult` (status / headers /
  retained body / exact `body_size` / exact `body_sha256` /
  `sentinel_match`) and `_do_request` wires the contract's
  `limits.max_body_bytes` (`self._max_body`, previously assigned
  but never read) and the representation Sentinel. The proxy
  gains a `max_body_bytes` field (contract limits win, default
  1 MiB) and truncates at `_fetch_origin`.
- **Consistency argument:** the truncation happens once, at the
  proxy fetch, so everything downstream sees the same retained
  bytes and hashes stay self-consistent (a stored entry's
  `body_sha256` equals the hash the runner computes from what
  the proxy served). The classifier still rejects oversize
  bodies via `body_too_large` (§8.6, E21). E21 is unaffected in
  substance: its padding is applied in `_serve_once` after the
  fetch, and stored entries keep the original small bodies.
- The old boundary note in `tests/privacy/test_body_limit.py`
  ("cap enforced at classification, not as a bounded read") is
  updated: the read itself is now bounded too.

## Decision 3 — T013-F02 (Oracle parity scope): widen to per-request verified states; production side is the classifier's confirmed states

- The parity check compared verdict + diagnostic projection +
  first error only. Since T014 it also compares the per-request
  verified MISS/HIT/BYPASS states (§12.4): the Oracle emits
  `verified_cache_states` (requests 001–008, confirmed state or
  null), `check_parity` (`scripts/s0_harness.py`) and
  `_oracle_parity` (`report_builder.py`) compare them, and an
  Oracle result without well-formed per-request states fails
  parity (fail-closed).
- **Correction made during T014:** the first implementation
  compared against the *runner's* observation-layer states and
  broke C21 parity. C21's adjudication origin-event list is
  empty, so the classifier downgrades every runner-verified
  state to UNKNOWN while the runner's observations still carry
  the verified states. The correct production side is the
  classifier's trusted states, so `ClassificationResult` now
  exposes `confirmed_cache_states` (built in `_finish` from the
  classifier's internal `confirmed_state` map; early returns
  carry none). The report's oracle block is unchanged (the new
  field is a parity input, not report content — no Schema
  impact).
- Regression tests pin the widening: a state disagreement with
  identical verdict/diagnostics/first-error now fails parity,
  and a missing `verified_cache_states` field fails parity.

## Decision 4 — T013-F05 (Oracle coupling): claim from the raw header; HIT tie from the Oracle's own confirmed MISS

- The Oracle took the production runner's `verified_cache_state`
  as its claimed state and tied HITs to earlier MISSes via the
  production `verified_cache_state`. Since T014 the claim is the
  raw cache-status header (`raw.cache_status_header`) — the same
  claim semantics as the production verifier
  (`cache_evidence.verify_cache_state` takes `header.status`) —
  and a storing MISS is one *this Oracle* confirmed (its own
  `confirmed` map). No Oracle code reads the production
  `verified_cache_state` anymore (verified by grep; the only
  remaining mentions are comments and the Oracle's own new
  `verified_cache_states` output field). Full Golden re-run
  (173 tests, 48/48 parity) confirms no divergence was
  introduced. The `verified_cache_state` field still travels in
  the oracle-input file as part of the raw observation record;
  the Oracle no longer uses it.

## Decision 5 — T008 P2-2 (revalidation parsing): RFC 9111-tolerant, mirrored in the Oracle

- Both `_requires_revalidation` (classifier) and
  `requiresRevalidation` (Oracle `evidence.ts`) now parse each
  directive as `name[=value]` with whitespace stripped around
  `=` and quoted-string parameters stripped, so `max-age = 0`,
  `max-age="0"`, and `no-cache="field"` trigger exactly like
  their compact forms. `max-age` triggers only on an integer
  `0` (`max-age=0.0` does not trigger — integer-only parsing,
  matched on both sides for parity). `no-cache` triggers with
  or without a field-name parameter.

## Decision 6 — T003 P2-01 / P2-02, T006 P3

- **T003 P2-01:** `_parse_accept` skips media types with
  `q <= 0` (RFC 9110 §12.5.1: `q=0` means "not acceptable");
  an Accept naming only `q=0` types classifies as neither and
  the handler answers 406. An invalid `q` value already mapped
  to `0.0` and is now likewise not acceptable (fail-closed).
- **T003 P2-02:** the tie rule ("first listed wins") was
  already correct; it now has tests (live origin, both orders,
  two q levels).
- **T006 P3:** `classifier.py` writes the literal `True` for
  `origin_journal_available` in the `event_support is False`
  branch, with a comment: `_events_support` returns `None`
  (not `False`) when `origin_events is None`, so the branch is
  only reachable when the journal exists. No behaviour change.

## Decision 7 — T011 P2 (cleanup scope): narrow the script, document the primitive

- The script (`scripts/clean_evidence.py`) now refuses any
  target outside the `evidence/` subtree of the workspace root,
  and its `--help` / docstring state the rule explicitly.
  `privacy.delete_evidence_files` gains an optional
  `allowed_subtrees` parameter (the script passes
  `("evidence",)`); callers that omit it keep the plain
  workspace boundary, so the existing primitive tests are
  untouched. Both halves of the review's either/or are done:
  the default subtree is narrowed *and* the rule is stated in
  CLI help and docs.

## Decision 8 — T013-F03 (clean-checkout rebuild path) and the remaining documentation items

- **F03:** from a clean checkout, `npm run build` fails
  (`tsc: not found`, `node_modules/` uncommitted) and `npm ci`
  needs registry access. The frozen rebuild path is: (a) with
  registry access, `npm ci` (pinned `typescript 5.9.3` in
  `report-ui/package-lock.json`) then `npm run build`; (b)
  offline, reuse an installed `node_modules/` with the pinned
  tsc 5.9.3 — T013 verified that rebuild is byte-identical to
  the committed `report-ui.js` (SHA-256 `784e3106…`). The
  committed `report-ui.js` is the frozen artifact; a clean
  checkout that cannot reach the registry cannot rebuild it
  from scratch, and that limitation is recorded in
  docs/LIMITATIONS.md and docs/INSTALL.md rather than hidden.
  No `node_modules/` is committed (unchanged).
- **T012 P2-2:** docs/USAGE.md now cites the committed
  `evidence/Performance/VERIFY_LOG.txt` instead of the
  builder-local `/tmp/t012_verify.log`.
- **T010 P2-1:** `report-ui/T010_NOTES.md` point 5 now reads
  "timeline/baseline/cache tables show digests; diagnostics
  evidence detail shows full hashes".
- **T010 P2-2:** the two conditional `pytest.skip`s in
  `tests/integration/test_report_ui.py` are now hard failures
  (`pytest.fail`, stating that headless Chromium is required);
  CI must provide Chromium (this repo's `_find_chrome` covers
  the Playwright chromium-1255 install). Full suite runs with
  0 skipped.

## Addendum (T014-C, 2026-11-24) — recorded Golden evidence regenerated

- The widened parity (Decision 3) made the *recorded*
  `evidence/Golden/*/production.json` and `oracle.json` (T008/T012
  era, before the new `confirmed_cache_states` /
  `verified_cache_states` fields existed) fail parity
  fail-closed, so `test_committed_samples_match_generator`
  failed on its 3 spot-checked scenarios (C01, C11, E22).
- Fix, by the project's own regeneration path (not by editing
  expectations): `scripts/run_all_48.py` re-executed all 48
  scenarios live (ALL48 PASS 48/48, parity 48/48, E13 3/3,
  E01 determinism 1 hash), then `scripts/build_reports_48.py`
  rebuilt the 48 report samples (REPORTS_STATUS PASS 48/48).
  Verified by diff: all 48 Golden report hashes and all 48
  Reports hashes are **identical** to before regeneration; the
  only changes are the two new parity-input fields plus
  ephemeral OS-assigned ports and port-derived cache keys.
  No verdict, first error, diagnostic, or Golden expectation
  changed. Full suite after regeneration: **967 passed**.
- Lesson: a fail-closed parity widening must be accompanied by
  regenerating the recorded evidence it reads, in the same
  change — the widening is incomplete until the recordings
  carry the new fields.

- The T014 task card requires each fix to be dispatched to a
  Coding Agent in a new session, with builder and reviewer on
  different models. The T014 coordinator runs as a depth-2
  subagent (`can_spawn=no`) and cannot spawn subagents, so all
  eight work packages were implemented directly by the
  coordinator, sequentially (one package at a time, never two
  writers on the same file), each with probe-first reproduction,
  regression tests, and module + Golden re-runs. Independent
  verification is provided by T014-C (independent probe
  re-checks per finding) and T014-D (full gate re-run in a clean
  worktree), and the deviation is reported to the parent agent
  so an additional independent reviewer can be arranged if
  wanted. No Golden expected value was changed; no frozen spec
  text was edited.
```

## 00_control/ADR-008.md

- SHA-256：`2d3bd1e6828ddae2c1f81fd74839dd027bf3c0526e7ee9337bd0cfa679290364`
- 字节数：6087

```
# ADR-008 — ADR-005 的 CLI 延期已被本次实现取代：§4.1 九条命令全部落地（P1-01 FIX-R1）

- **Status:** Accepted (supersedes ADR-005).
- **Date:** 2026-11-24 (P032 FIX-R1, P1-01).
- **Context:** PROJECT_BOOK §4.1 冻结了九条 CLI 命令；v1.0.0 只交付了
  `verify --suite` 与 `benchmark`，其余七条命令加 `verify --report`
  形式按 ADR-005 明确延期至 v1.0.0 之后。终审 R1 的 P1-01 不接受该
  延期作为完整 MVP，要求全部补齐并真实执行。本 ADR 记录延期已被
  本次实现取代；冻结规格正文（`01_project_book/PROJECT_BOOK.md`）
  未改动——与 ADR-005 一样，本 ADR 是记录决定的文件，不是规格修订。

## Decision

- **ADR-005 的延期决定即日起作废。** 以下命令已在
  `src/accepttwin/cli.py` 中落地，全部真实执行对应功能，无空壳、
  无占位帮助项（P1-01 验收：`tests/integration/test_cli_commands.py`
  全量正向 + 负向测试；两个自定义契约真实跑通，见下）：
  `demo`、`run --contract`、`verify --report`、`report preview`、
  `report export`、`report delete`、`clean --run-id`、
  `contract delete`。v1.0.0 的 `verify --suite` / `benchmark --suite`
  接口未变。
- **实现方式（复用，不另写第二套逻辑）：** `run`/`demo` 复用
  `accepttwin.experiment_runner`（冻结四实验）、
  `accepttwin.classifier`、独立 Oracle（`scripts/s0_harness.py`
  的 `run_oracle` + `check_parity`）与
  `accepttwin.report_builder`（正式 `accepttwin.report/v1` 报告）；
  Oracle parity 在 harness 与 report builder 两处各算一次，两处
  不一致时 fail-closed；`report preview/export` 复用
  `scripts/embed_report.py`（隐私预览先于写文件，§4.2 约束 7）；
  三个删除命令复用 `accepttwin.privacy` 的 T011 工作区边界规则。
- **退出码（本次冻结，见 `docs/USAGE.md`）：** 0 = 命令成功
  （`run`/`demo` 要求 Oracle parity 成立且报告 `final=true`；
  报告的裁决本身是数据、不决定退出码——一份有效的
  REPRESENTATION_BLEED 报告仍退出 0）；1 = 门禁/核验失败
  （parity 不一致、报告无效、基础设施失败）；2 = 输入错误或
  拒绝删除（文件缺失、契约非法、非回环 URL、越权删除）。
- **报告 `scenario_id` 标签（诚实说明）：** 冻结的 v1 报告 Schema
  只接受 `^[CE][0-9]{2}$`，因此用户运行的报告按其复现的 Golden
  配置标注（`run` 的 `--scenario-id`，或 S0 配置映射表：如
  healthy+respect_vary → C01、healthy+force_uri_only → C11；未列
  入映射表的配置必须显式传 `--scenario-id`）。该标签记录的是
  **配置**，不是 Golden 身份；运行的真实身份是
  `contract_id` + `contract_sha256` + run-id，记在同目录的
  `run-summary.json` 中。改变 Schema 以容纳自定义标签属于规格
  变更，不在本修复范围内。
- **删除命令的安全边界（与 T011 规则一致）：** 只删工作区内显式
  指定的常规文件；工作区外、符号链接、目录一律拒绝，且一次拒
  绝阻断整批删除。另有两层收窄：`report delete` 只接受
  `output/` 或 `evidence/Reports/` 下、JSON `schema` 为
  `accepttwin.report/v1` 的文件；`contract delete` 只接受
  `contracts/` 或 `output/` 下、JSON `schema` 为
  `accepttwin.contract/v1` 的文件；`clean` 只删
  `output/runs/<RUN_ID>/` 内的平铺常规文件，目录内含符号链接
  或子目录时整批拒绝。

## Verification (P1-01, 2026-11-24, real runs)

- 健康自定义契约 `tests/fixtures/contracts/custom-healthy.json`
  （contract_id `custom-healthy-001`，端口 18771/18772）：
  `accepttwin run` 退出 0，`PASS_OBSERVED`，first_error None，
  Oracle parity True，报告 `final=true`，8 条观测全 MISS。
- 串版自定义契约 `tests/fixtures/contracts/custom-bleed.json`
  （contract_id `custom-bleed-001`，端口 18773/18774，
  `--proxy-mode force_uri_only`）：退出 0，
  `REPRESENTATION_BLEED`，first_error 6（HTML_TO_MARKDOWN），
  请求 006/008 为 HIT，Oracle parity True，报告 `final=true`。
- `demo`：健康（C01 配置）`PASS_OBSERVED` + 串版（C11 配置）
  `REPRESENTATION_BLEED`，两份报告均 Oracle parity、均已导出
  HTML，`DEMO_STATUS: PASS`。
- `verify --report` 对两份报告均为 0（含 `--contract` 的
  contract_sha256 一致核对）；篡改裁决的报告退出 1；
  `report preview` 不写文件；`report export` 的 HTML 含报告
  哈希与裁决、0 远程引用、0 Sentinel 字面值。
- 全量测试见 `tests/integration/test_cli_commands.py`（P1-01 新增）
  与 `tests/unit/test_verify_s0_parity.py`（P2-01 新增）。

## Consequences

- ADR-005 不再有效：任何“§4.1 命令延期”的引用均以本 ADR 为准。
  `docs/USAGE.md`、`docs/LIMITATIONS.md` 与 `README.md` 中引用
  ADR-005 延期措辞处已同步改写。
- **不再延期核心入口。** 若未来某版本仍想延期某 CLI 子项，必须
  在此 ADR 之后另立 ADR，逐项写明理由，并判断是否影响 P1-01 的
  关闭：凡属 §4.1 九条命令之内的核心入口（`run`、`demo`、
  `verify --report`、报告预览/导出/删除、`clean`、
  `contract delete`），原则上不许再延期；延期其中任何一项都
  重新打开 P1-01，需终审重新裁决。
- `scripts/clean_evidence.py` 保持不变（仍是 `evidence/` 子树的
  脚本清理入口）；CLI 的 `clean` 是面向运行输出（`output/runs/`）
  的另一入口，两者边界在文档中分别写明，不互相替代。
- 本次同时顺手关闭 P2-01：`scripts/verify_s0.py` 的 parity 检查
  已扩大到八项 `verified_cache_states`，与
  `scripts/s0_harness.py:719–766` 与
  `src/accepttwin/report_builder.py:461–499` 三处判定逻辑一致，
  缺失或格式错误的状态 fail-closed；`verify_s0.py` 重跑 19/19
  通过。P2-01 的独立单元测试见
  `tests/unit/test_verify_s0_parity.py`。
```

## 00_control/ADR-009.md

- SHA-256：`1290ab5c47f4511cd9374353582ceaf2b863b949fa05c208db2dba4bf3e46efe`
- 字节数：10698

```
# ADR-009 — P1-03 规格截断占位补全（v1.0.0 → v1.0.1 建议）

- 日期：2026-11-24
- 背景：GPT 最终评审 R1（2026-11-24 ~18:06 GMT，GPT-6.2 + Extra High，FINAL_VERDICT: FAIL）给出 P1-03：正式规格两文件含 45 行 / 58 处页面提取截断占位标记（PROJECT_BOOK.md 21 行 / 26 处，IMPLEMENTATION_PLAN.md 24 行 / 32 处）。占位标记源于规格冻结时 GPT 侧页面提取截断，非有意留空。
- 决定：逐处补齐并删除全部占位标记；补齐内容逐处登记来源对照表 `00_control/P1_03_SOURCES.md`；两份 DOCX 重新生成并核对；顺手完成 P2-02、P2-04。

## 改动文件

| 文件 | 改动 |
|---|---|
| 01_project_book/PROJECT_BOOK.md | 补 21 行占位（26 处）+ frontmatter 补 `status: SPEC_FROZEN`；+510/−（净增约 450 行，含 §14.2 完整合成报告 JSON） |
| 02_implementation_plan/IMPLEMENTATION_PLAN.md | 补 24 行占位（32 处）；+79/−（净增约 55 行） |
| 01_project_book/PROJECT_BOOK.docx | 重新生成（python-docx，61,734 → 65,912 B） |
| 02_implementation_plan/IMPLEMENTATION_PLAN.docx | 重新生成（python-docx，55,960 → 57,638 B） |
| docs/LIMITATIONS.md | P2-02：T013-F01 行补“该哈希表示的是忽略端口值后的语义契约身份，不是完整的实际端点身份。” |
| 00_control/ADR-007.md | P2-02：决定 1 同补该句 |
| 08_release/RELEASE_NOTES.md | P2-04：T014-C 探针数 23 → 25 |
| 08_release/HOW_TO_REPRODUCE.md | P2-04：同上 |
| 00_control/PROJECT_STATE.md | P2-04：同上 |
| 00_control/VERIFY_LOG.md | 两处占位措辞改为“页面提取截断占位标记”；追加 P1-03 闭环注记 |
| 00_control/split_specs.py | MARK 常量置空并注明退役（一次性拆分脚本不再用于生成规格） |
| 00_control/P1_03_SOURCES.md | 新增：45 处逐处来源对照表 |
| 00_control/ADR-009.md | 新增：本文件 |

未改动：src/、oracle/、tests/（零改动）；08_release/RELEASE_MANIFEST.json、SHA256SUMS.txt、source.zip（留待重冻结时再生）；evidence/Review/INDEPENDENT_REVIEW.md（仅含短式提及，非字面标记）。

## 来源原则

1. **优先 GPT 已交付文字**：补全材料 `~/workspace/P032_SPECS.md`、`P032_SPECS_SUPPLEMENT.md`、`P032_SPECS_CLARIFY.md`（2026-11-24 ~12:10–12:33 GMT，GPT-6.2 + Extra High）。凡 GPT 已交付的措辞（示例值、字段名、免责声明）原样保留。
2. **GPT 未交付处以冻结实现为准**：源码、测试、Golden 夹具、实际运行报告（evidence/Reports/C11.json）、实际运行日志（t014c_checks.log）、冻结目录树（`git ls-files`）。不合 GPT 草签之处以冻结实现为准，并在来源表中登记差异（共两处：§5.7 Oracle 签名改写为冻结 `evaluateScenario(input: OracleInput)`；Oracle 树不含 package-lock.json，GPT 补全称有而冻结树无）。
3. **严禁臆造**：无 GPT 文字、无实现证据之处不编。结果：**UNSOURCED：无**——45 处全部有来源；仅有的三处判断性填补已在来源表注明（E03 curl 补一词、§4.3 示例观测值、§21 状态四行取重冻结时点现行值）。
4. **合成示例必须可验证**：§14.2 合成 C11 报告 JSON 结构逐字取真实运行报告 evidence/Reports/C11.json，哈希用占位合成值（64 位十六进制），整例通过 `schemas/accepttwin.report.v1.schema.json` 的 jsonschema 校验（初版缓存条目占位值不合 `^entry-[0-9a-f]{16}$` 模式，已改为 `entry-0000000000000001` 后通过）。
5. **不改历史**：R1 历史文件中的旧值（FINDINGS.json 旧 MD5、RELEASE_MANIFEST.json:1619 的 "23 checks"）一律不动；正确值（FINDINGS.json MD5 `4edbc89accc32f92f47a5ae5dc5616f0`，实测复核一致）写入本轮回报与来源表，由主协调员在 R2 消息中使用。

## 占位清零核对方法

1. 编辑脚本（`/tmp/p103_edits.py`，不随仓提交）对每一处旧串做唯一出现断言（`str.count(old) == 1`），替换后逐文件复核剩余标记数为 0。
2. 全仓 grep（仓库根目录，排除 .git）：核对命令为 `grep -rn "页面提取截断[，,]未取回全文" --exclude-dir=.git .`——字符类写法与字面标记等价，但核对文档本身不含该字面串，避免自引用误报。**结果：0 命中。** 两份规格 MD 各 0 处；两份 DOCX 经 python-docx 只读文本抽取（段落 + 表格）亦 0 命中。
3. DOCX 核对（只读文本抽取，不用 SHA 对比新旧 DOCX，因 python-docx 输出非字节确定）：PROJECT_BOOK.md 标题 104 项、IMPLEMENTATION_PLAN.md 标题 63 项，与对应 DOCX 标题逐项一致；关键内容抽查全部命中（Sentinel 标识、AC11、§15 架构图、§14.2 JSON 8 条观测、`evaluateScenario(input: OracleInput)`、S0 通过标准、T014-D 命令等）。
4. 残留说明：短式提及 `[页面提取截断]` 仍存于两处冻结文件（evidence/Review/INDEPENDENT_REVIEW.md:24、08_release/RELEASE_MANIFEST.json:1607），属历史记录措辞而非字面占位标记，不在 P1-03 清除范围内；IMPLEMENTATION_PLAN.md frontmatter 注记（“本文件 frontmatter 代码块在页面提取中未取回”）按 VERIFY_LOG.md D-05 原决定保留，不伪造 GPT 原 frontmatter。

## 版本建议：v1.0.0 → v1.0.1

**建议升版为 v1.0.1（文档补丁版），由主协调员在重冻结时最终裁决。理由：**

- 本次改动是纯文档补全：补齐的是 v1.0.0 冻结时已定稿、仅因页面提取截断而缺失的文字；未改动任何冻结语义——实验、裁决、诊断代码、Golden、Oracle、缓存证据规则、哈希规则均未变。补全内容与冻结实现逐项一致（见来源表），不存在“新规格”。
- 但提交 R2 的文件字节与 R1 评审过的 v1.0.0 字节不同：规格正文新增约 500 行（含 §14.2 完整 JSON、§15 图/树、§19/§4.1 完整交付树、§21 状态块）。升一个补丁号可使“R1 审过的文本”与“R2 将审的文本”在版本上可区分，避免混淆。
- **升版的下游代价（重冻结时一并处理）**：spec_version 出现在多处——两份规格 frontmatter（`spec_version: 1.0.0`）、§21 状态块（`SPEC_VERSION: 1.0.0`）、48 份报告样本的 `project.version`（如 evidence/Reports/C11.json）、RELEASE_MANIFEST.json 与 source.zip。若升版，须同步更新这些取值并重新生成清单与 ZIP；若决定不升版，则本轮补全记为 v1.0.0 的勘误（errata），以本 ADR 与来源表为据，同样可提交 R2。
- 不建议升 v1.1.0：无新增功能、无语义变更，不符合次版本含义。

## 升版执行（v1.0.1，重冻结 FIX-R1，2026-11-24）

主协调员已裁决采纳 v1.0.1。重冻结执行者按本节同步，执行结果如下：

- **已同步为 1.0.1**：
  - `01_project_book/PROJECT_BOOK.md` frontmatter `spec_version`、正文首行“版本 1.0.1”、§1 导语“ SPEC v1.0.1”、§14.1 Report 结构示例与 §14.2 合成 C11 报告示例中的 `project.version`、§21 “本项目书 v1.0.1 冻结……”与 `SPEC_VERSION: 1.0.1`（共 7 处）。
  - `src/accepttwin/report_builder.py:659` 生成器 `project.version`（1.0.0 → 1.0.1）；`schemas/accepttwin.report.v1.schema.json` 的 `project.version` const（同）；`tests/unit/test_report_builder.py:224` 与 `tests/unit/test_report_schema.py:121` 的断言值（同）。
  - 48 份报告样本 `evidence/Reports/*.json`：用正规生成器 `scripts/build_reports_48.py` 重生成（非手改），`REPORTS_STATUS: PASS`（schema 48/48、verdict 48/48、parity 48/48）；49 页 HTML 用 `scripts/embed_report.py --all-48` 重建（0 远程引用、0 Sentinel 字面值）。样本差异逐文件恰为 2 行：`project.version` 与 `report_hash`（正式 `report_hash` 的规范化输入含 `project.version`——`REPORT_HASH_EXCLUDED_FIELDS` 仅排除 6 个端口/计数类字段——故升版必然改变全部 48 个样本哈希；裁决、诊断、观测均未变）。C01 样本哈希由 `2decfb46…` 变为 `4645e3408cd6650b26780e71b2819e4fbdadae7ed346f1f1cd51c7e1ed6ae9ee`。**实况运行哈希不变**：`scripts/s0_harness.py:453` 的实况 `report_hash` 是对裁决相关约简字典（观测投影 + 诊断代码 + 裁决 + first_error）的哈希，不含 `project`，故 C01 实况哈希仍为 `67e69e68e128441b67fae155ac1af8dbb4e7992b4dfe70db7dcef1f04e62acde`（与 T007 修复后记录一致）；`docs/USAGE.md:242` 与 `08_release/HOW_TO_REPRODUCE.md` 引用的该哈希无需更改。双哈希并存仍是 T009 既有设计（实况 67e69e68… / 样本 4645e340…）。
  - `README.md:11` 规格版本行 v1.0.1；`RELEASE_MANIFEST.json`（`spec_version`、新冻结 commit/tag、source.zip 哈希/大小/文件数、samples 节、gate 实测值，随重建同步）；`source.zip`（`git archive` 新冻结，prefix `accepttwin-1.0.1/`）。
- **未改动（有意保留 1.0.0）**：
  - 产品版本：`pyproject.toml` `version`、`src/accepttwin/__init__.py` `__version__`、`oracle/package.json`、`report-ui/package.json` / `package-lock.json` 仍为 1.0.0；`AcceptTwin/1.0.0` User-Agent（含 `request_headers.py`、两份契约 Schema const、规格 §5/§14 示例中的 `user_agent`）仍为 1.0.0——本次升的是**规格版本**，不是产品版本。
  - `02_implementation_plan/IMPLEMENTATION_PLAN.md` **无 frontmatter**（D-05 原决定保留“frontmatter 未取回”注记，未伪造）；其 4 处 `1.0.0` 均为冻结历史/格式示例（§1 decision.json 示例、`§T013` 输入版本、`§T014` 清单格式示例），不改。
  - 历史记录：`00_control/VERIFY_LOG.md`（v1.0.0 核验事件记录）、`00_control/competitive_gate/decision.json`（T001 门禁执行时的 `spec_version`）、`00_control/ADR-001–ADR-007` 及 `P1_03_SOURCES.md` 中的 v1.0.0 引述、第三方 `cache-tests/package-lock.json`，一律不动。
- **顺手小修**：`PROJECT_BOOK.md` §15.2/§15.3/§15.4 三行行首多余中文冒号 `：` 已删除（同类残留全仓 grep 为 0）；DOCX 已用 `00_control/build_docx.py`（系统 python3 的 python-docx 1.1.0）重生成，标题 104/104、占位符 0 处、行首冒号 0 行。

## P2-02 / P2-04 附记

- P2-02 口径句已写入 LIMITATIONS.md 与 ADR-007 决定 1，与 R1 要求原文一致；ADR-007 决定 1 的原有论证（§10.4 强制碰撞、钉住测试）不变。
- P2-04 实测依据：`~/workspace/t014-scratch/t014c_checks.log` 含 25 条 `[PASS]`，`FAILURES: none`（第 31 行）；三处发布文本已统一为 25。RELEASE_MANIFEST.json:1619 的旧 "23 checks" 留待重冻结随清单再生刷新。
```

## 00_control/P1_03_SOURCES.md

- SHA-256：`259ba84e0a12edaa0e64d3b845924a55e75ae46ff2aa162594a325d07fe897d8`
- 字节数：20228

```
# P032 P1-03 — 规格截断占位逐处来源对照表

- 任务：P032 AcceptTwin FIX-R1 P1-03（2026-11-24 ~18:11–19:00 GMT）。
- 范围：`01_project_book/PROJECT_BOOK.md` 21 行 / 26 处、`02_implementation_plan/IMPLEMENTATION_PLAN.md` 24 行 / 32 处，合计 **45 行 / 58 处**字面占位标记，已全部补齐并删除。另补 PROJECT_BOOK.md frontmatter `status: SPEC_FROZEN`（R1 P1-03 表格点名、非字面标记，见末尾“附带处理”）。
- 来源优先顺序：GPT 已交付文字（S1–S3）＞ 冻结实现（F：源码、测试、Golden 夹具、实际运行报告与日志）＞ 本文件内其他已完整章节。**UNSOURCED：无。** 每一处都注明了来源；凡 GPT 原文与冻结实现不一致处，以冻结实现为准，并在表中写明差异。
- 行号： “原行”为补前文件行号；“新行”为补后文件行号（§14.2 完整 JSON 使 PROJECT_BOOK.md 后续行号后移）。

来源代号：

- S1 = `~/workspace/P032_SPECS.md`（GPT 主回复，2026-11-24 ~12:10 GMT，GPT-6.2 + Extra High）
- S2 = `~/workspace/P032_SPECS_SUPPLEMENT.md`（GPT 补全回复，~12:22 GMT）
- S3 = `~/workspace/P032_SPECS_CLARIFY.md`（GPT 追问回复，~12:33 GMT）
- F = 冻结实现（本仓库文件，写明路径与行号/位置）
- R1 = `~/workspace/P032_FINAL_REVIEW_R1.md`（GPT-6.2 + Extra High，2026-11-24 17:33 GMT）

## 一、PROJECT_BOOK.md（21 行 / 26 处）

| # | 原行 → 新行 | 缺失内容 | 填补内容摘要 | 来源 |
|---|---|---|---|---|
| PB-01 | 63 → 62 | E03 Cloudflare 示例 curl 尾部（截于 `Accept: text/m`） | 补为 `-H "Accept: text/markdown"`（仅补 `arkdown"` 一词） | S1 §2.3（同一句截于同处）；取值由同段“Accept: text/markdown”与本文件 §5.1.2 强制确定 |
| PB-02 | 91 → 90 | §4.2 主流程图后半段 | 补完整流程链：源站直连基线（O-H、O-M）→ HTML 独立冷请求 → Markdown 独立冷请求 → HTML→Markdown 暖缓存 → Markdown→HTML 暖缓存 → 分类裁决与首次错误定位 → Oracle 对账 → 生成 JSON 与自包含 HTML 报告 → 隐私预览与导出 | F：本文件 §6 全局固定顺序 + §10.2 步骤 01–25（S3 已完整交付）；S2 §7 只交付了图头与 7 条流程约束（已在文件内） |
| PB-03 | 99 → 98 | §4.3 区域 D 示例 `Observed…` 之后 | 补 Observed Representation: HTML、Observed Content-Type: text/html; charset=utf-8、Cache Status: HIT、Sentinel Match: false；`Request Index: 2` 为 GPT 已交付示例值，原样保留 | F：§8.2 串版七条件 + 首次错误字段集（report-ui/src/app.ts:427–438：请求序号/实验/请求表示/响应表示/状态码/Content-Type/缓存状态/Sentinel 匹配）；示例值本身按 S1 §4.3、S2 §8 的合成示例性质处理，非运行结果 |
| PB-04 | 107 → 104–110 | §4.3 代码块 `Request` 之后 | 与 PB-03 同一套字段，写成示例代码块：Request Index: 2、Requested/Observed Representation、Observed Content-Type、Cache Status: HIT、Sentinel Match: false | 同 PB-03（S2 §8 只交付到 `Request` 一词） |
| PB-05 | 382 → 386 起 | §14.1 核心数据对象树（两处标记） | 写出完整对象树：Contract（10 字段）、Representation（4 字段）、RequestObservation（13 字段）、Diagnostic（6 字段）、Report（16 顶层键）；附注：补全片段的 contractId/originUrl/requestHeaders/cacheBehavior 拼写按冻结实现统一为 snake_case | S2 §4（只交付 Contract 前半句）；F：src/accepttwin/contract.py:139–175（Contract/Representation）、§5.5（RequestObservation，本文件已完整）、src/accepttwin/diagnostics.py:135–148（Diagnostic）、schemas/accepttwin.report.v1.schema.json（Report 16 键）+ evidence/Reports/C11.json |
| PB-06 | 390 → 463 起 | §14.2 报告 JSON 示例全文 | 写出完整合成 C11 报告 JSON：16 顶层键、8 条观测、6 条诊断、verdict REPRESENTATION_BLEED、first_error 6 / HTML_TO_MARKDOWN；哈希全部为占位合成值（正文哈希 `a…a`/`b…b`、缓存键 `c…c`、契约哈希 `d…d`、Sentinel 哈希 `e…e`/`f…f`、报告哈希 `9…9`、缓存条目 `entry-0000000000000001`）；端口取 §5.1.1 默认值 18765/18766，contract_id 取 contracts/site.json 的 `site-example-001` | S2 §5（合成 C11 案例、占位哈希、first_error 为请求 6）；F：结构与非哈希值逐字取 evidence/Reports/C11.json（真实 C11 运行报告），字段集符合 schemas/accepttwin.report.v1.schema.json（已用 jsonschema 校验通过） |
| PB-07 | 410 → 757 起 | §15.1 技术架构图（两处标记） | 补完整流水线文字链 + ASCII 图：CLI → Contract Validator → Synthetic Origin + Controlled Cache Proxy → Experiment Runner → Production Classifier → Report Builder → Self-contained HTML Report；Independent Oracle 与生产分类器并行对账 | S1 §15.1（只交付 `AcceptTwin CLI → Contract Validator → …`）；S2 §6（只交付 CLI 方框顶）；F：§10.2 步骤 + §15.2–15.4 模块职责分工 |
| PB-08 | 414 → 801 | §15.2 Python 模块一句话清单（两处标记） | 补全 17 个模块文件名（按冻结目录顺序） | F：`git ls-files src/accepttwin/`（17 文件）；S1 §15.2、S2 §6.1 只交付到 contract.py |
| PB-09 | 418 → 805 | §15.3 前端模块一句话清单（两处标记） | 补全 report-ui 文件清单：src/ 4 个 TS + index.html、styles.css、package.json、package-lock.json、tsconfig.json、report-ui.js、T010_NOTES.md | F：`git ls-files report-ui/`（排除 node_modules）；S1 §15.3、S2 §6.2 只交付到 diagnostics.ts |
| PB-10 | 422 → 809 | §15.4 Oracle 一句话清单（两处标记） | 补全 oracle 文件清单：package.json、tsconfig.json、src/input.ts、evidence.ts、oracle.ts、index.ts | F：`git ls-files oracle/`（6 文件，无 package-lock.json）；S1 §15.4、S2 §6.3 只交付到 `ora…` |
| PB-11 | 428 → 816 起 | §15 ASCII 图 CLI 方框底边（1 处标记） | 与 PB-07 同一完整架构图（本行属该图的一部分，随图一并补齐） | 同 PB-07 |
| PB-12 | 429 → 849 | 6.1 Python 模块树标题（1 处标记） | 标题补完；其下为完整 17 模块树 | F：`git ls-files src/accepttwin/` |
| PB-13 | 435 → 855 起 | 6.1 树 `contract.py` 行之后（1 处标记） | 补齐树剩余部分：diagnostics.py、evidence.py、experiment_runner.py、origin_server.py、privacy.py、report_builder.py、request_headers.py、schema.py、url_guard.py | F：同 PB-12；S2 §6.1 只交付到 contract.py |
| PB-14 | 436 → 869 | 6.2 前端模块树标题（1 处标记） | 标题补完；其下为完整 report-ui 树 | F：`git ls-files report-ui/` |
| PB-15 | 443 → 877 起 | 6.2 树 `└` 行（1 处标记） | src/ 止于 diagnostics.ts（冻结 src/ 仅 4 个 TS）；其后补 report-ui 根目录文件：index.html、styles.css、package.json、package-lock.json、tsconfig.json、report-ui.js、T010_NOTES.md | F：同 PB-09；注：GPT 原文的 `└` 后无第 5 个 src/ 文件，冻结树为准 |
| PB-16 | 444 → 883 | 6.3 Oracle 模块树标题（1 处标记） | 标题补完；其下为完整 oracle 树 | F：`git ls-files oracle/` |
| PB-17 | 451 → 890 起 | 6.3 树 `│   ├── e` 行（1 处标记） | 补为 evidence.ts，其后 oracle.ts、index.ts；**未列 package-lock.json**：S2 §6.3 称 oracle/ 含 package-lock.json，但冻结树（`git ls-files` 与磁盘）均无此文件，以冻结树为准 | F：同 PB-10；差异已在此登记 |
| PB-18 | 512 → 952 | §19 交付物目录树引言（1 处标记） | 引言补完；其下为完整交付树（见 PB-19） | S3 §19（引言句本身完整，树只展开到 pyproject.toml） |
| PB-19 | 518 → 958 起 | §19 树 `├── package` 行（1 处标记） | 补完整交付树：根文件 + 00_control/、01_project_book/、02_implementation_plan/、08_release/、contracts/、docs/、evidence/、fixtures/、oracle/、report-ui/、schemas/、scripts/、src/、tests/；“还必须有”清单（源码 ZIP、Golden、Oracle、报告样本等）逐项对应 08_release/ 与 evidence/ | F：冻结仓库根目录实际条目（`ls -a`）；注：根目录无 package.json/package-lock.json，GPT 的 `package…` 残行无从补出具体文件名，故按冻结根目录写出完整树 |
| PB-20 | 533 → 986 | §21 状态块引言（1 处标记） | 引言补完；其下为完整状态块（见 PB-21） | S3 §21（引言与前 4 行已交付） |
| PB-21 | 538 → 991–994 | §21 状态块 `IMPLEMENTATIO` 截断行（1 处标记） | 补全四行：IMPLEMENTATION_STATUS: COMPLETE、RELEASE_STATUS: READY_FOR_FINAL_REVIEW、FINAL_GPT_REVIEW: PENDING、ACCEPTED: PENDING | F：字段名来自 S2 T014 完成定义；取值取重冻结时点的现行项目状态，见 00_control/PROJECT_STATE.md:5（同一四字段）；§21“项目当前状态”为现行状态，非规格冻结时点快照，特此说明 |

## 二、IMPLEMENTATION_PLAN.md（24 行 / 32 处）

| # | 原行 → 新行 | 缺失内容 | 填补内容摘要 | 来源 |
|---|---|---|---|---|
| IP-01 | 29 → 29 | §0.5 状态机横向链（1 处标记） | 补全链：TODO → READY → RUNNING → SUCCESS / RETRYABLE_ERROR / FATAL_ERROR | S1 §0.5（链本身已交付到 `RETRYABLE_ERROR / ……`）；S2 §四（状态机图头 + 状态定义 + 12 条强制转换规则，本文件已完整） |
| IP-02 | 36 → 36–45 | §0.5 纵向状态机图 `READY` 之后（1 处标记） | 补纵向链：READY → RUNNING → SUCCESS / RETRYABLE_ERROR / FATAL_ERROR（三个终态分支） | S2 §四（图头 TODO → READY）；其余与本文件已有的横向链（IP-01）与转换规则逐项一致 |
| IP-03 | 37 → 45 | BLOCKED 行尾部（1 处标记） | 补为 `BLOCKED \| 前置任务全部 SUCCESS → READY` | S2 §四强制转换规则第 7 条（BLOCKED → READY：全部前置任务通过并完成交接） |
| IP-04 | 63 → 63–72 | §1.5 decision.json 示例 `evidence` 之后（1 处标记） | 补全示例 JSON 的完整字段结构：stop_condition、evidence{spec_version、base_commit、started_at、elapsed_minutes、budget_hours、eq_verdicts（EQ01–EQ08）、closest_competitor、second_closest、hardest_gaps_vs_all_tools、not_verified、deliverables}；`decision: CONTINUE` 为 GPT 原示例值，保留；文件后仍有免责声明（示例不得预填冒充实际结果） | F：00_control/competitive_gate/decision.json（冻结 T001 实际文件）的字段结构与取值；S1 §1.5（示例头） |
| IP-05 | 87 → 96 起 | §4.1 工作区根目录树（两处标记） | 补完整根目录树：projects/P032-accepttwin/ 下 README.md、LICENSE、THIRD_PARTY_NOTICES.md、pyproject.toml 及 15 个目录 | F：冻结仓库根目录实际条目；S1 §4.1（只交付到 pyproject.toml） |
| IP-06 | 101 → 132 | §5.1 “主要接口”后（1 处标记） | 仅删除占位标记；三个接口定义（load_contract / validate_contract / canonical_contract_hash）本身已完整在场，无缺失实质内容 | —（标记处无缺失内容，特此登记，非臆造） |
| IP-07 | 125 → 156 | §5.7 Oracle 接口签名尾部（1 处标记） | 改写为冻结签名 `function evaluateScenario(input: OracleInput): OracleResult`，OracleInput 含 format、contract、observations、raw_observations、origin_events、origin_events_available、resets | F：oracle/src/oracle.ts:116（`evaluateScenario(input: OracleInput): OracleResult`）、oracle/src/input.ts:85–93（OracleInput 定义）；注：S1 §5.7 的多参草签（contract、rawObservations、originEvents…）本身即截断未交付，且与冻结实现不符，以冻结实现为准 |
| IP-08 | 137 → 168 | T001 输出列表 `comma…` 之后（1 处标记） | 补 commands.log、decision.json | F：00_control/competitive_gate/ 实际目录（两文件均在）；S1 T001（截于 `comma`，即 commands.log 词中） |
| IP-09 | 141 → 172 | T002 输出列表（两处标记） | 补 src/accepttwin/request_headers.py、tests/unit/test_contract.py、tests/unit/test_url_guard.py | F：冻结源码树 + T002 验收命令（本文件已列两测试文件）；S1 T002（截于 `reque…`，即 request_headers.py 词中） |
| IP-10 | 149 → 180 | T004 第二条验收命令（1 处标记） | 补 `python -m pytest -q tests/unit/test_cache_evidence.py` | F：冻结测试树（tests/unit/test_cache_evidence.py 存在；tests/integration/ 下无 test_cache_evidence.py）；S1 T004（同处截断） |
| IP-11 | 153 → 184 | T005 输出列表（1 处标记） | 补 tests/integration/test_experiment_runner.py | F：冻结测试树；S1 T005（同名文件） |
| IP-12 | 157 → 188 | T006 输出列表（1 处标记） | 补 tests/unit/test_diagnostics.py | F：冻结测试树；S1 T006（同名文件） |
| IP-13 | 161 → 192 | T007 输出列表（1 处标记） | 补 evidence/S0/（C01–C24 场景证据与 S0_SUMMARY.json）、scripts/s0_harness.py | F：冻结目录（evidence/S0/S0_SUMMARY.json 存在，scripts/s0_harness.py 存在）；S1 T007（截于 `S…`） |
| IP-14 | 161 → 192 | T007 S0 通过标准（同行第 2 处标记） | 补 S0_KNOWN_FAILURE_DETECTED: 12/12、S0_STATUS: PASS，并注另须同时满足 C11 串版 3/3、repeat-100 唯一哈希、单场景 < 1s | F：scripts/run_s0.py:216–244（S0_STATUS 判定条件：passed==24、parity==24、bleed_ok、repeat_ok、max_duration<1.0；S0_KNOWN_FAILURE_TOTAL: 12；S0_FALSE_POSITIVE 计 C01/C02/C03/C04/C05/C06/C17/C18） |
| IP-15 | 169 → 200 | T009 输出列表（两处标记） | 补 src/accepttwin/report_builder.py、tests/unit/test_report_builder.py、tests/unit/test_report_schema.py、evidence/Reports/（48 场景报告样本） | F：冻结源码/测试/证据树；S1 T009（截于 `report_buil…`） |
| IP-16 | 173 → 204 | T010 输出列表（1 处标记） | 补 tests/integration/test_report_ui.py | F：冻结测试树；S1 T010（同名文件） |
| IP-17 | 181 → 212 | T012 输出列表（两处标记） | 补 evidence/S0/（S0 24 条重跑证据）、evidence/Reports/（48 场景报告样本复核） | F：evidence/Performance/T012_NOTES.md 验收结果表（S0 重跑见 evidence/S0/S0_SUMMARY.json；48 报告样本见 evidence/Reports/REPORTS_SUMMARY.json）；S1 T012（截于 `evidence/…`） |
| IP-18 | 207 → 238 | T012 验收命令注记（1 处标记） | 补 `python -m accepttwin benchmark --suite all` | S1 T012 验收命令（四条命令完整）；S2 T012（同一位置截断） |
| IP-19 | 215 → 246 | T013 输出列表（1 处标记） | 补 SOURCE_FILE_MANIFEST.md、REVIEW_PACK_03.md、FINDINGS.json、INDEPENDENT_REVIEW.md | F：evidence/Review/ 实际 7 个文件（PROJECT_STATE.md:36 亦有 7 文件清单）；S2 T013（截于 `SOURCE_FILE_MAN`） |
| IP-20 | 249 → 280 | T013 验收命令（同行两处标记之一） | 补 `npm run oracle:parity` | S2 T012 验收命令、S1 T012（`npm run oracle:parity` 为冻结验收命令之一） |
| IP-21 | 249 → 280 | T013 待阅文件清单 `s…`（同行第 2 处标记） | 补 classifier.py、diagnostics.py、contract.py、url_guard.py、origin_server.py、canonical_json.py、report_builder.py、oracle/src/oracle.ts、evidence.ts、input.ts、index.ts、scripts/verify_s0.py、s0_harness.py、run_s0.py | F：实际 T013 阅读清单（00_control/PROJECT_STATE.md:36：全文精读/全文阅读两组文件）+ 冻结源码树 |
| IP-22 | 263 → 294 | T014 输出列表与 Drive 归档树（同行两处标记） | 输出补 HOW_TO_REPRODUCE.md、RELEASE_MANIFEST.json、SHA256SUMS.txt、source.zip；Drive 树补 02_implementation_plan/、08_release/、contracts/、docs/、evidence/、fixtures/、oracle/、report-ui/、schemas/、scripts/、src/、tests/ | F：08_release/ 实际 8 个文件；Drive 归档按冻结目录结构（S2 T014-I），目录集即冻结仓库根目录 |
| IP-23 | 283 → 314 | T014-D 门禁命令（1 处标记） | 补 `npm run oracle:parity` | 同 IP-20 |
| IP-24 | 295 → 326 | RELEASE_MANIFEST.json 示例 `release_status`（1 处标记） | 补 `"release_status": "READY_FOR_FINAL_REVIEW"}` | S2 T014 完成定义（RELEASE_STATUS: READY_FOR_FINAL_REVIEW）；08_release/RELEASE_NOTES.md:8（同一取值） |
| IP-25 | 305 → 336 | T014 验收命令（1 处标记） | 补 `python -m accepttwin verify --suite all；npm run oracle:parity；python -m accepttwin benchmark --suite all` | S1/S2 T012 验收命令集（T014 验收为同一命令集；S2 T014 验收命令本身截于同处） |
| IP-26 | 309 → 340 | T014 完成定义 `ACC…`（1 处标记） | 补 `ACCEPTED: PENDING` | S2 T014 完成定义（前三项）；F：08_release/RELEASE_NOTES.md:9（`ACCEPTED: PENDING`）与 00_control/PROJECT_STATE.md:5（同一四字段） |

注：IP-13 与 IP-14、IP-20 与 IP-21、IP-22 的两项各属同一原行，故行数 24 行、处数 32 处；上表按“处”列出 26 项（含同行第 2 处）。

## 三、附带处理（非 45 行内，但属本次 P1-03 范围）

- **PROJECT_BOOK.md frontmatter**：补 `status: SPEC_FROZEN`，删除“余下字段在页面提取中截断”注记。来源：S1（frontmatter 开头：…spec_version: 1.0.0，status……后略）；取值取本文件 §21 `SPEC_STATUS: SPEC_FROZEN`。R1 P1-03 表格明确点名该行。
- **IMPLEMENTATION_PLAN.md frontmatter**：**未补**。VERIFY_LOG.md D-05 原决定不变——不得伪造成 GPT 原 frontmatter；本轮未新增 frontmatter 块，文件内“本文件 frontmatter 代码块在页面提取中未取回”注记原样保留。该注记不含字面占位标记，不在 45 行内。
- **P2-02**：docs/LIMITATIONS.md T013-F01 行与 00_control/ADR-007.md 决定 1 各补一句：“该哈希表示的是忽略端口值后的语义契约身份，不是完整的实际端点身份。”来源：R1 P2-02 要求原文；ADR-007 决定 1 已有接受残留论证（§10.4 强制碰撞、钉住测试）。
- **P2-04**：T014-C 探针数 23→25。实测：`~/workspace/t014-scratch/t014c_checks.log` 含 **25** 条 `[PASS]`，`FAILURES: none`（第 31 行）——R1 所称 25 条属实。已统一：08_release/RELEASE_NOTES.md:70、08_release/HOW_TO_REPRODUCE.md:149、00_control/PROJECT_STATE.md:38。**未改**：08_release/RELEASE_MANIFEST.json:1619 的旧 "23 checks" 措辞（冻结清单文件，改动将使其自身哈希与 SHA256SUMS.txt 失配，留待重冻结时随清单再生一并刷新）；历史文件中的旧值按任务要求不改。FINDINGS.json 正确 MD5（R1 给出，本轮实测复核一致）：`4edbc89accc32f92f47a5ae5dc5616f0`（文件 20,773 B）——仅写入本回报，不改历史文件。
- **占位标记退役清理**：00_control/VERIFY_LOG.md D-04 与拆分规则第 3 条的两处字面标记措辞改为“页面提取截断占位标记”（历史含义保留）；00_control/split_specs.py 的 MARK 常量置空并注明退役（该一次性拆分脚本不再用于生成规格）。以下两处**未动**，因其含的不是字面标记（仅短式 `[页面提取截断]`），且属冻结证据/清单：evidence/Review/INDEPENDENT_REVIEW.md:24、08_release/RELEASE_MANIFEST.json:1607。
- **§14.2 示例的缓存条目占位值**：初版 `entry-placeholder-0001` 不合 Schema 模式 `^entry-[0-9a-f]{16}$`，已改为 `entry-0000000000000001`（8 处），改后整例通过 `schemas/accepttwin.report.v1.schema.json` 的 jsonschema 校验；其余占位哈希（`a…a`/`b…b`/`c…c`/`d…d`/`e…e`/`f…f`/`9…9`）均为 64 位十六进制，符合模式。

## 四、核对

- 全仓 grep 该字面占位标记：**0 命中**（核对命令见 ADR-009；命令用字符类写法表示模式，避免本文档本身含该字面串）。
- §14.2 示例 JSON：可解析；16 顶层键与 Schema `required` 逐项一致，无多余键；jsonschema 校验 PASS；verdict REPRESENTATION_BLEED、first_error 6 / HTML_TO_MARKDOWN、8 观测、6 诊断、critical_count 6 / warning_count 0。
- 未改动：src/、oracle/、tests/（零改动，见 git status）；未发 GPT 消息。
```

## 00_control/GIT_LOG_T014.txt

- SHA-256：`0c8e83af84981f9008fbbc397eb0b5b63ba8e95f957b41963f810b89763996e6`
- 字节数：2847

```
P032 AcceptTwin — Git record at T014 freeze (generated 2026-11-24 ~17:15 GMT)

== frozen source identity ==
freeze commit: d3bee545d8d42b4f4da3fc48bb0a2f514cdbfa7f (tag P032-v1.0.0)
NOTE: HEAD at record time is 7b42bd7 (post-freeze commit adding only
08_release/ text artifacts + .gitignore; it touches no source).
The frozen source identity is d3bee54, not HEAD.

== HEAD at record time ==
7b42bd78202c99d220ddd404b6117ba12614e467
commit 7b42bd78202c99d220ddd404b6117ba12614e467
Author: Muse <muse@local>
Date: Tue Nov 24 17:09:04 2026 +0000
Subject: P032-T014 release files: 08_release/ text artifacts (manifest, sums, notes, reproduce guide); source.zip stays on Drive, not git

== tag ==
P032-v1.0.0
d3bee545d8d42b4f4da3fc48bb0a2f514cdbfa7f

== log (T014 work, d22ee92..HEAD) ==
7b42bd7 P032-T014 release files: 08_release/ text artifacts (manifest, sums, notes, reproduce guide); source.zip stays on Drive, not git
d3bee54 P032-T014 WP-10: refresh committed S0 evidence for widened parity (verify s0 + benchmark re-run); PROJECT_STATE T014 record through T014-D
aa68ea7 P032-T014 WP-9 (T014-C follow-up): regenerate recorded Golden evidence + 48 report samples for widened parity; all 48 report hashes identical, 967 passed
4aa43a1 P032-T014 WP-7: ADR-005 (§4.1 CLI deferral), ADR-006 (D-03 honest-boundary clause), ADR-007 (T014 fix record); docs cite ADRs; LIMITATIONS residual table closed
c4daaae P032-T014 WP-6+WP-8: cleanup subtree narrowed to evidence/ (T011 P2); USAGE.md durable log path (T012 P2-2); T010_NOTES wording (T010 P2-1); offline rendering tests fail hard without Chromium (T010 P2-2)
8afd7c1 P032-T014 WP-5: Oracle parity widened to per-request verified states (T013-F02); Oracle decoupled from production verified_cache_state (T013-F05); classifier exposes confirmed_cache_states
6e126b2 P032-T014 WP-4: origin q=0 returns 406 (T003 P2-01, RFC 9110 12.5.1); q-tie tests (T003 P2-02)
2da97ce P032-T014 WP-3: RFC 9111-tolerant revalidation parsing (T008 P2-2) in classifier + Oracle; T006 P3 constant-True cleanup
f07b875 P032-T014 WP-2: bounded reads (T011 F-01, T013-F04) via privacy.read_http_body_bounded; runner returns exact size/hash/sentinel, proxy retains limit+1
1419ae4 P032-T014 WP-1: T013-F01 port-swap hash collision accepted with proof (ADR-007 pending); pinning test added, no production change

== freeze commit file stats ==
 evidence/S0/C24/production.json             |  34 +++++++++
 evidence/S0/C24/raw-observations.json       |  88 +++++++++++------------
 evidence/S0/C24/scenario.json               |   2 +-
 evidence/S0/S0_SUMMARY.json                 |  54 +++++++-------
 455 files changed, 9863 insertions(+), 8230 deletions(-)

== worktree status at record time ==
?? 00_control/GIT_LOG_T014.txt
?? evidence/Performance/T014_OFFLINE_LOG.txt
?? evidence/Performance/T014_TEST_LOG.txt
(end)
```
