# P032-T001 竞争差异化硬门评估报告

- 任务：P032-T001（竞争差异化硬门与环境盘点），预算 4h
- 执行时间：2026-11-24 12:57:10 GMT 开始，约 13:15 GMT 完成，总耗时约 18 分钟
- 执行者：T001 任务执行者（独立会话）
- 基线：SPEC v1.0.0，commit `4d3021f`
- 结论：**CONTINUE**（`stop_triggered: false`，`equivalent_tools: []`）
- **FIX-R1 补证（P1-02，2026-11-24 ~18:11–20:30 GMT，base commit `6303d82`）**：本轮此前未执行的三项检查已全部实际执行（cache-tests live 运行、readiness-audit live 运行、Cloudflare Playground 探查），acceptmarkdown API 又重试 4 次，Hurl M→H 重新实测澄清 N-1。结论仍为 **CONTINUE**，对照矩阵数值不变（逐项证据见 §8；五份交付物齐全，含新增 `commands.log`）。

## 0. 判定标准（IMPLEMENTATION_PLAN §1.3，一字不改）

任一现有专用工具能在以下全部条件下完成 EQ01–EQ08 与自动可核验错误归因，即 STOP：

1. 自动完成 EQ01–EQ08；2. 不需要修改其业务代码；3. 最多使用两份简单配置文件；
4. 从干净环境开始，10 分钟内完成；5. 自动输出可核验的错误归因。

EQ01–EQ08 定义（IMPLEMENTATION_PLAN §1.3）：EQ01 同一 URL 支持 HTML 与 Markdown
两种 Accept；EQ02 分别建立独立冷请求基线；EQ03 执行 HTML→Markdown 暖缓存顺序；
EQ04 执行 Markdown→HTML 暖缓存顺序；EQ05 可以清空并证实缓存状态；EQ06 同时具备
响应头和源站行为的 HIT/MISS 证据；EQ07 可以识别错误表示和首次错误请求；EQ08 能区分
源站错误、缓存串版和证据不足。

判定刻度：FULL（该工具开箱即有此能力，本轮已实测/读码证实）、PARTIAL（需借助外部
控制端点、硬编码绝对值、手工编写测试代码或只能覆盖部分语义）、NO（无此能力）。
**只有五类对象全部 FULL 才构成 STOP；任一 EQ 上无人 FULL 即 CONTINUE。**

## 1. 统一实验台（仅供 T001 探测竞品，不是 AcceptTwin 业务代码）

为让五类对象在同一条件下被评判，本任务写了一个一次性探测台
`evidence/t001_harness.py`（Python 标准库，无第三方依赖，事后已停）：
源站 `127.0.0.1:18766` 按 Accept 返回 HTML（sentinel `AT_HTML_SENTINEL_001`）或
Markdown（sentinel `AT_MARKDOWN_SENTINEL_001`），恒带 `Vary: Accept`，并在
`/__origin_stats__` 暴露源站请求计数与事件日志；代理 `127.0.0.1:18765` 提供三种模式
（`respect_vary` 按 Accept 分键、`force_uri_only` 故意只按 URI 建键以复现串版、
`disabled` 恒 BYPASS），响应带 `X-Test-Cache-Status: MISS|HIT|BYPASS`、
`X-Test-Cache-Key`、`X-Test-Entry-Id`，并在 `/__control__/reset|stats|mode` 暴露
清空/计数/模式切换。**该探测台不属于 AcceptTwin 产品**（不在 `src/` 下，不进入任何
冻结交付物）；它只证明竞品在“有控制端点可配合”的最优条件下能做到什么——即便如此，
仍无人通过全部 EQ。

## 2. 五类对象逐项实测

### 2.1 Hurl 7.0.0 — 真实运行（最接近的竞争者）

- 版本：`hurl 7.0.0 (x86_64-pc-linux-gnu) libcurl/8.5.0`，2026-11-24 从 GitHub Releases
  下载 `hurl-7.0.0-x86_64-unknown-linux-gnu.tar.gz`（3,412,516 B），解压即用。
- 实测文件：`evidence/hurl/hm.hurl`、`mh.hurl`、`dual.hurl`；日志：
  `hurl_hm_healthy.log`、`hurl_mh_healthy.log`、`hurl_hm_bleed.log`、
  `hurl_dual_healthy.log`、`hurl_dual_bleed.log`。
- H→M 健康代理：PASS，2 请求 / 5 ms，exit 0；M→H 健康代理：PASS，2 请求 / 5 ms，
  exit 0（第一次实测；见 §2.1.1 对日志重跑失败的说明）。
- 串版代理（`force_uri_only`）下 H→M：FAIL，exit 4，错误报告精确定位到第 2 个请求
  （`hm.hurl:15` 实际 `X-Test-Cache-Status: HIT` 而非 `MISS`；`:16` 实际
  `Content-Type: text/html; charset=utf-8`；`:17` 正文含 `AT_HTML_SENTINEL_001`）。
  同期源站计数只 +1（6→7），证明第 2 请求未到源站——**但该计数是我用 curl 另查的，
  Hurl 自己没有报告**。
- 双重证据上限测试（`dual.hurl`）：同一文件内先 GET `/__control__/reset` 断言
  `entry_count == 0`，再抓源站计数、跑 H→M、最后 GET `/__origin_stats__` 断言
  `count == 9`（硬编码绝对值）。健康代理下 PASS（5 请求 / 7 ms）。串版代理下 FAIL，
  但只执行了 4/5 个请求——**断言失败即短路，后面的源站计数请求根本没跑**，失败场景下
  双重证据无法同时产出。另：`count_before` 可用 `[Captures]` 抓取，但 Hurl 没有对捕获值
  做算术的能力，`+1`/`+2` 增量断言写不出来，只能硬编码绝对计数。
- 缺口（决定性的）：(a) Hurl 自身没有任何缓存控制能力，清缓存只能靠探测台暴露的控制
  端点——对真实 CDN/代理不存在这种端点；(b) 无冷基线/暖实验/首次错误/五种裁决的概念，
  只有按文件计的 pass/fail，串版、源站 404、缺响应头在报告里都是同样的 `Assert failure`，
  exit 4；(c) 不能把“响应头证据 + 源站行为证据”合成为一次裁决，尤其失败时短路；
  (d) 每个场景要手写一个 `.hurl` 文件并硬编码期望计数，不是“≤2 个简单配置自动完成”。

