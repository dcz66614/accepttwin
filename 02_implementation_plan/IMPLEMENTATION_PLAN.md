# 文件二：IMPLEMENTATION_PLAN.md

以下为完整实施计划，版本 1.0.1。

版本声明（FIX-R1 后补，非 GPT 原 frontmatter）：本文件版本 v1.0.1，由 v1.0.0 于 FIX-R1 升版；本次升版为纯文档补全（补齐页面提取截断缺失的文字），无语义变更。本文件无 GPT 原 frontmatter——原 frontmatter 代码块在页面提取中未取回，按 D-05 原决定不伪造；此处版本声明为 FIX-R1 执行者后补的版本标识，不是 GPT 原 frontmatter 原文。

# P032 AcceptTwin（网页双态镜）实施计划

本文件是施工任务合同，不是施工记录。所有任务初始状态均为 TODO / NOT_VERIFIED。任何预期 PASS、性能数字、测试数量均为验收门槛，不代表已经执行。

## §0 执行总则与不可变决定

### 0.1 项目目标

在 72 小时有效工程预算及 16 小时缓冲内，实现 AcceptTwin：本地合成 HTTP 源站、本地受控缓存代理、HTML/Markdown 双表示契约、两种独立冷请求、HTML→Markdown 暖缓存实验、Markdown→HTML 暖缓存实验、缓存 MISS/HIT/BYPASS 双重证据、首次错误请求定位、五种确定性裁决、48 组 Golden、独立 TypeScript Oracle、accepttwin.report/v1 JSON、自包含静态 HTML 报告、隐私、离线和许可证验证。产品核心机制严格遵循：对同一 URL 建立 HTML/Markdown 独立冷请求基线，然后分别执行 HTML→Markdown、Markdown→HTML 的暖缓存实验，识别内容串版及首次错误请求。不得将项目缩减成：检查 Vary 是否存在；分别请求两次 HTML 和 Markdown；只测试一个请求顺序；只根据 Age 判断 HIT；只根据 HTTP 200 判断正确；只根据 Content-Type 判断正确；仅用预设 expected result 代替独立 Oracle；只运行合成函数而不真实发送本地 HTTP 请求。

### 0.2 不可变工程决策

1. 产品运行时仅支持本地回环地址；2. 被测资源只使用 HTTP GET；3. 首版不支持 HTTPS；4. 不访问公网；5. 不扫描公网网站；6. 不跟随重定向；7. 不读取系统代理环境变量；8. 不发送 Cookie 或 Authorization；9. HTTP 请求头集合固定；10. HTML 与 Markdown 使用同一 URL；11. 两种表示的 Accept 值不同；12. 每个实验都必须有明确缓存重置证据；13. MISS/HIT/BYPASS 必须同时具备响应头证据和行为证据；14. 四种实验缺一不可；15. 48 组 Golden 全部固定；16. Oracle 独立于生产实现；17. 正文原文不进入默认日志；18. 不使用 LLM、GPU 或收费 API；19. 运行时不依赖互联网；20. 许可证 MIT。

### 0.3 角色职责

Muse：项目 Owner 代理及总调度——负责管理项目工作区、检查当前虚拟机环境、执行任务派发、根据实际测试过的免费模型清单分配工种、创建独立任务会话、运行门禁命令、检查任务输出、检查文件哈希、记录 Git commit、验收任务交接、归档证据、上传 Google Drive、整理终审材料；Muse 不负责编写业务代码、修改业务算法、编写业务测试、编写独立 Oracle、替代独立代码评审、把施工 Agent 自评当作最终验收。Coding Agent：施工执行——负责 Python 生产实现、HTTP 源站、缓存代理、实验执行器、分类器、测试、JSON Schema、TypeScript 报告界面、独立 Oracle、文档构建、修复、打包。独立 Reviewer——负责审查规格实现一致性、检查是否漏掉实验、检查缓存状态是否有双重证据、检查错误归因、检查隐私、检查 Oracle 独立性、检查报告 Schema、检查 S0 门禁覆盖、检查发布文件和哈希；施工模型与独立 Reviewer 必须尽量使用不同模型或独立会话。

### 0.4 新会话纪律

每张任务卡都必须在免费模型平台开启全新会话。禁止：依赖旧会话隐式记忆；将整个项目无限上下文交给施工模型；两个 Agent 同时修改同一文件；一个 Agent 同时担任核心实现和该实现的独立评审；未经验收直接合并；未固定 base commit 就开始修改。每个新会话只接收：1. TASK_ID；2. 当前 base commit；3. 相关项目书章节；4. 任务输入文件；5. 接口契约；6. 文件 ownership；7. 禁止修改文件；8. 验收命令；9. 预期证据；10. 失败回退方式。

### 0.5 状态机

状态机：TODO → READY → RUNNING → SUCCESS / RETRYABLE_ERROR / FATAL_ERROR；只有 SUCCESS 的任务才允许合并；T001 如果触发竞争差异化 STOP，整个 AcceptTwin 施工流程立即停止。

补全回复取回的片段（状态机图开头、状态定义与强制转换规则完整）：

TODO
|
v
READY
|
v
RUNNING
|
+--> SUCCESS
|
+--> RETRYABLE_ERROR
|
+--> FATAL_ERROR
另有依赖阻断状态：BLOCKED | 前置任务全部 SUCCESS → READY
状态定义：TODO：尚未准备派发 / 等待输入；READY：输入、依赖和文件归属均已满足 / 可以创建新任务会话；RUNNING：Coding Agent 正在执行 / 等待交付；SUCCESS：任务验收通过 / 允许合并；RETRYABLE_ERROR：可定位、可修复的任务失败 / 保留日志后重新派发；FATAL_ERROR：当前任务存在无法自行解决的阻断 / 停止并提交 Owner 决策；BLOCKED：前置任务未通过或依赖不满足 / 禁止启动。
强制转换规则：1. TODO → READY：Muse 确认任务输入和依赖完整。2. READY → RUNNING：开启新的 Coding Agent 会话。3. RUNNING → SUCCESS：验收命令真实通过，证据完整。4. RUNNING → RETRYABLE_ERROR：发生可修复失败，保留失败证据。5. RETRYABLE_ERROR → READY：修复任务包准备完成，使用新会话重试。6. RUNNING → FATAL_ERROR：发生重大阻断，等待 Owner 决策。7. BLOCKED → READY：全部前置任务通过并完成交接。8. 只有 SUCCESS 的任务可以合并。9. 未验收的任务不得合并。10. T001 STOP 时，T002–T014 全部保持 BLOCKED。11. T007 S0 FAIL 时，T008–T014 全部保持 BLOCKED。12. 任何 P0/P1 未关闭时，T014 不得完成正式发布冻结。Muse 负责维护状态、调度和证据归档，不直接实施业务代码修改。

## §1 竞争差异化硬门

T001：

### 1.1 目的

这是项目 Day 1 的硬门，不是普通文献调查。立项前已经确认存在以下相关工具：Hurl、cache-tests、acceptmarkdown.com、readiness-audit、Cloudflare Agent Readiness；这些先例已经覆盖 HTTP 请求测试、缓存测试、Markdown 内容协商和 AI 网站 readiness 的部分或全部能力；因此必须实际测试 AcceptTwin 是否真的具有足够独立的价值。

### 1.2 必须对照的对象

