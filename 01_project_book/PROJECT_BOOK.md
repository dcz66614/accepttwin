文件一：PROJECT_BOOK.md

以下为完整项目书，版本 1.0.1。

PROJECT_BOOK.md

---
project_id: P032
slug: accepttwin
name: AcceptTwin（网页双态镜）
document: PROJECT_BOOK
spec_version: 1.0.1
status: SPEC_FROZEN
---

# P032 AcceptTwin（网页双态镜）项目书
副标题：同一网址，两种表示，验证交付是否正确
README 一句话：> Your website serves humans and AI. Make sure it never mixes them up。

P032 AcceptTwin 网页双态镜——方向已锁定，SPEC v1.0.1，正式规格 · 2026-11-24。以下两份文件分别是产品需求与算法权威、施工与任务交接权威。它们定义的是待开发软件，不代表已经通过 S0、运行测试或完成发布。

外部证据核验结果：正式写入规格前，已实际打开并读取三类指定来源的原文。E01：RFC 9110（2022-06）§12.5.1、§12.5.5；RFC 9111（2022-06）§4、§4.1。均为 IETF Standards Track。E02：Firecrawl Issue #5956，2026-11-21 创建，当前页面状态 Open。确认 Accept 包含 text/markdown 时，react.dev 返回 404，而不包含时返回 200；Firecrawl Local 的 scrape API 又将带有 404 元数据的结果报告为 success: true。E03：Cloudflare 官方博客《Introducing Markdown for Agents》，2026-02-12 发布；官方开发文档当前显示 2026-11-09 更新。确认 Markdown 请求 Accept: text/markdown，响应的 Content-Type 为 text/markdown，并包含 Vary: Accept。一项重要的证据边界：E02 是源站内容协商异常，不是已经证实的缓存串版事故。E03 是 Cloudflare 对正确实现方式的示例，不是对所有 CDN 的测试结论。另外，RFC 9110 §12.5.5 对 Vary 使用的是 SHOULD 级别的建议，RFC 9111 §4.1 则定义缓存如何根据 Vary 匹配请求。因此本项目不会把缺少 Vary: Accept 自动判成缓存故障；还必须核验实际缓存策略、响应表示和缓存行为。

## §1 产品定位与一句话价值

### 1.1 首要目标用户

AcceptTwin 的首要目标用户是维护同时面向人类浏览器和 AI 客户端提供内容的开源文档网站的独立开发者或小型工程团队中的网站维护工程师。具体人物是一名负责维护开源软件文档站点的工程师。他使用 Windows 或 Linux 笔记本电脑进行日常开发，通过 GitHub 管理网站源码，使用 Python、Node.js 或静态网站生成工具[…]。他维护的网站需要同时满足两类访问需求：普通浏览器访问时返回 HTML，方便人类阅读；AI 客户端请求同一个 URL 时，通过 Accept: text/markdown 获得 Markdown，方便 AI 获取结构化文本。两种表示可能由同一个源站根据请求头选择，也可能经过反向代理和共享缓存后再返回给客户端。这名维护者通常在新增 Markdown for Agents 支持、修改 Nginx 缓存配置、更换反向代理、调整 Vary 或 Cache-Control、更新网站生成器，或者处理 AI 抓取异常时，需要确认两种表示是否始终正确。

### 1.2 典型使用场景

典型场景发生在一次文档网站部署或缓存配置变更之后。维护者在 Windows 或 Linux 笔记本电脑上启动本地开发环境，准备验证网站是否正确支持 HTML 和 Markdown 两种表示。他首先使用浏览器访问某个文档 URL，确认页面可以正常显示；[…] Accept: text/markdown 请求，确认服务器能够返回 Markdown。两次请求分别成功后，他可能认为双表示功能已经正常。但如果网站前面存在共享缓存，实际问题可能尚未暴露。例如，浏览器请求先到达缓存代理，代理将 HTML 响应保存下来。随后 AI 客户端请求同一个 URL，虽然这次请求要求 Markdown，缓存代理却可能错误地复用之前保存的 HTML。第二个请求仍然可[…]。反过来，如果 Markdown 请求先写入缓存，后续浏览器请求也可能错误地收到 Markdown。因此，维护者需要在部署前分别验证两种请求顺序，而不是只验证两种请求各自能否成功。另一个典型场景是：AI 网页抓取工具报告某个网站返回 404，但维护者使用普通浏览器访问同一网址却完全正常。他需要判断问题究竟发生在源站内容协商、请求头处理，还是缓存代理，而不能直接把所有异常都归咎于[…]。

### 1.3 痛点频率、强度与每次代价

以下数字是项目立项阶段的规划假设，不是已经通过真人访谈、用户调查或生产数据验证的行业统计。对于首要目标用户，预计在新增 Markdown 表示、修改缓存配置或处理网站交付异常的开发周期内，每周约有 2–3 次需要检查 HTML/Markdown 双表示及其交付行为的情况。相关问题的痛点强度评估为 5/5，因为即使两种表示各自正常，也不能排除共享缓存使其中一种表示被错误地交付给另一种请求方。一次相关问题的人工排查预计需要 20–60 分钟。时间主要花在构造不同 Accept 请求、反复清空缓存、改变请求顺序、检查响应状态码和 Content-Type、查看缓存响应头，以及对照源站日志确认[…]。如果没有可靠的缓存行为证据，维护者还可能需要反复调整配置并重新部署，才能判断问题是否真正解决。错误地将源站协商问题归因于缓存，也会导致修改错误的配置位置，增加排查成本。对于第二类用户，即维护网页抓取器、AI 搜索入口、网页转 Markdown 服务或 RAG 内容采集工具的工程师，预计每周约有 1–3 次相关内容获取异常需要排查，痛点强度规划为 4/5，每次预计耗费 10–40 分钟。这类用户尤其需要判断：浏览器返回 200、AI 请求返回 404，究竟是源站内容协商异常，还是其他交付环节的问题。这些频率和耗时只用于 MVP 范围与潜在价值评估，不能在项目发布时宣传为已经测量的用户收益。

### 1.4 当前替代做法及其不足

目前最直接的替代做法是使用 curl 分别请求 HTML 和 Markdown。例如，维护者先发送 Accept: text/html 请求，再发送 Accept: text/markdown 请求，检查状态码、Content-Type 和正文内容。这种方法可以检查两种表示是否分别存在，却无法单独证明共享缓存中的两种表示不会互相污染。第二种做法是手动清空缓存，再按照不同顺序发送请求。维护者先请求 HTML，再请求 Markdown，之后重新清空缓存，反过来先请求 Markdown，再请求 HTML。这种方法方向正确，但操作容易遗漏，尤其容易忘记在两组实验之间清空缓存，或者在暖缓存实验的两个请求之间误清缓存，从而破坏实验条件。第三种做法是检查 Nginx、反向代理或 CDN 的缓存配置，查看是否设置了 Vary: Accept、Cache-Control 等响应头。这可以帮助发现配置问题，但配置文件本身不能证明实际请求使用了什么缓存键，也不能证明某一次请求究竟命中了缓存还是重新访问了源站。第四种做法是查看 Age、Via、X-Cache 等响应头。这些信息可以作为辅助线索，但不同缓存实现的响应头并不统一，而且单独一个状态头不能充分证明实际缓存行为。即使代理声称 HIT，也需要核对源站是否确实没有收到第二次请求。第五种做法是使用通用 HTTP 测试工具编写多个请求和断言。这类工具具有较强的灵活性，但维护者仍然需要自行组织冷缓存基线、缓存重置、双向暖缓存顺序、源站计数和错误分类，容易形成不同项目各自维护的一套测[…]。现有 AI 网站 readiness 检查工具也能够检查 Markdown negotiation、Vary: Accept、响应状态和其他 AI 发现能力，但不能仅因为某项检查通过，就推断两个表示在共享缓存中的双向交付行为已经得到证明。这些替代做法的共同不足是：单次响应检查、配置检查和缓存行为证明是不同层次的问题，不能互相替代。

### 1.5 AcceptTwin 的解决机制

AcceptTwin 将上述人工排查过程固化为确定性的本地实验。对同一 URL 建立 HTML/Markdown 独立冷请求基线，然后分别执行 HTML→Markdown、Markdown→HTML 的暖缓存实验，识别内容串版及首次错误请求。四种实验缺一不可：HTML 独立冷请求用于建立浏览器表示基线；Markdown 独立冷请求用于建立 AI 表示基线；HTML→Markdown 用于检查 HTML 首先写入缓存后是否影响 Markdo[…]。每次实验都同时检查缓存响应头和源站行为证据。只有两类证据同时成立，才能确认 MISS、HIT 或 BYPASS。对于无法确认缓存状态的情况，产品必须输出 INCONCLUSIVE，而不是根据某个响应头[…]。产品通过双表示并排展示、双向请求时间线、缓存状态证据、Sentinel 对照和首次错误定位，让维护者能够看到错误发生在哪个请求、哪种表示以及哪个实验阶段。

### 1.6 最接近已有方案与不同点

最接近的已有方案包括 Hurl、HTTP cache-tests、acceptmarkdown.com 和 Agent and Search Readiness。Hurl 已经支持 HTTP 请求串联、响应状态和响应头断言以及测试报告。AcceptTwin 不重新实现通用 HTTP 测试工具，而是提供固定的双表示冷暖缓存实验及其专用诊断。HTTP cache-tests 已经具有缓存行为测试、客户端与源站追踪及结果展示能力。AcceptTwin 不宣称发明 HTTP 缓存测试，而是聚焦同一 URL 的 HTML/Markdown 双表[…]。acceptmarkdown.com 已经支持 Markdown negotiation、Vary: Accept 和相关请求检查。AcceptTwin 不再做一个普通的 Markdown 支持检测器，而是重点核验两种表示经过共享缓存后的实际交付行为。Agent and Search Readiness 已经提供综合性 AI 网站 readiness 检查。AcceptTwin 不做 AI 网站总评分，也不检查 robots.txt、llms.tx[…]。因此，AcceptTwin 的产品差异不是 HTTP 请求、Markdown 支持或缓存测试本身，而是将同一 URL 的双表示、独立冷基线、双向暖缓存实验、缓存双重证据、首次错误定位和独立 Oracl[…]。上述差异仍须通过 IMPLEMENTATION_PLAN.md 的 T001 竞争差异化硬门进行实际验证；如果已有专用工具在规定配置数量和时间限制内能够完成全部等价实验及错误归因，则停止 Accept[…]。