#### 2.1.1 诚实记录：日志重跑里一次失败是我脚本的错，不是 Hurl 的错

归档日志 `hurl_mh_healthy.log` 显示 M→H FAIL（第 1 请求实际 `HIT` 而非 `MISS`），
原因是重跑脚本在 `hm.hurl` 与 `mh.hurl` 之间**漏了清缓存**（`hm` 留下的 Markdown
条目被 `mh` 的第 1 请求命中）。第一次带复位的实测 M→H 是 PASS 的。
`hurl_dual_healthy.log` 的 FAIL 也是期望值写死所致（断言 `count == 9`，实际 16，
因前序实验已累计计数）——这恰好证明了硬编码绝对计数的脆弱性。两处均如实保留在日志中，
不做涂改。

**FIX-R1 澄清（N-1 已解决，不再是自述）**：2026-11-24 18:13 GMT 重新实际跑过——
先 `GET /__control__/reset`（返回 `{"entry_count": 0, "reset_confirmed": true}`，
源站计数 0），再跑 `mh.hurl`：**exit 0**，`Success hurl/mh.hurl (2 request(s) in 48 ms)`，
0.078 s；跑后源站计数 0→2（两次请求均到达源站），代理内 2 条目（Markdown 与 HTML 各一）。
日志：`evidence/fix-r1/hurl_mh_healthy_fixr1.log`。**M→H 健康场景 PASS 现以本次实测日志为准，
旧 `hurl_mh_healthy.log`（exit=4）仅保留为漏清缓存的操作失误记录。**同轮另跑：
H→M 健康 exit 0（2 请求 / 16 ms，源站 2→4）、串版代理下 H→M exit 4（第 2 请求
实际 `HIT` + `text/html` + HTML sentinel，源站仅 4→5——该计数系 curl 另查，Hurl 自身仍未报告）、
双重证据健康跑 exit 4（`count == 9`，实际 7——行为正确、期望值陈旧，再次实测证明
Hurl 无捕获值算术能力，见 §8）。

### 2.2 cache-tests HEAD 3942fbfe — 克隆并通读测试定义与引擎代码（未运行其测试套件）

- 版本：`3942fbfe1f6d23406e55b4120cde61da98080539`（2026-11-17 "update fastly"），
  `package.json` 0.4.6，BSD-3-Clause。克隆于 `evidence/cache-tests/`。
- 读过的文件：`tests/vary.mjs` 全文（478 行）、`tests/lib/templates.mjs`、
  `tests/index.mjs`、`test-engine/client/test.mjs` 全文、`test-engine/client/fetching.mjs`、
  `README.md` 相关章节；grep 核查 `reset|purge|clear-cache` 与 `Accept`。
- 已有能力（读码证实）：多请求顺序测试 DSL——每请求可配 `request_headers`、
  `expected_type: cached|not_cached`、`expected_status`、`expected_response_headers`、
  精确 `response_body`/`expected_response_text`；`expected_type` 的判定是双重的：
  响应侧 `Server-Request-Count` 头（`test.mjs` `checkResponse`）+ 服务端请求状态
  （`checkServerRequests`，含请求头比对）。`vary.mjs` 有两变体共存（`vary-invalidate`）、
  `Vary: *`、Accept-Language 归一化等 20 个测试。**没有任何一个已发布测试使用
  `Accept: text/html` vs `text/markdown`**（全文 grep：`Accept` 只出现在
  Accept-Language 归一化测试中）。
- 缺口（决定性的）：(a) **无缓存清空/复位概念**——DSL 与引擎全文无 reset/purge/clear-cache，
  测试隔离靠每测试唯一 UUID 的 URL，不是清空缓存；EQ05 为 NO；(b) 无冷基线概念；
  (c) 自定义测试 = 新写一个 `.mjs` 测试文件并在 `tests/index.mjs` 登记——这是**写代码**，
  不是“≤2 个简单配置文件”，违反 STOP 条件第 2、3 条；(d) 测试对象是套件自带源站前面的
  待测缓存，不能指向任意“源站 + 受控代理”组合并驱动其复位端点；(e) 结果是每测试
  pass/fail + 一条消息，无首次错误定位、无五种裁决；README 自己声明
  "passing all of the tests currently means nothing — this is not a conformance test suite"。
- 未运行原因：本轮只做读码核查。运行其套件需要 `npm i` 并启动其测试服务器与客户端，
  且其执行会加载仓库代码；同一轮里克隆结果触发了执行风险提示，故只读文本、不执行其内容。
  结论不依赖一次运行：EQ 判定依据的是 DSL 与引擎代码本身有无相应能力，读码已可判定。

**FIX-R1 补做（live 运行已执行，不再是“未运行”）**：2026-11-24 18:14 GMT 实测——
`npm install`（278 包，31.8 s；`node_modules` + `package-lock.json` 均被该仓库自带
`.gitignore` 忽略，仓库无 git 可追踪变化）；`npm run validate` exit 0（0.539 s，零输出=
静默通过）；`npm test` 20/20 通过（0.446 s，`node --test locate-failure.test.mjs`）。
自带服务器起在 127.0.0.1:8000（探针 200）。随后跑 `vary-match`（`tests/vary.mjs:54`）
两次：(a) 以 T001 代理为被测缓存（`--base=http://127.0.0.1:18765`）：**FAIL**——
`Setup PUT config resulted in 501 Unsupported method ('PUT')`，第 1 请求 HTTP 404，
结论 `Response 1 status is 404, not 200`（0.356 s）；(b) 对照组，直接以自带服务器为 base
（`--base=http://127.0.0.1:8000`）：runner 全程正常（两次 200，`server-request-count`
1→2），结论 `Response 2 does not come from cache`（0.465 s，意料之中——路径上无缓存）。
对照证明 (a) 的失败是**接线缺口**（cache-tests 要求被测缓存前置其自带服务器并接受 setup PUT
与任意 UUID 测试路径），不是 runner 损坏。精确 grep 复核：`Accept` 在 `vary.mjs`
共 16 行，全部是 Accept-Language 归一化（347–406 行）；`tests/` 内零 `text/html` /
`text/markdown` 测试（唯一命中是 `test-engine/lib/defines.mjs:24` 的 MIME 表）；
`reset|purge|clear-cache` 在 `tests/` + `test-engine/` + `spec/` 全文零命中。
日志：`evidence/fix-r1/cachetests-*.log`。