A. Hurl（官方 https://hurl.dev/，文档 https://hurl.dev/docs/running-tests.html；测试内容：多请求串联、HTML 请求和 Markdown 请求、响应状态断言、Content-Type 断言、正文 Sentinel 断言、两种请求顺序、源站请求计数检查、缓存状态检查、错误位置报告）。B. cache-tests（GitHub https://github.com/http-tests/cache-tests；必须检查当前 HEAD commit、当前测试定义、请求/响应追踪、客户端与源站日志、是否能够按 Accept 建立不同表示、是否支持同一 URL 的双向请求序列、是否能验证缓存命中行为、是否能定位首次错误请求；不得仅凭 README 中没有某项功能，就认定其完全不支持；必须阅读其测试定义及必要的实现代码）。C. acceptmarkdown.com（https://acceptmarkdown.com/；必须检查 HTML/Markdown 请求、Vary: Accept、406、q-value、是否有缓存清空能力、是否有暖缓存请求顺序实验、是否能同时证明 HIT 和源站未被访问）。D. readiness-audit（GitHub https://github.com/geeks-accelerator/agent-and-search-readiness；必须检查 Markdown negotiation、本地 --base、相关缓存检查、结果归因、是否存在两种表示的暖缓存双向测试）。E. Cloudflare Agent Readiness（https://blog.cloudflare.com/agent-readiness/；检查其当前可用网站 readiness 检查能力，以及是否存在同等的冷暖缓存诊断）。

### 1.3 竞争等价判定合同

将以下 8 项定义为等价功能：EQ01 同一 URL 支持 HTML 与 Markdown 两种 Accept；EQ02 分别建立独立冷请求基线；EQ03 执行 HTML→Markdown 暖缓存顺序；EQ04 执行 Markdown→HTML 暖缓存顺序；EQ05 可以清空并证实缓存状态；EQ06 同时具备响应头和源站行为的 HIT/MISS 证据；EQ07 可以识别错误表示和首次错误请求；EQ08 能区分源站错误、缓存串版和证据不足。STOP 条件：如果任何一个现有专用工具能够：1. 自动完成 EQ01–EQ08；2. 不需要修改其业务代码；3. 最多使用两份简单配置文件；4. 从干净环境开始，10 分钟内完成；5. 自动输出可核验的错误归因；则 COMPETITIVE_GATE: STOP，ACCEPTTWIN_DEVELOPMENT: BLOCKED，停止后续开发任务；不能因为 AcceptTwin 已经完成项目书，就忽略竞争门；STOP 后：保存完整对照报告；保存工具版本、commit、配置和日志；不启动 T002–T014；向 Owner 提交 STOP 证据；ArgvLens 作为下一备选方向提交重新立项评估，不得未经确认直接把 AcceptTwin 源码目录改名为 ArgvLens。CONTINUE 条件：如果没有任何一个现有工具满足全部 EQ01–EQ08，则 COMPETITIVE_GATE: CONTINUE；必须说明哪些能力已有成熟先例、哪些能力需要配置组合才能完成、哪些能力需要手工补充、哪些能力仍是 AcceptTwin 的产品差异；不能把“工具没有一键按钮”当作唯一创新理由。

### 1.4 T001 执行步骤

1. 记录每个工具的版本或 commit；2. 阅读对应 README 与相关文档；3. 运行工具自带示例；4. 使用统一的 HTML/Markdown 合成源站；5. 分别尝试两种请求顺序；6. 检查是否可以重置缓存；7. 检查是否可以证明源站是否收到第二次请求；8. 检查是否能报告首次错误；9. 记录操作时间；10. 判断是否触发 STOP。T001 不允许通过编写 AcceptTwin 业务代码来帮助竞品测试。

### 1.5 T001 交付物

00_control/competitive_gate/，T001_COMPETITIVE_GATE.md，comparison_matrix.csv，decision.json（示例：{"task_id": "P032-T001", "decision": "CONTINUE", "equivalent_tools": [], "stop_triggered": false, "stop_condition": "A single existing dedicated tool completes EQ01-EQ08 automatically, without modifying its business code, with at most 2 simple config files, from a clean environment within 10 minutes, with automatic verifiable error attribution (IMPLEMENTATION_PLAN §1.3).", "evidence": {"spec_version": "1.0.0", "base_commit": "4d3021f", "started_at": "2026-11-24T12:57:10Z", "elapsed_minutes": 18, "budget_hours": 4, "eq_verdicts": {"EQ01": {"any_full": true, "full_tools": ["Hurl 7.0.0"]}, "EQ02": {"any_full": false, "full_tools": []}, "EQ03": {"any_full": false, "full_tools": []}, "EQ04": {"any_full": false, "full_tools": []}, "EQ05": {"any_full": false, "full_tools": []}, "EQ06": {"any_full": false, "full_tools": []}, "EQ07": {"any_full": false, "full_tools": []}, "EQ08": {"any_full": false, "full_tools": []}}, "closest_competitor": "Hurl 7.0.0: runs both warm orders, asserts headers/sentinels, pinpoints failing request; but has no cache control, no cold-baseline concept, no origin-counter delta arithmetic, short-circuits on failure (dual-evidence request never runs), and no verdict taxonomy.", "second_closest": "cache-tests HEAD 3942fbfe: DSL can express two-request sequences with cached/not_cached dual verification, but needs new test code (not config), has no cache reset, no cold baselines, no verdicts.", "hardest_gaps_vs_all_tools": ["Dual header+origin evidence still produced on the failure path (Hurl short-circuits; cache-tests only for its own server)", "Automatic 5-way verdict attribution distinguishing origin error vs cache bleed vs insufficient evidence (no tool has any verdict taxonomy)"], "not_verified": ["acceptmarkdown.com /api/readiness and /api/negotiate: 3 POST attempts timed out (HTTP 000, 30.0s each); approval prompt timed out unanswered; not retried", "readiness-audit live run: not executed; clone result raised an execution-risk check requiring user approval, which a subagent cannot obtain", "cache-tests suite run: not executed, same execution-risk reason; verdict based on reading the DSL/engine source", "Cloudflare Playground / isitagentready.com: not run live (login/zone required; public sites only)"], "deliverables": ["00_control/competitive_gate/T001_COMPETITIVE_GATE.md", "00_control/competitive_gate/comparison_matrix.csv", "00_control/competitive_gate/tool_versions.json", "00_control/competitive_gate/decision.json"]}}；该文件只是输出格式示例，不能预先写入 CONTINUE 冒充实际结果。（示例中的 spec_version 1.0.0 为 T001 门禁执行当时的历史规格版本——门禁文件 00_control/competitive_gate/decision.json 原文如此，按 ADR-009 不改历史记录；现行规格版本为 1.0.1，见文件顶部版本声明。）

### 1.6 T001 验收

五类竞争对象均已核查；Hurl 已真实运行；cache-tests 已阅读相关测试实现；AI readiness 工具已实际核查；统一对照表已完成；EQ01–EQ08 均有证据；时间预算有真实记录；STOP/CONTINUE 结论可复核；Muse 独立检查 T001 证据。

## §2 阶段门槛与工时预算

### 2.1 总预算