## §2 外部问题证据与竞争差异化

### 2.1 E01-A RFC 9110 — HTTP Semantics

（来源 https://www.rfc-editor.org/rfc/rfc9110.html，出版日期 2022-06，发布机构 IETF，状态 Internet Standards Track；直接参考 §8.3 Media Type、§12 Content Negotiation、§12.5.1 Accept、§12.5.5 Vary；Accept 允许客户端表达可接受或偏好的响应媒体类型，例如 Accept: text/html 与 Accept: text/markdown 可以构成不同的表示选择条件；Vary 用于说明请求中的哪些字段影响了响应表示的选择；借鉴 HTTP 内容协商语义、Accept 的表示选择作用、Vary 的请求维度说明、媒体类型的正确识别；不复制或扩张：不实现完整 HTTP 协议栈、不实现所有内容协商算法、不实现所有媒体类型、不把 Accept 之外的全部协商维度纳入首版）。E01-B RFC 9111 — HTTP Caching（来源 https://www.rfc-editor.org/rfc/rfc9111.html，出版日期 2022-06，IETF，Internet Standards Track；直接参考 §3 Storing Responses in Caches、§4 Constructing Responses from Caches、§4.1 Calculating Cache Keys with the Vary Header Field、§4.2 Freshness、§5.1 Age；RFC 9111 §4.1 规定，缓存使用包含 Vary 的存储响应时，必须检查后续请求中相应字段是否匹配，或进行有效重新验证；本项目特别保留一个重要区别：没有 Vary: Accept 不自动等于已经发生缓存故障，必须结合：1. 双表示契约；2. 源站实际返回的响应；3. Cache-Control 等缓存控制字段；4. 缓存代理实际使用的键；5. 暖缓存请求是否真正命中；6. 源站是否再次收到请求；7. 返回正文是否与请求表示一致。缺少 Vary 可以形成诊断提示，但不能仅凭这一点输出 REPRESENTATION_BLEED）。

### 2.2 E02 Firecrawl Issue #5956

（来源 https://github.com/firecrawl/firecrawl/issues/5956，标题：firecrawl-local: sites that content-negotiate on text/markdown return 404 (e.g. react.dev), with no……，创建日期 2026-11-21，报告者 eekfonky，涉及版本 firecrawl-local 0.1.1，页面状态 Open（本轮读取时）。实际报告内容：使用 Firecrawl Local 的抓取请求；请求头中默认包含 text/markdown;q=0.9；对 react.dev 的请求得到 404；不包含 text/markdown 的请求得到 200；Firecrawl 返回的结果外层标记 success: true，但元数据中的 HTTP 状态码为 404；报告者建议针对特定 4xx 情况去掉 Markdown 偏好后重试。证据边界：这个 Issue 证明了一个真实的内容协商问题：不同 Accept 请求可能使同一个网站返回不同状态码，调用方也可能错误地将错误结果报告为成功。但是：该 Issue 没有证明发生缓存串版；没有证明缓存 HIT；没有证明 HTML 响应被错误地复用于 Markdown 请求；没有证明 Vary 缺失是该问题的原因。因此，E02 只用于证明源站内容协商异常的真实性，不能用来证明缓存故障已经普遍发生。AcceptTwin 将分别测试源站错误与缓存错误，避免混淆）。

### 2.3 E03 Cloudflare Markdown for Agents

（官方博客 https://blog.cloudflare.com/markdown-for-agents/，发布日期 2026-02-12，作者 Celso Martinho、Will Allen；官方开发文档 https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/，本轮读取时开发文档最后更新日期 2026-11-09。实际官方示例：Cloudflare Markdown for Agents 支持通过内容协商返回 Markdown；请求示例 curl https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/ -H "Accept: text/markdown"；官方展示的响应包括：HTTP/2 200，content-type: text/markdown; charset=utf-8，vary: accept，cache-control: public, max-age=3600；Cloudflare 文档说明：转换后 Content-Type 设置为 text/markdown; charset=utf-8；Vary 包含 Accept；其他原有 Vary 维度予以保留；缓存相关响应头在转换中得到保留；官方示例中的响应 Date 为 2026-02-11；博客正式发布日期为 2026-02-12。借鉴：同一 URL 的 HTML/Markdown 双表示模式、Accept: text/markdown 请求、Content-Type 表示标识、Vary: Accept 缓存区分；不复制：Cloudflare 边缘网络、HTML 自动转换为 Markdown、Cloudflare 账号或 Zone 配置、CDN 缓存实现、Content Signals 策略系统。AcceptTwin 只检查双表示交付和缓存一致性）。

### 2.4 最接近的开源和商业方案

A. Hurl（https://github.com/Orange-OpenSource/hurl，文档 https://hurl.dev/docs/running-tests.html；已有能力：HTTP 请求执行、多请求串联、响应状态断言、响应头断言、正文断言、测试报告、CI 集成、顺序执行及重复测试；不复制通用 HTTP 请求语言、通用 API 测试能力、Hurl 的语法和运行器；AcceptTwin 的差异是把双表示冷暖实验、双重缓存证据及首次错误归因作为一个冻结的专用工作流）。B. cache-tests（https://github.com/http-tests/cache-tests，许可证 BSD-3-Clause（以仓库实际 LICENSE 为准）；已有能力：HTTP 缓存行为测试、浏览器缓存、反向代理、CDN 测试、客户端和源站请求/响应追踪、JSON 测试结果、HTML 结果展示、自定义测试用例扩展；它是非常重要的直接竞争先例；AcceptTwin 不得宣称自己发明 HTTP 缓存测试；差异假设：专门以 HTML/Markdown 双表示为对象、固定双向冷暖实验、同时验证两种请求顺序、通过受控代理状态和源站计数双重核实缓存行为、输出五种明确裁决、提供与独立 Oracle 对账的最小错误见证）。C. acceptmarkdown.com（https://acceptmarkdown.com/；该网站已经提供：Accept: text/markdown 请求测试、HTML/Markdown 内容协商检查、Vary: Accept 检查、不支持类型的 406 检查、q-value 检查、在线 Accept 请求测试器；这是比普通 AI readiness checker 更接近本项目的竞争对象；其已展示能力主要是表示协商与相关响应头检查；AcceptTwin 的差异假设在于冷暖缓存顺序实验和缓存命中证据，而不是再做一个 Markdown 支持检测器）。D. readiness-audit / Agent and Search Readiness（https://github.com/geeks-accelerator/agent-and-search-readiness，NPM https://www.npmjs.com/package/readiness-audit，许可证 MIT；已有能力：网站 AI Agent readiness 检查、Markdown negotiation、AI 发现文件、robots.txt、sitemap、MCP 与 API 相关检查、JSON 报告、本地预览地址检查；它是综合型 AI 网站 readiness 工具；AcceptTwin 不做 readiness 总评分，不检查 llms.txt、MCP、robots.txt 或 SEO）。竞争边界结论：以上先例已经覆盖大量基础功能。因此 AcceptTwin 的白空间只在一个非常窄的组合：同一 URL 的两种表示 + 独立冷请求 + 双向暖缓存顺序 + 双重缓存证据 + 首次错误归因 + 独立 Oracle。这一差异必须在 T001 竞争差异化硬门中再次实际验证。若已有专用工具可以在两份简单配置以内、10 分钟以内完成全部等价实验与错误归因，则停止项目，不得继续开发。

## §3 产品目标、非目标与成功定义

### 3.1 MVP 目标

1. 支持本地合成 HTML/Markdown 源站；2. 支持受控本地缓存代理；3. 支持双表示契约 JSON；4. 支持固定 HTTP GET 请求；5. 支持两种独立冷请求；6. 支持两种相反暖缓存顺序；7. 支持缓存状态双重取证；8. 支持五种最终裁决；9. 支持至少八种诊断代码；10. 支持 48 个固定合成 Golden；11. 支持独立 TypeScript Oracle；12. 支持 JSON 机器报告；13. 支持自包含 HTML 报告；14. 支持本地预览、导出和删除；15. 支持完全离线运行。

### 3.2 明确非目标（不实现）

真实 CDN 认证；Cloudflare、Fastly、Akamai 等真实 CDN 的兼容性认证；真实网站公网扫描；渗透测试；网站漏洞扫描；通用 AI 网站 readiness 评分；SEO 检查；robots.txt 检查；llms.txt 检查；MCP Server 检查；网页转 Markdown 引擎；HTML 转 Markdown；PDF 转 Markdown；浏览器自动化平台；通用 API 测试框架；通用 HTTP 测试 DSL；缓存修复代理；自动修改 Nginx/CDN 配置；生产流量监听；实时流量镜像；真实客户数据采集；远程报告上传；账号、订阅和遥测；LLM 或 AI 推理。

### 3.3 双层成功定义

工程成功——四种实验全部存在并真实执行；S0 24/24 通过；最终 Golden 48/48 与 Oracle 一致；已知故障全部检出；健康场景零误报；单场景运行时间小于 1 秒；100 次重复运行得到相同规范化报告哈希；JSON Schema 验证通过；HTML 报告完全自包含；依赖许可证核对完成；本地离线运行通过。产品价值——当前没有真人参与者，因此 USER_VALUE_NOT_MEASURED；不能声称：已证明用户愿意使用、已证明节省了多少时间、已证明有真实客户、已证明有付费意愿、已证明有企业收购意向。GitHub 传播力和商业潜力属于产品假设，不属于工程验收事实。

## §4 用户流程与完整交互设计

### 4.1 产品入口

accepttwin --help；accepttwin demo；accepttwin run --contract contracts/site.json；accepttwin verify --report output/report.json；accepttwin report preview output/report.json；accepttwin report export output/report.json；accepttwin clean --run-id <RUN_ID>；accepttwin report delete output/report.json；accepttwin contract delete contracts/site.json；以上为冻结的 CLI 命令契约；具体参数、帮助文本和退出码由实施计划 T002 冻结。

### 4.2 用户主流程

启动 AcceptTwin → 读取或创建双表示契约 → 检查契约与回环地址 → 启动合成源站与缓存代理 → 执行源站直连基线（O-H、O-M）→ 执行 HTML 独立冷请求 → 执行 Markdown 独立冷请求 → 执行 HTML→Markdown 暖缓存实验 → 执行 Markdown→HTML 暖缓存实验 → 分类裁决与首次错误定位 → Oracle 对账 → 生成 JSON 报告与自包含 HTML 报告 → 隐私预览与导出。

