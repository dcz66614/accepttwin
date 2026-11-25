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
