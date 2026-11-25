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