补全回复取回的流程约束（完整）：

1. 源站基线不经过缓存代理。2. 每种独立冷请求都需要单独清空缓存。3. 每个暖缓存实验需要单独清空缓存。4. 每个暖缓存实验的两次请求之间不允许清缓存。5. 两种暖缓存顺序必须真实执行。6. Oracle parity 失败时，不得将报告标记为最终有效。7. 隐私预览必须发生在 HTML 导出之前。

### 4.3 UI 页面

报告首页采用单页静态 HTML。区域 A 最终裁决：显示最终 verdict、诊断数量、CRITICAL 数量、WARNING 数量、首次错误请求、输入契约 SHA-256、场景 ID。区域 B 双表示基线（左右两列 HTML / Markdown）：Accept 请求值、预期状态码、实际状态码、预期 Content-Type、实际 Content-Type、Sentinel 匹配、源站基线结果。区域 C 双向缓存时间线：第一条 RESET → HTML MISS → Markdown MISS / HIT / BYPASS；第二条 RESET → Markdown MISS → HTML MISS / HIT / BYPASS；显示请求顺序、请求表示、响应表示、缓存状态、缓存键摘要、源站请求计数变化、Sentinel 是否匹配。区域 D 首次错误定位（示例格式）：First Error，Experiment: HTML_TO_MARKDOWN，Request Index: 2，Requested Representation: MARKDOWN，Observed Representation: HTML，Observed Content-Type: text/html; charset=utf-8，Cache Status: HIT，Sentinel Match: false；这是预期展示格式，不是已运行结果。区域 E 诊断列表：每条诊断包括 code、severity、message、experiment、request index、expected、observed、evidence references。区域 F 报告与隐私：显示报告是否包含原始正文（必须为 false）、是否包含敏感请求头（必须为 false）、是否包含允许展示的请求头（是）、是否包含正文原始内容（否）、是否包含正文哈希（是）、导出文件路径、导出前预览状态。

补全回复取回的片段与首次错误定位规则（完整）：

First Error
================================================
Experiment:
HTML_TO_MARKDOWN
Request Index: 2
Requested Representation: MARKDOWN
Observed Representation: HTML
Observed Content-Type: text/html; charset=utf-8
Cache Status: HIT
Sentinel Match: false
首次错误定位规则：• 请求序号按实际执行顺序递增。• 不得按诊断严重程度重新排序请求。• first_error 是首次违反冻结契约的请求。• 如果源站基线首先失败，首次错误必须指向源站基线。• 如果源站基线正常，暖缓存第二请求首次串版，则指向对应的第二请求。• 如果缓存证据不足，不得把疑似串版当作已确认错误。• 首次错误与最终裁决必须分别存储，不能因为后续发现更严重的错误而改写历史请求顺序。

## §5 双表示契约与请求规范

### 5.1 契约文件

文件格式 JSON，Schema accepttwin.contract/v1，文件建议路径 contracts/site.json。契约必须包含以下字段：schema（string，必填，accepttwin.contract/v1）、contract_id（string，必填，契约唯一 ID）、name（string，必填，契约名称）、url（string，必填，通过缓存代理访问的 URL）、origin_url（string，必填，直连源站 URL）、representations（object，必填，HTML 与 Markdown 契约）、request_headers（object，必填，固定公共请求头）、cache_behavior（object，必填，缓存行为声明）、limits（object，必填，请求及正文边界）、metadata（object，必填，可选说明，不参与判定）。

### 5.1.1 URL

首版只允许 http://127.0.0.1、http://[::1]、http://localhost，但解析出的全部地址必须属于 loopback；禁止：公网 IPv4、公网 IPv6、内网其他地址、域名解析到非回环地址、自动跟随到公网的重定向、用户提供的 HTTP_PROXY / HTTPS_PROXY 环境变量、非 HTTP 协议；url 必须指向本地受控缓存代理；origin_url 必须指向本地受控合成源站；两者路径必须相同，端口不同；推荐默认端口 Proxy 18765、Origin 18766；端口可由契约指定，但两个服务必须在本地启动前完成冲突检查。

### 5.1.2 双表示字段

HTML 和 Markdown 各自必须具备以下字段（完整 JSON，字段值据补全回复字段表写出；页面原 JSON 代码块未完整取回）：

```json
{"representations": {"html": {"accept": "text/html", "expected_status": 200, "expected_content_type": "text/html; charset=utf-8", "sentinel": "AT_HTML_SENTINEL_001"}, "markdown": {"accept": "text/markdown", "expected_status": 200, "expected_content_type": "text/markdown; charset=utf-8", "sentinel": "AT_MARKDOWN_SENTINEL_001"}}}
```

字段含义：accept：HTML text/html / Markdown text/markdown；expected_status：200 / 200；expected_content_type：text/html; charset=utf-8 / text/markdown; charset=utf-8；sentinel：AT_HTML_SENTINEL_001 / AT_MARKDOWN_SENTINEL_001。

冻结规则：• 两种 Sentinel 必须不同。• Sentinel 必须在对应正文中真实存在。• 精确匹配，不做语义推断。• 以 UTF-8 正文字节进行计算。• 报告保存 Sentinel 匹配结果和正文哈希，不保存原始正文。

Sentinel 必须：在对应合成正文中存在；HTML 与 Markdown 使用不同值；不与另一个表示的 Sentinel 相同；不依赖自然语言语义识别；采用精确字节匹配；不使用 LLM 判断正文是否正确。

### 5.1.3 请求头集合

首版固定请求头：Accept：HTML text/html，Markdown text/markdown；Accept-Encoding：identity / identity；User-Agent：AcceptTwin/1.0.0 / AcceptTwin/1.0.0；Accept-Language：en / en。以下请求头禁止在首版自定义：Cookie、Authorization、Proxy-Authorization、Referer、Origin、用户自定义 X-* 头、不受控的 Cache-Control 请求指令。固定请求头的目的：1. 使实验可复现；2. 避免不同请求意外改变其他缓存维度；3. 减少敏感信息暴露；4. 让 Accept 成为唯一需要测试的表示维度。缓存控制与调试信息由受控代理内部生成，不作为用户请求头。

### 5.2 缓存行为声明 cache_behavior

示例 A：按 Accept 区分缓存：{"cache_behavior": {"mode":"variant_by_accept","vary_accept":"advisory","max_age_seconds":60}}
含义：• variant_by_accept：HTML 和 Markdown 必须按表示维度分别缓存。• advisory：缺少 Vary: Accept 产生 WARNING，但不直接判定故障。• max_age_seconds：合成缓存的最大新鲜时间。
示例 B：不存储：{"cache_behavior": {"mode":"no_store","vary_accept":"not_required","max_age_seconds":null}}
含义：• 不允许存储响应。• 每次请求都必须到达源站。• 缓存代理不得复用先前响应。• 两种请求顺序都应产生 BYPASS。• 不要求 Vary: Accept，但仍需检查其他契约要求。
vary_accept 取值：required：契约要求响应包含 Vary: Accept；advisory：缺少该字段只产生 WARNING；not_required：契约不要求该字段。
特别说明：Vary: Accept 是协议层缓存维度声明，实际缓存行为还必须通过受控代理的缓存键、状态头及源站计数验证。不能仅根据上述 JSON 或响应头推断实际缓存已经正确隔离。

主回复的模式描述（保留）：

（示例 JSON：{"mode":"variant_by_accept","vary_accept":"advisory","max_age_seconds":60}，页面截断显示）。支持模式：variant_by_accept——声明 HTML 与 Markdown 应分别缓存；缓存不能把一种表示复用于另一种表示；不同表示的缓存键必须能区分；默认期望响应可缓存；vary_accept 可选 required / advisory / not_required，默认 advisory，即缺少 Vary: Accept 产生 WARNING，但是否发生故障仍需结合真实缓存行为判断；当用户明确声明 required 时，缺少 Vary: Accept 构成契约违反，但仍不得直接输出 REPRESENTATION_BLEED，因为它没有证明正文已经串版。no_store——声明响应不应被缓存存储；每个代理请求都应转发至源站；不应复用先前的响应；要求 HTTP Cache-Control: no-store，在受控代理中预期状态为 BYPASS。

### 5.3 缓存 MISS/HIT/BYPASS 的精确定义

这是 AcceptTwin 最重要的证据合同。任何缓存状态都必须同时具有响应头证据与行为证据。两者缺一不可。A. MISS：响应头证据 X-AcceptTwin-Cache-Status: MISS，X-AcceptTwin-Cache-Key: <SHA256>，X-AcceptTwin-Entry-Id: <ENTRY_ID>；行为证据：对应请求确实到达源站；源站请求计数增加 1；源站事件日志中存在与该请求对应的记录；缓存条目在本次响应后被建立；只有两个证据均成立，才能判为 MISS。B. HIT：响应头证据 X-AcceptTwin-Cache-Status: HIT，X-AcceptTwin-Cache-Key: <SHA256>，X-AcceptTwin-Entry-Id: <ENTRY_ID>；行为证据：源站请求计数没有增加；缓存条目 ID 与之前实际存储的条目一致；返回的正文哈希与缓存条目记录的正文哈希一致；只有两个证据均成立，才能判为 HIT。C. BYPASS：响应头证据 X-AcceptTwin-Cache-Status: BYPASS；行为证据：源站请求计数增加 1；源站存在对应事件；缓存条目数量没有增加；两个证据均成立才能判为 BYPASS。D. 不可确认：下列情况都不能猜测缓存状态：响应头说 HIT，但源站计数增加；响应头说 MISS，但源站计数没有增加；缺少缓存状态头；缺少源站事件日志；缓存键无法关联；缓存重置未确认成功；代理和源站日志互相矛盾。此时诊断 CACHE_STATE_UNKNOWN，最终结果 INCONCLUSIVE。E. 其他响应头：Age、Via、标准 Vary、Cache-Control 可以作为辅助证据，但不能单独证明本次 HIT 或 MISS。X-AcceptTwin-* 是本地合成代理专用测试头，不是 HTTP 标准头，也不应被当成任意公网服务提供的可信证据。