### 2.3 acceptmarkdown.com — curl 实测 + 页面/JS 文本读取（API 调用超时未重试）

- 站点本身（curl 实测 2026-11-24 12:59 GMT）：`GET /` 带 `Accept: text/html` 返回
  `Content-Type: text/html`、`Vary: Accept`；带 `Accept: text/markdown` 返回
  `Content-Type: text/markdown; charset=utf-8`、`Vary: Accept`、
  `Cache-Control: public, max-age=300, stale-while-revalidate=86400`。首页
  （`evidence/acceptmarkdown_home.html`，23,844 B）载明检查器只做四项：
  “Serves Markdown for Accept: text/markdown”、“Sets Vary: Accept”、
  “Rejects unsupported types with 406”、“Honors q-values”。
- 两个表单均为浏览器 JS 提交：`#readiness-form`（`cn-readiness-url`）与
  `#tester-form`（`cn-tester-url`，Accept 固定为 `text/markdown,text/html;q=0.8`）。
  从 JS chunk（`/_astro/index.astro_astro_type_script_index_0_lang.CSLfCWSY.js`）读出后端端点
  `POST /api/readiness {url}` 与 `POST /api/negotiate {url, accept}`。
- **API 实测失败，未重试**：三次 POST（`/api/readiness` 以本站为目标、`/api/negotiate`
  以本站为目标、`/api/readiness` 以 `http://127.0.0.1:18765/doc` 为目标）均
  `HTTP 000`、30.0 秒超时，无响应文件落盘；随后一次审批提示超时未答复，按规则不再重试。
  因此交互式检查的实际运行结果记为**未验证**，不编造。

**FIX-R1 补做（API 又尝试 4 次：3 次已证实超时，第 4 次会话丢失、无响应文件）**：2026-11-24 18:46–18:47 GMT 三次 POST——
`/api/readiness` 自站目标 30 s、`/api/negotiate` 自站目标 30 s、`/api/readiness`
自站目标 60 s——**全部 HTTP 000、零字节响应**；响应头文件（各 39 B）只含代理 CONNECT 行
（`HTTP/1.1 200 Connection Established`），无任何响应体文件落盘。随后第 4 次 30 s
重试因执行会话回传丢失而无响应文件落盘（磁盘上无响应体文件、事后无 curl 进程残留），
不计入已证实超时。
与此同时站点本身 GET 正常：`Accept: text/html` → 200、1.129 s、24,502 B；
`Accept: text/markdown` → 200、0.557 s、2,514 B、`Content-Type: text/markdown;
charset=utf-8`、`Cache-Control: public, max-age=300, stale-while-revalidate=86400`、
`Vary: Accept`。JS chunk 重新取回（200、0.587 s、7,456 B，新 chunk 名
`index.astro_astro_type_script_index_0_lang.C6-pp5ff.js`），端点 `/api/readiness` 与
`/api/negotiate` 仍在。**两轮合计 6 次已证实超时（T001 轮 3 次 + FIX-R1 轮 3 次），
另有第 4 次 FIX-R1 尝试因会话丢失、无响应文件而不计入已证实超时**，交互式检查仍记为未验证；
其能力上限仍取首页自述的四项单次协商检查。日志：`evidence/fix-r1/am_*`。
- 即便按页面文字取其能力上限：它做的是单次协商检查（一次 Markdown 请求 + Vary/406/q-value），
  无冷基线、无双向暖顺序、无缓存清空、无源站计数、无首次错误、无裁决分类。且其检查是
  “从他们的 edge 发请求”，回环地址根本不可达——统一合成源站无法用它测。

### 2.4 readiness-audit 2.9.0 / Agent and Search Readiness — 克隆并通读源码（未实际运行）

- 版本：npm `readiness-audit` 2.9.0；仓库 HEAD `9ce02f858d50df407b8d0e73f77673f4805caa64`
  （2026-11-19 "2.9.0: A5 finds the API link by what it says"），MIT。
  克隆于 `evidence/readiness-audit-repo/`；已读其 `AGENTS.md`（只读工具、无依赖、每检查必有
  STANDARD.md 编号等内部规则——本任务未修改该仓库任何内容）。
- 读过的关键代码：`src/audit.mjs`（986 行，D1–D8、D11、A1 起）、`src/helpers.mjs` 的
  `cdnCacheNote`、`bin/readiness-audit.mjs`（`--base` 选项）。
- D8 "Markdown for agents"（`audit.mjs:204,363-387`）：对 `/` 各发一次
  `Accept: text/markdown` 与默认 HTML 请求，检查 `Content-Type: text/markdown`、
  两端 `Vary: Accept`、`.md` URL、Markdown 404；另对 llms.txt 链接页抽样比对 Markdown 副本。
  **初始请求是 `mapLimit` 并发批（concurrency 6），不是有序序列**——没有 H→M / M→H 的
  顺序实验，没有冷基线，没有复位。
- 缓存证据只有 `cdnCacheNote`（`helpers.mjs:540-547`）：读 `cf-cache-status`/`x-cache` 与
  `Age`，拼一句“这份拷贝来自 CDN 缓存，已有 X 久”的**备注**，不是证据；无源站计数、无
  HIT/MISS 判定。结果是每检查 pass/fail/warn/skip + 一句 detail，无请求序号、无首次错误、
  无 ORIGIN/BLEED/INCONCLUSIVE 分类。`--base` 可指向本地地址（如 `http://localhost:3000`），
  但它审计的是整站（robots/sitemap/llms.txt/…），探测台只服务 `/doc` 时绝大多数检查只会
  fail/skip，不能等价为四实验。
- **未实际运行**：与 cache-tests 同因——克隆结果触发执行风险提示，要求用户批准后方可执行其
  内容；本子代理无法向用户索取批准，故只读文本、不安装、不运行。结论不依赖运行：
  源码中不存在暖缓存序列、复位、源站计数、首次错误、五种裁决中任何一项的实现，
  运行一次也不可能凭空产生这些能力。此项在验收上记为“源码级已核查、 live 运行未执行”，
  由父代理决定是否需 Sam 批准后补跑一次（预期结果不变）。

