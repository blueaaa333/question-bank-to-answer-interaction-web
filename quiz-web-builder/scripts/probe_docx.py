#!/usr/bin/env python3
"""题库 docx 结构探查脚本。

在写解析器之前先跑本脚本，看清文档真实结构，避免凭前几行猜测导致大面积解析错误。

用法：
    python probe_docx.py "<题库.docx>"

输出六部分：
  1. 题号标题的分布与编号重启点（判断是否多份题库拼接、哪些分区是答案区）
  2. 选项的三种排版形态统计（表格型 / 带 a.b.c.d. 前缀型 / 空行分隔型）
  3. 判断题 True/False 合并行数量
  4. 格式标记统计（高亮色、字体色、加粗）——用于判断答案是否用格式标注
  5. 被标记选项数量的分布——验证标记语义是否为「正确答案」的关键
  6. 每题块的前若干行原文样例——确认切分规则

仅读取文档，不做任何修改。
"""
import re
import sys
import collections
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

HDR = re.compile(r"^\s*(?:#+\s*)?Question\s+(\d+)\s*(.*)$", re.I)
OPTMARK = re.compile(r"^\s*(?:#+\s*)?Question\s+\d+\s+options\s*:?\s*$", re.I)
PREFIX = re.compile(r"^([a-dA-Z])\s*[\.\)]\s+")
TF = re.compile(r"^(?:a\s*[\.\)]\s*)?True\s+(?:b\s*[\.\)]\s*)?False\s*$", re.I)
ANSLETTER = re.compile(r"^([a-dA-D])\s*$")

ANSWER_COLORS = {"00B050", "00B150", "008000", "FF0000"}
ANSWER_HIGHLIGHTS = {"yellow", "green", "cyan"}


def clean(s):
    """LMS 导出文档里 \xa0 极常见（用于对齐数字列），必须归一化。"""
    if not s:
        return ""
    for a, b in (("\xa0", " "), ("\u2019", "'"), ("\u2018", "'"),
                 ("\u201c", '"'), ("\u201d", '"'), ("\u2013", "-"), ("\u2014", "-")):
        s = s.replace(a, b)
    return s


def read_seq(path):
    """按文档顺序返回 [('p', runs) | ('tbl', rows)]，run 携带格式标记。"""
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    seq = []
    for el in body:
        tag = el.tag.replace(W, "")
        if tag == "p":
            seq.append(("p", runs_of(el)))
        elif tag == "tbl":
            rows = []
            for tr in el.findall(W + "tr"):
                row = []
                for tc in tr.findall(W + "tc"):
                    rr = []
                    for p in tc.findall(W + "p"):
                        rr.extend(runs_of(p))
                    row.append(rr)
                rows.append(row)
            seq.append(("tbl", rows))
    return seq


def runs_of(p):
    out = []
    for r in p.findall(W + "r"):
        text = clean("".join(t.text or "" for t in r.findall(W + "t")))
        if not text:
            continue
        rpr = r.find(W + "rPr")
        hl = col = bold = False
        if rpr is not None:
            h = rpr.find(W + "highlight")
            hl = h.get(W + "val") if h is not None else None
            c = rpr.find(W + "color")
            col = c.get(W + "val") if c is not None else None
            bold = rpr.find(W + "b") is not None
        out.append({"t": text, "hl": hl, "col": col, "b": bold})
    return out


def txt(runs):
    return re.sub(r"[ \t]+", " ", "".join(r["t"] for r in runs)).strip()


def marks_of(r):
    """返回该 run 携带的全部候选标记标识（可能同时有高亮和字色）。"""
    out = []
    if r["hl"]:
        out.append("高亮:" + r["hl"])
    if r["col"] and r["col"] not in ("auto", "000000"):
        out.append("字色:" + r["col"])
    return out


def mark(r):
    """兼容旧调用：任意候选标记都算命中。"""
    return "M" if marks_of(r) else ""