### 5.4 冷缓存与暖缓存的精确定义

冷缓存必须满足：1. 对指定场景执行缓存清空；2. 代理缓存条目数为 0；3. 缓存重置操作得到成功确认；4. 请求发送前记录源站计数；5. 发送请求；6. 收到响应；7. 核实响应头状态为 MISS，或在 no_store 契约下为 BYPASS；8. 核实源站行为计数变化；9. 保存对应证据。仅仅执行一个“清缓存”命令而没有确认缓存条目数为零，不算冷缓存。暖缓存实验必须：1. 清空缓存；2. 记录初始缓存状态；3. 执行第一个表示请求；4. 核实第一个请求为 MISS 或 BYPASS；5. 保留缓存状态；6. 不清缓存；7. 执行第二个表示请求；8. 核实第二个请求为 MISS、HIT 或 BYPASS；9. 对比第二个响应与该请求的表示契约；10. 结合源站请求计数确认缓存行为。注意：在 variant_by_accept 的正确实现中，第二种表示应当产生新的缓存 MISS，而不是复用第一种表示的 HIT。在 no_store 模式中，两次请求都应 BYPASS。因此，暖缓存实验不等于要求第二个请求一定 HIT。

## §6 四种实验与执行顺序

### 6.1 全局固定顺序

每次完整运行必须按以下顺序执行。阶段 0 源站直连基线：请求不经过缓存代理，O-H: Origin HTML，O-M: Origin Markdown；作用：检查源站是否真的支持 HTML；检查源站是否真的支持 Markdown；将源站错误与缓存错误分离；直连请求不改变代理缓存状态。实验 1 HTML 独立冷请求：RESET → VERIFY_EMPTY → H → VERIFY_MISS_OR_BYPASS；预期：variant_by_accept：MISS；no_store：BYPASS。实验 2 Markdown 独立冷请求：RESET → VERIFY_EMPTY → M → VERIFY_MISS_OR_BYPASS；预期同上。实验 3 HTML → Markdown：RESET → VERIFY_EMPTY → H → VERIFY_FIRST_REQUEST → M → VERIFY_SECOND_REQUEST；预期：variant_by_accept：MISS → MISS；no_store：BYPASS → BYPASS；如果第二个请求得到 HTML Sentinel、HTML Content-Type，并且有充分 HIT 证据，则认定表示串版。实验 4 Markdown → HTML：RESET → VERIFY_EMPTY → M → VERIFY_FIRST_REQUEST → H → VERIFY_SECOND_REQUEST；预期同实验 3；如果第二个请求得到 Markdown Sentinel、Markdown Content-Type，并且有充分 HIT 证据，则认定表示串版。

### 6.2 缓存重置规则

四个实验各自独立复位。禁止：将实验 1 的缓存状态带入实验 2；将实验 2 的缓存状态带入实验 3；将实验 3 的缓存状态带入实验 4；在实验 3 或实验 4 的两次请求之间清缓存；为第二次请求修改 URL 来绕开原有缓存条目；为不同表示使用不同的缓存路径来规避问题。四个实验使用同一个 url 字符串。

### 6.3 首次错误定位

执行记录使用严格的顺序编号：001 O-H，002 O-M，003 H-COLD，004 M-COLD，005 HM-1，006 HM-2，007 MH-1，008 MH-2。所有诊断按上述顺序排序。first_error 指整个运行中第一个违反冻结契约的请求。如果第一次错误发生在源站直连基线，后续缓存异常不得掩盖源站错误。如果源站基线正常，首次错误发生在 HM-2，应精确定位到第二个暖缓存请求。如果缓存证据不足，则不得把这个请求升级为已证实的缓存串版。

## §7 一致性不变量与确定性算法

### 7.1 I-01 HTML 源站基线不变量

直接访问源站并使用 HTML Accept 请求时：状态码等于契约值；Content-Type 等于契约值；HTML Sentinel 必须存在；否则产生源站错误。

### 7.2 I-02 Markdown 源站基线不变量

同理，Markdown 状态码、Content-Type、Markdown Sentinel，否则产生源站错误。

### 7.3 I-03 HTML 冷请求不变量

清空缓存后，HTML 请求必须得到 HTML 表示；缓存状态必须与契约声明一致。

### 7.4 I-04 Markdown 冷请求不变量

同理。

### 7.5 I-05 HTML→Markdown 顺序不变量

第一请求 HTML 正确，不得导致第二请求 Markdown 得到 HTML。

### 7.6 I-06 Markdown→HTML 顺序不变量

第一请求 Markdown 正确，不得导致第二请求 HTML 得到 Markdown。

### 7.7 I-07 缓存证据不变量

每次 MISS/HIT/BYPASS 必须同时具备代理响应头证据和源站行为证据；缺少任意一种证据不得确认缓存状态。

### 7.8 I-08 重复运行不变量

相同契约、相同场景、相同代理配置和相同输入，100 次运行的规范化报告哈希必须完全相同。

### 7.9 I-09 健康场景零误报

所有健康 Golden 必须输出 PASS_OBSERVED；允许存在不改变裁决的 WARNING，例如 VARY_ACCEPT_ABSENT；不得将 WARNING 误升级为 CRITICAL。

### 7.10 I-10 错误可归因性

每个已确认的故障必须关联场景 ID、实验 ID、请求序号、请求表示、实际表示、状态码、Content-Type、Sentinel 匹配结果、缓存状态证据、源站计数变化；不能只给一个笼统的“缓存异常”。

### 7.11 I-11 Vary 不能独立决定裁决

Vary: Accept 存在，但缓存实际忽略它并发生串版：判定故障；Vary: Accept 不存在，但缓存通过明确的 Accept 缓存键正确隔离：不得判为缓存串版；Vary: Accept 不存在，缓存状态无法证实：判 INCONCLUSIVE；Vary: Accept 不存在，缓存错误地复用另一表示，且有充分 HIT 证据：判 REPRESENTATION_BLEED。

### 7.12 I-12 正文保密不变量

原始正文不得写入普通运行日志或默认 JSON 报告；允许保存正文 SHA-256、Sentinel 是否匹配、受控的长度、预先声明的 Sentinel 标识。

## §8 诊断代码（诊断严重级别只允许 CRITICAL / WARNING）

### 8.1 ORIGIN_NEGOTIATION_ERROR（CRITICAL）

触发条件：绕过缓存的源站基线未按表示契约返回正确内容，包括 HTML 请求返回 404、Markdown 请求返回 404、HTML 返回错误 Content-Type、Markdown 返回错误 Content-Type、源站返回错误 Sentinel；证据字段：stage、request_index、requested_representation、expected_status、observed_status、expected_content_type、observed_content_type、expected_sentinel_sha256、sentinel_match、origin_direct: true。

### 8.2 REPRESENTATION_BLEED（CRITICAL）

触发条件必须同时满足：1. 源站双表示基线正确；2. 第一个暖缓存请求正确；3. 第二个暖缓存请求得到另一种表示；4. 代理响应头确认 HIT；5. 源站请求计数没有增加；6. 缓存条目与第一个请求的条目一致；7. 第二个响应的 Sentinel 与请求方期望不一致，并与第一个表示的证据吻合；证据字段：experiment_id、request_index、requested_representation、observed_representation、cache_status、cache_key_sha256、cache_entry_id、origin_counter_before、origin_counter_after、origin_counter_delta、sentinel_match、body_sha256；只有上述证据链完整，才可以认定缓存串版。

### 8.3 CONTRACT_MISMATCH（CRITICAL）

触发条件：响应不符合声明契约，但不满足已证实的源站错误或缓存串版归因条件，包括 HTTP 状态码错误、Content-Type 错误、不支持的响应变换、缓存行为违反契约、受控代理返回不符合预期的正文；证据字段：request_index、expected、observed、stage、response_status、response_content_type、cache_status、sentinel_match。

### 8.4 CACHE_STATE_UNKNOWN（WARNING）

触发条件：无法用双重证据确认 MISS、HIT 或 BYPASS，包括缺少状态响应头、缺少源站事件计数、两种证据互相矛盾、无法确认缓存是否清空；证据字段：proxy_cache_header_present、origin_journal_available、origin_counter_delta、cache_reset_confirmed、evidence_conflict；通常导致最终裁决 INCONCLUSIVE。

### 8.5 SENTINEL_MISMATCH（CRITICAL）

触发条件：响应正文缺少请求表示应有的精确 Sentinel；证据字段：expected_sentinel_sha256、body_sha256、sentinel_match、request_index、requested_representation、observed_content_type；不记录正文原文。

### 8.6 INCONCLUSIVE_LIMIT（WARNING）

触发条件：超出首版支持范围，无法形成可靠判断，包括重定向、外部地址、不支持的协议、超过正文大小限制、无法识别的缓存行为、需要未实现的缓存重新验证语义、响应无法解析；证据字段：limit_code、request_url、response_status、redirect_target（仅记录已验证的脱敏地址）、body_size、supported_limit。

### 8.7 VARY_ACCEPT_ABSENT（WARNING）

触发条件：双表示可缓存，但源站响应没有声明 Vary: Accept，且契约没有要求该字段；不单独改变最终裁决；如果缓存实际按 Accept 分离且双向实验通过，则可以 PASS_OBSERVED，同时保留该 WARNING。

### 8.8 CACHE_EVIDENCE_CONFLICT（WARNING）

触发条件：代理报告的缓存状态与源站行为证据不一致，例如 Proxy: HIT 但 Origin Counter: +1，或 Proxy: MISS 但 Origin Counter: 0；证据字段：proxy_reported_status、origin_counter_delta、cache_key_sha256、cache_entry_id、evidence_consistent；该情况不得被解释为已证实的 REPRESENTATION_BLEED。

### 8.9 CACHE_POLICY_MISMATCH（CRITICAL）

触发条件：契约声明 no_store，但受控缓存代理实际存储或复用了该响应；或者契约声明 variant_by_accept，实际代理行为与契约明确规定的缓存模式冲突；证据字段：declared_cache_mode、observed_cache_status、cache_entry_count_before、cache_entry_count_after、cache_entry_id、cache_control。

## §9 五种最终裁决与优先级

### 9.1 ORIGIN_NEGOTIATION_ERROR