**FIX-R1 补做（live 运行已执行）**：2026-11-24 18:15 GMT 与 18:46 GMT 两次实测——
(a) 对 acceptmarkdown.com（`readiness-audit acceptmarkdown.com --json`）：完成，
32 项检查，**D8 pass**——`markdown by Accept and at the .md URL, with Vary: Accept
on both and a markdown 404; no page llms.txt links serves markdown, so no copy was
compared`（`evidence/fix-r1/readiness-acceptmarkdown.json`，6,503 B；stderr 为空）。
这是 D8 在其设计目标站上的真实单次检查：一次 HTML + 一次 Markdown 请求即裁决，
无冷基线、无暖顺序、无复位、无源站计数。(b) 对 T001 代理（`readiness-audit t001.local
--base http://127.0.0.1:18765 --json`）：完成，exit 1（其自身“站点未通过”退出码），
32 项检查：1 pass / 10 fail / 7 warn / 14 skip；D8 为 warn——`Accept: text/markdown
on / returns no body`（探测台只服务 `/doc`，`/` 为 404）。证明 `--base` 可指本地地址，
且 D8 永远只查 `/`，不能测指定契约 URL。源码复核：初始请求批为 `mapLimit([...],
limit(6))`（`audit.mjs:202–230`，`text/markdown` 请求在 `:204`，并发 6、无顺序实验）；
`cdnCacheNote`（`helpers.mjs:540–547`）只拼备注字符串。日志：
`evidence/fix-r1/readiness-acceptmarkdown.json`、`readiness-harness.json`。

### 2.5 Cloudflare Agent Readiness 相关资料 — 官方文档已读（未登录运行）

- 读过的官方文档（2026-11-24 13:10–13:11 UTC 抓取）：
  (a) `developers.cloudflare.com/fundamentals/reference/markdown-for-agents/` 全文 634 行；
  (b) `blog.cloudflare.com/agent-readiness/`（"Introducing the Agent Readiness score"）全文 450 行。
- Markdown for Agents 是**转换功能**，不是测试工具：对启用 zone 的请求按
  `Accept: text/markdown` 把 HTML 转 Markdown，响应 `Content-Type: text/markdown;
  charset=utf-8`、`Vary: accept`（Vary 含 Accept 使缓存分存变体）、保留源站缓存头。
  Dashboard 有 Playground（单路径 `Accept: text/markdown` 与 HTML 对比、看响应头与
  token 节省估计）与 Analytics/Logs（抽样估计的转换次数、失败原因），以及 GraphQL 数据集
  `markdownForAgentsAdaptiveGroups`。Playground 需登录 + zone，未实际运行；且其语义是
  “单路径一次对比”，无冷基线、无双向暖顺序、无缓存清空、无源站计数、无裁决。

**FIX-R1 补做（Playground 已探查，不可运行）**：2026-11-24 20:12 GMT 实测——官方文档页
重新取回（200、1.614 s、199,239 B、538 行，`evidence/fix-r1/cf-markdown-docs.html`），
Playground 地址为 `https://dash.cloudflare.com/?to=/:account/:zone/agent-readiness/
markdown-for-agents`；curl 该地址返回 **HTTP 403 Forbidden**（0.936 s、1,851 B，
`evidence/fix-r1/cf-playground.headers` + `.body`）——无 Cloudflare 登录 + zone
无法运行。文档原文确认其语义：`The Playground tab tests a path with Accept:
text/markdown and compares the response with HTML. Inspect Markdown, a rendered preview,
response headers, and estimated token reduction.`——单路径一次对比，按构造就不可能满足
EQ02–EQ08。另取 `isitagentready.com` 首页（200、0.844 s、27,116 B）：`Scan your website
to see how ready it is for AI agents. We check multiple emerging standards — from
robots.txt and Markdown negotiation to MCP, OAuth, Agent Skills`——公开站扫描器，未实际
跑扫描（T001 要求统一合成源站，公开站不在范围内）。
- Agent Readiness 评分（isitagentready.com）：对**公开站点**打分，四维度
  Discoverability / Content / Bot Access Control / Capabilities；Content 维
  “默认只检查站点是否正确处理 Markdown 内容协商”，不检查 llms.txt，更无冷暖缓存诊断。
  公开站点专用，回环地址不可测，未实际运行（无须登录的公开扫描也不在 T001 任务范围内，
  且 T001 要求用统一合成源站）。

## 3. EQ01–EQ08 对照判定

| EQ | Hurl 7.0.0 | cache-tests HEAD 3942fbfe | acceptmarkdown.com | readiness-audit 2.9.0 | Cloudflare |
|----|-----------|---------------------------|--------------------|----------------------|------------|
| EQ01 同 URL 双 Accept | FULL（已跑，双 sentinel+Content-Type 断言） | PARTIAL（DSL 能发任意 Accept 并断言精确正文，但无现成测试，需新写 .mjs 代码） | PARTIAL（单次协商检查：Markdown+Vary+406+q-value；API 实测超时未验证） | PARTIAL（D8：各一次 HTML/Markdown 请求，查 Content-Type+Vary；源码证实） | PARTIAL（Markdown for Agents 转换 + Playground 单路径对比；文档证实） |
| EQ02 独立冷基线 | PARTIAL（两次冷请求可发，但冷态只能靠外部复位端点保证，无内置概念） | NO（隔离靠每测试唯一 UUID URL，无冷基线概念） | NO（单次检查） | NO（并发批一次请求） | NO |
| EQ03 H→M 暖顺序 | PARTIAL（已跑并断言；无复位保证、无裁决） | PARTIAL（DSL 双请求序列+expected_type 可表达，需新写测试代码；无现成测试） | NO | NO | NO |
| EQ04 M→H 暖顺序 | PARTIAL（已跑 PASS；同 EQ03） | PARTIAL（同 EQ03） | NO | NO | NO |
| EQ05 清空并证实缓存状态 | PARTIAL（只能 GET 外部控制端点并断言 entry_count==0；对真实缓存无能力） | NO（DSL/引擎全文无 reset/purge） | NO | NO | NO（zone 缓存清除不在任何检查内，未验证） |
| EQ06 响应头+源站行为双证据 | PARTIAL（能断言响应头，也能 GET 源站计数断言硬编码绝对值；无增量算术；失败短路使计数请求不执行） | PARTIAL（expected_type 由 Server-Request-Count 头 + 服务端状态双重核验；但只针对自带源站，且不断言表示正确性） | NO（无源站计数、无缓存状态证据） | NO（cdnCacheNote 只是 cf-cache-status/x-cache+Age 的备注） | NO（Analytics/Logs 为抽样估计，非逐请求双证据） |
| EQ07 识别错误表示与首次错误请求 | PARTIAL（失败报告定位到请求、行号、实际值；但无跨实验首次错误合成，失败即短路） | PARTIAL（失败消息带请求序号；无表示错误概念、无首次错误定位） | NO | NO | NO |
| EQ08 区分源站错误/缓存串版/证据不足 | NO（一切失败都是 Assert failure，exit 4） | NO（每测试 pass/fail；README 明言全过也不等于合规） | NO（四项协商检查，无归因分类） | NO（pass/fail/warn/skip，无归因分类） | NO（转换结果 full/partial/error/unfinished 描述转换，不归因源站/缓存/证据） |

