#!/usr/bin/env python3
"""P032 AcceptTwin 规格拆分脚本（逐字拼装，不发明内容）。

输入：~/workspace/P032_SPECS.md（主回复 PARTIAL）
      ~/workspace/P032_SPECS_SUPPLEMENT.md（补全回复）
      ~/workspace/P032_SPECS_CLARIFY.md（追问回复）
输出：~/workspace/p032-accepttwin/01_project_book/PROJECT_BOOK.md
      ~/workspace/p032-accepttwin/02_implementation_plan/IMPLEMENTATION_PLAN.md

规则：
- 主回复逐字取用；补全/追问回复按任务书指定的位置替换或追加。
- 页面提取截断处只保留已取回部分，缺失处标注页面提取截断占位标记（P1-03 已退役该标记，见 00_control/ADR-009.md）。
- 任何锚点未命中即报错退出，不静默跳过。
"""
import re
import sys
from pathlib import Path

WS = Path.home() / "workspace"
OUT = WS / "p032-accepttwin"
MARK = ""  # P1-03（2026-11-24）：截断占位标记已退役，规格中的 58 处占位已全部补齐；本脚本为一次性拆分工具，不再用于生成规格。

main = (WS / "P032_SPECS.md").read_text(encoding="utf-8")
supp = (WS / "P032_SPECS_SUPPLEMENT.md").read_text(encoding="utf-8")
clar = (WS / "P032_SPECS_CLARIFY.md").read_text(encoding="utf-8")

# ---------- 主回复：去头、去缩进、拆两文件 ----------
mlines = main.split("\n")
assert mlines[0].startswith("# P032 SPECS — PARTIAL"), mlines[0]
assert mlines[6] == "---", repr(mlines[6])
body = mlines[8:]  # 从第 9 行（GPT 回复开头）起
body = [ln[4:] if ln.startswith("    ") else ln for ln in body]
split_idx = next(i for i, ln in enumerate(body) if ln.startswith("文件二：IMPLEMENTATION_PLAN.md："))
pb_lines = body[:split_idx]
ip_lines = body[split_idx:]
while pb_lines and not pb_lines[-1].strip():
    pb_lines.pop()
while ip_lines and not ip_lines[-1].strip():
    ip_lines.pop()
assert pb_lines[0].startswith("P032 AcceptTwin 网页双态镜——方向已锁定"), pb_lines[0][:40]
assert pb_lines[2].startswith("外部证据核验结果："), pb_lines[2][:20]
assert pb_lines[4].startswith("文件一：PROJECT_BOOK.md（页面代码块显示的 frontmatter 开头为："), pb_lines[4][:30]
assert pb_lines[-1].startswith("§18 验收指标："), pb_lines[-1][:20]
assert ip_lines[0].startswith("文件二：IMPLEMENTATION_PLAN.md：本文件是施工任务合同"), ip_lines[0][:30]
assert ip_lines[-1].startswith("T012 — 性能、重复性、离线与文档"), ip_lines[-1][:20]

# 每节一行：§1..§18 在 pb_lines 的偶数位（扣除前 6 行：preamble/blank/evidence/blank/文件一/blank）
sec_lines = {}
for ln in pb_lines:
    m = re.match(r"§(\d+) ", ln)
    if m:
        sec_lines[int(m.group(1))] = ln
assert sorted(sec_lines) == list(range(1, 19)), sorted(sec_lines)

ip_sec_lines = {}
for ln in ip_lines:
    m = re.match(r"§(\d+) ", ln)
    if m:
        ip_sec_lines[int(m.group(1))] = ln
assert sorted(ip_sec_lines) == list(range(0, 7)), sorted(ip_sec_lines)

task_lines = {}
for ln in ip_lines:
    m = re.match(r"(T0\d\d) — ", ln)
    if m:
        task_lines[m.group(1)] = ln
assert sorted(task_lines) == [f"T{str(i).zfill(3)}" for i in range(1, 13)], sorted(task_lines)


def split_head(line: str, prefix: str) -> tuple[str, str]:
    """把 '§N 标题：正文' 拆成 (标题, 正文)；prefix 为 '§N ' 或 'T0NN — '。"""
    assert line.startswith(prefix), (prefix, line[:40])
    rest = line[len(prefix):]
    idx = rest.find("：")
    assert idx > 0, line[:80]
    return rest[:idx], rest[idx + 1:]


