# P032 AcceptTwin — FIX-R1 独立审查索引（REVIEW_INDEX.md）

- 审查对象 commit：`221f902798a245b7a2672f3a53a9a63ab176e014`（tag `P032-v1.0.1`，FIX-R1 重冻结，规格 v1.0.1）
- 上一冻结：`d3bee545d8d42b4f4da3fc48bb0a2f514cdbfa7f`（tag `P032-v1.0.0`，R1 评审对象，FINAL_VERDICT: FAIL）
- 本索引生成：2026-11-24 ~21:14 GMT，由重冻结执行者从 tag 的 git 对象重生成审查包；审查包内容与 tag 逐字节一致（核对方法见下）。
- 冻结规格 SHA（核对一致）：`01_project_book/PROJECT_BOOK.md` 82,148 B，SHA-256 `1e5f32bdd8200a5fd56e86cdef64c22a1731e2d9656342ea18f27298e0afd8f2`；`02_implementation_plan/IMPLEMENTATION_PLAN.md` 54,476 B，SHA-256 `7e846fab376dd55c6177f304ed28339b1687996db99015a2b35354ee8f13b2ba`
- 结论：**本索引只证明审查包与冻结 tag 的可追溯性，不代替独立审查。** T013 独立审查报告（见下）审查的是 `c02387c`，不是本 tag；FIX-R1 的三项 P1 与四项 P2 各自由独立复核员审查（见“FIX-R1 差异与独立复核”一节），R2 终审由主聊天另行安排。

## 审查包文件清单

| 文件 | 内容 | SHA-256 |
| --- | --- | --- |
| `REVIEW_INDEX.md`（本文件） | 审查对象、范围、FIX-R1 差异、门禁实测结果、发现汇总 | 见下“本索引文件哈希” |
| `REVIEW_PACK_01.md` | 生产源码 `src/accepttwin/` 全部 17 个文件，全文 + SHA-256（352,679 B） | `66f13d4cb54eff53fb1f6dffc54a7671b6948e31ab643e5d5ca432930c790e0b` |
| `REVIEW_PACK_02.md` | Oracle（4 个 TS + package/tsconfig）、`scripts/` 全部 7 个脚本、report-ui 源码与配置、schemas、contracts/site.json、pyproject/LICENSE/THIRD_PARTY_NOTICES/README/docs、ADR-001–ADR-009、P1_03_SOURCES.md、GIT_LOG_T014.txt，共 44 个文件，全文 + SHA-256（353,026 B） | `d386b747725fe48bc1e48a51b955ab4c8940fb8b27f00f4d2814ac010bd50e3f` |
| `REVIEW_PACK_03.md` | 全部 Golden 夹具（fixtures/s0 24 + fixtures/extended 24 + fixtures/origin 15 + fixtures/contracts 2）与全部测试（tests/ 32 个文件），共 95 个文件，全文 + SHA-256（464,674 B） | `7c73102e16cbddba41b3af1d88283b6baa92aa9b19b89422c9fc857aff943986` |
| `SOURCE_FILE_MANIFEST.md` | 审查对象 tag 下全部 970 个已跟踪文件的 SHA-256 清单 | `06a26caa81614096e95ed1efa9afdcfd1dcd69332c5ab05b28c1f87e942d2ff6` |
| `INDEPENDENT_REVIEW.md` | T013 独立审查报告全文（历史记录，审查对象 `c02387c`，不是本 tag；原文保留，未改动） | `b9b52415bc77c10dc7daf6bf3ead6a716e37ddfd5aa551c2e4adf3de695503f7` |
| `FINDINGS.json` | T013 的 16 项发现机读清单（历史记录，0 P0 / 0 P1 / 15 P2 / 1 P3；原文保留，未改动） | `24bd6cf10311abcc9a697842ad6d2b3694bc0d5e4a76529256e60786cd9da1c9` |

包内源码哈希核对：审查包由脚本从 tag 的 git 对象生成（`git show P032-v1.0.1:<path>`），生成器 `/tmp/p032_freeze/build_packs_v101.py`；随后用独立核对脚本 `/tmp/p032_freeze/verify_release_v101.py` 逐节重核：156/156 节 SHA-256 与字节数与 `git show P032-v1.0.1:<path>` 一致，0 处不符；SOURCE_FILE_MANIFEST.md 970/970 行一致；`RELEASE_MANIFEST.json` 的 `files[]` 165/165 与 `source.zip` 内文件一致，`samples` 98/98 与磁盘文件一致，ZIP 条目集合与 tag 树（除 `evidence/`、`00_control/competitive_gate/`、`.gitignore`、`08_release/`）一致。