S0-A：T001，4h，退出条件竞争门 CONTINUE；S0-B：T002–T006，29h，退出条件契约、源站、缓存代理、执行器、分类器完成；S0-C：T007，5h，退出条件核心 24 Golden 全部通过；S1-A：T008–T009，10h，退出条件扩展 Golden 与 JSON 报告完成；S1-B：T010–T012，14h，退出条件 HTML、隐私、性能、离线完成；S1-C：T013–T014，10h，退出条件独立审查及最终冻结；有效施工 T001–T014，72h，全部完成；缓冲独立预留，16h，用于真实修复和复测；总计 88h。

### 2.2 阶段定义

S0 核心算法可行性（T001–T007）：必须证明产品具有竞争差异、真实本地 HTTP 请求能够执行、缓存能被独立清空、MISS/HIT/BYPASS 双证据可用、两种请求顺序真实执行、24/24 核心 Golden 通过、Oracle 24/24 一致、100 次重复哈希一致；S0 不通过不得启动 S1。S1 完整 MVP（T008–T014）：完成 48 Golden、独立 Oracle 最终对账、JSON Schema、JSON 报告、静态 HTML 报告、隐私与安全、性能、离线运行、许可证、发布包、独立代码审查。

## §3 任务依赖图

Mermaid 图表（页面显示节点）：T001 竞争差异化硬门 → T002 契约与 Schema → T003 合成源站 → T004 受控缓存代理 → T005 四实验执行器 → T006 生产分类器 → T007 S0 Golden + 独立 Oracle → T008 扩展 Golden → T009 JSON Schema + 报告 → T010 自包含 HTML → T011 隐私与安全 → T012 性能与离线 → T013 独立代码审查 → T014 修复与冻结。任何任务失败时，下游任务保持 BLOCKED；T001 STOP 时，图中后续任务全部取消。

## §4 工作区布局与文件归属

### 4.1 工作区根目录

工作区根目录 projects/P032-accepttwin/，包含 README.md、LICENSE、THIRD_PARTY_NOTICES.md、pyproject.toml 及以下目录：

```
projects/P032-accepttwin/
├── README.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── pyproject.toml
├── 00_control/
├── 01_project_book/
├── 02_implementation_plan/
├── 08_release/
├── contracts/
├── docs/
├── evidence/
├── fixtures/
├── oracle/
├── report-ui/
├── schemas/
├── scripts/
├── src/
└── tests/
```

### 4.2 文件所有权

pyproject.toml——T002；contracts/——T002；schemas/——T002、T009 分别按文件分配；src/accepttwin/contract.py——T002；src/accepttwin/url_guard.py——T002；src/accepttwin/origin_server.py——T003；src/accepttwin/cache_proxy.py——T004；src/accepttwin/cache_evidence.py——T004；src/accepttwin/experiment_runner.py——T005；src/accepttwin/classifier.py——T006；src/accepttwin/diagnostics.py——T006；oracle/——T007；fixtures/s0/——T007；fixtures/extended/——T008；src/accepttwin/report_builder.py——T009；report-ui/——T010；src/accepttwin/privacy.py——T011；tests/performance/——T012；docs/——按 T012/T014 子任务明确分配。同一文件在同一时间只允许一个任务修改。

### 4.3 Git 规则

main 仅接收已验收任务；每个任务有独立分支或 worktree；每张任务卡注明 base commit；先验收，后合并；合并后记录 commit；不允许直接在冻结提交上做未记录修改；每次冻结必须重新计算文件哈希；发布包必须从指定冻结 commit 构建。

## §5 接口契约

### 5.1 Contract

生产模块 src/accepttwin/contract.py；输入 accepttwin.contract/v1；主要接口：def load_contract(path: str) -> Contract；def validate_contract(contract: Contract) -> ValidationResult；def canonical_contract_hash(contract: Contract) -> str。要求：不自动修正用户输入；缺少必填字段时拒绝运行；不支持的字段不得静默忽略；URL 必须通过回环检查；Sentinel 不得重复；variant_by_accept 与 no_store 的字段组合必须合法。

### 5.2 URL Guard

（接口：def validate_loopback_url(url: str) -> ValidatedURL）：必须校验协议、校验 host、校验解析后的 IP、校验端口、拒绝非 loopback、拒绝 URL userinfo、禁止自动重定向、禁止使用环境代理。

### 5.3 Origin

（接口：class SyntheticOrigin，def start(self) -> None，def stop(self) -> None，def counter_snapshot(self) -> CounterSnapshot，def event_log(self) -> list[OriginEvent]）：源站只服务固定合成场景；不能根据自然语言或 LLM 推断表示。

### 5.4 Cache Proxy

（接口：class ControlledCacheProxy，def reset_cache(self, namespace: str) -> ResetEvidence，def cache_snapshot(self) -> CacheSnapshot，def start(self) -> None，def stop(self) -> None）：代理必须提供可验证的 MISS、HIT、BYPASS、Cache Key Hash、Entry ID、Cache Entry Count；代理内部缓存不能依赖真实 CDN。

### 5.5 Request Observation

（接口：@dataclass(frozen=True) class RequestObservation：request_index: int，experiment_id: str，requested_representation: str，response_status: int，response_content_type: str，body_sha256: str，sentinel_match: bool，cache_status: str，cache_key_sha256: str|None，cache_entry_id: str|None，origin_counter_before: int，origin_counter_after: int，origin_counter_delta: int）：原始响应正文不得存入该对象。

### 5.6 Production Classifier

（接口：def classify_run(contract: Contract, observations: list[RequestObservation], origin_events: list[OriginEvent], reset_evidence: list[ResetEvidence]) -> ClassificationResult）：不得使用文件名推测、预设最终答案、只看状态码、只看 Vary、只看 Age、只看 Sentinel；必须根据完整证据链判定。

### 5.7 Oracle

（TypeScript）：function evaluateScenario(input: OracleInput): OracleResult，其中 OracleInput 包含 format、contract、observations、raw_observations、origin_events、origin_events_available、resets；不得调用 Python 分类器。

### 5.8 Report

（接口：def build_report(contract: Contract, production_result: ClassificationResult, oracle_result: OracleResult) -> dict）：报告必须在 Oracle parity 通过后才能标记为最终有效报告。

## §6 T001–T014 原子任务卡

所有任务统一使用输入、输出、禁止修改、执行步骤、验收标准、命令、预期证据、完成定义、失败回退；每张卡对应全新模型会话。

### T001 — 竞争差异化硬门与环境盘点（4h）

目标：确定 AcceptTwin 是否存在足够独立的产品白空间，并完成实际开发环境探测。输入：PROJECT_BOOK.md §2、Hurl 官方文档、cache-tests 仓库、acceptmarkdown.com、readiness-audit 仓库、Cloudflare Agent Readiness 资料。输出：00_control/competitive_gate/，T001_COMPETITIVE_GATE.md，comparison_matrix.csv，tool_versions.json，commands.log，decision.json。禁止：编写 AcceptTwin 业务代码；修改项目书；跳过任意指定竞争对象；以搜索摘要代替运行和阅读；虚构工具能力。执行步骤：1. python --version；2. node --version；3. npm --version；4. git --version；5. 记录 OS、CPU、内存和可用磁盘；6. 获取竞争工具版本；7. 运行 Hurl 的顺序请求实验；8. 检查 cache-tests 的自定义测试能力；9. 实际运行 AI readiness 检查；10. 对照 EQ01–EQ08；11. 记录每项耗时；12. 作出 STOP/CONTINUE 决定。验收：五类对象全部有实际证据；EQ01–EQ08 全部逐项核查；配置文件数量和耗时有证据；STOP 条件严格执行。完成定义：仅在竞争门明确 CONTINUE 时，T001 才能 SUCCESS；STOP 是一个合法的任务结论，不允许通过改写评估标准强行通过。失败回退：缺少证据时保持 BLOCKED，最多补充一次定向检查，不允许自动宣布 CONTINUE。