def main(path):
    seq = read_seq(path)
    print("=" * 70)
    print("1. 题号标题分布与编号重启点")
    print("=" * 70)

    # options: 标记行不是真题目，必须排除，否则其前一道题会丢掉全部选项
    headers = [i for i, (t, v) in enumerate(seq)
               if t == "p" and HDR.match(txt(v)) and not OPTMARK.match(txt(v))]
    optmarks = [i for i, (t, v) in enumerate(seq) if t == "p" and OPTMARK.match(txt(v))]
    print("题号标题数: %d   （另有 'Question N options:' 标记行 %d 条，已排除）"
          % (len(headers), len(optmarks)))

    blocks = []
    prev, bank = None, 0
    for k, i in enumerate(headers):
        end = headers[k + 1] if k + 1 < len(headers) else len(seq)
        m = HDR.match(txt(seq[i][1]))
        num = int(m.group(1))
        rest = m.group(2).strip()
        if prev is not None and num < prev:
            bank += 1
        prev = num
        al = ANSLETTER.match(rest)
        blocks.append({"bank": bank, "num": num, "start": i, "end": end,
                       "ans_letter": al.group(1).lower() if al else None,
                       "stem_inline": bool(rest) and not al})
    print("编号重启 %d 次 → 文档由 %d 个分区拼接而成" % (bank, bank + 1))
    for b in range(bank + 1):
        sub = [x for x in blocks if x["bank"] == b]
        if not sub:
            print("  未匹配 Question N 题头；请检查数字题号或图片题，不能据此断言没有题目。")
            continue
        la = sum(1 for x in sub if x["ans_letter"])
        si = sum(1 for x in sub if x["stem_inline"])
        note = ""
        if la:
            note = "  ← %d 题的题号后附带答案字母，可能是答案区" % la
        if si and not la:
            note = "  ← %d 题的题干跟在题号同一行" % si
        print("  分区%d: %3d 题  题号 %d..%d%s"
              % (b, len(sub), sub[0]["num"], sub[-1]["num"], note))

    print()
    print("=" * 70)
    print("2/3. 选项排版形态与判断题")
    print("=" * 70)
    shape = collections.Counter()
    for b in blocks:
        seg = seq[b["start"] + 1:b["end"]]
        has_tbl = any(t == "tbl" for t, _ in seg)
        ps = [txt(v) for t, v in seg if t == "p"]
        if has_tbl or any(OPTMARK.match(p) for p in ps):
            shape["表格型 (options: + table)"] += 1
        elif TF.match(next((p for p in ps if p), "")) or any(TF.match(p) for p in ps):
            shape["判断题 (True/False 同行)"] += 1
        elif sum(1 for p in ps if PREFIX.match(p)) >= 2:
            shape["前缀型 (a. b. c. d.)"] += 1
        elif any(p == "" for p in ps):
            shape["空行分隔型"] += 1
        else:
            shape["无明显分隔（需人工确认）"] += 1
    for k, v in shape.most_common():
        print("  %-34s %d" % (k, v))

    print()
    print("=" * 70)
    print("4. 格式标记统计（用于判断答案是否用格式标注）")
    print("=" * 70)
    sig = collections.Counter()
    for t, v in seq:
        if t == "p":
            for r in v:
                if r["hl"]:
                    sig["高亮 " + r["hl"]] += 1
                if r["col"] and r["col"] not in ("auto", "000000"):
                    sig["字色 " + r["col"]] += 1
                if r["b"]:
                    sig["加粗"] += 1
        else:
            for row in v:
                for cell in row:
                    for r in cell:
                        if r["hl"]:
                            sig["高亮 " + r["hl"] + " (表格内)"] += 1
                        if r["col"] and r["col"] not in ("auto", "000000"):
                            sig["字色 " + r["col"] + " (表格内)"] += 1
    if not sig:
        print("  未发现任何格式标记 —— 答案可能需要靠计算或学科原理判定")
    for k, v in sig.most_common():
        flag = "  ← 可能是答案标记" if any(c in k for c in ANSWER_COLORS | ANSWER_HIGHLIGHTS) else ""
        print("  %-34s %d%s" % (k, v, flag))

    print()
    print("=" * 70)
    print("5. 被标记选项数量分布 —— 验证标记语义的关键")
    print("=" * 70)
    dist = collections.Counter()
    for b in blocks:
        seg = seq[b["start"] + 1:b["end"]]
        n = 0
        for t, v in seg:
            if t == "p":
                s = txt(v)
                if s and any(mark(r) for r in v):
                    n += 1
            else:
                for row in v:
                    for cell in row:
                        if txt([r for r in cell]) and any(mark(r) for r in cell):
                            n += 1
        dist[min(n, 5)] += 1
    for k in sorted(dist):
        label = str(k) if k < 5 else "5+"
        print("  标记了 %s 个内容行的题块: %d" % (label, dist[k]))
    one, multi = dist[1], sum(v for k, v in dist.items() if k > 1)
    if one and multi == 0:
        print("\n  ✓ 判定：所有被标记的题块都恰好标记 1 项 → 标记语义是「正确答案」，可采信")
    elif one and multi:
        print("\n  ⚠ 有 %d 个题块标记了多项 → 标记可能是重点强调而非答案，需逐题核查" % multi)
    elif one == 0:
        print("\n  ✗ 没有题块恰好标记 1 项 → 格式标记不是答案，改用计算或学科原理判定")

    print()
    print("=" * 70)
    print("6. 题块原文样例（确认切分规则）")
    print("=" * 70)
    for b in blocks[:3]:
        print("\n--- 分区%d Question %d%s ---"
              % (b["bank"], b["num"], "  [答案字母: %s]" % b["ans_letter"] if b["ans_letter"] else ""))
        for t, v in seq[b["start"]:b["end"]][:12]:
            if t == "p":
                s = txt(v)
                mk = "".join(mark(r) for r in v)
                print("   P%-3s %r" % (("[" + mk + "]") if mk else "", s[:88]))
            else:
                print("   TBL  %r" % ([txt([r for c in row for r in c])[:40] for row in v][:5],))

    print("\n" + "=" * 70)
    print("下一步：按上述形态写解析器。切分规则判定优先级、去重投票方式与")
    print("常见陷阱见 references/docx-structure-parsing.md")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])

