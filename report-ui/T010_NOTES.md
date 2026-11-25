# T010 — 自包含 HTML 报告（P032）

## 交付物

- `report-ui/src/types.ts` — 报告 JSON 类型与冻结实验元数据（§6.1/§6.3）。
- `report-ui/src/timeline.ts` — 双向缓存时间线纯函数（§4.3 区域 C）与双重证据一致性判定（§5.3）。
- `report-ui/src/diagnostics.ts` — 诊断展示与首次错误定位纯函数（§8/§6.3）。
- `report-ui/src/app.ts` — DOM 渲染（十项界面）与启动；全部数据经 `textContent` 插入，绝无 `innerHTML`。
- `report-ui/tsconfig.json` / `report-ui/package.json` / `report-ui/package-lock.json` — TypeScript 5.9.3 精确锁定（离线可装，见下）；`npm run build` 生成 `report-ui/report-ui.js`。
- `report-ui/report-ui.js` — 已提交的编译产物（tsc 单文件输出，无打包器、无运行时依赖）。
- `report-ui/index.html` — 模板：静态页眉/页脚 + 十个空章节 + 三个 JSON 载荷槽 + 内嵌脚本槽；直接打开显示“未嵌入报告数据”说明。
- `report-ui/styles.css` — 全部样式（系统字体栈，无任何外部引用）。
- `scripts/embed_report.py` — 生成器：校验 → 隐私预览（先于写入）→ 扫描 → 写入；`--all-48` 生成 48 页 + 汇总。
- `tests/integration/test_report_ui.py` — 21 个测试（全量 761 passed，基线 740 + 新增 21）。
- `evidence/Reports/html/<sid>.html`（48）+ `evidence/Reports/html/index.html` — 生成的 HTML 报告样本与 48 场景汇总。

## 界面十项与规格映射

| # | 界面项 | 位置 | 规格依据 |
| --- | --- | --- | --- |
| 1 | 最终裁决 | section-verdict | §4.3 区域 A |
| 2 | HTML/Markdown 基线 | section-baseline | §4.3 区域 B |
| 3 | 四种实验状态 | section-experiments | §6（可展开/折叠，§14.4） |
| 4 | 双向时间线 | section-timeline | §4.3 区域 C |
| 5 | 缓存证据 | section-cache | §5.3 双重证据 |
| 6 | 首次错误定位 | section-first-error | §4.3 区域 D、§6.3 |
| 7 | 诊断代码 | section-diagnostics | §4.3 区域 E、§8 |
| 8 | Oracle parity | section-oracle | §12.4 |
| 9 | 报告哈希 | section-hash | §10.4、ADR-003 |
| 10 | 隐私预览 | section-privacy | §4.3 区域 F、§17.3 |

## 设计决定（与规格的张力，如实记录）

1. **TypeScript 而非手写 JS**：§15.3/§16.3 要求前端用 TypeScript。§15.3 的前端模块树在冻结提取中被截断（D-04），只存活了 app.ts / types.ts / timeline.ts / diagnostics.ts 四个名字——本实现恰好采用这四个模块，不补编不存在的模块名。编译用 `tsc --outFile` + `namespace`（无打包器），因为冻结环境中无 bundler；`erasableSyntaxOnly` 未启用（namespace 不是可擦除语法）。TypeScript 5.9.3 已验证可从本机 npm 缓存完全离线安装（`npm install --offline`，731ms），`package-lock.json` 已锁定；`node_modules/` 不提交（见 `.gitignore` 追加）。
2. **基线“预期”值的来源**：报告 JSON（T009 设计）不含 `representations`，因此基线表的预期状态码/Content-Type/Accept 来自 `--contract` 传入的运行契约（只复制 accept / expected_status / expected_content_type 三个安全字段，绝不复制 Sentinel 值），或无契约时取冻结 §5.1.2 常量。已核实 48 份契约的 representations 完全相同，故两种来源结果一致。基线块以独立的第二个 JSON 载荷嵌入，报告 JSON 本身绝不改动。
3. **时间线 RESET 标记**：§4.3 区域 C 的两条时间线以 RESET 开头；报告 JSON 不含重置记录，因此 RESET 在此仅表示“§6.2 实验边界”，页面与 `timeline.ts` 注释中均明确说明，不伪装成观测到的重置事件。
4. **暖缓存“存入”请求不隐藏**：§4.3 区域 C 的 lane 简写只画了冷请求与暖缓存第二请求，但 §6.3 固定序列有 8 个请求；时间线把暖缓存第一次请求（005/007）明确画在冷请求与第二请求之间，lane 标题仍以第二请求的缓存状态为准。不隐藏证据。
5. **缓存键与正文哈希的显示粒度**：时间线/基线/缓存表显示缓存键 SHA-256 与 `body_sha256` 的前 16 位摘要 + `…`（§4.3 区域 C 称“缓存键摘要”）；诊断“证据引用”详情显示完整 64 位哈希。完整哈希同时保留在嵌入的 JSON 与可下载的 JSON 报告中。哈希不是正文（§4.3 区域 F 要求报告含正文哈希，§17.2 允许记录正文哈希），显示完整哈希不构成泄漏。`body_sha256` 同理。
6. **汇总页链接是相对链接**：`index.html` 的 48 个“查看报告”链接为 `C11.html` 形式的相对路径（非远程）；单报告页不含任何链接。下载 JSON 按钮在点击时用 Blob 就地生成，不经过网络。
7. **生成物位置**：生成的 48 页 + 汇总放在 `evidence/Reports/html/`（与 T009 的 JSON 样本同目录），因 T013/T014 预期在此找“HTML 报告样本”。`report-ui/` 只放模板与源码，不放生成物。
8. **诚实边界脚注**：页脚引用 VERIFY_LOG.md D-03 中记录的集中表述（分散在 §3.2/§3.3/§7.11 的实质内容），仅作展示，不替代 D-03 终审前集中成条款的要求。