### T002 — 双表示契约、Schema 与 URL Guard（5h）

目标：建立冻结契约的唯一代码实现。输入：PROJECT_BOOK.md §5、PROJECT_BOOK.md §14、T001 的 CONTINUE 证据、accepttwin.contract/v1 设计。输出：src/accepttwin/contract.py，src/accepttwin/schema.py，src/accepttwin/url_guard.py，src/accepttwin/request_headers.py，tests/unit/test_contract.py，tests/unit/test_url_guard.py。禁止：修改双表示字段定义；增加用户自定义敏感 Header；放宽公网地址检查；修改 Accept 值；让不合法字段静默通过。执行步骤：1. 定义 Python 类型；2. 实现 JSON 读取；3. 实现字段检查；4. 实现 Canonical JSON；5. 实现 URL 解析；6. 实现 loopback 校验；7. 实现固定请求头；8. 编写非法输入测试。验收命令：python -m pytest -q tests/unit/test_contract.py；python -m pytest -q tests/unit/test_url_guard.py。验收标准：合法契约通过；缺失字段拒绝；重复 Sentinel 拒绝；非回环地址拒绝；非 HTTP 拒绝；URL userinfo 拒绝；非法端口拒绝；请求头不在白名单时拒绝；契约哈希重复计算一致。完成定义：接口类型、测试、Schema 和示例契约全部通过。失败回退：不改变 PROJECT_BOOK 冻结语义；实现错误退回 T002 分支修复。

### T003 — 合成源站（5h）

目标：构建真正接收 HTTP GET 的本地 HTML/Markdown 合成源站。输入：T002 合并 commit、PROJECT_BOOK.md §5、PROJECT_BOOK.md §10。输出：src/accepttwin/origin_server.py，tests/integration/test_origin_server.py，fixtures/origin/。禁止：联网；HTML 自动转 Markdown；动态读取公网内容；依赖第三方网站；将正文写入默认日志。执行步骤：1. 启动本地 HTTP 服务；2. 注册合成场景；3. 实现 HTML 响应；4. 实现 Markdown 响应；5. 实现状态码故障夹具；6. 实现 Content-Type 故障夹具；7. 实现 Sentinel 故障夹具；8. 实现源站请求计数；9. 实现源站事件记录；10. 实现关闭与清理。验收命令：python -m pytest -q tests/integration/test_origin_server.py。验收标准：HTML Accept 返回 HTML；Markdown Accept 返回 Markdown；两种 Sentinel 不相同；源站状态码可控；源站 Content-Type 可控；请求计数准确；事件顺序准确；正文不写普通日志；关闭服务后端口释放。完成定义：通过全部源站测试，并提供真实 localhost HTTP 请求日志。失败回退：不修改 T002 契约；修复只限源站模块及其测试。

### T004 — 受控缓存代理与双重证据（7h）

目标：实现真正能够缓存、复用、清空和记录缓存状态的本地代理。输入：T003 合并 commit、PROJECT_BOOK.md §5.3、PROJECT_BOOK.md §5.4、PROJECT_BOOK.md §10.3。输出：src/accepttwin/cache_proxy.py，src/accepttwin/cache_evidence.py，tests/integration/test_cache_proxy.py。禁止：使用真实 CDN；仅凭 Age 判断 HIT；用响应头单独判断 MISS；用预设答案伪造源站计数；忽略 no-store；在缓存条目中保存用户真实数据。执行步骤：1. 实现缓存条目结构；2. 实现 URL 缓存键；3. 实现 Accept 维度缓存键；4. 实现 respect_vary；5. 实现 force_uri_only；6. 实现 manual_accept_key；7. 实现 disabled；8. 实现 opaque；9. 实现 ignore_no_store；10. 实现缓存重置；11. 实现缓存状态响应头；12. 实现源站行为计数关联；13. 实现双重证据校验。验收命令：python -m pytest -q tests/integration/test_cache_proxy.py；python -m pytest -q tests/unit/test_cache_evidence.py。验收标准：MISS：响应头 MISS + 源站计数 +1；HIT：响应头 HIT + 源站计数 0；BYPASS：响应头 BYPASS + 源站计数 +1；reset 后 entry_count=0；force_uri_only 可真实复现缓存串版；respect_vary 在 Vary: Accept 存在时区分表示；manual_accept_key 在无 Vary 时仍可正确区分；no-store 不得存储；证据冲突时输出 UNKNOWN。完成定义：双重证据单元测试与真实 HTTP 集成测试全部通过。失败回退：禁止降低双重证据要求；缓存代理不能可靠提供证据时，项目不得进入 T005。

### T005 — 四实验执行器（6h）

目标：严格按项目书 §6 执行全部四种实验。输入：T002–T004、PROJECT_BOOK.md §6、PROJECT_BOOK.md §7。输出：src/accepttwin/experiment_runner.py，src/accepttwin/evidence.py，tests/integration/test_experiment_runner.py。禁止：删除实验；调换规定的最终执行顺序；暖缓存实验中间清空缓存；改变 URL；为第二种表示生成另一条 URL；使用预设报告代替 HTTP 请求。执行步骤：1. 读取契约；2. 执行源站 HTML 基线；3. 执行源站 Markdown 基线；4. 清空缓存并执行 HTML 冷请求；5. 清空缓存并执行 Markdown 冷请求；6. 清空缓存并执行 HTML→Markdown；7. 清空缓存并执行 Markdown→HTML；8. 记录全部请求；9. 记录所有缓存状态；10. 生成原始观测文件。验收命令：python -m pytest -q tests/integration/test_experiment_runner.py。验收标准：每个场景必须有 O-H、O-M、H-COLD、M-COLD、H→M、M→H；两种暖缓存顺序各自必须包含两个实际请求；四个实验之间必须有复位记录；暖缓存实验的两个请求之间不得发生缓存复位。完成定义：至少一个健康场景和一个串版场景均能真实完成四种实验。失败回退：修复执行器，不得用简化实验代替完整实验。

### T006 — 生产分类器与首次错误定位（6h）

目标：实现五种裁决和九种冻结诊断代码。输入：T005 原始观测、PROJECT_BOOK.md §8、PROJECT_BOOK.md §9。输出：src/accepttwin/classifier.py，src/accepttwin/diagnostics.py，tests/unit/test_classifier.py，tests/unit/test_diagnostics.py。禁止：只根据 Vary 判断；只根据 200 判断；只根据 Sentinel 判断 HIT；缓存证据不完整时输出已证实串版；使用人工维护的固定场景结果代替分类算法。执行步骤：1. 实现响应契约比较；2. 实现源站基线错误判断；3. 实现缓存状态证据检查；4. 实现表示串版判定；5. 实现契约错误判定；6. 实现 INCONCLUSIVE；7. 实现 WARNING；8. 实现首次错误索引；9. 实现确定性诊断排序。验收命令：python -m pytest -q tests/unit/test_classifier.py；python -m pytest -q tests/unit/test_diagnostics.py。验收标准：五种 verdict 均可触发；九种 diagnostic 均有正向测试；每种诊断至少有一个负向测试；源站错误不误报缓存串版；缺少 Vary 的健康缓存不误报；HIT/MISS 证据冲突不误报串版；首次错误位置准确；多条诊断排序稳定。完成定义：分类器测试全部通过，且与项目书逐条对应。

