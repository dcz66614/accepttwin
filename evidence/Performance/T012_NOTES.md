# T012 交付笔记 — 性能、重复性、离线与文档（2026-11-24）

## 结论

T012 完成定义 10 项全部达成（见下“验收结果”）。T008 P2-1
（CLI 不存在）关闭：`python -m accepttwin verify --suite all` 与
`benchmark --suite all` 均可运行且通过。

## 验收结果（全部为本次交付内的真实运行）

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 48/48 Golden | PASS | `evidence/Golden/ALL48_SUMMARY.json` |
| 48/48 Oracle parity | PASS | 同上 |
| S0 24/24 重跑 | PASS（含 repeat-100 distinct=1、串版 3/3） | `evidence/S0/S0_SUMMARY.json` |
| `verify --suite all` | exit 0，`VERIFY_STATUS: PASS` | `evidence/Performance/VERIFY_LOG.txt` |
| 单场景 < 1s | 最大 0.040s，中位 0.0156s（限值 1.000s） | `evidence/Performance/BENCHMARK_SUMMARY.json` |
| repeat-100 唯一哈希 | distinct=1，`67e69e68…e62acde`（与 T007 修复后记录的 C01 哈希一致），最大单次 0.0494s | 同上 |
| Canonical JSON 无非确定性字段 | 扫描通过（`generated_at`/`duration_ms`/`process_id`/`temporary_path`/`ephemeral_port`/`timestamp`/`uuid`/`random` 均无），哈希重算一致 | 同上（`canonical_json_free_of_nondeterministic_fields: true`） |
| 离线运行 | `OFFLINE_VERIFY: PASS`（新网络命名空间：外部连接失败如预期；全量 pytest 936 passed；S0 PASS；报告生成；HTML 导出 49 页；`npm run build`；全新 venv 离线安装 + `--help`/`--version`） | `evidence/Performance/OFFLINE_LOG.txt`（脚本 `offline_verify.sh`） |
| `npm run build`（冻结锁文件） | PASS，离线完成，`report-ui.js` 与提交版字节一致 | 同上 |
| HTML 自包含 | 49 页，0 违规；裁决/首次错误/哈希与 JSON 逐页一致 | `BENCHMARK_SUMMARY.json`（`html.clean: true`） |
| JSON Schema | 48/48 有效，裁决 48/48，parity 48/48 | `evidence/Reports/REPORTS_SUMMARY.json` |
| 隐私检查 | 48 份正式报告 `assert_report_clean` 通过；HTML 目录扫描干净 | benchmark 交叉检查 |
| 文档齐备 | README、INSTALL、USAGE、LIMITATIONS（命令与 `--help` 逐字一致，测试断言） | `README.md`、`docs/` |
| 全量测试 | **936 passed，0 failed**（T011 基线 921 + T012 新增 15） | `evidence/Performance/T012_TEST_LOG.txt` |

## 设计决定

- CLI（`src/accepttwin/cli.py` + 薄 `__main__.py`）只做委托：
  `verify` 调 `scripts/run_s0.py` / `scripts/run_all_48.py`，
  `benchmark` 调 `run_all_48` + `s0_harness.run_scenario`（repeat-100）
  + `build_reports_48` + `embed_report --all-48` + `privacy` 扫描；
  规范化哈希只用 `accepttwin.contract.canonical_json_bytes`。
  无第二套 Golden 执行、分类、报告生成逻辑。
- CLI 只提供 `verify` / `benchmark`（+ `--help`/`--version`）。
  项目书 §4.1 的其余命令（`demo`/`run`/`report preview` 等）未以
  占位形式冒充，见 `docs/LIMITATIONS.md`。
- `pyproject.toml` 增加 `[project.scripts]`（`accepttwin` 控制台
  命令）与 `readme = "README.md"`（README 现已存在，T002 的暂缓
  注释随之移除）。包须先 `pip install -e .` 进 `.venv`，
  `python -m accepttwin` 才能按字面工作（交付时已装好并验证）。
- T009 的交接测试（`test_verify_entry_point_importable_for_t012`）
  原断言“CLI 文件必须不存在”，T012 按其自身 docstring 的预期
  将其翻转为“CLI 存在且可委托”；除此一处外无已有断言改动。

## 交付中发现并已处理的问题

1. **派生证据失同步（已修复，留作流程记录）**：`verify --suite
   all` 重跑 48 场景会用新端口重写 `evidence/Golden/`，而
   `evidence/Reports/` 是派生文件，不重建即失同步，导致
   `test_committed_samples_match_generator[C01/C11/E22]` 失败
   （首次全量：3 failed / 933 passed）。修复：重跑
   `build_reports_48.py` + `embed_report.py --all-48` 后 3 项通过，
   最终全量 936 passed。`benchmark` 内部已含重建步骤，跑完即同步；
   流程说明已写入 `docs/USAGE.md`“证据同步说明”。这不是产品缺陷。
2. **执行风险提示（无实际拒绝）**：`pip install -e .` 的返回中
   出现 execution-risk 检查提示文字，但命令 exit 0 正常完成，
   无任何操作被拒绝；按 AGENTS.md 2026-11-20 记录的教训，以实际
   exit 码为准继续工作，未停工、未另行请示。特此记录。

## 未解决 / 留待 T013/T014

- T011 F-01（`experiment_runner.py:301` 无界读取）未修复：
  不属 T012（文件禁止修改），见 `docs/LIMITATIONS.md`。
- 其余残留项见 `docs/LIMITATIONS.md`（T003 P2-01/P2-02、T006 P3、
  T008 P2-2、T010 P2-1/P2-2、T011 清理子树 P2、D-03 等）。
- 与规格的张力见 `docs/LIMITATIONS.md`“规格引用张力”一节：
  §4.1 其余 CLI 命令未落地；`npm run oracle:parity` 命令串在
  补全回复中截断、无法确认，未虚构；T012 输出列表本身截断
  （D-06），按任务卡正文与 §18 交付。
