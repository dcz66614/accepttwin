# 使用指南 (USAGE.md) — P032 AcceptTwin，T012

本文档的命令与实际 CLI `--help` 输出逐字一致（`tests/performance/test_cli.py`
逐项断言）。凡与 `--help` 不符处，以 `--help` 为准。

## 验收命令

```bash
.venv/bin/python -m accepttwin verify --suite all
.venv/bin/python -m accepttwin verify --suite s0
.venv/bin/python -m accepttwin demo
.venv/bin/python -m accepttwin run --contract contracts/site.json
.venv/bin/python -m accepttwin verify --report output/runs/demo-healthy/report.json
.venv/bin/python -m accepttwin benchmark --suite all
.venv/bin/python -m pytest -q
```

## `run`

```text
usage: accepttwin run [-h] --contract CONTRACT [--scenario SCENARIO]
                      [--proxy-mode {respect_vary,force_uri_only,manual_accept_key,disabled,opaque,ignore_no_store}]
                      [--scenario-id SCENARIO_ID] [--run-id RUN_ID]
                      [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --contract CONTRACT   contract JSON file (accepttwin.contract/v1, loopback
                        URLs only)
  --scenario SCENARIO   synthetic origin scenario: a name under
                        fixtures/origin/ or a path to a scenario JSON file
                        (default: healthy)
  --proxy-mode {respect_vary,force_uri_only,manual_accept_key,disabled,opaque,ignore_no_store}
                        controlled proxy mode (§10.3); default follows the
                        contract: variant_by_accept -> respect_vary, no_store
                        -> disabled
  --scenario-id SCENARIO_ID
                        report scenario_id label (C01-C24 / E01-E24); default
                        follows the S0 configuration table for a known
                        (origin scenario, proxy mode) pair
  --run-id RUN_ID       run id (output directory under output/runs/; default:
                        the contract_id)
  --output OUTPUT       report JSON path (default: output/runs/<run-id>/
                        report.json; sibling evidence files land next to it)
```

跑一份用户自己的双表示契约：真实执行冻结四实验（8 个真实 HTTP
请求）、生产分类、独立 Oracle 对账、正式 `accepttwin.report/v1`
报告。Oracle parity 在 harness 与 report builder 两处各算一次，
两处不一致时 fail-closed，不出报告。输出默认写到
`output/runs/<run-id>/`（`run-id` 默认 = `contract_id`）：
`report.json`、`raw-observations.json`、`contract.json`、
`production.json`、`oracle-input.json`、`oracle.json`、
`run-summary.json`。`--output` 可改报告路径，兄弟证据文件随之
落在其旁。

- 契约端口用契约文件写明的端口（须为空闲回环端口；被占用时
  报错退出 1，不静默换端口）。`demo` 用临时端口，无此要求。
- `--scenario` 是合成源站场景（`fixtures/origin/` 下的名字，
  如 `healthy`、`no_vary`、`html_404`，或场景 JSON 文件路径），
  不是 Golden 编号；`--proxy-mode` 是受控代理模式（§10.3）。
  健康契约 + `force_uri_only` 代理就是故意复现串版的办法。
- 报告的 `scenario_id` 标签：冻结的 v1 报告 Schema 只接受
  `C01–C24 / E01–E24`，因此用户运行按其复现的 Golden **配置**
  标注（映射表：healthy+respect_vary → C01、healthy+disabled →
  C05、healthy+force_uri_only → C11、healthy+ignore_no_store →
  C19、healthy+opaque → C20、no_vary+manual_accept_key → C03、
  no_vary+respect_vary → C13、no_vary+force_uri_only → C15、
  no_vary+disabled → C17、html_404 → C07、markdown_404 → C08、
  html_wrong_content_type → C09、markdown_sentinel_missing →
  C10；未列入映射表的配置必须显式传 `--scenario-id`）。该标签
  记录的是配置，不是 Golden 身份；运行的真实身份是
  `contract_id` + `contract_sha256` + run-id，见同目录的
  `run-summary.json`（见 `00_control/ADR-008.md`）。