### T007 — S0 核心 Golden、独立 Oracle 与硬门（5h）

唯一 S0 裁决任务。目标：完成 C01–C24 核心 Golden，并建立独立 TypeScript Oracle。输入：T002–T006、PROJECT_BOOK.md §11.2、PROJECT_BOOK.md §12、PROJECT_BOOK.md §13。输出：fixtures/s0/，oracle/，tests/golden/test_s0.py，scripts/run_s0.py，scripts/verify_s0.py，evidence/S0/（C01–C24 场景证据与 S0_SUMMARY.json），scripts/s0_harness.py。禁止：复用生产 Python 分类器；从生产最终 verdict 读取 Oracle 结果；删除失败 Golden；把 24/24 改为抽样；把两种暖缓存顺序合并为一种；仅用模拟函数代替 HTTP 请求；只检查最终状态，不检查请求序列。T007-A：24 条 Golden：实现 C01–C24；每个场景固定输入、固定缓存代理配置、完整四实验、预期 verdict、预期诊断、首错位置。T007-B：独立 Oracle：采用 TypeScript/Node.js 24.x；Oracle 必须独立读取原始观测、独立计算缓存证据、独立计算表示匹配、独立计算诊断、独立计算 verdict、独立计算首错位置；不得 import 生产实现。T007-C：S0 门禁：严格按 PROJECT_BOOK.md §13 执行；门禁验收逐条映射：24/24 场景——§11.2——C01–C24 全部实际执行；四种实验——§0.2、§6——四种实验全部完成；24/24 Oracle parity——§12——逐场景一致；已知故障全部检出——§8、§11.2——故障场景全部触发预期诊断；健康零误报——§7、§11.2——健康案例全部 PASS_OBSERVED；双向顺序——§6——HM、MH 均有真实请求记录；冷缓存——§5.4——清空、空状态和 MISS/BYPASS 双证据；暖缓存——§5.4——两次请求之间无 reset；缓存双证据——§5.3——响应头 + 源站行为；稳定串版——§8.2——至少一个案例独立清缓存后连续 3/3 复现；Vary 健康对照——§7.11——C03/C04 不误报；no-store 健康对照——§5.2、§11.2——C17/C18 正确通过；哈希重复性——§7.8、§10.4——100/100 同哈希；性能——§10.5——每场景小于 1 秒；首错定位——§6.3——请求序号准确；证据不足——§8.4、§8.8——C20–C23 不误报；报告规范化——§10.4——Canonical JSON 一致。这张映射表属于门禁定义本身，不得在执行脚本中遗漏任何一项。S0 通过标准：S0_CORE_GOLDEN: 24/24 PASS；S0_ORACLE_PARITY: 24/24 PASS；S0_FALSE_POSITIVE: 0；S0_KNOWN_FAILURE_DETECTED: 12/12；S0_STATUS: PASS（另须同时满足：C11 串版独立复现 3/3；repeat-100 唯一规范化报告哈希；单场景完整四实验小于 1 秒）。所有字段必须有实际日志支持。完成定义：只有上述所有门槛均真实通过，T007 才能标记 SUCCESS。失败回退：S0 FAIL 时：S0_STATUS: FAIL，T008–T014 BLOCKED；只允许针对真实失败原因修复；不得通过修改 Golden 预期值使错误实现通过。

### T008 — 扩展 Golden 与 48 场景集成（5h）

目标：补齐 E01–E24，并形成最终 48 场景集合。输入：T007 S0 PASS、PROJECT_BOOK.md §11.3。输出：fixtures/extended/，tests/golden/test_extended.py，tests/golden/test_all_48.py，evidence/Golden/。禁止：修改 S0 冻结夹具；降低已知故障覆盖；将 INCONCLUSIVE 当作 PASS；只运行扩展集而不重跑核心集。执行步骤：1. 编写 E01–E24；2. 加入 Vary 大小写测试；3. 加入 Vary 多字段测试；4. 加入 Vary:*；5. 加入 no-store 对照；6. 加入 no-cache 和 max-age=0 限制；7. 加入源站协商故障；8. 加入缓存证据故障；9. 加入响应大小限制；10. 加入重定向限制；11. 加入代理响应修改；12. 运行 48 场景全套；13. 对账独立 Oracle。验收命令：python -m pytest -q tests/golden/；python -m accepttwin verify --suite all。验收标准：48/48 实际执行；48/48 Oracle parity；每条实验请求序列完整；所有场景的最终裁决与 PROJECT_BOOK §11 一致；S0 24 条重新运行仍通过。

### T009 — JSON Schema、Canonical JSON 与报告生成（5h）

目标：完成正式机器报告和校验机制。输入：T007、T008、PROJECT_BOOK.md §14。输出：schemas/accepttwin.report.v1.schema.json，src/accepttwin/canonical_json.py，src/accepttwin/report_builder.py，tests/unit/test_report_builder.py，tests/unit/test_report_schema.py，evidence/Reports/（48 场景报告样本）。禁止：修改报告 Schema 版本；将原始正文加入报告；将敏感请求头加入报告；将临时端口和耗时加入规范化哈希；只依赖生产生成器自行验证自己。验收标准：Schema Draft 2020-12；顶层额外字段拒绝；五种 verdict 枚举正确；诊断级别正确；哈希格式正确；不存在正文原文字段；Canonical JSON 重复一致；48 个报告样本均可验证。

### T010 — 自包含 HTML 报告（6h）

目标：完成可视化报告界面。输入：T009 JSON 报告、PROJECT_BOOK.md §4、PROJECT_BOOK.md §14。输出：report-ui/src/，report-ui/index.html，report-ui/styles.css，scripts/embed_report.py，tests/integration/test_report_ui.py。禁止：引入远程 CDN；引入远程字体；使用在线图表服务；上传报告；自动打开外部网址；默认显示正文原文。界面必须包含：1. 最终裁决；2. HTML/Markdown 基线；3. 四种实验状态；4. 双向时间线；5. 缓存证据；6. 首次错误定位；7. 诊断代码；8. Oracle parity；9. 报告哈希；10. 隐私预览。验收标准：离线打开成功；无远程请求；自包含；正确显示五种 verdict；正确显示 48 场景汇总；不泄漏正文；HTML 导出与 JSON 报告内容一致。

### T011 — 隐私与本地安全回归（4h）

目标：验证所有隐私和网络边界。输入：T009、T010、PROJECT_BOOK.md §17。输出：src/accepttwin/privacy.py，tests/privacy/，evidence/Privacy/。禁止：真实用户数据；真实公网地址；真实认证信息；外部代理；外部网络访问；修改隐私要求以通过测试。验收场景：公网 IPv4 拒绝；公网 IPv6 拒绝；DNS 解析到非回环拒绝；重定向不跟随；非白名单请求头拒绝；Authorization 拒绝；Cookie 拒绝；超过正文大小拒绝；日志不包含正文；日志不包含敏感请求头；HTML 不访问远程资源；删除命令能清理指定文件；清理命令不能删除工作区之外的任意路径。验收命令：python -m pytest -q tests/privacy/。