条件：HTML 或 Markdown 的直连源站基线违反声明契约，例如 HTML 返回 404、Markdown 返回 404、Markdown 请求返回 HTML Content-Type、源站正文 Sentinel 错误；这是源站内容协商错误，不能误报为缓存串版。

### 9.2 REPRESENTATION_BLEED

条件：暖缓存第二个请求收到第一种表示，并且缓存 HIT 与源站未被再次访问两项证据都成立；必须存在完整证据链。

### 9.3 CONTRACT_MISMATCH

条件：能够观察到响应违反契约，但不能归类为已证实的源站协商错误或缓存串版，例如代理修改 Content-Type、no-store 契约却被缓存、Sentinel 不匹配但缓存状态不能支持串版归因。

### 9.4 INCONCLUSIVE

条件：无法证实缓存状态、缓存清空失败、双重证据互相冲突、发生超出范围的重定向、运行条件不满足、关键日志丢失。

### 9.5 PASS_OBSERVED

条件：两种源站基线正确、两种独立冷请求正确、HTML→Markdown 正确、Markdown→HTML 正确、缓存状态证据完整、无 CRITICAL 诊断、所有输入均在支持范围内；允许保留不改变裁决的 WARNING。

### 9.6 裁决优先级（生产判定顺序）

1. 输入不合法或执行超出支持范围：INCONCLUSIVE；2. 源站直连基线错误：ORIGIN_NEGOTIATION_ERROR；3. 已证实暖缓存串版：REPRESENTATION_BLEED；4. 其他已确认的契约错误：CONTRACT_MISMATCH；5. 没有上述问题但关键证据不足：INCONCLUSIVE；6. 所有实验和证据均符合：PASS_OBSERVED。若源站基线错误和其他缓存问题同时出现，以源站基线错误为最终裁决，其他问题保留为次级诊断，不隐藏证据。

## §10 确定性算法与实验执行

### 10.1 算法输入

双表示契约、本地合成源站配置、受控缓存代理配置、固定实验序列、固定响应 Sentinel、固定缓存行为声明。

### 10.2 算法步骤

以下 25 个步骤按执行顺序冻结，不得删除、交换或合并。

1. ValidateContract：读取并校验双表示契约，检查必填字段、字段类型、Accept 值、期望状态码、Content-Type、Sentinel 和缓存行为声明。
2. ValidateLoopbackTargets：解析 url 和 origin_url，验证协议、实际 IP、端口及回环地址范围，拒绝公网和非回环目标。
3. StartSyntheticOrigin：启动本地合成源站，提供符合契约的 HTML 和 Markdown 两种表示及预设故障场景。
4. StartControlledCacheProxy：启动本地受控缓存代理，加载当前场景指定的缓存模式和缓存键策略。
5. VerifyLocalPorts：检查源站和代理是否成功监听预期回环地址及端口，并确认两个服务能够正常通信。
6. CaptureOriginCounterBaseline：记录源站初始请求计数和事件日志位置，为后续缓存行为核验建立基线。
7. DirectOriginHTML：绕过缓存代理，直接向源站发送 Accept: text/html 请求，记录 HTML 基线响应。
8. DirectOriginMarkdown：绕过缓存代理，直接向源站发送 Accept: text/markdown 请求，记录 Markdown 基线响应。
9. ResetCache：清空受控缓存代理中的全部测试缓存条目，为 HTML 独立冷请求准备干净环境。
10. VerifyCacheEmpty：核对缓存清空确认记录及缓存条目数量，只有确认条目数为零才允许继续。
11. HTMLColdRequest：通过缓存代理发送 HTML 冷请求，并记录状态码、Content-Type、Sentinel、正文哈希和缓存响应头。
12. VerifyMissOrBypass：同时核对代理响应头和源站行为记录，确认该 HTML 请求为 MISS 或 BYPASS。
13. ResetCache：再次清空缓存，确保 Markdown 独立冷请求不受 HTML 冷请求产生的缓存条目影响。
14. VerifyCacheEmpty：核对第二次缓存重置结果及缓存条目数，确认 Markdown 独立冷请求开始前缓存为空。
15. MarkdownColdRequest：通过缓存代理发送 Markdown 冷请求，并记录状态码、Content-Type、Sentinel、正文哈希和缓存响应头。
16. VerifyMissOrBypass：同时核对代理响应头和源站行为记录，确认该 Markdown 请求为 MISS 或 BYPASS。
17. ResetCache：清空缓存，建立 HTML→Markdown 暖缓存实验的独立初始状态。
18. VerifyCacheEmpty：确认 HTML→Markdown 实验开始前缓存条目数为零，并保存重置证据。
19. HTMLWarmFirst：在空缓存条件下首先发送 HTML 请求，核实其 MISS 或 BYPASS 状态，并保存产生的缓存条目证据。
20. MarkdownWarmSecond：不清空缓存、不改变 URL，紧接着发送 Markdown 请求，核实其实际响应表示及缓存行为。
21. VerifyCacheEvidence：联合检查 HTML 和 Markdown 两次请求的响应头、缓存键、条目 ID、源站计数变化和 Sentinel，判断是否存在表示串版。
22. ResetCache：清空缓存，建立 Markdown→HTML 暖缓存实验的独立初始状态。
23. VerifyCacheEmpty：确认 Markdown→HTML 实验开始前缓存条目数为零，并保存重置证据。
24. MarkdownWarmFirst：在空缓存条件下首先发送 Markdown 请求，核实其 MISS 或 BYPASS 状态，并保存产生的缓存条目证据。
25. HTMLWarmSecond：不清空缓存、不改变 URL，紧接着发送 HTML 请求，核实其实际响应表示及缓存行为。

执行顺序特别约束：步骤 19 和 20 之间不得执行缓存重置；步骤 24 和 25 之间不得执行缓存重置；步骤 9、13、17、22 是四个独立实验的缓存复位点；四种实验必须全部真实执行；任意缓存状态不能通过单一响应头推断，必须同时检查响应头证据和源站行为证据。
说明：这 25 步是 HTTP 实验核心序列；原规格后续的证据规范化、生产分类、Oracle 对账、报告生成、哈希计算、隐私预览和 HTML 导出仍然保留，不因本次列出 25 步而删除。

### 10.3 缓存代理配置

合成代理至少支持以下配置：respect_vary（根据响应 Vary 决定缓存键维度）、force_uri_only（故意忽略 Accept）、manual_accept_key（即使源站未声明 Vary，也按 Accept 分离）、disabled（完全不存储，所有请求 BYPASS）、opaque（隐藏关键缓存证据，用于验证 INCONCLUSIVE）、ignore_no_store（故意违反 no-store，用于负向测试）；以上均为本地合成代理模式，不代表真实 CDN 的完整行为。

### 10.4 规范化哈希

规范化 JSON：UTF-8；Object key 字典序；不包含多余空白；数字格式统一；Header 名称转为小写；Header 值按规定规范化；不包含当前时间；不包含进程 ID；不包含临时目录；不包含动态端口；不包含运行耗时；不包含随机 UUID；不包含非确定性缓存请求 ID。以下字段不进入规范化报告哈希：generated_at、duration_ms、process_id、temporary_path、ephemeral_port。必须进入哈希：输入契约哈希、场景 ID、四种实验结果、源站基线结果、缓存状态证据、诊断代码、最终裁决、首次错误位置。计算：report_hash = SHA256(canonical_json_bytes)。100 次运行必须得到完全相同的结果。

### 10.5 性能

参考环境 Python 3.12、Node.js 24.x、本地回环网络、CPU-only、无外部请求。要求：单场景完整四实验运行时间小于 1 秒；48 场景完整套件记录总时间；报告生成不纳入单场景核心算法时间；100 次重复测试单独统计；不得用缓存结果跳过真实请求来伪造性能。性能门槛是待验证要求，不是预先声称的实测成绩。

## §11 48 组固定合成场景与 Golden 集

### 11.1 固定执行序列缩写

所有场景都执行完整序列 O-H、O-M、H-COLD、M-COLD、H -> M、M -> H；其中 O-H 源站直连 HTML，O-M 源站直连 Markdown，H-COLD HTML 独立冷请求，M-COLD Markdown 独立冷请求，H→M HTML 首请求、Markdown 第二请求，M→H Markdown 首请求、HTML 第二请求；表中的 H/M 表示对应请求返回预期表示；H/H 表示两个请求均得到 HTML；M/M 表示两个请求均得到 Markdown；所有场景的响应正文使用唯一合成 Sentinel。

### 11.2 S0 核心 Golden

24 组（S0 必须 24/24）：C01 正确 Vary，respect_vary，HTML 先——H=MISS，M=MISS；H→M 正确；M→H 正确——PASS_OBSERVED；C02 正确 Vary，respect_vary，Markdown 先——H=MISS，M=MISS；两种顺序均正确——PASS_OBSERVED；C03 缺少 Vary，manual_accept_key，HTML 先——两种表示独立 MISS，无串版；Vary WARNING——PASS_OBSERVED；C04 缺少 Vary，manual_accept_key，Markdown 先——两种表示独立 MISS，无串版；Vary WARNING——PASS_OBSERVED；C05 no-store，disabled，HTML 先——H/M 及两种顺序全部 BYPASS——PASS_OBSERVED；C06 no-store，disabled，Markdown 先——两种顺序全部 BYPASS——PASS_OBSERVED；C07 源站 HTML 返回 404——O-H 错误，其余请求继续取证——ORIGIN_NEGOTIATION_ERROR；C08 源站 Markdown 返回 404——O-M 错误，其余请求继续取证——ORIGIN_NEGOTIATION_ERROR；C09 源站 HTML Content-Type 错误——O-H 返回 text/plain——ORIGIN_NEGOTIATION_ERROR；C10 源站 Markdown Sentinel 缺失——O-M 正文标记不匹配——ORIGIN_NEGOTIATION_ERROR；C11 有 Vary，代理强制 URI-only，HTML 先——H→M：MISS→HIT(H)——REPRESENTATION_BLEED；C12 有 Vary，代理强制 URI-only，Markdown 先——M→H：MISS→HIT(M)——REPRESENTATION_BLEED；C13 无 Vary，respect_vary，HTML 先——H→M：MISS→HIT(H)——REPRESENTATION_BLEED；C14 无 Vary，respect_vary，Markdown 先——M→H：MISS→HIT(M)——REPRESENTATION_BLEED；C15 无 Vary，force_uri_only，HTML 先——两种表示使用同一 URI 缓存键，H→M 串版——REPRESENTATION_BLEED；C16 无 Vary，force_uri_only，Markdown 先——两种表示使用同一 URI 缓存键，M→H 串版——REPRESENTATION_BLEED；C17 no-store、Vary 缺失、代理 BYPASS——H/M 均正确，两个顺序均 BYPASS——PASS_OBSERVED；C18 no-store、Vary 存在、代理 BYPASS——H/M 均正确，两个顺序均 BYPASS——PASS_OBSERVED；C19 no-store 契约，但代理忽略 no-store 并存储——正文可能正确，但存储行为违反契约——CONTRACT_MISMATCH；C20 代理隐藏 Cache-Status——缺少响应头证据——INCONCLUSIVE；C21 源站事件日志不可用——缺少行为证据——INCONCLUSIVE；C22 代理声明 HIT，但源站计数增加——两种缓存证据矛盾——INCONCLUSIVE；C23 缓存重置失败——冷请求前缓存条目非零——INCONCLUSIVE；C24 源站正常，代理修改 Markdown Content-Type——代理返回 text/html——CONTRACT_MISMATCH。每个场景都必须执行源站直连和四种实验，不得通过预先知道场景答案而跳过请求。C11–C16 的串版认定都必须有完整双重缓存证据。C03、C04 是专门证明“缺少 Vary 不必然等于缓存串版”的健康对照。C17、C18 是专门证明 no-store 下缺少 Vary 不必然构成错误的健康对照。

