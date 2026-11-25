# P032 AcceptTwin — T013 独立审查报告（INDEPENDENT_REVIEW.md）

- 审查员：T013 独立审查员（与 T001–T012 的构建者、修复者、复核者均不同路线；独立判断）
- 审查对象 commit：`c02387c8d9f7aaeb3da7e8482f97756580ec0a08`（`P032-T012 SUCCESS (independent review PASS, 0 P0/0 P1/2 P2 non-blocking, 936 tests); T013 dispatched`）
- 审查日期：2026-11-24 ~16:21–16:45 GMT
- 审查方式：只读主工作区；全部执行在独立工作树 `~/workspace/p032-review-wt`（同一 commit 的 detached HEAD），用主工作区 `.venv` 运行；无公网访问；无真实用户数据
- 结论：**审查完成（REVIEW COMPLETE）。发现 0 P0 / 0 P1 / 15 P2 / 1 P3。T013 SUCCESS（审查工作完成，不表示项目零缺陷）。未发现假 PASS、缓存错误漏检、证据不足却强行归因、或 S0 门禁缩窄规格。T014 须逐项处置 15 项 P2 与 1 项 P3 后冻结；其中 T012 P2-1（§4.1 CLI）与 D-03 须在冻结前以 ADR 明确处置，不得无声遗漏。**

## T013-A — 审查对象身份核对

- `git rev-parse HEAD` = `c02387c8d9f7aaeb3da7e8482f97756580ec0a08`，与任务简报一致。
- `git status --short`：审查开始与结束时均干净（仅本审查输出 `evidence/Review/` 新建文件未跟踪）。
- 冻结规格 SHA 与 PROJECT_STATE.md 一致：PROJECT_BOOK.md 66,492 B / `ecef2bac4a5fc42fd66118f703f3a01c44d12c011af789392deb79cb232b36f8`；IMPLEMENTATION_PLAN.md 51,364 B / `d3e56decfe999be95484357b9f1df64a845dfa5e833bf023106eb3e4cd79dafd`。
- `git log -- 01_project_book/ 02_implementation_plan/`：自冻结 commit 4d3021f 后无任何改动；实现变更均经 ADR-001–ADR-004，未发现未登记的核心源码修改。
- 源码清单：审查对象 commit 下共 913 个已跟踪文件，SHA-256 全部列入 SOURCE_FILE_MANIFEST.md；审查包内 145 个文件（生产源码 17、Oracle/脚本/UI/配置 37、夹具与测试 91）的 SHA-256 已逐一核对与 `git show <commit>:<path>` 字节一致，0 处不符。
- 生成证据（evidence/，544 个文件，7.9 MB）未逐字节内嵌进审查包（体量原因），但其 SHA-256 在 SOURCE_FILE_MANIFEST.md 中全量登记；其语义内容由本次亲自重跑的 verify/benchmark（见下）独立复现验证，而非采信提交版日志。

## T013-B — 需求覆盖审查（§0–§21 摘要）

逐项结论见 REVIEW_INDEX.md 的覆盖表。本节记录审查方法与关键证据：

- 每个 §结论均有文件级映射与实测命令支撑，不只凭函数名推断。核心文件已逐行阅读（见 REVIEW_INDEX.md 实际阅读清单），其中 classifier.py（925 行）、diagnostics.py（988 行）、experiment_runner.py（806 行）、cache_proxy.py（875 行）、cache_evidence.py（268 行）、oracle.ts（511 行）、evidence.ts（194 行）、verify_s0.py（635 行）、s0_harness.py（697 行）为全文精读；其余为全文阅读。
- §4 是唯一“部分通过”章节：§4.1 九命令中仅 `verify`/`benchmark` 落地，`demo`/`run`/`report preview`/`report export`/`report delete`/`clean`/`contract delete` 未实现为 CLI 子命令；且 §4.1 的 `verify --report <path>` 形式亦未落地——实现的是 `verify --suite s0|all`（不同接口）。缺口在 docs/USAGE.md:108–110 与 docs/LIMITATIONS.md 中如实披露，无占位冒充，裁决为 T012 P2-1（P2，非阻断 T013 SUCCESS；T014 必须书面处置）。
- §5.1.2/§14.1/§14.2/§15.x 等处有 [页面提取截断] 标注（D-04）：审查中未把截断缺失内容当成已取回正文；凡依赖这些位置的断言，均以实际代码/样本核对（如 §14.2 示例的关键结论“C11 首次错误为请求 6”与实际样本一致；§15 模块树以磁盘实际文件核对）。
- §18 AC01–AC11 全部满足，实测数：AC02 24/24、AC03 48/48、AC04 48/48、AC05 已知故障 19/19、AC06 误报 0、AC07 双向真实执行（每场景 8 请求）、AC08 双重证据逐请求重算、AC09 C11 3/3、AC10 repeat-100 distinct=1、AC11 max 单场景 0.030s。

