# AcceptTwin — 网页双态镜 (P032)

> Your website serves humans and AI. Make sure it never mixes them up.

同一 URL 对浏览器返回 HTML、对 AI 返回 Markdown。AcceptTwin 在本地验证：
网站是否**从不把两种表示混淆**——用真实本地 HTTP 请求、四种实验
（两个独立冷请求 + HTML→Markdown、Markdown→HTML 两个暖缓存实验）、
缓存 MISS/HIT/BYPASS 双重证据、五种确定性裁决、48 组固定 Golden，
并用独立 TypeScript Oracle 逐场景对账。

- 规格：`01_project_book/PROJECT_BOOK.md` v1.0.1（冻结）
- 实施计划：`02_implementation_plan/IMPLEMENTATION_PLAN.md`
- 许可证：MIT（见 `LICENSE`；第三方依赖见 `THIRD_PARTY_NOTICES.md`）

## 快速开始

```bash
# 1. 安装（需要 Python 3.12；见 docs/INSTALL.md）
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .            # 生产包，零运行时依赖
.venv/bin/python -m pip install -e ".[dev]"     # 再加 pytest（测试用）

# 2. 验收命令（全部为真实本地运行，无网络、无真人、无收费 API）
.venv/bin/python -m accepttwin verify --suite all
.venv/bin/python -m accepttwin benchmark --suite all
.venv/bin/python -m pytest -q

# 3. 跑你自己的契约（P1-01 已落地，见 docs/USAGE.md）
.venv/bin/python -m accepttwin demo   # 健康 + 故意串版，各跑一次并导出 HTML
.venv/bin/python -m accepttwin run --contract contracts/site.json
.venv/bin/python -m accepttwin verify --report output/runs/demo-healthy/report.json
```

## CLI

```text
usage: accepttwin [-h] [--version] COMMAND ...

AcceptTwin (P032): same URL, two representations — verify delivery is never
mixed up. Local-only, offline, no real users.

positional arguments:
  COMMAND
    run       run one user contract end to end (real experiments + Oracle
              parity + formal report)
    demo      run the bundled example contract twice: healthy (PASS) then a
              deliberate bleed (REPRESENTATION_BLEED), with HTML export
    verify    re-run the Golden gate live (48 scenarios + Oracle parity;
              --suite all also re-runs S0 24/24), or verify one formal report
              file (--report)
    report    preview, export or delete a formal report JSON file
    clean     delete one run's output files under output/runs/<RUN_ID>
    contract  manage stored contracts
    benchmark
              measure per-scenario time (<1s), repeat-100 determinism, and re-
              validate reports + self-contained HTML

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit
```

子命令帮助（逐字引自实际 `--help` 输出，见 `docs/USAGE.md`）：

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

```text
usage: accepttwin benchmark [-h] [--suite {all}]

options:
  -h, --help     show this help message and exit
  --suite {all}  suite to benchmark (default: all)
```

其余子命令：`accepttwin demo`（无参数）、`accepttwin report preview <报告>`、
`accepttwin report export <报告>`、`accepttwin report delete <报告>`、
`accepttwin clean --run-id <RUN_ID>`、`accepttwin contract delete <契约>`，用法与示例见
`docs/USAGE.md`。退出码：0 = 命令成功（`run`/`demo` 要求 Oracle parity 成立且报告
`final=true`；报告裁决本身是数据，不决定退出码）；1 = 门禁/核验失败；2 = 输入错误或
拒绝删除。

## 验收命令

| 命令 | 通过标准 |
| --- | --- |
| `.venv/bin/python -m accepttwin verify --suite all` | 48/48 Golden、48/48 Oracle parity、S0 24/24 重跑通过（含 repeat-100） |
| `.venv/bin/python -m accepttwin verify --suite s0` | S0 24/24、parity 24/24、串版 3/3 复现、repeat-100 唯一哈希 |
| `.venv/bin/python -m accepttwin demo` | 健康 `PASS_OBSERVED` + 故意串版 `REPRESENTATION_BLEED`，两份报告均 Oracle parity 且均已导出 HTML |
| `.venv/bin/python -m accepttwin run --contract contracts/site.json` | 真实四实验 + Oracle parity + 正式报告写到 `output/runs/<contract_id>/` |
| `.venv/bin/python -m accepttwin benchmark --suite all` | 单场景 < 1 秒、100 次重复唯一规范化报告哈希、48/48 Schema 有效、49 页 HTML 自包含且与 JSON 一致 |
| `.venv/bin/python -m pytest -q` | 全量测试通过（见 `docs/USAGE.md` 的实测数） |

## 文档

- 安装：`docs/INSTALL.md`
- 使用：`docs/USAGE.md`
- 限制与未测试环境：`docs/LIMITATIONS.md`（未测试的环境一律标 `NOT_TESTED`，不推断为通过）

## 诚实边界

本工具只证明“在给定双表示契约、受控缓存与有界场景内，网站按声明
交付了正确的表示”。它**不**证明真实 CDN 行为、**不**修复缓存、**不**
认证网站的 AI 友好度、**不**保证任何真实网站的交付正确；没有
`Vary: Accept` 本身不是故障证据。完整限制见 `docs/LIMITATIONS.md`。
集中条款见 `00_control/ADR-006.md`（D-03，终审前已集中成单一条款；
规格原文仍分散在 §3.2/§3.3/§7.11，ADR-006 为唯一集中表述）。