### 11.3 扩展 Golden

24 组：E01 Vary 字段名小写 accept——正常按 Accept 区分——PASS_OBSERVED；E02 Vary 包含 Accept 与 Accept-Encoding——正确区分两个请求表示——PASS_OBSERVED；E03 Vary:*——缓存不能复用存储条目，第二请求 MISS——PASS_OBSERVED；E04 无 Vary，手动 Accept 缓存键——两种表示正确，产生 Vary WARNING——PASS_OBSERVED；E05 no-store，无 Vary——两种表示 BYPASS——PASS_OBSERVED；E06 no-store，有 Vary——两种表示 BYPASS——PASS_OBSERVED；E07 max-age=0，需要重新验证——首版不实现重新验证——INCONCLUSIVE；E08 no-cache，需要重新验证——首版不实现完整重新验证——INCONCLUSIVE；E09 源站对 Markdown 请求始终返回 HTML——O-M 失败——ORIGIN_NEGOTIATION_ERROR；E10 源站对 HTML 请求始终返回 Markdown——O-H 失败——ORIGIN_NEGOTIATION_ERROR；E11 源站对 Markdown 返回 406——O-M 状态码不符——ORIGIN_NEGOTIATION_ERROR；E12 源站返回本地重定向——首版不自动跟随——INCONCLUSIVE；E13 有 Vary，URI-only 缓存，HTML 先——H→M 确认 HIT 串版——REPRESENTATION_BLEED；E14 有 Vary，URI-only 缓存，Markdown 先——M→H 确认 HIT 串版——REPRESENTATION_BLEED；E15 no-store，无 Vary，代理正常 BYPASS——两种顺序均正确——PASS_OBSERVED；E16 no-store，有 Vary，代理正常 BYPASS——两种顺序均正确——PASS_OBSERVED；E17 Cache-Status 缺失，其他证据可用——无法确认 HIT/MISS——INCONCLUSIVE；E18 源站计数缺失，状态头存在——无法完成双重证明——INCONCLUSIVE；E19 HIT 头与源站请求记录冲突——证据矛盾——INCONCLUSIVE；E20 MISS 头与源站计数冲突——证据矛盾——INCONCLUSIVE；E21 正文超过 1 MiB——超出首版限制——INCONCLUSIVE；E22 重定向指向非回环地址——禁止跟随——INCONCLUSIVE；E23 源站正常，代理返回冲突 Content-Type——代理响应不符合契约——CONTRACT_MISMATCH；E24 源站正常，代理暖响应 Sentinel 错误——暖响应正文不符合契约——CONTRACT_MISMATCH。

### 11.4 Golden 总体要求

最终核心 Golden 24 条、扩展 Golden 24 条，总计 48 条；每条具有固定输入文件、固定预期结果、可复现的请求序列、独立 Oracle 结果、对应证据文件。必须证明：1. 已知故障场景全部检出；2. 正常场景零误报；3. 两种请求顺序都真实执行；4. 至少一个串版案例可在独立清空缓存后稳定复现；5. 缺少 Vary 的健康场景不被错误判定为缓存串版；6. 缓存证据不完整时不产生假阳性；7. 100 次重复运行产生相同规范化报告哈希。

## §12 独立 Oracle

### 12.1 实现语言

生产实现 Python 3.12；独立 Oracle TypeScript / Node.js 24.x；两者必须分别实现判定规则。

### 12.2 Oracle 输入

Oracle 读取冻结契约 JSON、固定场景定义、原始规范化 HTTP 观测记录、缓存代理响应头证据、源站事件日志、缓存重置记录；Oracle 不读取生产实现生成的最终 verdict 作为输入。

### 12.3 独立性要求

Oracle 不得 import 生产 Python 模块、调用生产分类函数、读取生产最终裁决来决定自身结果、使用生产实现输出的诊断代码作为自身输入、复用生产实现的判定表、从生产实现复制生成的预期答案代替独立计算；Oracle 可以读取双方共同的原始输入夹具和原始观测数据。

### 12.4 对账内容

每个场景逐项对比 Origin HTML 结果、Origin Markdown 结果、HTML 冷请求结果、Markdown 冷请求结果、HTML→Markdown 结果、Markdown→HTML 结果、MISS/HIT/BYPASS 证据、诊断代码集合、首次错误位置、最终裁决；最终要求：S0_ORACLE_PARITY = 24/24，FINAL_ORACLE_PARITY = 48/48；任何一条不一致都不得以平均准确率掩盖。

## §13 S0 硬门与规格逐条映射

S0 由 T007 实施；S0 的门禁定义必须严格等于本书中的规格要求，不得在实现时缩窄。映射表：24 条核心案例——§11.2——C01–C24 全部存在；24/24 Oracle parity——§12——独立 Oracle 与生产结果逐场景一致；已知故障全部检出——§8、§11.2——C07–C16、C19、C24 等对应故障；正常场景零误报——§7、§11.2——C01–C06、C17、C18；两种顺序真实执行——§0.2、§6——HM 与 MH 均产生真实请求记录；独立冷请求——§5.4、§6——缓存清空、空状态证据、MISS/BYPASS 双重证明；双重缓存证据——§5.3——响应头证据 + 源站行为证据；至少一个稳定串版复现——§8.2、§11.2——C11–C16 中至少一项独立复现；缺少 Vary 健康场景——§7.11、§11.2——C03/C04 正确 PASS；100 次报告哈希一致——§7.8、§10.4——同一输入重复 100 次；单场景小于 1 秒——§10.5——参考 VM 实际测量；证据不足不误判——§8.4、§8.8、§9.4——C20–C23；首次错误定位——§6.3、§8——具体实验和请求编号。S0 通过条件：以上各项必须全部通过；任何一项未通过，T008–T014 不得进入正常施工；S0 失败必须停止并向 Muse 提供真实日志、失败案例、输入哈希和根因分析。

## §14 JSON 数据结构与接口

### 14.1 核心数据对象

Contract、Representation、RequestObservation、Diagnostic 与 Report 的字段如下（字段名按冻结实现）：

```json
{
  "Contract": {
    "schema": "accepttwin.contract/v1",
    "contract_id": "string",
    "name": "string",
    "url": "string",
    "origin_url": "string",
    "representations": {
      "html": "Representation",
      "markdown": "Representation"
    },
    "request_headers": "object",
    "cache_behavior": "object",
    "limits": "object",
    "metadata": "object"
  },
  "Representation": {
    "accept": "string",
    "expected_status": "integer",
    "expected_content_type": "string",
    "sentinel": "string"
  },
  "RequestObservation": {
    "request_index": "integer",
    "experiment_id": "string",
    "requested_representation": "string",
    "response_status": "integer",
    "response_content_type": "string",
    "body_sha256": "string",
    "sentinel_match": "boolean",
    "cache_status": "string",
    "cache_key_sha256": "string | null",
    "cache_entry_id": "string | null",
    "origin_counter_before": "integer",
    "origin_counter_after": "integer",
    "origin_counter_delta": "integer"
  },
  "Diagnostic": {
    "code": "string（九种冻结诊断代码之一，见 §8）",
    "severity": "CRITICAL | WARNING",
    "message": "string",
    "experiment_id": "string | null",
    "request_index": "integer | null",
    "evidence": "object（按诊断代码取对应证据字段，见 §8；只含哈希、状态、计数与标识，不含正文原文）"
  },
  "Report": {
    "schema": "accepttwin.report/v1",
    "project": {"project_id": "P032", "version": "1.0.1"},
    "scenario_id": "string",
    "input": "object（契约摘要，见 §14.2）",
    "observations": "RequestObservation[]（8 条，见 §6.3）",
    "diagnostics": "Diagnostic[]",
    "verdict": "string（五种最终裁决之一，见 §9）",
    "first_error": "integer | null",
    "first_error_experiment_id": "string | null",
    "critical_count": "integer",
    "warning_count": "integer",
    "reasons": "string[]",
    "oracle": "object（Oracle 的 first_error、first_error_experiment_id、verdict）",
    "oracle_parity": "boolean",
    "final": "boolean",
    "report_hash": "string（64 位小写十六进制，见 §10.4）"
  }
}
```

注：补全回复片段中的 contractId、originUrl、requestHeaders、cacheBehavior 拼写，按冻结实现（src/accepttwin/contract.py、contracts/site.json）统一为 contract_id、origin_url、request_headers、cache_behavior；字段含义不变。

补全回复取回的片段：

Contract 包含 contractId、schema、name、url、originUrl、representations（含 html …）。原始响应正文不属于 RequestObservation、Diagnostic 或 Report 的持久化字段。receivedAt 仅属于运行期原始事件；不得进入规范化报告哈希。

### 14.2 报告 JSON 示例

以下是合成示例，不代表软件已经执行：