## T013-C — 核心算法审查（15 项，逐项结论）

1. **源站 HTML/Markdown 是否分别真实请求**：是。experiment_runner.py execute() 步骤 07/08 经 `_do_request(1,"html",via_proxy=False)` / `_do_request(2,"markdown",via_proxy=False)` 发真实 `http.client` GET；origin_server.py 为真实 ThreadingHTTPServer。我的 verify 重跑每场景 8 个真实请求（request_count==8，全 48 项）。
2. **两种独立冷请求**：是。步骤 09–12（HTML）与 13–16（Markdown），各自由 ResetCache + VerifyCacheEmpty 开头。
3. **HTML→Markdown 真实执行**：是。步骤 17–21，请求 005/006，实验 ID HTML_TO_MARKDOWN。
4. **Markdown→HTML 真实执行**：是。步骤 22–25，请求 007/008，实验 ID MARKDOWN_TO_HTML。
5. **暖实验中间是否错误清空缓存**：否。步骤 19/20 之间与 24/25 之间无 reset 调用；verify_s0.py 检查 5 逐场景断言 ResetCache 步骤恰为 [9,13,17,22] 且步骤名 19–20、24–25 连续。
6. **是否使用相同 URL**：是。四实验共用 `contract.url`（`_do_request` 中 `via_proxy` 时统一取 `contract.url`）；contract 校验强制 url 与 origin_url 同 path、不同端口。
7. **缓存清空是否有实际确认**：是。`_reset()` 要求 `evidence.success and entry_count==0`；`_verify_empty()` 再核对条目数为 0；C23 注入（首个 reset 报告 success=False）真实导致 INCONCLUSIVE。
8. **MISS 双证据**：是。cache_evidence.py `verify_cache_state`：MISS 要求状态头 + key + entry id、计数 +1、源站事件存在、条目已创建；任一缺失 → UNKNOWN。verify_s0 检查 7 从原始证据逐请求重算。
9. **HIT 三重关联证据**：是。HIT 要求状态头 + key + entry id、计数 0、entry id 与此前存储条目一致、正文哈希与存储条目一致（cache_evidence.py；Oracle evidence.ts 取“最近一次同 entry id 的 MISS”绑定）。
10. **BYPASS 双证据**：是。BYPASS 要求状态头、计数 +1、源站事件存在、条目数不变。
11. **缺少 Vary 是否被错误判为串版**：否。I-11 在 classifier（Vary 缺失至多 WARNING；`required` 时为 CONTRACT_MISMATCH，绝非 BLEED）与 Oracle 中实现；C03/C04 健康对照 PASS 且仅带 VARY_ACCEPT_ABSENT；E04 同理。check_bleed 的七条件不含 Vary。
12. **源站错误是否优先归类**：是。§9.6 优先级在 classifier.py 与 oracle.ts 中逐字实现（out-of-scope → ORIGIN → BLEED → CONTRACT → INCONCLUSIVE → PASS）；C07–C10/E09–E11 全部判 ORIGIN_NEGOTIATION_ERROR，first_error 指向基线 001/002；次级诊断保留。
13. **证据矛盾是否导致 INCONCLUSIVE**：是。C22（HIT 头 + 计数 +1）→ CACHE_EVIDENCE_CONFLICT + INCONCLUSIVE；C20/C21/C23 → INCONCLUSIVE；E17–E20 同理；无一判为 BLEED。
14. **首次错误定位是否准确**：是。first_error 取最小违规请求号（VARY_ACCEPT_ABSENT 除外），不按严重程度重排；verify_s0 检查 13 从诊断逐场景重算，24/24 一致；C11 first_error=6（非 8），与 §14.2 说明一致。
15. **五种裁决优先级是否符合规格**：是。见第 12 项；48/48 场景 verdict 与夹具预期一致，Oracle 独立复算亦一致。

## T013-D — Oracle 独立性审查

