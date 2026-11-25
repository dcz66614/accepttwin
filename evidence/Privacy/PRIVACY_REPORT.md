# P032-T011 隐私与本地安全回归 — 证据报告（PRIVACY_REPORT.md）

- 任务：T011 隐私与本地安全回归（预算 4h）
- 规格：PROJECT_BOOK.md v1.0.0 §17 / §5.1.1 / §5.1.3 / §7.12 I-12；IMPLEMENTATION_PLAN.md T011
- Base commit：`609ea1d`（P032-T010 SUCCESS；T011 派发时 HEAD）
- 结论：**13 个验收场景全部覆盖并通过；隐私套件 160 passed；全量 921 passed（基线 761 + 新增 160），零破坏。**
- 验收命令（实测，见 `PRIVACY_TEST_LOG.txt`）：
  - `.venv/bin/python -m pytest -q tests/privacy/` → **160 passed**
  - `.venv/bin/python -m pytest -q` → **921 passed**

## 交付物

| 文件 | 行数 | 说明 |
| --- | --- | --- |
| `src/accepttwin/privacy.py` | 582 | T011 回归层：回环/请求头委托校验、正文上限、日志与报告审计、HTML 自包含扫描、工作区有界清理 |
| `scripts/clean_evidence.py` | 84 | 最小清理命令 CLI（§17.3）；工作区此前无此类命令，本任务新建 |
| `tests/privacy/test_loopback_guard.py` | 213 | 场景 1–3 |
| `tests/privacy/test_redirect_and_proxy.py` | 197 | 场景 4 + 环境代理隔离 |
| `tests/privacy/test_privacy_request_headers.py` | 209 | 场景 5–7 |
| `tests/privacy/test_body_limit.py` | 309 | 场景 8 |
| `tests/privacy/test_log_confidentiality.py` | 277 | 场景 9–10 |
| `tests/privacy/test_html_self_contained.py` | 136 | 场景 11 |
| `tests/privacy/test_cleanup_command.py` | 234 | 场景 12–13 |
| `evidence/Privacy/privacy_scan_49_pages.json` | — | 49 页 HTML 扫描机读结果（0 违规） |
| `evidence/Privacy/PRIVACY_TEST_LOG.txt` | — | `pytest -q tests/privacy/` 实际输出 |

合计：生产代码 666 行，测试 1,575 行（7 个文件，160 个测试）。

## 13 个验收场景逐项覆盖