- 退出码：0 = 运行完成且 Oracle parity 成立、报告 `final=true`
  （裁决本身是数据：真实的 `REPRESENTATION_BLEED` 发现仍退出
  0）；1 = parity 不一致或基础设施失败；2 = 输入错误（文件缺
  失、契约非法、非回环 URL、未知场景、非法 `--scenario-id` /
  `--run-id`）。

示例（两个自定义契约，见 `tests/fixtures/contracts/`，均非 Golden
重放——自有 contract_id 与自有回环端口，真实跑通全流程）：

```bash
# 健康：PASS_OBSERVED，8 条观测全 MISS，Oracle parity，final=true
.venv/bin/python -m accepttwin run --contract tests/fixtures/contracts/custom-healthy.json
# 串版：同一份健康契约改走 URI-only 代理 → REPRESENTATION_BLEED，first_error=6
.venv/bin/python -m accepttwin run --contract tests/fixtures/contracts/custom-bleed.json --proxy-mode force_uri_only
```

## `demo`

```text
usage: accepttwin demo [-h]

options:
  -h, --help  show this help message and exit
```

用自带的 `contracts/site.json` 模板跑两次（均用临时回环端口，
不占用固定端口）：健康（C01 配置，`respect_vary`，期望
`PASS_OBSERVED`）与故意串版（C11 配置，同一份契约改走
`force_uri_only` 代理，期望 `REPRESENTATION_BLEED`、
first_error=6）。两次都做 Oracle parity 并导出 HTML，输出在
`output/runs/demo-healthy/` 与 `output/runs/demo-bleed/`。
`DEMO_STATUS: PASS` 当且仅当两边裁决都符合预期、两边 parity 都
成立、两份 HTML 都已导出；否则退出 1。

## `verify --report`

```text
usage: accepttwin verify [-h] [--suite {s0,all}] [--report REPORT]
                         [--contract CONTRACT]

options:
  -h, --help           show this help message and exit
  --suite {s0,all}     suite to verify: s0 (C01-C24 + repeat-100) or all (48
                       scenarios + S0 re-run) (default: all)
  --report REPORT      verify one formal report JSON file instead of re-
                       running a suite (Schema + hash + privacy + Oracle
                       parity/final)
  --contract CONTRACT  with --report: also check the report's contract_sha256
                       against this contract file
```

`--suite` 与 `--report` 互斥。`verify --report` 核验一份正式报告
文件（独立 Schema 校验 + 报告哈希重算 + 隐私扫描 + Oracle
parity/final），不重新跑实验；`--contract` 可再核对报告的
`contract_sha256`。退出 0 = 报告已验证为真实一致（裁决本身不
决定退出码：一份有效的 `REPRESENTATION_BLEED` 报告仍退出 0）；
退出 1 = 报告无效、哈希不符或 parity 不成立；退出 2 = 文件缺失
或契约非法。

## `report preview` / `report export` / `report delete`

```text
usage: accepttwin report preview [-h] [--contract CONTRACT] report
usage: accepttwin report export [-h] [--contract CONTRACT] [--out OUT]
                                [--check-only]
                                report
usage: accepttwin report delete [-h] report
```

- `preview`：打印隐私预览（§4.2 约束 7：预览先于导出）与人类可读
  摘要（裁决、首次错误、诊断、8 条请求、缓存状态、报告哈希），
  **不写任何文件**。
- `export`：先打印隐私预览，再导出自包含离线 HTML（§14.4；
  默认写到报告旁的 `<report-stem>.html`，`--out` 可改）；
  `--check-only` 只校验与预览，不写文件。导出的页面经远程引用
  与 Sentinel 字面值扫描，任一命中即失败。
- `delete`：只删 `output/` 或 `evidence/Reports/` 下、JSON
  `schema` 为 `accepttwin.report/v1` 的文件；其他文件、工作区外、
  符号链接、目录一律拒绝（退出 2，什么都不删）。

## `clean`

```text
usage: accepttwin clean [-h] --run-id RUN_ID [--dry-run]
```