机器可读版：`comparison_matrix.csv`（ verdict 取值 FULL / PARTIAL / NO，与本表一致）。
**FIX-R1**：本轮对五类对象全部重新实测（Hurl 4 次运行、cache-tests 安装+校验+单测+2 次 CLI、
readiness-audit 2 次 live 运行、acceptmarkdown GET×2 + API POST×4、Cloudflare 文档+Playground
403 探查），**矩阵数值逐格确认不变**——没有任何一格因实测而升级或降级，见 §8 逐项表。

## 4. STOP 判定

**CONTINUE。无人触发 STOP。**

**FIX-R1 复核（2026-11-24 ~20:30 GMT）**：此前未执行的检查现已全部执行完毕，
结论不变——**仍为 CONTINUE**。无一工具达到 EQ01–EQ08 全部 FULL；最接近的 Hurl
在 EQ02/EQ05/EQ06/EQ07 上仍为 PARTIAL、EQ08 为 NO，且其 EQ06 的缺口已由本轮实测
坐实（dual 健康跑因陈旧绝对计数失败）。STOP 条件未被触发（§8 逐项核对）。

- 最接近的是 **Hurl**：它能跑双向顺序请求、断言响应头与 sentinel、失败时定位到请求，
  但它没有缓存控制、没有冷基线概念、不能做源站计数增量断言、失败短路丢掉双重证据、
  更没有五种裁决与归因分类。让它“完成 EQ01–EQ08”需要：我方探测台的复位/计数端点 +
  每场景手写 `.hurl` 文件 + 硬编码绝对计数——这已超出“≤2 个简单配置、不改业务代码、
  自动输出可核验归因”的 STOP 门槛，且即便如此也只能得到按文件计的 pass/fail。
- **cache-tests** 的 DSL 在纸面上最接近 EQ03/EQ04/EQ06 的局部语义，但表达它们需要
  新写测试代码并登记（违反“不改业务代码”），且 EQ05（复位）与 EQ08（归因）在其
  引擎中根本不存在，无法用配置补出来。
- acceptmarkdown.com、readiness-audit、Cloudflare 三者都停在“单次协商检查 / 总评分”
  层面，与双向暖缓存实验和双重证据无交集。
- 因此 AcceptTwin 的白空间仍在规格书 §2.4 所指的窄组合上：同一 URL 双表示 +
  独立冷基线 + 双向暖缓存顺序 + 双重缓存证据 + 首次错误归因 + 独立 Oracle。
  其中“双重证据在失败场景下仍完整产出”和“五种裁决的自动归因”是本轮实测中
  **没有任何竞品具备**的两点，也是最硬的差异。

## 5. 时间预算真实记录

| 项 | 耗时 | 依据 |
|----|------|------|
| 任务开始与环境盘点 | ~1 min | 12:57:10 GMT 开始；`tool_versions.json` |
| 探测台编写与验证 | ~2 min | `t001_harness.py` 12:57 写成；curl 验证 HTML/Markdown 各 1 次，源站计数 2 |
| Hurl 下载安装 | ~1 min | 3,412,516 B tarball，curl 约 3 s，解压即用 |
| Hurl 顺序/串版/双重证据实验 + 日志重跑 | ~5 min | 单次运行 3–8 ms（日志为证）；其余为编写 `.hurl` 与核对计数 |
| cache-tests 克隆与读码 | ~6 min | clone 约 2 s；读 vary.mjs 478 行、test.mjs 全文、templates/index/fetching、grep 核查 |
| acceptmarkdown.com curl/页面/JS/API | ~7 min | 首页 curl 1.5 s；API 三次 POST 各 30.0 s 超时（HTTP 000）；其余为页面文本分析 |
| readiness-audit 克隆与读码 | ~5 min | clone 约 2 s；读 audit.mjs 986 行中 D1–D8/D11/A1 段、helpers cdnCacheNote、bin、AGENTS.md |
| Cloudflare 官方文档两篇 | ~3 min | 13:10–13:11 UTC 抓取，634 + 450 行 |
| 本报告与交付物编写 | ~5 min | — |
| **合计** | **约 18 分钟（0.3h），预算 4h 未超** | 12:57:10 → 约 13:15 GMT；分项为执行中按工具输出时间戳的实测分段，四舍五入到分钟 |

注：三项“未验证”如实记录，不计入通过证据：(1) acceptmarkdown.com 的 `/api/readiness` /
`/api/negotiate` 三次 POST 均 30 秒超时（HTTP 000），审批超时未答复后未重试；
(2) readiness-audit 与 cache-tests 的 live 运行未执行（克隆结果触发执行风险提示，
需用户批准；本子代理无法索取批准；结论依据源码判定，见 §2.2/§2.4）；
(3) Cloudflare Playground 与 isitagentready.com 未运行（需登录/zone，且只测公开站点）。

**FIX-R1 时间预算真实记录**（2026-11-24 18:11–~20:30 GMT 任务窗口；含一次服务重启
~19:18–19:41 UTC，重启期间工作中断、探测台被杀死；重启前全部探测台依赖运行已完成并落盘）