### T012 — 性能、重复性、离线与文档（4h）

目标：完成最终运行环境和性能验证。输入：T007–T011、PROJECT_BOOK.md §18。输出：tests/performance/，docs/INSTALL.md，docs/USAGE.md，docs/LIMITATIONS.md，evidence/Performance/，evidence/S0/（S0 24 条重跑证据），evidence/Reports/（48 场景报告样本复核）。验收命令：python -m pytest -q；python -m accepttwin verify --suite all；python -m accepttwin benchmark --suite all。验收标准：48/48 Golden；48/48 Oracle parity；

• 单场景完整四实验运行时间小于 1 秒，使用真实本地 HTTP 请求，不允许通过跳过请求或读取缓存的历史结果伪造性能。
• 48/48 Golden 全部通过。
• 48/48 Oracle parity 全部一致。
• S0 核心 24 条重新运行仍全部通过。
• 100 次完整重复运行的规范化报告 SHA-256 完全一致。
• 重复运行必须重新执行真实实验，不能直接重复读取第一次运行的报告。
• Canonical JSON 不包含时间戳、临时目录、进程 ID、随机 UUID、动态端口和耗时等非确定性字段。
• 离线运行成功：关闭外部网络后，可以完成安装后运行、测试、报告生成及 HTML 导出。
• 产品运行时没有任何外部网络请求。
• npm run build 可以根据已冻结的依赖锁文件完成构建。
• Python 生产实现只使用冻结的 Python 3.12 环境及已批准依赖。
• HTML 报告完全自包含，没有远程 CSS、JavaScript、字体、图标、图片、iframe 或 CDN 请求。
• JSON 报告符合 accepttwin.report/v1 Schema。
• HTML 报告和 JSON 报告中的裁决、诊断及首次错误位置一致。
• 所有报告均不包含原始响应正文、Authorization、Cookie 或其他敏感请求头。
• 导出前隐私预览正常工作。
• README、INSTALL、USAGE、LIMITATIONS 中的命令与实际 CLI --help 输出一致。
• 实际未测试的操作系统和环境必须标记 NOT_TESTED，不得推断为通过。
• 测试日志包含真实执行命令、退出码、运行环境、时间及测试结果。

完成定义：1. 全部 48 条 Golden 通过。2. Oracle parity 为 48/48。3. 单场景完整实验耗时满足小于 1 秒的要求。4. 100 次重复运行产生唯一规范化报告哈希。5. 离线运行验证通过。6. HTML 自包含验证通过。7. JSON Schema 验证通过。8. 隐私检查通过。9. 安装、使用和限制文档齐备。10. 所有日志和测试证据已归档。T012 完成后，项目进入独立代码审查准备状态。

失败回退：• 性能不达标：定位具体请求或计算阶段，不允许减少四种实验。• 重复哈希不一致：检查动态字段、诊断排序和规范化逻辑，不允许忽略不同裁决。• 离线运行失败：定位外部资源或运行时依赖，不允许把在线资源加入白名单后声称离线通过。• 隐私检查失败：返回 T011 修复，不得以文档免责声明替代实际修复。• JSON/HTML 不一致：返回 T009 或 T010 修复。• Golden 或 Oracle 失败：返回 T007/T008 对应任务修复。• 保留失败日志、原始输入、运行环境及失败 commit，不覆盖历史证据。

注：补全回复另给出验收命令：Bash：python -m pytest -q；python -m accepttwin verify --suite all；npm run oracle:parity；python -m accepttwin benchmark --suite all。

### T013 — 独立代码审查（4h）

目标：由独立 Reviewer 对 AcceptTwin 的完整实现进行只读审查。重点不是检查代码能否运行，而是确认：生产实现是否真实符合 PROJECT_BOOK.md v1.0.1，是否存在假 PASS、缓存错误漏检、证据不足却强行归因、S0 门禁缩窄规格等问题。T013 是 S1-C 的第一部分，计划工时 4 小时。

输入：1. PROJECT_BOOK.md v1.0.1。2. IMPLEMENTATION_PLAN.md v1.0.1。3. T001–T012 全部已验收任务的交接记录。4. 当前冻结候选 Git commit。5. 完整生产源码。6. 独立 Oracle 全部源码。7. 48 条 Golden 夹具。8. Python 测试日志。9. Oracle parity 日志。10. S0 门禁日志。11. Repeat-100 日志。12. 性能日志。13. 隐私与离线验证日志。14. JSON 报告样本。15. HTML 报告样本。16. 依赖锁文件。17. LICENSE 与第三方许可证清单。18. SHA-256 文件清单。

输出：evidence/Review/，含 REVIEW_INDEX.md、REVIEW_PACK_01.md、REVIEW_PACK_02.md、SOURCE_FILE_MANIFEST.md、REVIEW_PACK_03.md、FINDINGS.json、INDEPENDENT_REVIEW.md。

禁止：• 修改生产源码。• 修改 Oracle。• 修改 Golden 预期值。• 修改项目书或实施计划以掩盖实现偏差。• 删除失败测试。• 仅凭 README、测试摘要或开发者自评给出 PASS。• 使用生产分类器计算 Oracle 结果。• 仅审查部分核心文件后宣称完成全部审查。• 使用未核对哈希的源码副本。• 执行公网访问。• 在审查过程中使用真实用户数据。Reviewer 必须只读工作区。需要执行测试时使用独立工作树或临时副本。

执行步骤：

#### T013-A：

核对审查对象身份：1. 读取当前 Git commit。2. 检查工作区状态。3. 读取源码文件清单。4. 核对文件 SHA-256。5. 核对源码包与冻结候选 commit 的对应关系。6. 检查是否有未登记的修改文件。

#### T013-B：

需求覆盖审查：逐项检查 PROJECT_BOOK.md：§0 项目定义和冻结决定；§1 用户与痛点；§2 外部证据与竞争边界；§3 目标和非目标；§4 用户流程与 UI；§5 双表示契约；§6 四种实验；§7 一致性不变量；§8 诊断代码；§9 最终裁决；§10 算法；§11 Golden；§12 独立 Oracle；§13 S0 门禁；§14 JSON 和接口；§15 系统架构；§16 技术栈；§17 隐私安全；§18 验收指标；§19 最终交付物；§20 外部参考资料；§21 规格冻结声明。每项记录：规格要求、实现文件、实际实现位置、验证命令、真实验证结果、审查结论。不得只根据函数名称推断功能已经实现。

#### T013-C：

核心算法审查：重点检查：1. 源站 HTML 和 Markdown 是否分别真实请求。2. 是否执行两种独立冷请求。3. HTML→Markdown 是否真实执行。4. Markdown→HTML 是否真实执行。5. 两种暖缓存实验中间是否错误地清空缓存。6. 是否使用相同 URL。7. 缓存清空是否有实际确认。8. MISS 是否有响应头与源站计数双证据。9. HIT 是否有响应头、源站计数和缓存条目关联证据。10. BYPASS 是否有响应头和源站行为证据。11. 缺少 Vary 是否被错误地直接判为串版。12. 源站错误是否被正确优先归类。13. 证据矛盾是否导致 INCONCLUSIVE。14. 首次错误请求是否准确定位。15. 五种裁决的优先级是否符合规格。