删除一次运行的输出文件（`output/runs/<RUN_ID>/` 内的平铺常规
文件，删完移除空目录）。目录不存在、是符号链接、或内含符号链
接/子目录时整批拒绝（退出 2，什么都不删）；`--dry-run` 只列出、
不删除。`scripts/clean_evidence.py` 仍是 `evidence/` 子树的脚本
清理入口，两者边界不同，不互相替代。

```bash
.venv/bin/python -m accepttwin clean --run-id demo-bleed --dry-run
.venv/bin/python -m accepttwin clean --run-id demo-bleed
```

## `contract delete`

```text
usage: accepttwin contract delete [-h] contract
```

只删 `contracts/` 或 `output/` 下、JSON `schema` 为
`accepttwin.contract/v1` 的文件；其他文件、工作区外、符号链接、
目录一律拒绝（退出 2，什么都不删）。

## 退出码总表

| 退出码 | 含义 |
| --- | --- |
| 0 | 命令成功（`run`/`demo` 要求 Oracle parity 成立且报告 `final=true`；`verify --report` 要求报告有效且 parity 成立） |
| 1 | 门禁/核验失败（parity 不一致、报告无效、基础设施失败、demo 预期不符） |
| 2 | 输入错误或拒绝删除（参数错误、文件缺失、契约非法、非回环 URL、越权删除） |

## `verify`

```text
usage: accepttwin verify [-h] [--suite {s0,all}]

options:
  -h, --help        show this help message and exit
  --suite {s0,all}  suite to verify: s0 (C01-C24 + repeat-100) or all (48
                    scenarios + S0 re-run) (default: all)
```

- `--suite s0`：重跑 S0 门禁——C01–C24 全部真实执行、Oracle parity
  24/24、串版 C11 独立复现 3/3、repeat-100（C01，每次全新服务与端口）
  唯一哈希。证据写到 `evidence/S0/`（`S0_SUMMARY.json`）。
- `--suite all`（默认）：先跑 48 场景全套（`evidence/Golden/`，
  `ALL48_SUMMARY.json`），再重跑 S0 全套。退出码 0 当且仅当两边
  均为 PASS。
- 每次运行都重新启动源站与代理、重新发送全部 8 个真实 HTTP 请求；
  不读缓存的历史报告。

## `benchmark`

```text
usage: accepttwin benchmark [-h] [--suite {all}]

options:
  -h, --help     show this help message and exit
  --suite {all}  suite to benchmark (default: all)
```

依次做四件事，全部为本次调用内的真实运行：

1. 跑 48 场景，记录每场景实验耗时（限值 1 秒，见 §10.5；报告生成
   时间不计入单场景时间）。
2. C01 重复 100 次（每次全新服务与端口），核对规范化报告哈希唯一，
   并扫描首份规范化 JSON 是否含时间戳、临时目录、进程 ID、随机
   UUID、动态端口、耗时等非确定性字段（§10.4）。
3. 用 `scripts/build_reports_48.py` 从新鲜 Golden 证据重建 48 份
   `accepttwin.report/v1` 报告并独立校验 Schema。
4. 用 `scripts/embed_report.py --all-48` 导出 49 页自包含 HTML，
   再用 `accepttwin.privacy` 扫描全目录，并逐页核对裁决、首次错误
   与报告哈希与 JSON 一致。

汇总写到 `evidence/Performance/BENCHMARK_SUMMARY.json`。

## 实测结果（本机，2026-11-24，见证据文件）

| 项目 | 实测 |
| --- | --- |
| `verify --suite all` | 48/48 Golden、48/48 Oracle parity、S0 24/24 重跑通过（日志 `evidence/Performance/VERIFY_LOG.txt`，证据 `evidence/Golden/ALL48_SUMMARY.json`、`evidence/S0/S0_SUMMARY.json`） |
| `benchmark --suite all` | `BENCHMARK_STATUS: PASS`，总耗时 20.57s |
| 单场景耗时 | 最大 0.041s，中位 0.0146s，最小 0.0080s（限值 1.000s） |
| repeat-100 | C01 哈希唯一：`67e69e68e128441b67fae155ac1af8dbb4e7992b4dfe70db7dcef1f04e62acde`（与 T007 修复后记录的 C01 哈希一致），最大单次 0.0266s |
| 报告 Schema | 48/48 有效，裁决 48/48 一致，parity 48/48 |
| HTML | 49 页，0 违规；裁决/首次错误/哈希与 JSON 逐页一致 |
| 全量测试 | `.venv/bin/python -m pytest -q`（见下） |