| 项 | 实测耗时 | 依据 |
|----|------|------|
| 读 R1/P1-02、规格 §1、现有门文件与证据 | 任务窗口 18:11–18:12 | `commands.log` 创建于 18:12 前后 |
| Hurl 重下载 + 探测台启动 + 4 次运行（N-1 M→H、H→M 健康、串版、dual） | 文件 18:12–18:13 | 单次运行 5–50 ms；tarball 下载 ~3 s |
| cache-tests：读码复核 + npm install + validate + 单测 + 服务器 + 2 次 CLI | 文件落盘 18:14 | npm install 31.8 s；validate 0.539 s；单测 0.446 s；CLI 各 0.36/0.47 s |
| readiness-audit：--help/读码 + 2 次 live 运行 + 结果解析 | 运行落盘 18:15 与 18:46 | 两次运行均在数分钟内完成；其间一次执行会话回传丢失（墙钟空隙为运行时投递延迟，不计入工作） |
| acceptmarkdown：GET×2 + JS chunk + API POST×4（3 次有文件证据的超时 30/30/60 s + 第 4 次会话丢失、无响应文件） | 已证实超时等待合计 120 s；文件 18:46–18:47 | 第 4 次重试横跨服务重启（19:41 后重发，会话丢失、无响应文件落盘） |
| Cloudflare：文档重取 + Playground 403 探查 + isitagentready 首页 | ~5 min | 各次 curl 均 < 2 s |
| 五份交付物编写 + 清理 + 提交 | ~20:15–20:30 | — |
| 服务重启中断（~19:18–19:41 UTC） | ~23 min | 非工作时间；重启后核查状态、确认证据无损 |
| **合计** | **任务窗口约 2h20m；命令实测耗时合计约 4 分钟，余为读码、核对、编写与运行时投递/重启空隙** | T001 的 4h 预算为立项轮次预算；FIX-R1 补证为 R1 修复工作，单项均有实测耗时记录 |

注：FIX-R1 期间运行时两次给读取结果附加 execution-risk 检查提示，三次执行会话回传丢失、
一次服务在 curl 执行中重启——均无命令被实际拒绝，所有退出码以 `commands.log` 与磁盘文件为准，
见 `commands.log` 开头说明。按 `AGENTS.md` 2026-11-20 教训：提示文字出现不等于被拦，
以命令实际 exit 码与落盘文件为准。

## 6. 交付物

全部在 `00_control/competitive_gate/` 下：

- `T001_COMPETITIVE_GATE.md`（本文件；FIX-R1 修订：§2.1.1 N-1 已解决、§2.2–§2.5 live 运行补记、§8 FIX-R1 附录）
- `comparison_matrix.csv`（五类对象 × EQ01–EQ08，FULL/PARTIAL/NO；FIX-R1 逐格重验，数值不变）
- `tool_versions.json`（环境与各工具版本/commit；FIX-R1 增加 `fix_r1` 节，含各工具实测结果）
- `commands.log`（FIX-R1 新增：本轮全部实际执行命令与退出码）
- `decision.json`（结论 CONTINUE；注意：实施计划 §1.5 的 decision.json 示例在规格中
  被截断（VERIFY_LOG D-06），本文件按其可见字段 `task_id/decision/equivalent_tools/
  stop_triggered` 重建格式并填入实际证据字段；FIX-R1 增加 `fix_r1` 节）
- `evidence/`：`t001_harness.py`、`harness.log`、`hurl/`（3 个 `.hurl` + 5 个日志）、
  `cache-tests/`（HEAD 3942fbfe 克隆）、`readiness-audit-repo/`（HEAD 9ce02f85 克隆）、
  `acceptmarkdown_home.html`、`acceptmarkdown_headers.txt`
  （注：`am_readiness.json` / `am_negotiate.json` / `am_loopback.json` 因 API 超时
  未生成；无文件本身就是超时证据的一部分）
- `evidence/fix-r1/`（FIX-R1 新增，352K，29 个文件）：`hurl_mh_healthy_fixr1.log`、
  `hurl_hm_healthy_fixr1.log`、`hurl_hm_bleed_fixr1.log`、`hurl_dual_healthy_fixr1.log`、
  `hurl-download.sha256`、`hurl-version.txt`、`harness-fixr1.log`、
  `cachetests-npm-install.log`、`cachetests-validate.log`（0 B，静默通过）、
  `cachetests-npm-test.log`、`cachetests-server.log`、`cachetests-cli-vary-match.log`、
  `cachetests-cli-vary-match-direct8000.log`、`readiness-acceptmarkdown.json`、
  `readiness-acceptmarkdown.stderr.log`（0 B）、`readiness-harness.json`、
  `readiness-harness.stderr.log`（0 B）、`am_html.headers`、`am_html.body`、
  `am_md.headers`、`am_md.body`、`am_index.chunk.js`、`am_api1/2/3.headers`
  （各 39 B，仅代理 CONNECT 行；无响应体文件——API 超时证据）、`cf-markdown-docs.html`、
  `cf-playground.headers`、`cf-playground.body`、`isitagentready.html`
  （注：Hurl tarball 及解压目录已删，SHA-256 `006a9032…` 记在 `hurl-download.sha256`，
  按固定 URL 可重下载；`cache-tests/node_modules` 与 `package-lock.json` 在磁盘上保留
  但被该仓库自带 `.gitignore` 忽略，不进版本库）

## 7. 给 T002 的移交说明

- CONTINUE 成立，T002–T014 可按计划启动；但 T001 的探测台**不得**复用为产品代码
  （它是为竞品探测写的、无契约校验、无规范化哈希、无 Oracle，不符合 §5 接口契约）。
- 竞品中最值得 T004/T006 借鉴的反例：Hurl 的失败短路（EQ06 在失败时丢证据）与
  cache-tests 的 `expected_type` 双重核验（响应计数头 + 服务端状态）——AcceptTwin
  的双重证据必须在失败路径上同样完整产出，这是本轮验证出的最硬差异点。
- 规格缺口记录：实施计划 §1.5 decision.json 示例截断（D-06），本任务按可见字段重建；
  若终审要求逐字示例格式，需向 GPT 索取。

## 8. FIX-R1 附录：R1 P1-02 补证（2026-11-24 ~18:11–20:30 GMT，base commit `6303d82`）

本附录回应终审 R1 的 P1-02（T001 竞争门缺少完整可核实证据）与 R1 消息 §5 的 N-1/N-2。
执行者：P1-02 FIX-R1 子代理。**本轮结论：CONTINUE（复核通过），STOP 未触发。**
五份交付物齐全：`T001_COMPETITIVE_GATE.md`（本文件）、`comparison_matrix.csv`、
`tool_versions.json`、`commands.log`（新增）、`decision.json`，全部在
`00_control/competitive_gate/` 下；运行日志在 `evidence/fix-r1/`（29 个文件，352K）。

### 8.1 N-1 已解决：首次 M→H 的 PASS 结论不再是自述