```json
{
  "critical_count": 6,
  "diagnostics": [
    {
      "code": "REPRESENTATION_BLEED",
      "evidence": {
        "body_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "cache_entry_id": "entry-0000000000000001",
        "cache_key_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "cache_status": "HIT",
        "experiment_id": "HTML_TO_MARKDOWN",
        "first_request_index": 5,
        "observed_representation": "html",
        "origin_counter_after": 5,
        "origin_counter_before": 5,
        "origin_counter_delta": 0,
        "requested_representation": "markdown",
        "sentinel_match": false
      },
      "experiment_id": "HTML_TO_MARKDOWN",
      "message": "warm-cache request 006 for markdown was served the other representation from a verified HIT of the entry stored by request 005",
      "request_index": 6,
      "severity": "CRITICAL"
    },
    {
      "code": "CONTRACT_MISMATCH",
      "evidence": {
        "cache_status": "HIT",
        "expected": {
          "content_type": "text/markdown; charset=utf-8",
          "status": 200
        },
        "expected_content_type": "text/markdown; charset=utf-8",
        "expected_status": 200,
        "observed": {
          "content_type": "text/html; charset=utf-8",
          "status": 200
        },
        "observed_content_type": "text/html; charset=utf-8",
        "observed_status": 200,
        "requested_representation": "markdown",
        "response_content_type": "text/html; charset=utf-8",
        "response_status": 200,
        "sentinel_match": false,
        "stage": "HTML_TO_MARKDOWN"
      },
      "experiment_id": "HTML_TO_MARKDOWN",
      "message": "response for request 006 violates the markdown contract: content-type 'text/html; charset=utf-8' (expected 'text/markdown; charset=utf-8')",
      "request_index": 6,
      "severity": "CRITICAL"
    },
    {
      "code": "SENTINEL_MISMATCH",
      "evidence": {
        "body_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "expected_sentinel_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "observed_content_type": "text/html; charset=utf-8",
        "requested_representation": "markdown",
        "sentinel_match": false
      },
      "experiment_id": "HTML_TO_MARKDOWN",
      "message": "response body for request 006 lacks the exact Sentinel of the requested markdown representation",
      "request_index": 6,
      "severity": "CRITICAL"
    },
    {
      "code": "REPRESENTATION_BLEED",
      "evidence": {
        "body_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "cache_entry_id": "entry-0000000000000001",
        "cache_key_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "cache_status": "HIT",
        "experiment_id": "MARKDOWN_TO_HTML",
        "first_request_index": 7,
        "observed_representation": "markdown",
        "origin_counter_after": 6,
        "origin_counter_before": 6,
        "origin_counter_delta": 0,
        "requested_representation": "html",
        "sentinel_match": false
      },
      "experiment_id": "MARKDOWN_TO_HTML",
      "message": "warm-cache request 008 for html was served the other representation from a verified HIT of the entry stored by request 007",
      "request_index": 8,
      "severity": "CRITICAL"
    },
    {
      "code": "CONTRACT_MISMATCH",
      "evidence": {
        "cache_status": "HIT",
        "expected": {
          "content_type": "text/html; charset=utf-8",
          "status": 200
        },
        "expected_content_type": "text/html; charset=utf-8",
        "expected_status": 200,
        "observed": {
          "content_type": "text/markdown; charset=utf-8",
          "status": 200
        },
        "observed_content_type": "text/markdown; charset=utf-8",
        "observed_status": 200,
        "requested_representation": "html",
        "response_content_type": "text/markdown; charset=utf-8",
        "response_status": 200,
        "sentinel_match": false,
        "stage": "MARKDOWN_TO_HTML"
      },
      "experiment_id": "MARKDOWN_TO_HTML",
      "message": "response for request 008 violates the html contract: content-type 'text/markdown; charset=utf-8' (expected 'text/html; charset=utf-8')",
      "request_index": 8,
      "severity": "CRITICAL"
    },
    {
      "code": "SENTINEL_MISMATCH",
      "evidence": {
        "body_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "expected_sentinel_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "observed_content_type": "text/markdown; charset=utf-8",
        "requested_representation": "html",
        "sentinel_match": false
      },
      "experiment_id": "MARKDOWN_TO_HTML",
      "message": "response body for request 008 lacks the exact Sentinel of the requested html representation",
      "request_index": 8,
      "severity": "CRITICAL"
    }
  ],
  "final": true,
  "first_error": 6,
  "first_error_experiment_id": "HTML_TO_MARKDOWN",
  "input": {
    "cache_behavior": {
      "max_age_seconds": 60,
      "mode": "variant_by_accept",
      "vary_accept": "advisory"
    },
    "contract_id": "site-example-001",
    "contract_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "origin_url": "http://127.0.0.1:18766/doc",
    "request_headers": {
      "accept_encoding": "identity",
      "accept_language": "en",
      "user_agent": "AcceptTwin/1.0.0"
    },
    "url": "http://127.0.0.1:18765/doc"
  },
  "observations": [
    {
      "body_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "cache_entry_id": null,
      "cache_key_sha256": null,
      "cache_status": null,
      "experiment_id": "ORIGIN_HTML",
      "origin_counter_delta": 1,
      "request_index": 1,
      "requested_representation": "html",
      "response_content_type": "text/html; charset=utf-8",
      "response_status": 200,
      "sentinel_match": true
    },
    {
      "body_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "cache_entry_id": null,
      "cache_key_sha256": null,
      "cache_status": null,
      "experiment_id": "ORIGIN_MARKDOWN",
      "origin_counter_delta": 1,
      "request_index": 2,
      "requested_representation": "markdown",
      "response_content_type": "text/markdown; charset=utf-8",
      "response_status": 200,
      "sentinel_match": true
    },
    {
      "body_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "cache_entry_id": "entry-0000000000000001",
      "cache_key_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "cache_status": "MISS",
      "experiment_id": "HTML_COLD",
      "origin_counter_delta": 1,
      "request_index": 3,
      "requested_representation": "html",
      "response_content_type": "text/html; charset=utf-8",
      "response_status": 200,
      "sentinel_match": true
    },
    {
      "body_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "cache_entry_id": "entry-0000000000000001",
      "cache_key_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "cache_status": "MISS",
      "experiment_id": "MARKDOWN_COLD",
      "origin_counter_delta": 1,
      "request_index": 4,
      "requested_representation": "markdown",
      "response_content_type": "text/markdown; charset=utf-8",
      "response_status": 200,
      "sentinel_match": true
    },
    {
      "body_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "cache_entry_id": "entry-0000000000000001",
      "cache_key_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "cache_status": "MISS",
      "experiment_id": "HTML_TO_MARKDOWN",
      "origin_counter_delta": 1,
      "request_index": 5,
      "requested_representation": "html",
      "response_content_type": "text/html; charset=utf-8",
      "response_status": 200,
      "sentinel_match": true
    },
    {
      "body_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "cache_entry_id": "entry-0000000000000001",
      "cache_key_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "cache_status": "HIT",
      "experiment_id": "HTML_TO_MARKDOWN",
      "origin_counter_delta": 0,
      "request_index": 6,
      "requested_representation": "markdown",
      "response_content_type": "text/html; charset=utf-8",
      "response_status": 200,
      "sentinel_match": false
    },
    {
      "body_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "cache_entry_id": "entry-0000000000000001",
      "cache_key_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "cache_status": "MISS",
      "experiment_id": "MARKDOWN_TO_HTML",
      "origin_counter_delta": 1,
      "request_index": 7,
      "requested_representation": "markdown",
      "response_content_type": "text/markdown; charset=utf-8",
      "response_status": 200,
      "sentinel_match": true
    },
    {
      "body_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "cache_entry_id": "entry-0000000000000001",
      "cache_key_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "cache_status": "HIT",
      "experiment_id": "MARKDOWN_TO_HTML",
      "origin_counter_delta": 0,
      "request_index": 8,
      "requested_representation": "html",
      "response_content_type": "text/markdown; charset=utf-8",
      "response_status": 200,
      "sentinel_match": false
    }
  ],
  "oracle": {
    "first_error": 6,
    "first_error_experiment_id": "HTML_TO_MARKDOWN",
    "verdict": "REPRESENTATION_BLEED"
  },
  "oracle_parity": true,
  "project": {
    "project_id": "P032",
    "version": "1.0.1"
  },
  "reasons": [
    "a warm-cache second request was served the other representation from a verified HIT"
  ],
  "report_hash": "9999999999999999999999999999999999999999999999999999999999999999",
  "scenario_id": "C11",
  "schema": "accepttwin.report/v1",
  "verdict": "REPRESENTATION_BLEED",
  "warning_count": 0
}
```

补全回复取回的说明（完整）：

以下是故意构造的合成串版案例，场景为 C11。不代表软件已经运行或获得该测试结果。

说明：• 所有哈希都是占位用合成值。• duration_ms 是展示字段，不进入规范化报告哈希。• 两个暖缓存实验分别独立清空缓存。• 每个串版结果均具有响应头和源站行为双重证据。• 最终裁决为 REPRESENTATION_BLEED。• 首次错误是请求 6，而不是请求 8。

### 14.3 JSON Schema

正式 Schema 文件 schemas/accepttwin.report.v1.schema.json；核心要求：$schema 使用 JSON Schema Draft 2020-12；顶层 additionalProperties: false；schema 必须为 accepttwin.report/v1；verdict 必须属于五种冻结枚举；severity 只能是 CRITICAL 或 WARNING；request_index 为正整数；origin_counter_delta 为整数；哈希字段必须是 64 位小写十六进制；正文原文不得成为 Schema 中允许的报告字段；报告中的 URL 必须属于回环地址；不得出现 Authorization/Cookie 等敏感字段。

### 14.4 独立 HTML

HTML 必须自包含、内嵌 CSS、内嵌 JavaScript、不使用 CDN、不使用远程字体、不加载远程图标、不请求外部图片、不依赖在线 API、不使用外部 iframe、可在完全断网状态打开；支持展开/折叠实验、查看诊断、查看首次错误、查看缓存证据、下载 JSON 报告、查看报告哈希。

## §15 系统架构与模块划分

### 15.1 技术架构

技术架构：AcceptTwin CLI → Contract Validator → Synthetic Origin + Controlled Cache Proxy → Experiment Runner → Production Classifier → Report Builder → Self-contained HTML Report；Independent Oracle 与生产分类器并行对账（见 §12）。