## 测试

```bash
.venv/bin/python -m pytest -q                    # 全量
.venv/bin/python -m pytest -q tests/performance/ # 仅 T012 性能与 CLI 测试
.venv/bin/python -m pytest -q tests/golden/      # 仅 48 Golden
.venv/bin/python -m pytest -q tests/privacy/     # 仅隐私与安全回归
```

全量测试数以实际运行输出为准：T012 交付时 **936 passed、0 failed**
（T011 基线 921 + T012 新增 15），日志见
`evidence/Performance/T012_TEST_LOG.txt`；离线复核同样 936 passed，
见 `evidence/Performance/OFFLINE_LOG.txt`。FIX-R1 P1-01 + P2-01
交付时全量 **1026 项：1024 passed、2 failed**（2026-11-24 实测，
84 秒）；新增 59 项全部通过（`tests/integration/
test_cli_commands.py` 48 项 + `tests/unit/test_verify_s0_parity.py`
11 项）。2 项失败是既存环境原因，与本次改动无关：
`test_default_ports_from_site_contract` 与
`test_default_port_matches_contract_origin_url` 绑定契约默认端口
18765/18766，而当时该端口正被并行通道的进程占用。**重冻结时已
复核通过**：端口空闲后重跑这两项，2 passed（0.24s）；另跑
`accepttwin run --contract contracts/site.json` 默认端口运行，
exit 0，`RUN_STATUS: COMPLETE`（PASS_OBSERVED，parity True）；
随后全量重跑 **1026 passed、0 failed、0 skipped**（84.54s），
两项端口测试均在内（基线 967 的口径不变）。

## 其他脚本（不在 CLI 内，按原路径使用）

```bash
.venv/bin/python scripts/run_s0.py          # S0 门禁（verify --suite s0 的实现）
.venv/bin/python scripts/run_all_48.py      # 48 场景（verify --suite all 的实现）
.venv/bin/python scripts/build_reports_48.py # 48 份正式 JSON 报告
.venv/bin/python scripts/embed_report.py --all-48   # 49 页 HTML 导出
.venv/bin/python scripts/embed_report.py evidence/Reports/C11.json --check-only  # 导出前隐私预览
.venv/bin/python scripts/clean_evidence.py --dry-run evidence/Privacy/PRIVACY_TEST_LOG.txt  # 清理（见 §17.3）
```

## 证据同步说明

`verify --suite all`（及 `scripts/run_all_48.py`）会用新端口重跑
全部 48 场景并重写 `evidence/Golden/`；而 `evidence/Reports/`
是派生文件，只在 `build_reports_48.py` 运行时才与当前 Golden
同步。因此**单独跑完 `verify` 后，须再跑一次
`build_reports_48.py` + `embed_report.py --all-48`**，否则
`test_committed_samples_match_generator` 会因端口不同而失败——
这是派生证据的固有次序，不是产品缺陷。`benchmark` 内部已包含
重建与导出两步，跑完即同步。

项目书 §4.1 冻结的九条 CLI 命令已全部落地（P1-01 FIX-R1，见
`00_control/ADR-008.md`）：`run`、`demo`、`verify --report`、
`report preview/export/delete`、`clean`、`contract delete`，外加
原有的 `verify --suite` 与 `benchmark`。ADR-005 的延期决定已被
ADR-008 取代，不再有效。删除命令的安全边界见上文各节与
`docs/LIMITATIONS.md`；`scripts/clean_evidence.py` 仍只接受
`evidence/` 子树内的目标（见 ADR-007）。