#### T013-D：

Oracle 独立性审查：检查：TypeScript Oracle 是否有独立判定逻辑；是否 import Python 生产模块；是否调用生产分类函数；是否把生产最终 verdict 作为 Oracle 输入；是否自行计算 MISS/HIT/BYPASS；是否自行计算 Sentinel 匹配；是否自行计算五种最终裁决；是否逐场景比较原始观测；是否存在生产与 Oracle 共用同一判定实现的问题。必须对 48 条场景分别核验，不允许只比较总数。

#### T013-E：

S0 门禁覆盖审查：逐项对照 PROJECT_BOOK.md §13。重点核验：24/24 核心案例；24/24 Oracle parity；已知故障全部检出；健康场景零误报；两种请求顺序真实执行；独立冷缓存；双重缓存证据；稳定串版复现；缺少 Vary 的健康对照；Repeat-100；单场景性能；首次错误定位；证据不足场景；Canonical JSON。检查 S0 实际脚本是否存在比项目书更窄的判断条件。发现任何缩窄，至少登记 P1；如果会造成核心错误漏检或假 PASS，登记 P0。

#### T013-F：

隐私、安全与发布审查：检查：Loopback Guard；DNS 解析结果验证；重定向禁止；环境代理隔离；敏感请求头拒绝；正文不写日志；正文不进入报告；文件删除边界；HTML 无远程资源；依赖许可证；MIT LICENSE；锁文件完整性；报告 Schema；SHA-256 清单。

#### T013-G：

生成独立审查包：将核心源码和配置按文件路径、SHA-256、完整内容分批写入：REVIEW_PACK_01.md、REVIEW_PACK_02.md。如果两个包仍无法容纳全部需要审查的源码，可以增加后续编号，不得删减关键实现文件。

验收命令：只读工作区或独立工作树内执行：Bash：git status --short；git rev-parse HEAD；python -m pytest -q；python -m accepttwin verify --suite all；npm run oracle:parity。Reviewer 还必须逐项阅读并核对：src/accepttwin/cache_proxy.py、src/accepttwin/cache_evidence.py、src/accepttwin/experiment_runner.py、src/accepttwin/classifier.py、src/accepttwin/diagnostics.py、src/accepttwin/contract.py、src/accepttwin/url_guard.py、src/accepttwin/origin_server.py、src/accepttwin/canonical_json.py、src/accepttwin/report_builder.py、oracle/src/oracle.ts、oracle/src/evidence.ts、oracle/src/input.ts、oracle/src/index.ts、scripts/verify_s0.py、scripts/s0_harness.py、scripts/run_s0.py。实际文件名以冻结源码树为准；如果路径不同，必须在 REVIEW_INDEX.md 中提供实际路径映射。

验收标准：• 所有权威需求都有文件级映射。• 核心生产文件已实际阅读。• Oracle 核心文件已实际阅读。• 缓存代理与证据核验逻辑已实际阅读。• S0 脚本和门禁映射已实际核对。• 48 条 Golden 全部有覆盖记录。• 48/48 Oracle parity 有实际日志。• 没有用生产结果冒充 Oracle 独立结果。• 没有发现未记录的核心源码修改。• 所有发现都有文件路径、行号、复现命令及证据。• 每项 P0/P1/P2 都有明确分类。• REVIEW_INDEX.md 与实际审查包文件一致。• 审查包内源码哈希与冻结源码一致。• 没有通过文字修改掩盖代码缺陷。

完成定义：T013 的完成定义是：1. 独立审查范围覆盖完成。2. REVIEW_INDEX.md 已生成。3. 全部审查包已生成。4. INDEPENDENT_REVIEW.md 已给出结论。5. FINDINGS.json 已生成。6. 每项发现均有复现或明确证据依据。7. Muse 已核对审查包完整性。T013 的 SUCCESS 表示独立审查工作已经完成，不表示项目一定没有缺陷。如果发现 P0/P1，T014 必须先处理，不能直接冻结发布。

失败回退：• Reviewer 无法访问完整源码：保持 BLOCKED，要求补充源码包。• 哈希不一致：停止审查并核对冻结对象。• Oracle 依赖生产实现：登记 P0，返回 T007 修复。• S0 门禁缩窄规格：登记 P0/P1，返回 T007 修复。• 缓存证据不完整：登记 P0，返回 T004/T005 修复。• 分类器错误：返回 T006 修复。• JSON Schema 与实际输出不一致：返回 T009 修复。• HTML 远程依赖：返回 T010 修复。• 隐私或公网访问问题：返回 T011 修复。• 发现 P2：保留发现和影响说明，由 T014 判断是否在本次修复。任何失败都必须保留原始审查报告，不能覆盖历史记录。

### T014 — 修复、最终门禁与 Release Freeze（6h + 可用缓冲）

目标：处理 T013 独立审查发现的问题，重新执行完整验收，冻结唯一发布版本，生成源码包、哈希清单、发布清单及 Google Drive 归档证据。T014 是 S1-C 的第二部分。有效施工预算为 6 小时。额外 16 小时缓冲由整个项目共同使用，不是预先默认可以延长任务的工时。T014 不是简单打 ZIP。它必须证明最终发布包就是已经审查、已经测试的源码。

输入：1. T013 独立审查报告。2. FINDINGS.json。3. REVIEW_INDEX.md。4. 全部 REVIEW_PACK_XX.md。5. 当前冻结候选 commit。6. 48 条 Golden。7. 独立 Oracle。8. 完整测试日志。9. 性能和隐私证据。10. JSON/HTML 样本。11. 依赖锁文件。12. MIT LICENSE。13. SHA-256 文件清单。

输出：08_release/，含 README.md、LICENSE、THIRD_PARTY_NOTICES.md、RELEASE_NOTES.md、HOW_TO_REPRODUCE.md、RELEASE_MANIFEST.json、SHA256SUMS.txt、source.zip。Google Drive 归档位置：agent project auto/ 下 P032-accepttwin/，含 00_control/、01_project_book/、02_implementation_plan/、08_release/、contracts/、docs/、evidence/、fixtures/、oracle/、report-ui/、schemas/、scripts/、src/、tests/。

禁止：• 覆盖 T013 历史审查包。• 删除历史失败日志。• 修改 Golden 预期值以掩盖缺陷。• 未经 ADR 修改 PROJECT_BOOK。• 未经 ADR 修改 IMPLEMENTATION_PLAN。• 仅修改 README 就宣布 P0/P1 关闭。• 把没有运行的测试写成 PASS。• 把未测试的平台写成已支持。• 用文件名、大小代替 SHA-256。• 在冻结后继续修改源码而不重新冻结。• 直接把施工 Agent 的自评作为最终验收。• 在 ChatGPT 最终 PASS 前将项目登记为 ACCEPTED。

执行步骤：

#### T014-A：

审查问题分类与修复计划：1. 读取全部独立审查发现。2. 将问题分为 P0、P1、P2。3. 确认每个问题对应的源码文件、规格章节和复现证据。4. 为每个修复建立独立 TASK_ID。5. 修复任务必须使用新的模型会话。6. 修复构建者与复审者尽可能使用不同模型。7. 记录修复前 commit。8. 不允许在同一个工作树中并发修改相同文件。

#### T014-B：