```text
+----------------------+
|    AcceptTwin CLI     |
+----------+-----------+
           |
           v
+----------------------+
|  Contract Validator  |
+----------+-----------+
           |
           v
+----------------------+       +----------------------+
|  Synthetic Origin    | <---> | Controlled Cache Proxy|
+----------+-----------+       +----------+-----------+
           |                              |
           +--------------+---------------+
                          |
                          v
+----------------------+
|  Experiment Runner   |
+----------+-----------+
           |
           v
+----------------------+
| Production Classifier|
+----------+-----------+
           |
           v
+----------------------+       +----------------------+
|   Report Builder     | <---> |  Independent Oracle  |
+----------+-----------+       +----------------------+
           |
           v
+----------------------+
| Self-contained HTML  |
|       Report         |
+----------------------+
```

### 15.2 Python 模块

src/accepttwin/，__init__.py，__main__.py，cache_evidence.py，cache_proxy.py，canonical_json.py，classifier.py，cli.py，contract.py，diagnostics.py，evidence.py，experiment_runner.py，origin_server.py，privacy.py，report_builder.py，request_headers.py，schema.py，url_guard.py。

### 15.3 前端模块

report-ui/，src/，app.ts，types.ts，timeline.ts，diagnostics.ts，index.html，styles.css，package.json，package-lock.json，tsconfig.json，report-ui.js，T010_NOTES.md。

### 15.4 Oracle

oracle/，package.json，tsconfig.json，src/，input.ts，evidence.ts，oracle.ts，index.ts；Oracle 不得导入 Python 实现生成的最终裁决。

补全回复取回的片段（系统架构 ASCII 图、Python 模块树、前端模块树、Oracle 模块树开头部分）：

+----------------------+
|    AcceptTwin CLI     |
+----------+-----------+
           |
           v
+----------------------+
|  Contract Validator  |
+----------+-----------+
           |
           v
+----------------------+       +----------------------+
|  Synthetic Origin    | <---> | Controlled Cache Proxy|
+----------+-----------+       +----------+-----------+
           |                              |
           +--------------+---------------+
                          |
                          v
+----------------------+
|  Experiment Runner   |
+----------+-----------+
           |
           v
+----------------------+
| Production Classifier|
+----------+-----------+
           |
           v
+----------------------+       +----------------------+
|   Report Builder     | <---> |  Independent Oracle  |
+----------+-----------+       +----------------------+
           |
           v
+----------------------+
| Self-contained HTML  |
|       Report         |
+----------------------+
6.1 Python 模块树：
src/
└── accepttwin/
    ├── __init__.py
    ├── __main__.py
    ├── cache_evidence.py
    ├── cache_proxy.py
    ├── canonical_json.py
    ├── classifier.py
    ├── cli.py
    ├── contract.py
    ├── diagnostics.py
    ├── evidence.py
    ├── experiment_runner.py
    ├── origin_server.py
    ├── privacy.py
    ├── report_builder.py
    ├── request_headers.py
    ├── schema.py
    └── url_guard.py
6.2 前端模块树：
report-ui/
├── src/
│   ├── app.ts
│   ├── types.ts
│   ├── timeline.ts
│   └── diagnostics.ts
├── index.html
├── styles.css
├── package.json
├── package-lock.json
├── tsconfig.json
├── report-ui.js
└── T010_NOTES.md
6.3 独立 Oracle 模块树：
oracle/
├── package.json
├── tsconfig.json
└── src/
    ├── input.ts
    ├── evidence.ts
    ├── oracle.ts
    └── index.ts
三个模块的职责必须分开：• Python 是生产实验和分类实现。• TypeScript 是独立 Oracle。• TypeScript 静态 UI 负责报告展示，不参与生产裁决。不得为了减少代码而把 Oracle 与生产分类器合并。

## §16 技术栈与版本策略

### 16.1 Python

目标版本 Python 3.12.x；使用标准库 http.server、http.client、urllib.parse、ipaddress、json、hashlib、pathlib、argparse、dataclasses、threading、time、collections；不引入运行时 HTTP 客户端依赖。

### 16.2 测试

pytest；测试数据全部为合成夹具；不访问公网。

### 16.3 TypeScript

目标 Node.js 24.x；用于独立 Oracle、静态报告界面、JSON 数据验证、构建自包含 HTML；生产运行不依赖 Node 服务常驻。

### 16.4 依赖原则

免费开源；精确版本由 T001 环境探测后冻结；提交锁文件；依赖许可证逐项登记；优先 Python 标准库；不引入收费 API；不引入遥测依赖；不使用运行时 CDN。许可证要求：项目自有代码 MIT；第三方依赖保留原许可证，并在 THIRD_PARTY_NOTICES.md 中登记。

## §17 隐私、安全与数据管理

### 17.1 本地优先

所有工作在本地完成；不上传合成正文、契约文件、HTTP 请求、响应正文、缓存记录、诊断报告。

### 17.2 敏感字段

禁止请求头 Authorization、Cookie、Proxy-Authorization；默认不记录原始正文、未脱敏请求头、任意用户环境变量、远程代理配置；允许记录固定 Accept、固定 User-Agent、Accept-Encoding、Accept-Language、状态码、Content-Type、缓存证据、Sentinel 匹配结果、正文哈希。

### 17.3 可查看、可修改、可删除

契约采用普通本地 JSON 文件，用户可以查看、编辑、复制、删除；报告采用本地 JSON/HTML 文件，用户可以查看、预览、导出、删除；导出 HTML 前必须进行隐私预览。

### 17.4 本地网络安全

1. 所有 URL 必须回环地址；2. DNS 解析必须检查实际 IP；3. 不允许公网地址；4. 不自动跟随重定向；5. 不读取环境代理；6. 不执行用户提供的 Shell 命令；7. 不启动任意外部程序；8. 正文限制 1 MiB；9. 请求超时必须有限制；10. 本地服务退出时关闭端口；11. 缓存数据仅保存在运行内存；12. 运行结束清理临时数据。

## §18 验收指标

18. 验收指标

| ID | 指标 | 最终验收门槛 | 验证方式 |
| --- | --- | --- | --- |
| AC01 | 四种实验完整性 | 4/4，缺一不可 | 检查实际 HTTP 请求序列及实验记录 |
| AC02 | 核心 Golden | 24/24 | 执行 C01–C24 |
| AC03 | 最终 Golden | 48/48 | 执行 C01–C24、E01–E24 |
| AC04 | 独立 Oracle parity | 48/48 | Python 生产实现与 TypeScript Oracle 逐场景对账 |
| AC05 | 已知故障检出 | 100% | 所有预设故障场景均触发正确诊断和裁决 |
| AC06 | 健康场景误报 | 0 | 健康 Golden 全部为 PASS_OBSERVED |
| AC07 | 双向暖缓存实验 | HTML→Markdown、Markdown→HTML 均真实执行 | 检查请求 trace、顺序和缓存复位日志 |
| AC08 | 缓存证据 | MISS/HIT/BYPASS 均有双重证据 | 响应头证据与源站行为证据同时成立 |
| AC09 | 稳定串版复现 | 至少一个串版场景独立清空缓存后连续 3/3 复现 | 重置缓存、重新执行并核对完整证据链 |
| AC10 | 重复运行确定性 | 100/100 次规范化报告哈希一致 | repeat --count 100 |
| AC11 | 单场景性能 | 完整四实验小于 1 秒 | 在固定参考 VM 上真实测量 |

以上指标均为冻结的验收要求，不是已完成测试的声明。

## §19 最终交付物

正式交付必须包含：
P032-accepttwin/
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
还必须有：源码 ZIP；可重建依赖；完整测试日志；48 条 Golden；独立 Oracle；JSON 报告样本；HTML 报告样本；实际运行截图；100 次重复运行日志；许可证审查；SHA-256 清单；Git commit；源码审查包；REVIEW_INDEX.md；REVIEW_PACK_XX.md；最终发布说明。

## §20 参考网址与来源

HTTP 标准：1. RFC 9110 — HTTP Semantics（https://www.rfc-editor.org/rfc/rfc9110.html）；2. RFC 9111 — HTTP Caching（https://www.rfc-editor.org/rfc/rfc9111.html）。
真实问题：3. Firecrawl Issue #5956（https://github.com/firecrawl/firecrawl/issues/5956）。
官方双表示实践：4. Cloudflare Markdown for Agents（https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/）；5. Cloudflare 官方发布文章（https://blog.cloudflare.com/markdown-for-agents/）。
竞争先例：6. Hurl（https://github.com/Orange-OpenSource/hurl）；7. Hurl Testing Documentation（https://hurl.dev/docs/running-tests.html）；8. HTTP cache-tests（https://github.com/http-tests/cache-tests）；9. acceptmarkdown.com（https://acceptmarkdown.com/）；10. Agent and Search Readiness（https://github.com/geeks-accelerator/agent-and-search-readiness）；11. RFC 7763 — The text/markdown Media Type（https://www.rfc-editor.org/rfc/rfc7763.html）。
开发与许可：12. Python 3.12（https://docs.python.org/3.12/）；13. pytest（https://docs.pytest.org/）；14. TypeScript（https://www.typescriptlang.org/）；15. MIT License（https://opensource.org/license/mit/）。

## §21 规格冻结声明

本项目书 v1.0.1 冻结以下内容：1. 产品定位；2. 首要与次要用户；3. 核心机制；4. HTML/Markdown 双表示契约；5. HTTP 请求头集合；6. 冷缓存定义；7. 暖缓存定义；8. MISS/HIT/BYPASS 双重证据；9. 四种实验；10. 一致性不变量；11. 诊断代码；12. 五种最终裁决；13. 48 组 Golden；14. 独立 Oracle；15. S0 门禁；16. JSON 报告 Schema；17. 自包含 HTML 报告；18. 本地网络安全边界；19. 隐私约束；20. MIT 许可证；21. 88 小时预算。
任何修改必须通过 ADR。不得因实现便利而删除实验、缩减 Golden、取消 Oracle 或降低缓存证据要求。
项目当前状态：
PROJECT_ID: P032
PROJECT_NAME: AcceptTwin
SPEC_VERSION: 1.0.1
SPEC_STATUS: SPEC_FROZEN
IMPLEMENTATION_STATUS: COMPLETE
RELEASE_STATUS: READY_FOR_FINAL_REVIEW
FINAL_GPT_REVIEW: PENDING
ACCEPTED: PENDING
