# 限制与已知问题 (LIMITATIONS.md) — P032 AcceptTwin，T014

本文档如实列出已知限制。**凡未测试的环境一律标 `NOT_TESTED`，
不得推断为通过。**

## 未测试的环境（NOT_TESTED）

| 环境 | 状态 |
| --- | --- |
| Windows（任意版本） | NOT_TESTED |
| macOS（任意版本） | NOT_TESTED |
| Linux（除实测环境外的发行版/内核） | NOT_TESTED |
| Python ≠ 3.12.3 | NOT_TESTED |
| Node.js ≠ 24.22.1 | NOT_TESTED |
| CPU ≠ x86_64 | NOT_TESTED |
| 真实 CDN / 真实网站 / 公网 | NOT_TESTED（且按设计禁止：产品只接受回环地址，见 §0.2） |
| HTTPS 被测资源 | 不支持（§0.2 第 3 条；首版只支持 HTTP） |

实测环境：Linux `7.0.0-44-generic x86_64`、Python 3.12.3、
Node.js 24.22.1、npm 10.9.4、pytest 9.2.0、TypeScript 5.9.3。

## 已知限制（产品行为）

- 只支持本地回环地址（`127.0.0.0/8`、`::1`、`localhost`）与 HTTP
  GET；不跟随重定向；不读取环境代理变量；不发送 Cookie /
  Authorization；请求头集合固定。
- 不实现缓存重新验证（`no-cache` / `max-age=0` 的响应判
  `INCONCLUSIVE`，`limit_code == "revalidation_required"`，ADR-004）。
- `Vary: *` 下代理不存储（BYPASS）是合规行为，不触发 variant
  策略分句（ADR-004，RFC 9111 §4.1）。
- 正文限制 1 MiB：超限正文判 `INCONCLUSIVE_LIMIT`
  （`body_too_large`）；执行层读取自 T014 起有界（两处读取点只
  保留前 `limit + 1` 字节，见 ADR-007 决定 2），精确大小与整段
  哈希仍被测量。
- CLI 提供全部九条 §4.1 命令（`run` / `demo` / `verify --suite` /
  `verify --report` / `report preview` / `report export` /
  `report delete` / `clean --run-id` / `contract delete`，加
  `--help` / `--version` 与 `benchmark`；P1-01 FIX-R1，见
  `00_control/ADR-008.md`，ADR-005 的延期已被取代）。删除命令
  只接受工作区内显式指定的常规文件：`report delete` 限
  `output/` 或 `evidence/Reports/` 下的报告文件，`contract
  delete` 限 `contracts/` 或 `output/` 下的契约文件，`clean`
  限 `output/runs/<RUN_ID>/` 内的平铺文件；工作区外、符号链接、
  目录一律拒绝。清理脚本 `scripts/clean_evidence.py` 仍只接受
  `evidence/` 子树内的目标（见 ADR-007）。
- `npm ci`（全新安装 `report-ui` 依赖）需要访问 npm registry，
  不是离线步骤；干净检出 `npm run build` 会失败（`tsc: not
  found`），离线重建复用已存在的 `node_modules/`（钉死 tsc
  5.9.3，已验证与已提交 `report-ui.js` 字节一致）；冻结重建
  路径见 `docs/INSTALL.md` 与 ADR-007 决定 8。
- 性能门槛（单场景 < 1 秒）在参考 VM 上实测通过；其他机器上
  的耗时未测量，不得直接套用。

## 残留项（来自各任务复核，全部非阻断，留待 T013/T014）