| # | 验收场景 | 规格锚点 | 测试 | 结果 |
| --- | --- | --- | --- | --- |
| 1 | 公网 IPv4 拒绝 | §5.1.1、§17.4.1–3 | `test_loopback_guard.py`：9 个公网/私网/特殊 IPv4 拒绝（93.184.216.34、8.8.8.8、192.168.1.1、10.0.0.1、172.16.0.1、0.0.0.0 等）；4 个回环 IPv4 接受 | PASS |
| 2 | 公网 IPv6 拒绝 | §5.1.1、§17.4.1–3 | 同文件：5 个非回环 IPv6 拒绝（2606:4700:4700::1111、fe80::1、::、::ffff:93.184.216.34 等）；`[::1]` 接受 | PASS |
| 3 | DNS 解析到非回环拒绝 | §17.4.2 | 同文件：`socket.getaddrinfo` 桩返回公网 IPv4/IPv6、混合回环+公网（fail-closed，整名拒绝）、仅回环接受、真实 `localhost` 解析全回环、不可解析拒绝；全程无真实 DNS、无联网 | PASS |
| 4 | 重定向不跟随 | §0.2.6、§17.4.4 | `test_redirect_and_proxy.py`：真实本地服务器 301 到另一回环地址——返回 301 原样，目标命中 0 次；301 到公网地址——返回 301，本地仅 1 次请求；200 直连对照正常 | PASS |
| 5 | 非白名单请求头拒绝 | §5.1.3、§17.2 | `test_privacy_request_headers.py`：Referer/Origin/Cache-Control/X-*/DNT/Accept-Charset 拒绝；缺失/篡改固定头拒绝；大小写重复头拒绝；精确固定集（html/markdown）接受 | PASS |
| 6 | Authorization 拒绝 | §5.1.3、§17.2 | 同文件：4 种大小写 `Authorization` + `Proxy-Authorization` 均拒绝；且契约 `request_headers` 注入 Authorization 时 `parse_contract` 在加载时拒绝（加载前无任何请求发出） | PASS |
| 7 | Cookie 拒绝 | §5.1.3、§17.2 | 同文件：4 种大小写 `Cookie` 均拒绝；契约加载时注入 Cookie 同样被拒 | PASS |
| 8 | 超过正文大小拒绝 | §17.4.8 | `test_body_limit.py` 三层：①单元 `check_body_size`/`enforce_body_limit`（0/1MiB 边界接受，1MiB+1 拒绝，负数/非整数拒绝）；②分类器：伪造超大观测 → `INCONCLUSIVE_LIMIT` + `INCONCLUSIVE`，对照健康运行 `PASS_OBSERVED`；③实况：冻结 E21 夹具经 `s0_harness` 真实跑通，proxied 请求 `body_size` > 1MiB 全部被判 `INCONCLUSIVE_LIMIT`，且证据中无正文原文 | PASS |
| 9 | 日志不包含正文 | §7.12 I-12、§17.2 | `test_log_confidentiality.py`：扫描器正/负向（原文/Sentinel/短体）；真实 C01 全程运行：`caplog` 零记录（handlers 抑制 `log_message`、全模块无 logger 输出），`run.as_dict()` + 事件序列化无 Sentinel、无禁 key；`assert_log_clean` 不回显泄漏内容 | PASS |
| 10 | 日志不包含敏感请求头 | §17.2、§5.1.3 | 同文件：扫描器检出 4 类敏感头（行格式与 JSON key 格式、大小写不敏感）、干净文本通过；真实 C01 运行记录零敏感头；48 份冻结 JSON 报告 + `REPORTS_SUMMARY.json` 全部 `assert_report_clean` 通过；禁 key 集合与 `report_builder`/`embed_report` 三方一致（交叉断言），Sentinel 字面量与 `contracts/site.json` 一致 | PASS |
| 11 | HTML 不访问远程资源 | §14.4、§17.1 | `test_html_self_contained.py`：`evidence/Reports/html/` 全部 **49 页**逐页扫描，0 违规、0 Sentinel 原文，页数精确钉为 49（C01–C24、E01–E24、index.html）；19 个正向构造逐项触发（link/iframe/img/script src/@import/url()/data:/远程 URL/CDN/字体）；9 个负向构造通过（内联 script、相对链接、回环证据 URL、`redacted:non-loopback`） | PASS |
| 12 | 删除命令能清理指定文件 | §17.3 | `test_cleanup_command.py`：函数级删除指定文件（含相对路径、含 `.`/`..` 的合法路径）+ CLI 级删除与 `--dry-run`（只列不删）；无关文件保留 | PASS |
| 13 | 清理命令不能删除工作区之外的任意路径 | §17.3 | 同文件：工作区外绝对路径、`..` 逃逸、内外符号链接、根目录自身、目录、不存在文件、空列表均拒绝，**受害文件事后逐一断言仍存在**；单坏目标阻塞整批（无部分删除）；CLI 退出码 2 + `REFUSED` | PASS |

附加验证（不在 13 项内，但属 §17.4 边界，复用 T005 基础并独立重验）：
- **环境代理隔离**（§17.4.5）：`HTTP_PROXY/HTTPS_PROXY/http_proxy/https_proxy/ALL_PROXY` 逐个及全部指向死代理 `127.0.0.1:1` 时，本地 GET 仍成功（`test_redirect_and_proxy.py`，6 个测试）。客户端直连 URL 自身 host/port，从不读环境变量。

## 复用的已有基础（未静默重写）

