# T008 交接说明（扩展 Golden 与 48 场景集成）

- 48/48 Golden 通过，48/48 Oracle parity（`ALL48_SUMMARY.json`：`ALL48_STATUS: PASS`）。
- S0 24 条重跑仍通过（`scripts/run_s0.py` S0 PASS 24/24 + `scripts/verify_s0.py` 19/19）。

## 未按任务卡第二条验收命令执行的原因

任务卡验收命令之二 `python -m accepttwin verify --suite all` 目前无法运行：
`src/accepttwin/` 中尚无 CLI 入口（那是 T009/T012 的交付物）。本次**没有**
为通过验收而新建 CLI。等价验收为：`pytest -q tests/golden/`（见下）+
重跑 `scripts/run_s0.py` 与 `scripts/verify_s0.py`（S0 仍 PASS）+
`scripts/run_all_48.py`（48/48，证据见 `evidence/Golden/`）。
该命令待 T009/T012 落地后补跑。

## 注入场景清单（harness 层代理子类真实 HTTP 行为注入，生产代码不动）

| 场景 | 注入 kind | 机制 |
| --- | --- | --- |
| E12 | `proxy_returns_local_redirect` | 全部代理 GET 答 301，Location 指回环 origin URL，不接触源站 |
| E22 | `proxy_returns_external_redirect` | 全部代理 GET 答 301，Location 为 `http://example.com/doc`（合成夹具地址），不接触源站 |
| E20 | `proxy_lies_miss_with_stash_replay` | 第 4 个代理 GET（006）重放 004 观测到的 Markdown 正文，不接触源站（计数 +0），头称 MISS |
| E21 | `proxy_returns_oversize_body` | 全部代理响应正文补齐到 1 MiB + 1 字节，Sentinel 保留；存储条目保留原正文 |
| E23 | `proxy_rewrites_html_content_type` | 代理 HTML 响应 Content-Type 改写为 text/markdown，正文不变（C24 的 HTML 镜像） |
| E24 | `proxy_corrupts_warm_second_sentinel` | 暖缓存第二请求（006、008）返回正文的 Sentinel 字节被替换；存储条目保留正确正文 |
| E17 | —（`opaque` 代理模式） | 同 C20 |
| E18 | `origin_events_unavailable`（裁决输入层空日志） | 同 C21：空元组，非 None |
| E19 | `proxy_lies_hit_on_warm_second` | 同 C22 |

其余 E 场景无注入（源站夹具 / 代理模式自然产生）。

## 与 §11.3 原文的一处措辞说明

E03 原文写“第二请求 MISS”；按 §5.3，MISS 要求“缓存条目在本次
响应后被建立”，而 `Vary: *` 下代理依法不存储任何条目，诚实的
§5.3 标签是 BYPASS（条目数恒为 0，证据见 `evidence/Golden/E03/`）。
裁决不受影响：PASS_OBSERVED。依据见 `00_control/ADR-004.md` Decision 1。

## T003 遗留 P2-01 / P2-02：留待 T014

q=0 未返回 406、q 平局规则无测试——与 E01–E24 无关（执行器只发
不带 q 值的固定 Accept 头），本次不实现、不加测试，留待 T014。
依据见 `00_control/ADR-004.md` Deferred 节。

## 生产代码改动（ADR-004）

- `src/accepttwin/origin_server.py`：场景语言扩展（Vary 字面值 /
  字段名大小写 / Cache-Control），新增 7 个源站夹具。
- `src/accepttwin/diagnostics.py` + `src/accepttwin/classifier.py`：
  `Vary: *` 豁免 variant 分句；`no-cache` / `max-age=0` 触发
  §8.6 `revalidation_required`。
- `oracle/src/evidence.ts` + `oracle/src/oracle.ts`：上述两条规则
  的独立 TS 实现（不读生产结论、不 import 生产代码）。
- `scripts/s0_harness.py`：泛化加载/建对/运行（S0 默认行为不变，
  强制调用约定调用点原文未动）+ 6 个新注入代理类；新增
  `scripts/run_all_48.py`。
- 未修改：`fixtures/s0/`（冻结）、冻结规格文件、Oracle 独立性。