| ID | 内容 | 状态 |
| --- | --- | --- |
| T003 P2-01 | 源站 `Accept` 的 `q=0` 未返回 406 | CLOSED（T014：`_parse_accept` 跳过 q≤0，RFC 9110 §12.5.1；实况测试已补） |
| T003 P2-02 | q 平局规则无测试 | CLOSED（T014：平局“先列出者胜”实况测试已补） |
| T006 P3 | 分类器 `event_support is False` 分支中 `origin_journal_available` 写为 `(origin_events is not None)` 恒为 True | CLOSED（T014：改为字面 True 加注释，无行为变化） |
| T008 P2-2 | revalidation token 解析为精确匹配，`max-age = 0` 与 `no-cache="field"` 双侧均不触发 | CLOSED（T014：RFC 9111 宽容解析，生产与 Oracle 同步；参数化测试已补） |
| T010 P2-1 | `report-ui/T010_NOTES.md` 称 UI 只显示前 16 位哈希摘要，与实现不符（诊断证据详情显示完整 64 位哈希；行为合规，仅措辞） | CLOSED（T014：措辞已修正） |
| T010 P2-2 | `tests/integration/test_report_ui.py:465,492` 两处条件性 `pytest.skip`（无 Chromium 时跳过离线渲染测试） | CLOSED（T014：改为硬失败 `pytest.fail`，CI 须提供 Chromium） |
| T011 F-01 | `experiment_runner.py:301` 的 `_http_get` 用无界 `resp.read()`；`_max_body` 只赋值从未被读取。超限正文只在进程内存中短暂存在、随即丢弃，哈希与大小是唯一持久化物，无泄漏路径；但故障源站可迫使单次超限分配。**不在 T012 范围内**（`experiment_runner.py` 禁止 T012 修改，修复属 T013/T014） | CLOSED（T014：有界流式读取，见 ADR-007 决定 2） |
| T011 P2 | 清理命令可删子树未收窄：实现为“工作区内 + 显式指定 + 常规文件 + 非符号链接”，满足 §17.3 字面要求，但未收窄到 `evidence/` 等子目录；操作者显式点名即可删除工作区内任意常规文件（含源码） | CLOSED（T014：脚本默认只接受 `evidence/` 子树，CLI 帮助与文档明示；见 ADR-007 决定 7） |
| T012 P2-1 | 项目书 §4.1 其余 CLI 命令未落地（`demo`/`run`/`report preview/export/delete`/`clean`/`contract delete`，`verify --report` 形式亦无） | CLOSED（FIX-R1 P1-01：九条命令全部落地并真实执行，见 ADR-008；ADR-005 延期作废） |
| T012 P2-2 | `docs/USAGE.md` 引用 `/tmp/t012_verify.log`（构建者本机临时日志） | CLOSED（T014：改引已提交 `evidence/Performance/VERIFY_LOG.txt`） |
| T013-F01 | 端口交换契约哈希碰撞：`url`/`origin_url` 互换端口的两份契约哈希相同 | ACCEPTED（T014：见 ADR-007 决定 1——角色占位经实测证明无效，碰撞为 §10.4 所强制；钉住测试已加。**该哈希表示的是忽略端口值后的语义契约身份，不是完整的实际端点身份。**） |
| T013-F02 | Oracle parity 只比 verdict+诊断投影+first_error，未直接比对逐请求 verified MISS/HIT/BYPASS 状态 | CLOSED（T014：parity 加宽至逐请求状态；生产侧为分类器确认态，见 ADR-007 决定 3） |
| T013-F03 | 干净检出 `npm run build` 失败（`tsc: not found`，`node_modules` 未提交，`npm ci` 需 registry） | CLOSED（T014：冻结重建路径写入 `docs/INSTALL.md` 与 ADR-007 决定 8） |
| T013-F04 | F-01 无界读取不止一处：`cache_proxy.py:761` 的 `_fetch_origin` 同样无界 `resp.read()` | CLOSED（T014：与 F-01 同一有界读取 helper，见 ADR-007 决定 2） |
| T013-F05 | Oracle 以生产 runner 的 `verified_cache_state` 为声称状态（双腿均重算，fail-closed，但存在耦合） | CLOSED（T014：声称改取原始状态头，HIT 系缚改用 Oracle 自身确认态；见 ADR-007 决定 4） |
| D-03 | 诚实边界未集中成单一条款（实质分散在 §3.2/§3.3/§7.11） | CLOSED（T014：集中条款见 `00_control/ADR-006.md`） |
| D-01 | GPT 称 §19–§21“此前已存在”与交付记录不符（内容已补齐，仅供终审知悉） | 已登记，无行动 |
| D-04–D-08 | 规格长代码块/图表提取截断标注、frontmatter 不完整、§5.1.2 JSON 按字段表写出等 | 已标注，随规格移交 |
| T007 重审残留 | T007 修复重审 PASS，未登记新的残留项；已知张力为 ADR-003 的端口归一化解释（§10.4“不包含动态端口”不限于 `ephemeral_port` 字段，`url`/`origin_url` 的回环端口同样归一化为 0） | 已裁决（ADR-003），无 OPEN 项 |

## 规格引用张力（T012 发现，如实标注）

- 项目书 §4.1 冻结的 CLI 命令契约包含 `demo` / `run` /
  `report preview` 等命令，实施计划 T012 任务卡只要求落地
  `verify --suite all` 与 `benchmark --suite all`；T014 按任务卡
  交付两条命令、其余按 ADR-005 延期。FIX-R1 P1-01 已按 §4.1
  把其余命令全部补齐（见 ADR-008），本张力已消除。
- T012 任务卡引用的 `npm run oracle:parity` 在补全回复中被截断，
  无法确认其完整命令串；本版本不虚构该命令，Oracle parity 由
  `verify`/`benchmark` 内的 `run_oracle`（Node 直接执行
  `oracle/src/index.ts`）覆盖，`oracle/package.json` 本身也未定义
  `oracle:parity` 脚本。
- 实施计划 §6 的 T012 输出列表在页面提取中截断（VERIFY_LOG D-06）；
  本版本按任务卡正文与 §18 验收标准交付
  `tests/performance/`、`docs/`、`evidence/Performance/` 及 CLI，
  未补写截断的输出项。