审查报告与发现清单的文件哈希（T013 交付时；本索引自身的哈希须在提交后核对，因文件内含哈希值故无法自举）：

- `INDEPENDENT_REVIEW.md`：`b9b52415bc77c10dc7daf6bf3ead6a716e37ddfd5aa551c2e4adf3de695503f7`
- `FINDINGS.json`：`24bd6cf10311abcc9a697842ad6d2b3694bc0d5e4a76529256e60786cd9da1c9`

## FIX-R1 差异与独立复核（d3bee54 → 221f902）

`git diff --name-only d3bee54..P032-v1.0.1` 共 483 个文件，其中 416 个是 `evidence/` 下重跑再生的记录证据（差异仅临时端口、端口派生缓存键、HTTP 日期与耗时；裁决、诊断、parity、实况报告哈希均未变）。非 `evidence/` 的 67 个文件：

- **P1-01（CLI，commit 55ad6bc）：** `src/accepttwin/cli.py`、`tests/integration/test_cli_commands.py`、`tests/fixtures/contracts/custom-healthy.json`、`custom-bleed.json`、`00_control/ADR-008.md`、`README.md`、`docs/USAGE.md`、`docs/LIMITATIONS.md`、`docs/INSTALL.md`；顺手 P2-01：`scripts/verify_s0.py`、`tests/unit/test_verify_s0_parity.py`。独立复核 **PASS**（f7d726bf）：九条命令全部真实跑通，59 项新测试全过，全量 1024 passed + 2 端口环境失败；重冻结时端口重跑已变绿（1026 passed，0 failed）。
- **P1-02（T001 门禁，commit d5fa420 + 1be77fb）：** `00_control/competitive_gate/` 下 5 份门禁文件更新 + `evidence/fix-r1/` 28 个新增证据文件。独立复核 **FAIL（窄口径）**（7358f41c）：实质全部通过，仅两处文本错误；修复员更正后由主协调员亲自核对（commit 1be77fb）。门禁文件见下节。
- **P1-03（规格占位，commit 2cefa36）：** `01_project_book/PROJECT_BOOK.md` + `.docx`、`02_implementation_plan/IMPLEMENTATION_PLAN.md` + `.docx`、`00_control/ADR-009.md`、`P1_03_SOURCES.md`、`00_control/split_specs.py`、`00_control/VERIFY_LOG.md`、`docs/LIMITATIONS.md`、`00_control/ADR-007.md`、`08_release/RELEASE_NOTES.md`、`HOW_TO_REPRODUCE.md`；顺手 P2-02/P2-04。独立复核 **PASS**（8f70bda8）：占位 0 处，溯源抽查 6/6，DOCX 标题 104/104 与 63/63。
- **升版 v1.0.1（commit 0290be2）：** `src/accepttwin/report_builder.py`（生成器 `project.version`）、`schemas/accepttwin.report.v1.schema.json`（const）、`tests/unit/test_report_builder.py`、`test_report_schema.py`、两份规格正文 7 处版本串、`README.md`；48 份报告样本 + 49 页 HTML 由正规生成器重生成（逐文件差异仅 `project.version` 与 `report_hash`）；`PROJECT_BOOK.docx` 重生成（104/104 标题，0 占位）。产品版本仍为 1.0.0（pyproject、`__version__`、User-Agent）。
- **门禁重跑与证据再生（commit 221f902）：** `evidence/Golden/`、`evidence/S0/`、`evidence/Reports/`、`evidence/Performance/BENCHMARK_SUMMARY.json` 由 `verify --suite all` + `benchmark --suite all` 实况重跑再生；`docs/USAGE.md` 实测值更新；`00_control/ADR-009.md` 升版执行补记；`00_control/PROJECT_STATE.md` 规格版本 v1.0.1；`.gitignore` 增加 `08_release/*.bundle`。

## T001 竞争差异化门禁证据（R1 P1-02，本轮补交）

以下五份文件随本发布包归档于 Google Drive（`RELEASE_MANIFEST.json` 的 `gate_evidence` 节含同一组哈希），不属于 `source.zip`（设计排除，见清单 `source_zip.excludes`），但全部在冻结 tag 内，可用 `git show P032-v1.0.1:<path>` 核对：