## 隐私与泄漏控制

- 生成器在写入前做：独立 Schema 校验（复用 T009 的 `independent_schema_validator`，不 import 生成器）、禁 key 大小写不敏感扫描（与 `report_builder._FORBIDDEN_KEYS` 同集合）、Sentinel 原文扫描、输入 URL 回环校验、报告哈希用 `report_builder.compute_report_hash` 重算比对（复用唯一规范化实现，不另写）。
- 成品 HTML 再扫一遍：Sentinel 原文、非回环 http(s) URL、`<link>`/`<iframe>`/`<img>`/`<script src>`/`@import`/`url(`/`data:`；`<script>` 恰好 4 个（3 个 JSON 载荷 + 1 个内嵌 bundle）。
- 报告中唯一的 http(s) URL 是诊断证据里的回环 `request_url` / `redirect_target`（E12/E22 形，后者已脱敏为 `redacted:non-loopback`），扫描按回环 host 白名单放行。
- 诊断消息只含 `'` 特殊字符；即便如此，UI 仍只用 `textContent` 插入数据。

## 重建方法

```bash
cd report-ui && npm install --offline && npm run build   # 生成 report-ui.js
cd .. && .venv/bin/python scripts/embed_report.py --all-48  # 生成 48 页 + 汇总
```

## 验收（2026-11-24）

- `.venv/bin/python -m pytest -q` — **761 passed**（基线 740 + T010 新增 21），0 失败。
- `.venv/bin/python scripts/embed_report.py --all-48` — 49 文件，分布 PASS 16 / ORIGIN 7 / BLEED 8 / CONTRACT 4 / INCONCLUSIVE 13，Oracle parity 48/48；两次运行字节一致（`git status` 干净）。
- 无头 Chromium（Playwright 缓存的 chromium-1255，`--host-resolver-rules` 封锁非回环解析）离线渲染：C11 等五种裁决页十个章节均有内容，首次错误“请求 006”、双重证据、下载按钮均已渲染；汇总页 48 行 + 分布 chips 均已渲染。
- 泄漏扫描：48 页 + 汇总均无 Sentinel 原文、无远程引用（grep 与生成器扫描双重确认）。
- HTML↔JSON 一致性抽查：C11（串版）与 C01（PASS）的嵌入 JSON 与源报告逐字段相等（verdict、诊断、首错、哈希、Oracle parity、观测、输入、理由）。

## 未解决的疑问

- 无。§14.2 报告 JSON 示例截断（D-04）不影响本任务：界面以 §14.3 + §5.8 + T009 的 `report_builder` 实现为准，报告字段均来自实际样本而非截断示例。
- 提醒复核员：`report-ui.js` 是已提交的编译产物，`test_compiled_bundle_matches_typescript_sources` 在本地有 `tsc` 时重编译比对字节；无 `tsc` 的环境只断言内容标记（验收时已亲自重编译比对通过）。