def split_subsections(body_text: str, subs: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """按 [(编号, 标题)] 顺序把正文切成 [(编号, 标题, 内容)]；编号含 '§N' 或 'N.N'。
    找不到的标记直接报错。第一个小节之前的引言作为 ('', '', intro)。"""
    chunks = []
    rest = body_text
    for num, title in subs:
        marker = f"{num} {title}"
        pos = rest.find(marker)
        assert pos >= 0, f"subsection marker not found: {marker!r} in {rest[:60]!r}"
        assert rest.count(marker) == 1, f"marker not unique: {marker!r}"
        head, rest = rest[:pos], rest[pos + len(marker):]
        # 去掉标记后的 '：'
        if rest.startswith("："):
            rest = rest[1:]
        chunks.append((num, title, head))
    chunks.append((subs[-1][0], subs[-1][1], rest)) if False else None
    # 上面循环把每段的“之前文本”当作上一段的 head 存入；重组为正确结构：
    out = []
    # chunks[i] = (num_i, title_i, text_before_marker_i)
    # 段 i 的内容 = text_before_marker_{i+1}（对最后一段是 rest）
    for i, (num, title, head) in enumerate(chunks):
        if i == 0:
            if head.strip():
                out.append(("", "", head))
        else:
            prev_num, prev_title, _ = chunks[i - 1]
            out.append((prev_num, prev_title, head))
    out.append((subs[-1][0], subs[-1][1], rest))
    return out


def render_section(heading: str, body_text: str, subs: list[tuple[str, str]],
                   level: int = 2) -> str:
    parts = [f"{'#' * level} {heading}"]
    for num, title, content in split_subsections(body_text, subs):
        content = content.strip()
        if not content:
            continue
        if num:
            parts.append(f"\n### {num} {title}\n\n{content}")
        else:
            parts.append(f"\n{content}")
    return "\n".join(parts) + "\n"


def clean_truncation_notes(text: str) -> str:
    """把剩余的页面截断类括号标注统一换成标准标记（§1 摘要与 §3 节点摘要除外，
    它们是内容描述而非截断标注，保留原样并在 VERIFY_LOG 中登记）。"""
    text = re.sub(r"（页面[^）]*?(?:截断|未完整展开|只展开)[^）]*）", MARK, text)
    return text


# ---------- 补全回复：提取各段 ----------
slines = supp.split("\n")
def sup_slice(start_anchor: str, end_anchor: str | None) -> list[str]:
    i = next(i for i, ln in enumerate(slines) if ln.startswith(start_anchor))
    if end_anchor is None:
        j = len(slines)
    else:
        j = next(i for i, ln in enumerate(slines) if ln.startswith(end_anchor))
    out = slines[i:j]
    while out and not out[-1].strip():
        out.pop()
    return out

# T012 补全：行 16-38（验收标准续、验收命令、完成定义、失败回退）
t012_supp = sup_slice("验收标准（续）：", "7. T013 — 独立代码审查")
assert t012_supp[0] == "验收标准（续）："
assert t012_supp[-1].startswith("失败回退："), t012_supp[-1][:20]
# T013：行 40-57；T014：行 58-77
t013_supp = sup_slice("7. T013 — 独立代码审查", "8. T014 — 修复、最终门禁与 Release Freeze")
t014_supp = sup_slice("8. T014 — 修复、最终门禁与 Release Freeze", "二、PROJECT_BOOK.md §18")
assert t013_supp[-1].startswith("失败回退：")
assert t014_supp[-1].startswith("失败回退：")
# §18 干净表：行 81-93
s18 = sup_slice("| AC01 |", "以上指标均为冻结的验收要求")
assert s18[0].startswith("| AC01 |") and s18[-1].startswith("| AC11 |"), (s18[0][:30], s18[-1][:30])
s18_note = "以上指标均为冻结的验收要求，不是已完成测试的声明。"
# §5.1.2 / §5.2 / §14.1 / §14.2 / §15 / §4.2 / §4.3 / §0.5 片段
s512 = sup_slice("1. §5.1.2 双表示字段的完整 JSON：", "2. §5.2 cache_behavior")
s52 = sup_slice("2. §5.2 cache_behavior 的完整示例 JSON：", "3. §10.2 算法步骤完整列表")
s141 = sup_slice("4. §14.1 核心数据对象完整内容", "5. §14.2 报告 JSON 示例完整内容")
s142 = sup_slice("5. §14.2 报告 JSON 示例完整内容", "6. §15 系统架构 ASCII 图")
s15 = sup_slice("6. §15 系统架构 ASCII 图", "7. §4.2 用户主流程图完整文字")
s42 = sup_slice("7. §4.2 用户主流程图完整文字", "8. §4.3 区域 D")
s43 = sup_slice("8. §4.3 区域 D", "四、IMPLEMENTATION_PLAN.md §0.5")
s05 = sup_slice("四、IMPLEMENTATION_PLAN.md §0.5", "完整性说明：")

# ---------- 追问回复：提取 §10.2 与 §19–§21 ----------
clines = clar.split("\n")
def cl_slice(start_anchor: str, end_anchor: str | None) -> list[str]:
    i = next(i for i, ln in enumerate(clines) if ln.startswith(start_anchor))
    if end_anchor is None:
        j = len(clines)
    else:
        j = next(i for i, ln in enumerate(clines) if ln.startswith(end_anchor))
    out = clines[i:j]
    while out and not out[-1].strip():
        out.pop()
    return out

s102_steps = cl_slice("以下 25 个步骤按执行顺序冻结", "二、PROJECT_BOOK.md §19–§21")
assert s102_steps[0].startswith("以下 25 个步骤按执行顺序冻结")
assert s102_steps[1].startswith("1. ValidateContract"), s102_steps[1][:30]
assert s102_steps[25].startswith("25. HTMLWarmSecond"), s102_steps[25][:30]
assert s102_steps[26].startswith("执行顺序特别约束：")
assert s102_steps[27].startswith("说明：这 25 步是 HTTP 实验核心序列")
s19 = cl_slice("19. 最终交付物", "20. 参考网址与来源")
s20 = cl_slice("20. 参考网址与来源", "21. 规格冻结声明")
s21 = cl_slice("21. 规格冻结声明", "三、T013-B 章节引用核对")
assert s19[0] == "19. 最终交付物" and s20[0] == "20. 参考网址与来源" and s21[0] == "21. 规格冻结声明"

# ---------- PROJECT_BOOK.md 组装 ----------
pb = []
pb.append("文件一：PROJECT_BOOK.md\n")
pb.append("以下为完整项目书，版本 1.0.0。\n")
pb.append("PROJECT_BOOK.md\n")
pb.append("---\nproject_id: P032\nslug: accepttwin\nname: AcceptTwin（网页双态镜）\ndocument: PROJECT_BOOK\nspec_version: 1.0.0\n---\n")
pb.append("注：frontmatter 余下字段在页面提取中截断，未取回全文。\n")
pb.append("# P032 AcceptTwin（网页双态镜）项目书\n副标题：同一网址，两种表示，验证交付是否正确\nREADME 一句话：> Your website serves humans and AI. Make sure it never mixes them up。\n")
pb.append(pb_lines[0].strip() + "\n")   # 方向已锁定 preamble
pb.append(pb_lines[2].strip() + "\n")   # 外部证据核验结果

# §1：仅有页面提取摘要，逐字保留并登记为 MINOR（见 VERIFY_LOG D-02）。
# 注意：该行第一个全角冒号在括号注记内部，不能用通用 split_head 切分。
assert sec_lines[1].startswith("§1 产品定位与一句话价值（页面显示该节主要为前文的命令示例：")
t1 = "产品定位与一句话价值"
b1 = sec_lines[1][len("§1 产品定位与一句话价值"):]
pb.append(f"## §1 {t1}\n\n{b1.strip()}\n")

# §2
t2, b2 = split_head(sec_lines[2], "§2 ")
pb.append(render_section(f"§2 {t2}", b2, [
    ("2.1", "E01-A RFC 9110 — HTTP Semantics"),
    ("2.2", "E02 Firecrawl Issue #5956"),
    ("2.3", "E03 Cloudflare Markdown for Agents"),
    ("2.4", "最接近的开源和商业方案"),
]))

# §3
t3, b3 = split_head(sec_lines[3], "§3 ")
pb.append(render_section(f"§3 {t3}", b3, [
    ("3.1", "MVP 目标"), ("3.2", "明确非目标（不实现）"), ("3.3", "双层成功定义"),
]))

# §4（含 §4.2 / §4.3 补全）
t4, b4 = split_head(sec_lines[4], "§4 ")
# 先把 §4.2 的“（页面流程图文字）”标注去掉（转录注记，非规格内容）
b4 = b4.replace("4.2 用户主流程（页面流程图文字）：", "4.2 用户主流程：")
chunks4 = split_subsections(b4, [("4.1", "产品入口"), ("4.2", "用户主流程"), ("4.3", "UI 页面")])
parts4 = [f"## §4 {t4}"]
for num, title, content in chunks4:
    content = content.strip()
    if not content:
        continue
    if num == "4.2":
        # 主回复流程图只取回到“启动合成源站与缓存代理”，其余流程步骤未取回
        # （主回复的截断标注由 clean_truncation_notes 统一换成标准标记）
        frag42 = "\n".join(s42[1:])  # 跳过标题行“7. §4.2 …”
        content = content + "\n\n补全回复取回的流程约束（完整）：\n\n" + frag42.split("流程约束：", 1)[1].strip()
    if num == "4.3":
        frag43 = "\n".join(s43[1:])
        content = content + "\n\n补全回复取回的片段与首次错误定位规则（完整）：\n\n" + frag43
    parts4.append(f"\n### {num} {title}\n\n{content}" if num else f"\n{content}")
pb.append("\n".join(parts4) + "\n")

# §5（含 §5.1.2 / §5.2 替换）
t5, b5 = split_head(sec_lines[5], "§5 ")
chunks5 = split_subsections(b5, [
    ("5.1", "契约文件"), ("5.1.1", "URL"), ("5.1.2", "双表示字段"),
    ("5.1.3", "请求头集合"), ("5.2", "缓存行为声明 cache_behavior"),
    ("5.3", "缓存 MISS/HIT/BYPASS 的精确定义"), ("5.4", "冷缓存与暖缓存的精确定义"),
])
parts5 = [f"## §5 {t5}"]
for num, title, content in chunks5:
    content = content.strip()
    if not content:
        continue
    if num == "5.1.2":
        # 用补全回复的字段表写出完整 JSON（任务书规则 3）；字段含义与冻结规则逐字取自补全回复
        assert s512[0].startswith("1. §5.1.2"), s512[0][:30]
        assert s512[2].startswith("字段含义："), s512[2][:20]
        assert s512[3].startswith("冻结规则："), s512[3][:20]
        content = (
            "HTML 和 Markdown 各自必须具备以下字段（完整 JSON，字段值据补全回复字段表写出；"
            "页面原 JSON 代码块未完整取回）：\n\n"
            "```json\n"
            '{"representations": {"html": {"accept": "text/html", "expected_status": 200, '
            '"expected_content_type": "text/html; charset=utf-8", "sentinel": "AT_HTML_SENTINEL_001"}, '
            '"markdown": {"accept": "text/markdown", "expected_status": 200, '
            '"expected_content_type": "text/markdown; charset=utf-8", "sentinel": "AT_MARKDOWN_SENTINEL_001"}}}\n'
            "```\n\n"
            + s512[2] + "\n\n" + s512[3] + "\n\n"
            "Sentinel 必须：在对应合成正文中存在；HTML 与 Markdown 使用不同值；"
            "不与另一个表示的 Sentinel 相同；不依赖自然语言语义识别；"
            "采用精确字节匹配；不使用 LLM 判断正文是否正确。"
        )
    if num == "5.2":
        # 补全回复的完整示例 A/B + 取值 + 特别说明，保留主回复的模式描述
        frag52 = "\n".join(s52[1:])
        assert "示例 A：按 Accept 区分缓存" in frag52 and "示例 B：不存储" in frag52
        content = frag52.strip() + "\n\n主回复的模式描述（保留）：\n\n" + content
    parts5.append(f"\n### {num} {title}\n\n{content}" if num else f"\n{content}")
pb.append("\n".join(parts5) + "\n")

# §6
t6, b6 = split_head(sec_lines[6], "§6 ")
pb.append(render_section(f"§6 {t6}", b6, [
    ("6.1", "全局固定顺序"), ("6.2", "缓存重置规则"), ("6.3", "首次错误定位"),
]))

# §7
t7, b7 = split_head(sec_lines[7], "§7 ")
pb.append(render_section(f"§7 {t7}", b7, [
    ("7.1", "I-01 HTML 源站基线不变量"), ("7.2", "I-02 Markdown 源站基线不变量"),
    ("7.3", "I-03 HTML 冷请求不变量"), ("7.4", "I-04 Markdown 冷请求不变量"),
    ("7.5", "I-05 HTML→Markdown 顺序不变量"), ("7.6", "I-06 Markdown→HTML 顺序不变量"),
    ("7.7", "I-07 缓存证据不变量"), ("7.8", "I-08 重复运行不变量"),
    ("7.9", "I-09 健康场景零误报"), ("7.10", "I-10 错误可归因性"),
    ("7.11", "I-11 Vary 不能独立决定裁决"), ("7.12", "I-12 正文保密不变量"),
]))

# §8
t8, b8 = split_head(sec_lines[8], "§8 ")
pb.append(render_section(f"§8 {t8}", b8, [
    ("8.1", "ORIGIN_NEGOTIATION_ERROR（CRITICAL）"),
    ("8.2", "REPRESENTATION_BLEED（CRITICAL）"),
    ("8.3", "CONTRACT_MISMATCH（CRITICAL）"),
    ("8.4", "CACHE_STATE_UNKNOWN（WARNING）"),
    ("8.5", "SENTINEL_MISMATCH（CRITICAL）"),
    ("8.6", "INCONCLUSIVE_LIMIT（WARNING）"),
    ("8.7", "VARY_ACCEPT_ABSENT（WARNING）"),
    ("8.8", "CACHE_EVIDENCE_CONFLICT（WARNING）"),
    ("8.9", "CACHE_POLICY_MISMATCH（CRITICAL）"),
]))

# §9
t9, b9 = split_head(sec_lines[9], "§9 ")
pb.append(render_section(f"§9 {t9}", b9, [
    ("9.1", "ORIGIN_NEGOTIATION_ERROR"), ("9.2", "REPRESENTATION_BLEED"),
    ("9.3", "CONTRACT_MISMATCH"), ("9.4", "INCONCLUSIVE"),
    ("9.5", "PASS_OBSERVED"), ("9.6", "裁决优先级（生产判定顺序）"),
]))

# §10（含 §10.2 追问替换）
t10, b10 = split_head(sec_lines[10], "§10 ")
chunks10 = split_subsections(b10, [
    ("10.1", "算法输入"), ("10.2", "算法步骤"), ("10.3", "缓存代理配置"),
    ("10.4", "规范化哈希"), ("10.5", "性能"),
])
parts10 = [f"## §10 {t10}"]
for num, title, content in chunks10:
    content = content.strip()
    if not content:
        continue
    if num == "10.2":
        steps = "\n".join(s102_steps[1:26])  # 25 步
        tail = "\n".join(s102_steps[26:])
        content = (
            "以下 25 个步骤按执行顺序冻结，不得删除、交换或合并。\n\n"
            + steps + "\n\n" + tail
        )
    parts10.append(f"\n### {num} {title}\n\n{content}" if num else f"\n{content}")
pb.append("\n".join(parts10) + "\n")

# §11
t11, b11 = split_head(sec_lines[11], "§11 ")
pb.append(render_section(f"§11 {t11}", b11, [
    ("11.1", "固定执行序列缩写"), ("11.2", "S0 核心 Golden"),
    ("11.3", "扩展 Golden"), ("11.4", "Golden 总体要求"),
]))

# §12
t12, b12 = split_head(sec_lines[12], "§12 ")
pb.append(render_section(f"§12 {t12}", b12, [
    ("12.1", "实现语言"), ("12.2", "Oracle 输入"),
    ("12.3", "独立性要求"), ("12.4", "对账内容"),
]))

# §13（无小节）
t13, b13 = split_head(sec_lines[13], "§13 ")
pb.append(f"## §13 {t13}\n\n{b13.strip()}\n")

# §14（含 §14.1 / §14.2 补全片段）
t14, b14 = split_head(sec_lines[14], "§14 ")
chunks14 = split_subsections(b14, [
    ("14.1", "核心数据对象"), ("14.2", "报告 JSON 示例"),
    ("14.3", "JSON Schema"), ("14.4", "独立 HTML"),
])
parts14 = [f"## §14 {t14}"]
for num, title, content in chunks14:
    content = content.strip()
    if not content:
        continue
    if num == "14.1":
        # s141 只有一行：标题 + 内容在同一行，取“）：”之后的部分
        line141 = s141[0]
        assert "Contract 包含 contractId" in line141
        frag141 = line141.split("）：", 1)[1]
        content = content + "\n\n补全回复取回的片段：\n\n" + frag141
    if num == "14.2":
        # s142[0] 含场景说明与 JSON 开头；主回复已有 JSON 开头，只取场景说明句
        line142 = s142[0]
        assert "场景为 C11" in line142
        frag142_head = line142.split("完整内容：", 1)[1].split("JSON 开头", 1)[0].strip()
        assert frag142_head.startswith("以下是故意构造的合成串版案例，场景为 C11")
        frag142 = frag142_head + "\n\n" + "\n".join(s142[1:])
        assert "首次错误是请求 6" in frag142
        content = content + "\n\n补全回复取回的说明（完整）：\n\n" + frag142
    parts14.append(f"\n### {num} {title}\n\n{content}" if num else f"\n{content}")
pb.append("\n".join(parts14) + "\n")

# §15（含补全片段）
t15, b15 = split_head(sec_lines[15], "§15 ")
chunks15 = split_subsections(b15, [
    ("15.1", "技术架构"), ("15.2", "Python 模块"),
    ("15.3", "前端模块"), ("15.4", "Oracle"),
])
frag15 = "\n".join(s15[1:])
parts15 = [f"## §15 {t15}"]
for num, title, content in chunks15:
    content = content.strip()
    if not content:
        continue
    parts15.append(f"\n### {num} {title}\n\n{content}")
parts15.append("\n补全回复取回的片段（系统架构 ASCII 图、Python 模块树、前端模块树、Oracle 模块树开头部分）：\n\n" + frag15)
pb.append("\n".join(parts15) + "\n")

# §16
t16, b16 = split_head(sec_lines[16], "§16 ")
pb.append(render_section(f"§16 {t16}", b16, [
    ("16.1", "Python"), ("16.2", "测试"), ("16.3", "TypeScript"), ("16.4", "依赖原则"),
]))

# §17
t17, b17 = split_head(sec_lines[17], "§17 ")
pb.append(render_section(f"§17 {t17}", b17, [
    ("17.1", "本地优先"), ("17.2", "敏感字段"),
    ("17.3", "可查看、可修改、可删除"), ("17.4", "本地网络安全"),
]))

# §18：用补全回复的干净表替换错乱版
pb.append("## §18 验收指标\n\n18. 验收指标\n\n| ID | 指标 | 最终验收门槛 | 验证方式 |\n| --- | --- | --- | --- |\n"
          + "\n".join(s18) + f"\n\n{s18_note}\n")

# §19–§21（追问回复首次给出，追加到 §18 之后）
s19_body = "\n".join(s19[1:])
assert "正式交付必须包含" in s19_body and "还必须有：" in s19_body
pb.append("## §19 最终交付物\n\n" + s19_body + "\n")
s20_body = "\n".join(s20[1:])
pb.append("## §20 参考网址与来源\n\n" + s20_body + "\n")
s21_body = "\n".join(s21[1:])
pb.append("## §21 规格冻结声明\n\n" + s21_body + "\n")

project_book = "\n".join(pb)
project_book = clean_truncation_notes(project_book)
# 校验：残留的“（页面”括号注记只应是两处内容描述（§1 摘要、§3 节点摘要无此项）
# PB 只剩 §1 的摘要注记；其余截断标注均已换成标准标记。
pb_page_notes = re.findall(r"（页面[^）]*）", project_book)
assert pb_page_notes == ["（页面显示该节主要为前文的命令示例：accepttwin run --contract contracts/site.json；命令生成：四种实验的执行记录、两种源站表示基线、缓存 MISS/HIT/BYPASS 证据、每个请求的预期与实际表示对照、首次错误位置、最终裁决、JSON 报告、自包含 HTML 报告；上述命令属于规格要求，不代表目前已经存在可运行程序）"], pb_page_notes
assert project_book.count("§19") >= 1 and project_book.count("§21") >= 1
assert "25. HTMLWarmSecond" in project_book
assert "AT_HTML_SENTINEL_001" in project_book and "AT_MARKDOWN_SENTINEL_001" in project_book
assert "| AC11 | 单场景性能 | 完整四实验小于 1 秒 |" in project_book

# ---------- IMPLEMENTATION_PLAN.md 组装 ----------
ip = []
ip.append("# 文件二：IMPLEMENTATION_PLAN.md\n")
ip.append("注：本文件 frontmatter 代码块在页面提取中未取回。\n")
ip.append("# P032 AcceptTwin（网页双态镜）实施计划\n")
intro = ip_lines[0].split("文件二：IMPLEMENTATION_PLAN.md：", 1)[1].strip()
ip.append(intro + "\n")

# §0（含 §0.5 补全）
t0, b0 = split_head(ip_sec_lines[0], "§0 ")
chunks0 = split_subsections(b0, [
    ("0.1", "项目目标"), ("0.2", "不可变工程决策"), ("0.3", "角色职责"),
    ("0.4", "新会话纪律"), ("0.5", "状态机"),
])
parts0 = [f"## §0 {t0}"]
for num, title, content in chunks0:
    content = content.strip()
    if not content:
        continue
    if num == "0.5":
        frag05 = "\n".join(s05[1:])
        assert "状态定义：TODO：尚未准备派发" in frag05 and "强制转换规则：" in frag05
        content = content + "\n\n补全回复取回的片段（状态机图开头、状态定义与强制转换规则完整）：\n\n" + frag05
    parts0.append(f"\n### {num} {title}\n\n{content}" if num else f"\n{content}")
ip.append("\n".join(parts0) + "\n")

# §1
t1i, b1i = split_head(ip_sec_lines[1], "§1 ")
ip.append(render_section(f"§1 {t1i}", b1i, [
    ("1.1", "目的"), ("1.2", "必须对照的对象"), ("1.3", "竞争等价判定合同"),
    ("1.4", "T001 执行步骤"), ("1.5", "T001 交付物"), ("1.6", "T001 验收"),
]))

# §2
t2i, b2i = split_head(ip_sec_lines[2], "§2 ")
ip.append(render_section(f"§2 {t2i}", b2i, [
    ("2.1", "总预算"), ("2.2", "阶段定义"),
]))

# §3（Mermaid 图仅以节点摘要形式取回，保留原样并登记 MINOR）
t3i, b3i = split_head(ip_sec_lines[3], "§3 ")
ip.append(f"## §3 {t3i}\n\n{b3i.strip()}\n")

# §4
t4i, b4i = split_head(ip_sec_lines[4], "§4 ")
ip.append(render_section(f"§4 {t4i}", b4i, [
    ("4.1", "工作区根目录"), ("4.2", "文件所有权"), ("4.3", "Git 规则"),
]))

# §5
t5i, b5i = split_head(ip_sec_lines[5], "§5 ")
ip.append(render_section(f"§5 {t5i}", b5i, [
    ("5.1", "Contract"), ("5.2", "URL Guard"), ("5.3", "Origin"),
    ("5.4", "Cache Proxy"), ("5.5", "Request Observation"),
    ("5.6", "Production Classifier"), ("5.7", "Oracle"), ("5.8", "Report"),
]))

# §6 引言
t6i, b6i = split_head(ip_sec_lines[6], "§6 ")
ip.append(f"## §6 {t6i}\n\n{b6i.strip()}\n")

# T001–T011（主回复逐字）
for tid in [f"T{str(i).zfill(3)}" for i in range(1, 12)]:
    line = task_lines[tid]
    title, body_t = split_head(line, f"{tid} — ")
    ip.append(f"### {tid} — {title}\n\n{body_t.strip()}\n")

# T012：主回复 + 补全回复的验收标准续、完成定义、失败回退
title12, body12 = split_head(task_lines["T012"], "T012 — ")
trunc_tail = "验收标准：48/48 Golden；48/48 Oracle parity；单场景——（回复在此处截断，后续内容缺失：T012 剩余验收标准、T013、T014 及结尾说明均未输出）。"
assert trunc_tail in body12, body12[-200:]
body12_main = body12.split(trunc_tail)[0]
# 补全回复 T012：验收标准续（bullets）、验收命令、完成定义、失败回退
acc_cont = "\n".join(t012_supp[1:20])  # “• 单场景…”至“• 测试日志包含…”
assert acc_cont.startswith("• 单场景完整四实验运行时间小于 1 秒"), acc_cont[:40]
assert "• 测试日志包含真实执行命令" in acc_cont
acc_cmd = next(ln for ln in t012_supp if ln.startswith("验收命令："))
done_def = next(ln for ln in t012_supp if ln.startswith("完成定义："))
fail_back = next(ln for ln in t012_supp if ln.startswith("失败回退："))
acc_cmd_clean = clean_truncation_notes(acc_cmd[len("验收命令："):])
t012_full = (
    body12_main
    + "验收标准：48/48 Golden；48/48 Oracle parity；\n\n" + acc_cont
    + "\n\n" + done_def + "\n\n" + fail_back
    + "\n\n注：补全回复另给出验收命令：" + acc_cmd_clean
)
ip.append(f"### T012 — {title12}\n\n{t012_full.strip()}\n")

# T013 / T014（补全回复逐字，小节按行分段）
def render_task_supp(supp_lines: list[str], tid: str) -> str:
    first = supp_lines[0]
    assert first.startswith(("7. T013", "8. T014")), first
    title = first.split("—", 1)[1].strip()
    out = [f"### {tid} — {title}"]
    for ln in supp_lines[1:]:
        ln = ln.strip()
        if not ln:
            continue
        if re.match(rf"{tid}-[A-I]：", ln):
            sub, rest = ln.split("：", 1)
            out.append(f"\n#### {sub}：\n\n{rest.strip()}")
        else:
            out.append(f"\n{ln}")
    return "\n".join(out) + "\n"

ip.append(render_task_supp(t013_supp, "T013"))
ip.append(render_task_supp(t014_supp, "T014"))

implementation_plan = "\n".join(ip)
implementation_plan = clean_truncation_notes(implementation_plan)
# 校验：残留的“（页面”括号注记只应是 IP §3 的 Mermaid 节点摘要。
ip_page_notes = re.findall(r"（页面[^）]*）", implementation_plan)
assert ip_page_notes == ["（页面显示节点）"], ip_page_notes
assert "T013 — 独立代码审查" in implementation_plan
assert "T014 — 修复、最终门禁与 Release Freeze" in implementation_plan
assert "100 次完整重复运行的规范化报告 SHA-256 完全一致" in implementation_plan
assert "单场景完整四实验运行时间小于 1 秒" in implementation_plan

# ---------- 写出 ----------
pb_path = OUT / "01_project_book" / "PROJECT_BOOK.md"
ip_path = OUT / "02_implementation_plan" / "IMPLEMENTATION_PLAN.md"
pb_path.write_text(project_book, encoding="utf-8")
ip_path.write_text(implementation_plan, encoding="utf-8")
print("PROJECT_BOOK.md bytes:", pb_path.stat().st_size)
print("IMPLEMENTATION_PLAN.md bytes:", ip_path.stat().st_size)
print("PB markers:", project_book.count(MARK.strip()))
print("IP markers:", implementation_plan.count(MARK.strip()))
print("PB sections:", len(re.findall(r"^## §", project_book, re.M)))
print("IP sections:", len(re.findall(r"^## §", implementation_plan, re.M)))
print("IP tasks:", len(re.findall(r"^### T0", implementation_plan, re.M)))