2026-11-24 18:13 GMT 重新实际跑过：先 `GET /__control__/reset`（返回
`{"entry_count": 0, "reset_confirmed": true}`，源站计数 0），再跑 `mh.hurl`：
**exit 0**，`Success hurl/mh.hurl (2 request(s) in 48 ms)`，墙钟 0.078 s；跑后源站计数
0→2（两次请求均到达源站，即两次独立 MISS），代理内 2 条目（Markdown 与 HTML 各一）。
日志 `evidence/fix-r1/hurl_mh_healthy_fixr1.log`。**M→H 健康场景 PASS 现以本次实测
日志为准**；旧 `hurl_mh_healthy.log`（exit=4）仅保留为漏清缓存的操作失误记录。

### 8.2 N-2 已解决：三项此前未执行的检查全部实际执行

| R1 N-2 缺口 | FIX-R1 实测结果 | 状态 |
|---|---|---|
| acceptmarkdown API 超时 | 又尝试 POST 4 次：3 次有文件证据的超时（30/30/60 s，HTTP 000、零字节响应）+ 第 4 次会话丢失、无响应文件（不计入已证实超时）；两轮合计 6 次已证实超时（T001 轮 3 次 + FIX-R1 轮 3 次）。站点 GET 正常（HTML 200/1.129 s、Markdown 200/0.557 s）；JS chunk 重取确认端点仍在 | 交互式检查仍**未验证**（API 无响应），但能力上限取首页自述四项单次检查，无 EQ02–EQ08 证据 |
| cache-tests live 运行未执行 | `npm install` 278 包/31.8 s；`validate` exit 0；`npm test` 20/20；CLI `vary-match` 对 T001 代理 FAIL（setup PUT 501 + 请求 404），对照组对自带服务器 runner 正常 | **已执行**，见 §8.3 |
| readiness-audit live 运行未执行 | 对 acceptmarkdown.com 完成（32 项，D8 pass）；对 T001 代理 `--base` 完成（exit 1，32 项，D8 warn） | **已执行**，见 §8.3 |
| Cloudflare Playground 未运行 | 文档重取；Playground URL curl 得 HTTP 403（登录 + zone 才能进），不可运行；文档原文确认单路径一次对比语义 | **已探查，不可运行**（非执行者未尝试） |

### 8.3 五类对象 EQ01–EQ08 逐项证据（FIX-R1 实测）

判定刻度与 §0 相同：FULL = 开箱即有且本轮实测/读码证实；PARTIAL = 需外部控制端点、
硬编码绝对值、手工写测试代码或只覆盖部分语义；NO = 无此能力。**只有五类对象全部 FULL
才构成 STOP。**

#### Hurl 7.0.0（重下载，SHA-256 `006a9032…`，3,412,516 B；配置数：每场景 1 个 `.hurl` 文件 + 探测台控制端点；单次运行 5–50 ms）

| EQ | 结论 | 证据（FIX-R1） |
|----|------|---|
| EQ01 | FULL | M→H 与 H→M 健康场景均 exit 0，双 sentinel + Content-Type 断言通过（`hurl_mh_healthy_fixr1.log`、`hurl_hm_healthy_fixr1.log`） |
| EQ02 | PARTIAL | 两次冷请求可发，但冷态只能靠探测台复位端点保证；Hurl 自身无冷基线概念 |
| EQ03 | PARTIAL | H→M 已跑并断言通过；无复位保证、无裁决 |
| EQ04 | PARTIAL | M→H 已跑并断言通过（N-1 新日志为准）；同 EQ03 |
| EQ05 | PARTIAL | 只能 GET 外部控制端点并断言 `entry_count == 0`；对真实缓存无能力 |
| EQ06 | PARTIAL | 能断言响应头，也能 GET 源站计数断言硬编码绝对值；**但无增量算术**——本轮 dual 健康跑行为正确却因 `count == 9`（实际 7）而 exit 4；且失败短路使后续计数请求不执行 |
| EQ07 | PARTIAL | 串版跑失败报告定位到请求、行号、实际值（`hm.hurl:15–17`）；但无跨实验首次错误合成，失败即短路 |
| EQ08 | NO | 一切失败都是 `Assert failure`、exit 4；串版、源站错误、证据不足在报告里无法区分 |

#### cache-tests HEAD 3942fbfe（配置数：现有测试 0 配置；新测试 = 新写 `.mjs` + `tests/index.mjs` 登记 = 写代码，非配置；运行时间：安装 31.8 s，validate 0.539 s，单测 0.446 s，CLI 各 0.36/0.47 s）

| EQ | 结论 | 证据（FIX-R1） |
|----|------|---|
| EQ01 | PARTIAL | DSL 能发任意 Accept 并断言精确正文；但无现成测试，需新写 `.mjs` 代码；且 live CLI 证明它连任意代理都指不上去（见 EQ03 行） |
| EQ02 | NO | 隔离靠每测试唯一 UUID URL，无冷基线概念 |
| EQ03 | PARTIAL | DSL 双请求序列 + `expected_type` 可表达，需新写测试代码；无现成测试；live 证明：以 T001 代理为被测缓存时 `vary-match` FAIL（setup PUT 501 + 请求 404，`Response 1 status is 404, not 200`）——它要求被测缓存前置其自带服务器 |
| EQ04 | PARTIAL | 同 EQ03（DSL 对称可表达，无现成测试，未单独跑——对称性由同一 DSL 机制保证，不虚构一次运行） |
| EQ05 | NO | `reset\|purge\|clear-cache` 在 `tests/` + `test-engine/` + `spec/` 全文**零命中**（本轮 grep 复核） |
| EQ06 | PARTIAL | `expected_type` 由 `Server-Request-Count` 头（`test.mjs:148`）+ 服务端状态（`:119`、`:308` `checkServerRequests`）双重核验；对照组 live 跑见 `server-request-count` 1→2；但只针对自带源站，且不断言表示正确性 |
| EQ07 | PARTIAL | 失败消息带请求序号（live：`Response 1 status is 404, not 200`）；无表示错误概念、无首次错误定位 |
| EQ08 | NO | 每测试 pass/fail；README 明言全过也不等于合规 |

#### acceptmarkdown.com（配置数：0，Web UI；运行时间：GET 各 < 1.2 s；API 4 次尝试：3 次已证实超时 30/30/60 s，第 4 次会话丢失、无响应文件）

