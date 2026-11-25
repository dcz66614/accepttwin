# T009 — JSON Schema、Canonical JSON 与报告生成（P032）

## 交付物

- `schemas/accepttwin.report.v1.schema.json` — 正式报告 Schema
  （JSON Schema Draft 2020-12，`accepttwin.report/v1`）。
- `src/accepttwin/report_builder.py` — `build_report` /
  `compute_report_hash`（§5.8 / §14）。
- `src/accepttwin/canonical_json.py` — thin re-export：只从
  `accepttwin.contract` 导入并重新导出 `canonical_json_bytes` /
  `canonical_contract_hash`，无第二份规范化实现（单一来源，ADR-003）。
- `tests/unit/independent_schema_validator.py` — 独立最小 Schema
  校验器（只读 Schema 文件，只用标准库，不 import 任何生产模块）。
- `tests/unit/test_report_builder.py`、`tests/unit/test_report_schema.py`
  — 验收测试（T009 新增 152 个；全量 715 个，见下）。
- `scripts/build_reports_48.py` — 从 `evidence/Golden/` 真实记录
  生成 48 个报告样本。
- `evidence/Reports/<sid>.json`（48 个）+ `REPORTS_SUMMARY.json`。

## 报告结构（§14.2 合成示例已截断，按 §14.3 + §5.8 + T007 的
## canonical_report 雏形设计）

顶层：`schema` / `project` / `scenario_id` / `input`（`contract_id`、
`contract_sha256`、`url`、`origin_url`、`cache_behavior`、固定
`request_headers`）/ `observations`（8 条，§5.5 形状，只含
`origin_counter_delta`，不含绝对计数）/ `diagnostics`（§8 全量
evidence）/ `verdict` / `first_error` / `first_error_experiment_id` /
`critical_count` / `warning_count` / `reasons` / `oracle` /
`oracle_parity` / `final` / `report_hash`。

## 报告哈希（§10.4，ADR-003）

`report_hash = SHA256(canonical_json_bytes(hash payload))`，其中
hash payload = 报告去掉 `report_hash` 本身，再去掉
`REPORT_HASH_EXCLUDED_FIELDS`（`cache_key_sha256`、
`cache_entry_id`、`origin_counter_before`、`origin_counter_after`、
`request_url`、`redirect_target`）。排除理由：缓存键材料就是带
临时端口的 origin URL（`cache_key_for`），键哈希无法被归一化；
entry id 由键派生；绝对计数遵循 T007 `canonical_report` 先例只
留 delta；`request_url` / `redirect_target` 带有临时端口。
`url` / `origin_url` 的端口由 `canonical_json_bytes` 归一化为 0
（ADR-003）。报告本身保留这些证据字段（§8 要求，§4.3 区域 C
需要缓存键摘要），只不进入哈希。换端口哈希不变已由测试钉住；
重建 48 样本字节一致。

## 隐私与脱敏（§7.12、§8.6、§14.3）

- 报告不含任何正文原文字段与敏感请求头：`build_report` 在输入
  与最终报告两层做全深度禁 key 扫描（`body` / `body_text` /
  `response_body` / `authorization` / `cookie` /
  `proxy-authorization` / `set-cookie`），命中即报 `ReportError`。
- `redirect_target`：非回环目标一律记为固定标记
  `redacted:non-loopback`（E22 的 `http://example.com/doc` 已脱敏）；
  回环目标保留原文（E12）。
- 报告不含时间戳、耗时、进程号、临时路径、随机 ID。

## Oracle 与 final（§4.2 约束 6、§12.4）

只有提供了 Oracle 结果且与生产在 verdict、诊断投影（code +
request_index）、首次错误位置三项上一致时，`oracle_parity=true`
且 `final=true`。无 Oracle 时 `oracle=null`、`oracle_parity=null`、
`final=false`——不用生产自证最终有效。

## 校验独立性

`report_builder` 没有任何 `validate` 方法。校验只由
`tests/unit/independent_schema_validator.py` 执行：它只读 Schema
文件，不 import `report_builder`。48 样本全部经它校验通过；另有
手写最小合法报告与 30 项变异拒绝测试钉住校验器本身。

## CLI 归属判定：属于 T012，不是 T009

- §4.2 文件归属：T009 只拥有 `report_builder.py`（与按文件分配
  的 schemas/）；`__main__.py` / `cli.py` 未分配给 T009。
- T012 验收命令同时要求 `python -m accepttwin verify --suite all`
  与 `python -m accepttwin benchmark --suite all`，且要求 CLI
  `--help` 与 T012 拥有的 INSTALL/USAGE/LIMITATIONS 文档一致；
  两个子命令同属一个 CLI 文件，按 §4.2“同一文件同一时间只允许
  一个任务修改”，该文件只能归一个任务——即 T012。
- 因此 T009 未新建 CLI。供 T012 调用的可 import verify 逻辑已存在
  且已验证可导入：`scripts/run_all_48.py:run_all()`（48 场景执行 +
  Oracle 对账，返回 summary dict）与 `scripts/run_s0.py:run_all()`；
  测试 `test_verify_entry_point_importable_for_t012` 钉住该导入。
- 后果：`PYTHONPATH=src .venv/bin/python -m accepttwin verify
  --suite all` 在 T009 完成后仍无法运行（无入口模块，见下验收
  记录）；**T008 P2-1 仍未关闭，待 T012 落地 CLI 后补跑**。

## 验收

- `.venv/bin/python -m pytest -q tests/unit/test_report_builder.py
  tests/unit/test_report_schema.py` — 152 passed。
- `.venv/bin/python -m pytest -q` — 715 passed（T008 的 563 +
  T009 新增 152），0 failed。
- `.venv/bin/python scripts/build_reports_48.py` — REPORTS_STATUS:
  PASS（Schema 48/48、verdict 与记录一致 48/48、Oracle parity
  48/48；裁决分布 PASS 16 / INCONCLUSIVE 13 / BLEED 8 / ORIGIN 7 /
  CONTRACT 4，与 §11.3 一致）。
- `PYTHONPATH=src .venv/bin/python -m accepttwin verify --suite all`
  — 仍失败（`No module named accepttwin.__main__`），属预期：CLI
  待 T012。未为通过验收而造假命令。

## 再生成样本

`.venv/bin/python scripts/build_reports_48.py`（只读
`evidence/Golden/`，不重跑实验；重复运行输出字节一致）。
