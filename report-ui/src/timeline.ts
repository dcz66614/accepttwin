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