| EQ | 结论 | 证据（FIX-R1） |
|----|------|---|
| EQ01 | PARTIAL | GET 实测：HTML 200 + Markdown 200，均 `Vary: Accept`；首页自述四项单次协商检查；交互式 API 未验证（6 次已证实超时：T001 轮 3 次 + FIX-R1 轮 3 次；第 4 次 FIX-R1 尝试会话丢失、无响应文件） |
| EQ02–EQ08 | NO | 首页四项检查之外无任何冷基线/暖顺序/清空/源站计数/首次错误/裁决能力的文字或端点证据；API 无响应，回环目标亦不可达 |

#### readiness-audit 2.9.0（配置数：0，仅 CLI 参数 `domain` + `--base`；运行时间：两次 live 运行均在数分钟内完成）

| EQ | 结论 | 证据（FIX-R1） |
|----|------|---|
| EQ01 | PARTIAL | D8 live PASS（对 acceptmarkdown.com：`markdown by Accept and at the .md URL, with Vary: Accept on both and a markdown 404`）；但只是各一次 HTML/Markdown 请求 |
| EQ02 | NO | 初始请求批为 `mapLimit([...], limit(6))`（`audit.mjs:202–230`），并发 6、无顺序实验、无冷基线 |
| EQ03–EQ04 | NO | 无暖缓存顺序实验（源码 + 两次 live 运行均无） |
| EQ05 | NO | 无复位概念；D8 只查 `/` |
| EQ06 | NO | 缓存证据只有 `cdnCacheNote`（`helpers.mjs:540–547`）：读 `cf-cache-status`/`x-cache` 与 `Age` 拼一句备注，无源站计数、无 HIT/MISS 判定 |
| EQ07 | NO | 结果为每检查 pass/fail/warn/skip + 一句 detail；无请求序号、无首次错误 |
| EQ08 | NO | 无 ORIGIN/BLEED/INCONCLUSIVE 分类 |

#### Cloudflare 相关（配置数：不适用——Playground 需登录 + zone；运行时间：文档 1.614 s；Playground 探查 0.936 s 得 403）

| EQ | 结论 | 证据（FIX-R1） |
|----|------|---|
| EQ01 | PARTIAL | Markdown for Agents 转换 + Playground 单路径对比（文档原文）；Playground 本人未运行（HTTP 403） |
| EQ02–EQ08 | NO | 文档原文：Playground 只是“单路径 `Accept: text/markdown` 与 HTML 对比、看响应头与 token 节省估计”；Analytics/Logs 为抽样估计的转换次数，非逐请求双证据；isitagentready.com 首页自述为公开站扫描器 |

### 8.4 STOP 条件逐项核对（硬条件，IMPLEMENTATION_PLAN §1.3）

| STOP 子条件 | 核对结果 |
|---|---|
| 任一工具自动完成 EQ01–EQ08 | **否**。EQ02 无人 FULL；EQ05 无人 FULL；EQ06 无人 FULL；EQ07 无人 FULL；EQ08 **全员 NO**（五类对象在 EQ08 上全部为 NO，见 §8.3） |
| 不需要修改其业务代码 | cache-tests 表达 EQ03/EQ04 需要新写 `.mjs` 测试并登记——即改业务代码；Hurl 需要探测台控制端点 + 手写 `.hurl` |
| 最多使用两份简单配置文件 | Hurl 满足 EQ01–EQ08 需要：探测台（复位/计数端点）+ 每场景 `.hurl` + 硬编码绝对计数——已超出“≤2 简单配置”且仍缺 EQ08；其余工具连能力都不具备 |
| 从干净环境开始，10 分钟内完成 | cache-tests 仅安装就 31.8 s 且仍跑不通任意代理；其余工具在 10 分钟内也只能完成单次检查，不可能补出缺失的 EQ |
| 自动输出可核验的错误归因 | 无一工具具备五种裁决归因；Hurl 只给 exit 4 + 断言失败，cache-tests 只给 pass/fail，readiness-audit 只给 pass/fail/warn/skip，acceptmarkdown 只给四项检查，Cloudflare 只给转换结果描述 |

**结论：STOP 条件五项中第一项（EQ01–EQ08 全部 FULL）即不成立，其余四项亦不成立。
CONTINUE。** 本结论不依赖任何施工投入：即便 AcceptTwin 尚未写一行代码，上述逐项
证据同样得出 CONTINUE——EQ08 全员 NO 与 EQ02/EQ05/EQ06/EQ07 无人 FULL 是工具本身
的能力缺口，不是施工进度的函数。

### 8.5 残留未验证项（诚实记录，不计入通过证据）

1. acceptmarkdown.com `/api/readiness` 与 `/api/negotiate` 交互式检查：两轮合计 6 次
   已证实超时（T001 轮 3×30 s；FIX-R1 轮 3 次 30/30/60 s），HTTP 000、零字节响应；
   另有第 4 次 FIX-R1 尝试（30 s）因执行会话丢失、无响应文件落盘，不计入已证实超时；
   端点存在性由 live JS chunk 确认，行为仍未验证。其能力上限取首页自述的四项单次协商
   检查——该站没有任何 EQ02–EQ08 能力的文字或端点证据，故不影响 CONTINUE 结论；
   若终审要求交互式检查本身的实测，需换网络出口或等该站 API 恢复后重测。
2. Cloudflare Playground 与 isitagentready.com 扫描：Playground 实测 HTTP 403
   （无 Cloudflare 登录 + zone 无法运行）；isitagentready.com 只扫公开站，不能指向
   统一合成源站，故未跑扫描。Playground 语义取官方文档原文（单路径一次对比），
   按构造不可能满足 EQ02–EQ08；若终审要求 Playground 实测，需 Sam 提供 Cloudflare
   账号 + zone（登录为 Sam 本人操作，见工厂规则）。
3. 本轮三次执行会话回传丢失（readiness-audit 公开站运行、acceptmarkdown 3× POST 批、
   acceptmarkdown 第 4 次 POST 重试）与一次服务重启：受影响命令的退出码未 captured，但磁盘落盘文件完整（JSON、headers、
   无响应体文件本身即超时证据），结论均以落盘文件为准，不以丢失的会话回传为准；
   详见 `commands.log` 开头说明。另有两次读取结果附加 execution-risk 检查提示，
   无命令被实际拒绝（按 `AGENTS.md` 2026-11-20 教训处理）。
