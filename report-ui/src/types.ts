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