- oracle/src/*.ts 全文已读：oracle.ts（511 行）从 §8/§9 逐字重写九诊断与六级优先级；evidence.ts（194 行）独立重算 §5.3 双腿；input.ts（105 行）定义 `accepttwin.oracle-input/v1` 输入格式并拒绝含 verdict/diagnostics/production 键的输入；index.ts（33 行）为 CLI 入口。
- 无生产引用：`grep` oracle/src 仅在注释中出现 "production" 一词（“never imports production Python code…”等声明性文字）；无 `classify_run`、`.py`、`accepttwin.classifier`、`subprocess`、`production.json` 引用（verify_s0 检查 15 同样断言，通过）。
- Oracle 以独立 Node.js 子进程运行（s0_harness.py run_oracle，经 `node oracle/src/index.ts`，timeout 60s），读取的仅是 oracle-input.json（契约 + 原始观测 + 源站事件 + 重置记录），不含生产 verdict。
- **48 条场景分别核验**：我的 verify 重跑日志中 C01–C24、E01–E24 全部 48 行均为 `parity=OK`（非仅总数）；裁决分布 16/7/8/4/13 与 §11 一致；ALL48_SUMMARY.json 的 `oracle_parity` 逐场景均为 true。
- 两处收窄/耦合（P2，见 FINDINGS.json）：
  - T013-F02：parity 比较只含 verdict + 诊断投影（code+request_index）+ first_error，未直接比对逐请求 verified MISS/HIT/BYPASS 状态；§12.4 将“MISS/HIT/BYPASS 证据”列为对账内容。48 场景无实际分歧；但检查本身比规格条目窄，建议 T014 补逐请求状态比对。
  - T013-F05：Oracle evidence.ts 以生产 runner 的 `verified_cache_state`（`obs.cache_status`）作为“声称状态”再验双腿。它重算了全部证据腿（头、计数、事件、条目/正文哈希），无法仅凭声称过度确认；但生产 verifier 的错误验证会作为声称被继承（腿仍重算，故不能无中生有）。建议 T014 改以原始状态头为声称，或以 ADR 记录该耦合。

## T013-E — S0 门禁覆盖审查（§13 逐项）

verify_s0.py 的 19 项检查已逐项读过并与 §13 映射表核对；我的 verify 重跑复现 S0_STATUS: PASS（24/24 golden，parity 24/24）。结论：**门禁定义等于规格要求，未发现缩窄**。逐项：

| §13 映射项 | verify_s0 检查 | 核对结果 |
| --- | --- | --- |
| 24 条核心案例 | 检查 1（夹具存在 + verdict/first_error/诊断投影逐项等于冻结预期） | 通过；夹具 verdict 与 §11.2 原文逐项核对 0 差异 |
| 24/24 Oracle parity | 检查 2（verdict + 诊断投影 + first_error + experiment 逐场景） | 通过 |
| 已知故障全部检出 | 检查 3（C07–C16、C19、C24，12/12） | 通过 |
| 健康零误报 | 检查 4（C01–C06、C17、C18 全部 PASS） | 通过 |
| 两种顺序真实执行 | 检查 5（8 请求序列、实验 ID、表示顺序、ResetCache 恰为 [9,13,17,22]、暖内无 reset、源站事件 ≥6） | 通过 |
| 独立冷请求 | 检查 6（4 次重置均确认空；003/004/005/007 起于空缓存；冷请求 MISS/BYPASS 双证明；C20 例外为 UNKNOWN） | 通过。C21 注释准确：其 runner 层状态为 MISS，故障在 adjudication 边界 |
| 双重缓存证据 | 检查 7（从原始证据重算头腿 + 行为腿；HIT 绑定最近一次同 entry id 的 MISS；UNKNOWN 须有理由） | 通过 |
| 稳定串版复现 | 检查 8（C11 3/3 BLEED，first_error 6，每次 2 条 bleed 诊断） | 通过；我的重跑复现 3/3 |
| 缺少 Vary 健康对照 | 检查 9（C03/C04 PASS + 恰好两条 VARY_ACCEPT_ABSENT） | 通过 |
| no-store 健康对照 | 检查 4 含 C17/C18 | 通过 |
| 100 次报告哈希一致 | 检查 10（100 次 distinct=1、fresh_pair_per_run、same_pair 相等、C01 哈希从已存证据重算、端口改写不变性、C11 三次复现哈希等于主场景） | 通过；我的重跑 C01 哈希 `67e69e68…` 与 T007 修复记录逐字一致 |
| 单场景 < 1s | 检查 11（全部 24 场景 + repeat max < 1.0s） | 通过（max 0.042s） |
| 证据不足不误判 | 检查 12（C20–C23 INCONCLUSIVE、0 bleed；C21 adjudication 输入 origin_events=[] 且 available=false） | 通过 |
| 首次错误定位 | 检查 13（从诊断重算最小违规请求号 + 实验 ID，24/24） | 通过 |
| Canonical JSON | 检查 10（重算 + 端口不变性） | 通过 |
| 强制调用约定（ADR-002 Decision 3） | 检查 14（s0_harness.py:586 调用点逐字核查：传真实元组 + raw_observations，永不传 None；C21 传空元组 `()`） | 通过；我亲自核对 s0_harness.py:586 与 :578–580 的 C21 分支 |
| Oracle 独立性 | 检查 15（oracle/src 无生产引用；oracle-input 无 verdict/diagnostics/production 键） | 通过 |

未发现“比项目书更窄的判断条件”。两个曾被质疑的例外均有合理解释且未缩小覆盖：检查 6 对 C20 的 UNKNOWN 例外是夹具设计的故障本身（opaque 代理）；检查 7 对 C21 UNKNOWN 的放行由检查 1（诊断与冻结预期逐项相等）与检查 12（adjudication 输入断言）联合覆盖。repeat-100 自 T007-FIX 起每次迭代 fresh pair（run_s0.py:175–183），same-pair 检查为补充；verify_s0 检查 10 的端口不变性断言真实有效（旧证据必失败，已由 T007 重审反向对照证实）。

## T013-F — 隐私、安全与发布审查

- **Loopback Guard**：url_guard.py 全读；`validate_loopback_url` 要求 http 方案、无 userinfo/fragment/zone id、端口 1–65535、且 getaddrinfo 返回的**全部**地址均为回环。160 隐私测试在全量内通过。
- **DNS 解析验证**：同上；非回环解析结果拒绝（测试用桩覆盖公网/混合地址）。
- **重定向禁止**：runner `_http_get` 与 proxy `_fetch_origin` 均不跟随重定向（http.client 默认不跟随）；classifier 将 3xx 判 INCONCLUSIVE_LIMIT（redirect）；E12/E22 均为 INCONCLUSIVE。
- **环境代理隔离**：`_http_get` 用 http.client 直连，从不读环境变量；全仓 grep：experiment_runner.py/evidence.py 无 os.environ/getenv 读取（注释除外）；隐私测试覆盖 5 个代理变量指向死代理。
- **敏感请求头拒绝**：固定请求头集合（§5.1.3）；Cookie/Authorization/Proxy-Authorization 拒绝；proxy 转发时重建请求头，丢弃客户端其他头（cache_proxy.py）。
- **正文不写日志/不进入报告**：evidence.py 的 RawObservation/RequestObservation 只存哈希与大小；origin/proxy handler 抑制默认日志；48 份报告经 assert_report_clean 扫描；49 页 HTML 经 assert_html_directory_clean 扫描，Sentinel 常量 0 命中；我的 benchmark 重跑复现“raw body false / sensitive headers false / body hashes true / remote references none”。
- **文件删除边界**：scripts/clean_evidence.py + privacy.py `resolve_cleanup_target`/`delete_evidence_files` 全读；工作区外/.. 逃逸/符号链接/目录均拒绝，单坏目标阻塞整批，--dry-run 只列不删。但可删范围为“工作区内任意显式指定的常规文件”，未收窄到 evidence/ 等子目录（T011 P2，P2，见 FINDINGS.json）。另注意：`accepttwin clean` 未接入 CLI（T012 P2-1 的一部分）。
- **HTML 无远程资源**：49 页扫描 0 违规（我的 benchmark 重跑复现）；report-ui 无 CDN/远程字体/图片；数据插入走 textContent。
- **依赖许可证**：LICENSE 为 MIT；THIRD_PARTY_NOTICES.md 26 行；Python 仅标准库；report-ui 锁文件存在（typescript 5.9.3）；Oracle 零依赖故无 package-lock.json（合理，非缺失）。
- **锁文件完整性**：report-ui/package-lock.json 已提交；`npm ci` 需 registry（已在 LIMITATIONS.md 诚实标注）；新鲜检出 `npm run build` 失败见 T013-F03。
- **报告 Schema**：schemas/accepttwin.report.v1.schema.json 为 Draft 2020-12、顶层 additionalProperties false；48/48 样本通过（benchmark 重跑复现）；独立校验器仅标准库。
- **SHA-256 清单**：SOURCE_FILE_MANIFEST.md（913 文件）；冻结规格 SHA 与 PROJECT_STATE 一致；审查包内 145 文件哈希逐一核对 0 不符。

## 必须裁决的已登记残留项（逐项）

- **T012 P2-1（§4.1 其余 CLI 命令未落地）——成立，P2**。亲自核对 cli.py（423 行）：仅 verify/benchmark 两个子命令；§4.1 的 demo/run/report preview/export/delete/clean/contract delete 均无；`verify --report` 形式亦无，实现为 `verify --suite s0|all`。缺口在 USAGE.md:108–110 与 LIMITATIONS.md 如实披露，无占位冒充。处置：T014 二选一——按 §4.1 落地，或以 ADR 记录为冻结前延期/修订 §4.1，不得无声遗漏。**不阻断 T013 SUCCESS**（CLI 缺口不影响任何裁决正确性），但**阻断无 ADR 的冻结**。
- **T012 P2-2（USAGE.md 引用 /tmp/t012_verify.log）——成立，P2**。docs/USAGE.md:64 引用构建者本机 /tmp 临时日志；durable 证据应为已提交的 evidence/Performance/VERIFY_LOG.txt。处置：T014 改引提交版路径。
- **T011 F-01（无界读取）——成立，P2**。亲自核实：experiment_runner.py:301 `body = resp.read()` 无界；:372 `self._max_body` 仅赋值，全仓仅此一处出现；自写探针证实 1,048,577 字节源站正文被原样读入内存。同意 T011 复核裁决：分类器按 body_size 判 INCONCLUSIVE_LIMIT（E21 实况）有效，超限正文只在内存短暂存在、无泄漏路径、威胁模型下风险可接受，故为 P2 而非 P1。处置：T014 补有界读取（`resp.read(limit+1)` 后判超限，或接入 privacy.enforce_body_limit），并把结论记入 ADR；本审查另发现同类问题见 T013-F04。
- **T011 P2（清理命令可删子树未收窄）——成立，P2**。亲自核对 privacy.py:516–582：规则确为“工作区内 + 显式指定 + 常规文件 + 非符号链接”，操作者显式点名即可删除工作区内任意常规文件（含源码）。处置：T014 二选一——收窄默认可删子树（如 evidence/ 等），或在 CLI 帮助与文档中明示。
- **T010 P2-1（T010_NOTES.md 第 5 点措辞）——成立，P2**。亲自核实：evidence/Reports/html/C11.html 含 24 处完整 64 位十六进制哈希（诊断证据详情显示完整 body_sha256/cache_key_sha256），与 NOTES“UI 只显示前 16 位摘要，完整哈希保留在嵌入与可下载的 JSON 中”不符。行为合规（哈希不是正文，§4.3 区域 F 要求报告含正文哈希，§17.2 允许记录正文哈希），仅措辞。处置：T014 修正措辞为“时间线/基线/缓存表显示摘要，诊断证据详情显示完整哈希”。
- **T010 P2-2（两处条件性 pytest.skip）——成立，P2**。tests/integration/test_report_ui.py:465,492 两处 `pytest.skip("no headless Chromium available…")`。本次全量 936 passed、0 skipped，两项渲染测试实际执行。处置：T014 改为硬失败或保证 CI 环境有 Chromium。
- **T008 P2-2（revalidation token 精确匹配）——成立，P2**。亲自探针：classifier `_requires_revalidation` 对 `max-age = 0` 与 `no-cache="field"` 均返回 False（`max-age=0`/`no-cache` 正常触发）；Oracle requiresRevalidation 行为一致。处置：T014 加固为 RFC 9111 宽容解析（去空格、去引号参数）。
- **T006 P3（origin_journal_available 恒为 True）——成立，P3**。classifier.py:595 位于 `event_support is False` 分支内，而该分支仅当 origin_events 非 None 时可达，故 `(origin_events is not None)` 恒为 True。无行为影响。处置：T014 清理。
- **T003 P2-01（q=0 未返回 406）——成立，P2**。亲自实测：`Accept: text/markdown;q=0` 与 `text/html;q=0` 均返回 200（RFC 9110 §12.5.1：q=0 表示不可接受，应为 406）。origin_server.py `_parse_accept` 以 best_q=-1.0 起步，q=0 仍被采纳。处置：T014 修复（q=0 的媒体类型视为不可接受）并补测试。
- **T003 P2-02（q 平局无测试）——成立，P2**。亲自实测平局规则本身工作正常（先列出者胜：HTML 先→HTML，Markdown 先→Markdown）；但全仓无 q 平局测试。处置：T014 补测试。
- **T007 重审残留风险——三项分别裁决**：
  - （a）证据文件仍含真实端口——**不构成缺陷**。原始证据（raw-observations.json、contract.json）本应记录实际使用的 URL 与端口；§10.4 的端口排除仅约束规范化报告哈希载荷，该载荷经 ADR-003 归一化且已验证（两次独立运行 C01 哈希逐字相同）。无行动。
  - （b）`url`/`origin_url` 在哈希中塌缩为同一 `:0`——**成立，新发现 T013-F01（P2）**。亲自探针：仅互换 url 与 origin_url 端口的两份契约哈希相同（`82686a3e6dc62a53…`）。两份语义不同的契约（代理与源站角色互换）共享同一哈希，削弱契约身份；执行仍用真实端口，裁决不受影响，无 Golden 场景可区分。处置：T014 改为角色区分的占位（如 url→`:0`、origin_url→`:1`）或在 ADR 中接受并记录。
  - （c）loopback 名仅识别 `localhost`——**不构成缺陷**。contract.py `_is_loopback_host` 对未知名字保守地不归一化，属 fail-closed 方向（只会使哈希带端口依赖，不会造成错误相等）；harness 使用 127.0.0.1。无行动。
- **D-03（诚实边界未集中成单一条款）——成立，P2，仍 OPEN**。README.md:84 已有诚实边界一节并引用 D-03，LIMITATIONS.md 登记 OPEN；但集中条款 ADR 尚未起草。处置：终审前起草集中条款经 ADR 补入。
- **D-01、D-04–D-08——已登记/已标注，随规格移交，无行动**。D-01（§19–§21“此前已存在”说法与交付记录不符，内容已补齐）；D-04（26+32 处截断标注，本审查未把截断内容当成正文）；D-05（frontmatter 不完整）；D-06（任务卡附属列表截断，T013 输出文件名即据此按实际需要命名并在 REVIEW_INDEX.md 中说明）；D-07（GPT 完整性声明不成立的部分仅限长代码块提取截断）；D-08（§5.1.2 JSON 按字段表写出，已核对）。

## 新发现（T013 亲自探针证实，详见 FINDINGS.json）

- **T013-F01（P2）**：端口交换契约哈希碰撞（上节 (b)）。
- **T013-F02（P2）**：Oracle parity 未直接比对逐请求 verified 缓存状态（§12.4 条目窄化）。
- **T013-F03（P2）**：新鲜检出 `npm run build` 失败——report-ui 工作树内无 node_modules，`tsc: not found`；`npm ci` 需 registry。tsc 字节一致性仅在借用主工作区已装 tsc 5.9.3 后验证通过。冻结后干净检出的重建路径须由 T014 明确。
- **T013-F04（P2）**：F-01 无界读取的范围不止 experiment_runner.py:301——cache_proxy.py `_fetch_origin` 同样用无界 `resp.read()`。修复须覆盖两处读取点。
- **T013-F05（P2）**：Oracle 以生产 runner 的 `verified_cache_state` 为声称状态（见 T013-D）。

## 验收命令实测汇总（独立工作树）

- 全量测试：**936 passed，0 failed，0 skipped，67.82s**。
- `verify --suite all`：**VERIFY_STATUS: PASS**（ALL48 48/48、parity 48/48；S0 24/24、parity 24/24；C11 3/3；repeat-100 distinct=1）。
- `benchmark --suite all`：**BENCHMARK_STATUS: PASS**（max 单场景 0.030s；repeat-100 distinct=1；schema 48/48；HTML 49 页 clean）。
- `npm run build`：新鲜工作树失败（T013-F03）；借用已装 tsc 编译 exit 0，产物与提交版字节一致。
- 冻结规格 SHA、git 干净状态、145 个审查包文件哈希：全部核对一致（见 T013-A 与 REVIEW_INDEX.md）。

## 未解决的疑问

1. `npm run build` 离线重建路径（T013-F03）。
2. §4.1 CLI 最终处置（实现 vs ADR 延期），由 T014 决定。
3. D-03 集中条款 ADR 仍待起草。