执行修复：每个修复任务必须提供：原问题 ID、原始复现命令、原始失败结果、修复文件、修复原因、回归测试、修复后结果、新 commit、文件哈希。修复必须首先证明原失败场景已经关闭。随后运行受影响模块的全部相关测试。

#### T014-C：

修复后独立复核：由非原构建者重新检查：P0/P1 是否真正关闭；回归测试是否覆盖原故障；是否产生新的副作用；规格是否与实现一致；是否修改了其他已通过区域。没有独立复核证据的修复不得标记 CLOSED。

#### T014-D：

完整门禁重跑：在干净工作树或干净 clone 中执行：Bash：python -m pytest -q；python -m accepttwin verify --suite s0；python -m accepttwin verify --suite all；npm run oracle:parity。随后检查：S0 24/24；最终 Golden 48/48；Oracle 48/48；健康场景零误报；已知故障全部检出；两种暖缓存顺序均真实执行；至少一个串版案例独立清空后连续 3/3 复现；单场景小于 1 秒；100 次重复结果相同；隐私检查通过；离线检查通过；JSON Schema 通过；HTML 自包含；MIT 与第三方许可证清单正确。

#### T014-E：

源码冻结：1. 确认所有 P0/P1 已关闭。2. 记录仍存在的 P2。3. 记录最终 Git commit。4. 检查 Git 工作区。5. 确认没有未登记的修改。6. 生成最终文件清单。7. 为每个交付文件计算 SHA-256。8. 创建最终 release tag。9. 将该 commit 作为唯一冻结源码身份。冻结后任何源码修改都必须产生新的 commit，并重新执行受影响的门禁及发布冻结流程。

#### T014-F：

构建发布包：从冻结 commit 构建 source.zip。发布包必须包含：全部必要生产源码；独立 Oracle 源码；全部 Schema；全部 48 条 Golden；测试代码；README；项目书；实施计划；依赖声明与锁文件；MIT LICENSE；第三方许可证说明；安装与复现说明。不得包含：.venv；node_modules；临时缓存；临时 HTTP 日志；个人密钥；用户真实数据；未经批准的本地环境文件；无法解释来源的二进制文件。

#### T014-G：

发布身份与哈希核对：必须计算：1. 每个源码文件 SHA-256。2. 每个 Golden 文件 SHA-256。3. Oracle 文件 SHA-256。4. Schema 文件 SHA-256。5. JSON 报告样本 SHA-256。6. HTML 报告样本 SHA-256。7. source.zip SHA-256。8. RELEASE_MANIFEST.json SHA-256。9. 最终 Git commit。RELEASE_MANIFEST.json 至少包含：JSON 开头 {"project_id":"P032","project_name":"AcceptTwin","spec_version":"1.0.1","release_status": "READY_FOR_FINAL_REVIEW"}。正式清单必须使用实际值替换示例值。其中 tests_status 不能在尚未完成门禁时预先写为 PASS。为避免自指哈希问题：source.zip 从冻结 Git commit 的指定文件集合构建；RELEASE_MANIFEST.json 在 ZIP 构建后生成；SHA256SUMS.txt 独立保存；发布清单及其哈希不要求被自身包含在 source.zip 内；必须明确清单所引用的源码 commit 和 ZIP 哈希。

#### T014-H：

独立解包验证：在新的临时目录中：1. 解压 source.zip。2. 检查文件数量。3. 逐文件核对 SHA-256。4. 检查项目文件结构。5. 检查依赖锁文件。6. 检查许可证。7. 检查 README 和运行命令。8. 从解包内容重建环境。9. 执行核心测试。10. 核对生成结果与冻结版本一致。不得只在原工作目录运行后宣布发布包可用。

#### T014-I：

Google Drive 归档：按冻结目录结构归档：四份规格文件；最终源码 ZIP；源码文件清单；48 条 Golden；Oracle；测试日志；Repeat-100 日志；性能日志；隐私与离线日志；UI 截图；Review Index；Review Packs；独立审查报告；最终发布清单；SHA-256 清单；Git commit 记录。归档完成后，Muse 必须重新读取关键文件并核对：文件存在；文件大小正确；SHA-256 正确；发布清单与实际 ZIP 一致；审查包与冻结源码一致。只看见 Drive 文件名不等于已经核对正文或文件内容。

验收命令：Bash：git rev-parse HEAD；git status --short；python -m pytest -q；python -m accepttwin verify --suite s0；python -m accepttwin verify --suite all；npm run oracle:parity；python -m accepttwin benchmark --suite all。哈希核对：Linux：Bash：sha256sum -c SHA256SUMS.txt。Windows PowerShell：powershell：Get-FileHash .\source.zip -Algorithm SHA256。解包验证：Bash：python -m zipfile -t source.zip。实际解包后必须重新执行必要的测试命令。

验收标准：• T013 发现的 P0/P1 全部关闭。• 每项修复都有独立回归证据。• P2 均已记录，注明影响和是否延期。• 全部 48 条 Golden 通过。• Oracle parity 48/48。• S0 门禁重新通过。• Repeat-100 唯一规范化哈希。• 单场景性能满足要求。• 隐私检查通过。• 离线检查通过。• JSON Schema 验证通过。• HTML 报告自包含。• LICENSE 为 MIT。• 第三方许可证清单完整。• 源码 ZIP 能独立解包。• SHA256SUMS 全部通过。• 发布清单与最终源码 commit 一致。• Git 工作区干净。• Drive 发布目录中的文件与本地发布清单一致。• REVIEW_INDEX 与 REVIEW_PACK 覆盖范围一致。• 所有实际执行日志均已归档。

完成定义：T014 成功后，项目状态只能标记：IMPLEMENTATION_STATUS: COMPLETE；RELEASE_STATUS: READY_FOR_FINAL_REVIEW；FINAL_GPT_REVIEW: PENDING；ACCEPTED: PENDING。T014 SUCCESS 表示施工与发布证据已准备完成，不代表 GPT 最终终审已经 PASS。必须向 GPT 提交：1. 项目书。2. 实施计划。3. 最终源码包。4. 最终 Git commit。5. RELEASE_MANIFEST。6. SHA256SUMS。7. REVIEW_INDEX。8. REVIEW_PACK。9. 完整测试日志。10. S0 日志。11. Oracle parity。12. Repeat-100。13. 性能日志。14. 隐私与离线证据。15. UI 演示截图。16. 许可证审查。17. Drive 归档位置。只有 ChatGPT 在本立项对话中独立给出最终 PASS，P032 才能正式标记 ACCEPTED。

失败回退：• P0 未关闭：不冻结，重新派发独立修复任务。• P1 未关闭：不冻结，重新派发独立修复任务。• P2 未解决：保留并登记，不得隐瞒；判断是否阻断核心要求。• Golden 失败：返回对应 T007/T008。• Oracle parity 失败：返回 T007。• S0 失败：按 §13 处理，禁止以最终 48 条的平均成绩掩盖。• 性能失败：返回 T012，不能减少实验请求。• 隐私失败：返回 T011。• Schema/HTML 失败：返回 T009/T010。• SHA-256 不一致：重新构建并检查冻结 commit。• ZIP 解包失败：重新构建发布包。• Drive 归档不一致：重新上传并下载核对。• 任何冻结后的源码修改：生成新的冻结 commit，并重新执行完整相关门禁。所有历史版本必须保留，不得覆盖之前的审查记录。