| 文件 | 字节 | SHA-256 |
| --- | --- | --- |
| `00_control/competitive_gate/T001_COMPETITIVE_GATE.md` | 44,110 | `85d8dd966e7e3f720d0713bef880dec8bc9ed4f77514298d4a8b44d7d109a2ed` |
| `00_control/competitive_gate/comparison_matrix.csv` | 561 | `3eb5a2037e87ef284c7ba450a602a9f41a5c9e7068029a621dd678c956cda234` |
| `00_control/competitive_gate/tool_versions.json` | 9,009 | `d4fcfc9d290d721594a6e8a21f34b6309fcae5bc120c087b4cad6006a85774fe` |
| `00_control/competitive_gate/commands.log` | 19,752 | `f5b4b19659501a4d2f65fcb42b75c72c0ab998765556eeb1f72099238450f125` |
| `00_control/competitive_gate/decision.json` | 6,981 | `4c33898d22507a2f195a223f4ac62c64b8cc6ddba8de10dd6c9755c6bee04fee` |

裁决：**CONTINUE**（STOP 未触发；EQ08 五类全 NO，无一工具八项全 FULL）。支撑证据子目录 `00_control/competitive_gate/evidence/`（28 个 fix-r1 文件 + T001 原始克隆的 cache-tests 仓库）保留在 git 内，不上传 Drive。

## 亲自执行的验收命令（重冻结执行者，主工作区，冻结 commit 干净树）

| 命令 | 结果 |
| --- | --- |
| `git rev-parse HEAD` / `git rev-parse P032-v1.0.1` | `221f902798a245b7a2672f3a53a9a63ab176e014`（两者一致） |
| `git status --short`（冻结前） | 干净 |
| `.venv/bin/python -m pytest -q` | **1026 passed，0 failed，0 skipped，84.54s**，exit 0 |
| `.venv/bin/python -m accepttwin verify --suite all` | VERIFY_STATUS: PASS（ALL48 48/48 golden、parity 48/48；S0 24/24 golden、parity 24/24；C11 串版 3/3；repeat-100 distinct_hashes=1；C01 实况哈希 67e69e68… 不变） |
| `.venv/bin/python -m accepttwin benchmark --suite all` | BENCHMARK_STATUS: PASS（max 单场景 0.0408s；repeat-100 distinct=1；schema 48/48；HTML 49 页 clean 0 违规；裁决 16/7/8/4/13） |
| `.venv/bin/python scripts/verify_s0.py` | 19/19 PASS |
| `bash evidence/Performance/offline_verify.sh` | OFFLINE_VERIFY: PASS |
| `npm run build`（report-ui） | exit 0，TypeScript 5.9.3，`report-ui.js` SHA-256 `784e3106f7a380845559690dfa04aa4f8549f0d044bf5edea66ee2aefec9c84d`，与提交版字节一致 |
| 端口重跑（P1-01 复核待办） | `test_default_ports_from_site_contract` 与 `test_default_port_matches_contract_origin_url`：2 passed（0.24s）；`accepttwin run --contract contracts/site.json` 默认端口（18765/18766）：exit 0，RUN_STATUS: COMPLETE（PASS_OBSERVED，parity True） |
| `python3 -m zipfile -t 08_release/source.zip` | OK；165 文件 + 26 目录；SHA-256 `b82cb7303b00ddbc9b195dfb3deea8b1108d5cded55c2876fa610330b0dd68a3`；603,654 B |
| `sha256sum -c SHA256SUMS.txt`（08_release/ 内） | source.zip: OK；RELEASE_MANIFEST.json: OK |
| 独立核对脚本 `/tmp/p032_freeze/verify_release_v101.py` | 8 项全部 PASS（156 节包哈希、970 行清单、165 文件 ZIP↔清单、98 样本、ZIP 条目集合、5 门禁文件） |

## 实际路径映射（T013 任务卡所列路径 vs 冻结源码树实际路径）

与 T013 索引一致，无缺失、无改名；新增：`tests/fixtures/contracts/custom-healthy.json`、`custom-bleed.json`（P1-01 自定义契约）、`tests/integration/test_cli_commands.py`（48 项）、`tests/unit/test_verify_s0_parity.py`（11 项）、`00_control/ADR-008.md`、`ADR-009.md`、`P1_03_SOURCES.md`。

## 残留说明

- T013 的 16 项发现已全部处置（见 `RELEASE_MANIFEST.json` `findings`）；其中 T012 P2-1 在 FIX-R1 由延期改为**已修复**（ADR-008 取代 ADR-005）。
- 唯一接受残留：T013-F01 端口交换契约哈希碰撞（ADR-007 决定 1）。
- 两个 C01 报告哈希并存仍是 T009 既有设计：实况运行哈希 `67e69e68…`（不变，harness 约简哈希不含 `project`）与报告样本哈希 `4645e340…`（v1.0.1 新值，正式哈希含 `project.version`）。
- `IMPLEMENTATION_PLAN.md` 无 frontmatter（D-05 原决定保留）；其 v1.0.0 字样均为冻结历史/格式示例，不改。
- 本索引文件自身的哈希须在提交后核对（文件内含哈希值，无法自举）。
