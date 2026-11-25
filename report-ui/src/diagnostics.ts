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
