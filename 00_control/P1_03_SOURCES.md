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