- `url_guard.py`（T002）、`request_headers.py`（T002）：`privacy.py` 仅委托调用并转为 `PrivacyError`，未复制判定逻辑。
- `experiment_runner._http_get`（T005）：重定向不跟随、环境代理禁用均直接对其做真实本地 HTTP 验证，未改动。
- `report_builder`（T009）、`embed_report.py`（T010）：禁 key 集合三方交叉断言；49 页 HTML 为 T010 已冻结产物，本任务只做扫描钉住，未修改任一页。
- `classifier`（T006）：超大正文拒绝走其 `INCONCLUSIVE_LIMIT` 路径（E21 实况），未改动。

## 发现与残留

### F-01（P2 残留，建议 T013/T014 处理）：正文上限未在 socket 读取层执行

- 事实（已实测）：`experiment_runner._http_get` 用 `resp.read()` 无界读取；`_Runner._max_body`（line 372）仅保存、从未被读取。实测：本地源站返回 1,048,577 字节时，`_http_get` 原样返回 1,048,577 字节。
- 现有防线（有效）：分类器按实测 `body_size` 判 `INCONCLUSIVE_LIMIT`（E21 实况通过）；`RawObservation`/`RequestObservation` 只存哈希与大小，正文永不落盘/入日志/入报告；本任务新增 `privacy.enforce_body_limit` 可供后续调用方在持有原始字节时先行拦截。
- 影响评估：低。源站是受控合成源站（本地、非用户提供、无公网），无泄漏发生；风险仅为恶意/故障源站可迫使单次读取分配超限内存。未在本任务内修改 `experiment_runner.py`（T005 归属文件、T011 输出范围外）；修复方案是把有界读取（`resp.read(limit + 1)` 后判超限）或 `enforce_body_limit` 接入 `_http_get`，留待 T013/T014 裁决。
- 不构成验收阻断：验收场景 8 要求的是“超过正文大小拒绝”，系统级行为（分类器拒绝 + 零正文持久化）已由 E21 实况证明。

### F-02（测试设计说明，非缺陷）：扫描器曾对 JS 误报，已修正

- 首轮运行 158/160：`scan_html_for_remote_resources` 把 JS 的 `URL.createObjectURL(blob)` / `URL.revokeObjectURL(url)` 误判为 CSS `url()`。修正：`url()`/`@import` 只在 `<style>` 块与 `style="..."` 属性内扫描（CSS 唯一合法位置），JS 的 blob 下载不再误报；19 个正向构造仍全部触发。修正后 160/160。

### 与规格的张力 / 未解决疑问（均未自行编造）

1. **§17.4.8 未写明上限执行层**：规格只说“正文限制 1 MiB”，未规定在读取层、分类层还是两者执行。本任务按可观测行为验收（超限即拒绝、零持久化），并把读取层缺口记为 F-01，请 T013 裁决是否需要在冻结前补有界读取。
2. **§17.3 未限定清理命令的可删子树**：规格只要求“只能删除工作区内指定的证据/临时文件”且“不能删除工作区之外的任意路径”。本任务实现为“工作区内 + 调用方显式指定 + 常规文件 + 非符号链接”，未再收窄到 `evidence/` 等子目录；收窄与否请 T013/T014 裁决（当前实现满足验收场景 12/13 的字面要求）。
3. **§17.4.6/7（不执行用户 Shell 命令、不启动任意外部程序）**：清理 CLI 全程只用 `pathlib.unlink`，无 `subprocess`/shell；测试中唯一的子进程调用是测试自身启动 CLI（`subprocess.run` 在测试代码内，不在产品/CLI 代码内），合规。
4. **D-03（VERIFY_LOG 残留，诚实边界未集中成单一条款）**：与 T011 无关，未触碰；仍待终审前处理。

## 未修改的文件

冻结规格（`01_project_book/`、`02_implementation_plan/`）、Golden 夹具、schemas、`src/accepttwin/` 其余模块、`evidence/Reports/`、`report-ui/`、其余测试文件：零改动。`git status` 在提交前仅含本任务新增文件（见提交记录）。
