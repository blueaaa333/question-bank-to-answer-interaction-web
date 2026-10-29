# 题库 docx 结构解析：模式识别与陷阱清单

教学系统（Blackboard / Moodle / Canvas 等）导出的题库文档，排版普遍混乱。这份清单来自实际解析中踩过的坑，按「识别模式 → 处理办法」组织。

## 一、文档常由多份题库拼接而成

题号会周期性重启（`Question 1 ... Question 195`，然后又出现 `Question 20`）。识别方法：顺序扫描题号，遇到比前一个小的题号即为新分区起点。

同一批题目往往被导出多次，形成多个分区，其中某些分区是**答案区**——题号后直接附带答案字母：

```
Question 35  c
An income statement of a business shows:-
The amount of cash the business has
...
```

解析答案区时要把字母从题号行剥离（`^Question\s+(\d+)\s+([a-dA-D])\s*$`），否则字母会被当成题干的一部分。

分区数不等于题目数。必须去重，否则题量会虚高数倍。

## 二、选项的三种排版形态

同一份文档里常常三种并存，解析器必须都能处理。

### 形态 A：表格型

选项被放进单列表格，表格前有一行 `Question 195 options:` 标记：

```
Question 20
Net Sales (excluding GST) to Debtors is recorded as a:
Question 195 options:
|  | Debit to the Debtor general ledger account |
| --- | --- |
|  | Credit to the Sales general ledger account |
```

**陷阱 1**：`Question 195 options:` 这行本身符合「Question + 数字」的题头正则，会被误识别成新题目，导致它前面那道题丢失全部选项。必须在收集题头时排除 `options:` 结尾的行（`^Question\s+\d+\s+options\s*:?$`）。

**陷阱 2**：`options:` 标记行的题号（195）与它服务的题目题号（20）不一致，不能用题号关联，只能靠**位置相邻**——它紧跟在所属题目之后。

**陷阱 3**：表格第二行 `| --- | --- |` 是 Markdown 分隔行（若走 md 路线）或空单元格，提取时要过滤掉纯 `-` 与空串。

### 形态 B：带 a./b./c./d. 前缀型

```
Question 1 What is not a definition of Accounting?
a The addition of all money in a business.
b. The language of business
c. It is an information process
d. Summarises all transactions in Financial Report
```

**陷阱 4**：题干跟在题号同一行（`Question 1 What is not...`），不是独立段落。要先把题号剥掉，剩余部分才是题干。

**陷阱 5**：首个选项的前缀可能不规范——`a` 后无句点（`a The addition...`）、或缺失字母。正则要同时兼容 `^[a-d]\s*[\.\)]\s+` 和 `^a\s+`。

**陷阱 6**：一行里挤了两个选项：

```
c. Bookkeepers generally do not interpret Reports d. Bookkeepers record transactions up to Trail Balance stage
```

需要用 `(?<=\s)([b-d])\s*[\.\)]\s+` 做行内二次切分。注意用 lookbehind 限定前面是空白，避免把选项正文里的 `b.` 之类误切。

### 形态 C：靠空行分隔型

题干与选项之间有空段落，选项本身不带字母前缀：

```
Question 1
The business organisation that has the following characteristics...
<空行>
Company
Partnership
Sole Trader
Trust
```

**陷阱 7**：这个分隔规则**不统一**。有的题目题干与选项之间没有空行：

```
Question 12
Which one of the below statements is correct in relation to a Franchise:-
A franchise agreement must be in writing          ← 直接就是选项，无空行
It is a contractual agreement between...
```

所以不能只靠空行切分。推荐的判定优先级：

1. 有 `options:` 表格 → 表格里的就是选项
2. 匹配 `True ... False` 合并行 → 判断题
3. 有 ≥2 个带 `a./b.` 前缀的段落 → 前缀模式，前缀之前的是题干
4. 有空行分隔 → 空行前是题干，空行后是选项
5. 空行在末尾（选项之后）而非中间 → 第一段是题干，其余是选项
6. 兜底：首段是题干，其余是选项

**陷阱 8**：题干本身可能是多段（题目背景 + 数据清单 + 提问句）：

```
Carrington Bicycles purchased equipment and incurred the following costs:
Purchase price (GST inclusive)      $26,400
Delivery Costs                       1,200
The purchase price for the equipment will be recorded at:-
```

规则 3、4 要能容纳多段题干，不能假设题干只有一段。

## 三、判断题

`True` 与 `False` 常挤在同一段落，靠空格分隔，有时还带选项字母：

```
True           False
a. True   b.  False
True b. False
```

统一用 `^(?:a\s*[\.\)]\s*)?True\s+(?:b\s*[\.\)]\s*)?False\s*$`（忽略大小写）识别，命中即产出 `["True","False"]` 两个选项。

**答案定位**：若文档用高亮标记正确答案，标记可能只落在 `True` 或 `False` 其中一个 run 上。需要遍历该段的 run，看被标记的 run 文本里包含 `true` 还是 `false`。

**去重陷阱**：所有判断题的选项集合都是 `["True","False"]`，完全相同。如果只按选项集合聚类，几十道判断题会被合并成一道。聚类键必须包含题干。

## 四、答案的格式标记

正确答案常用格式标记，而非文字标注。已见的形式：

- 黄色高亮：`<w:highlight w:val="yellow"/>`
- 绿色字体：`<w:color w:val="00B050"/>`（Office 标准绿）
- 红色字体：`<w:color w:val="FF0000"/>`（可能是强调，也可能是答案，需验证）
- 题号后附带答案字母

提取时按 run 级别读取 `rPr`，把标记信息附到选项上。

**必须先验证语义再采信**。统计每个题块中被标记的选项数量：

- 分布集中在「恰好 1 个」→ 标记语义是正确答案，可采信
- 有的 0 个、有的 3 个、分布散乱 → 标记是重点强调，不是答案，不可采信

实测样例：某文档 405 个可用题块中，256 个恰好标记 1 个选项，0 个标记多于 1 个，149 个无标记 → 判定为答案标记，覆盖率 63%。

**分区标记会混入选项文本**。蓝色字体的 `TOPIC 1 - INTRODUCTION TO ACCOUNTING` 是分区标题，但它常紧跟在最后一个选项之后被一起提取，出现 `Only when the business makes a profit TOPIC 1 - INTRODUCTION TO ACCOUNTING` 这样的脏选项。需要正则剥离：`\s*TOPIC\s*\d+\s*-\s*[A-Z\s\-]*$`。同理剥离页脚统计（`Practical 10`、`Theory 22`）。

## 五、去重与冲突处理

### 聚类

键 = `归一化题干[:90]` + `排序后的归一化选项文本元组`。

归一化：`\xa0`→空格、弯引号→直引号、去大小写、只保留字母数字（`re.sub(r'[^a-z0-9]+','',s.lower())`）。这样能吸收拼写差异（`characterisitics` / `characteristics`）与标点差异。

题干截断到 90 字符是为了容忍尾部细微差异，但要确认这个长度足以区分相似题目；若文档中有大量长题干前缀相同，需要加大截断长度或改用全文哈希。

### 投票

同一题的多个副本各自给出答案时，**按选项文本投票，不按位置**。因为副本间选项顺序被打乱过：

```
副本1 opts: [Trust, Company, Partnership, Sole Trader]  标记 idx0 = Trust
副本2 opts: [Company, Partnership, Sole Trader, Trust]  标记 idx3 = Trust
```

按位置投票会得出「idx0 vs idx3」的假冲突；按文本投票则一致收敛到 Trust。

实测对比：按位置投票报出 35 组冲突，改为按文本投票后只剩 3 组真冲突。

### 真冲突

同一题的不同副本标记了**语义不同**的答案（不只是拼写变体），说明原始题库本身标注有误。处理办法：按学科原理判定，并在交付说明中逐条写明题目、冲突双方的答案、以及判定依据。不要静默选一个。

## 六、必须剔除的题目

- **配对题**（`Match each of the following...`）：答案是一组对应关系而非单个选项，无法做成单选判分。
- **排序题**（`Arrange the steps in the correct order`）：同上。
- **占位废题**：如 `What is a dog` 配 `a cat / frog / bird`，是测试残留。
- **解析损坏**：题干被截断、选项混入题干、选项数为 0 或 1、出现空选项。
- **无任何答案依据**：既无文档标记，也无法核算或按原理判定。

剔除是正确行为，但必须在交付说明中报出数量与原因，不要静默丢弃。

## 七、无依赖解析骨架

不装 `python-docx` 也能解析，直接读 XML：

```python
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
z = zipfile.ZipFile(path)
root = ET.fromstring(z.read("word/document.xml"))
body = root.find(W + "body")

for el in body:                      # 按文档顺序遍历
    tag = el.tag.replace(W, "")
    if tag == "p":
        runs = []
        for r in el.findall(W + "r"):
            text = "".join(t.text or "" for t in r.findall(W + "t"))
            if not text:
                continue
            rpr = r.find(W + "rPr")
            hl = col = None
            if rpr is not None:
                h = rpr.find(W + "highlight")
                hl = h.get(W + "val") if h is not None else None
                c = rpr.find(W + "color")
                col = c.get(W + "val") if c is not None else None
            runs.append({"t": text, "hl": hl, "col": col})
    elif tag == "tbl":
        rows = []
        for tr in el.findall(W + "tr"):
            row = []
            for tc in tr.findall(W + "tc"):
                cell = ""
                for p in tc.findall(W + "p"):
                    cell += "".join(t.text or "" for t in p.iter(W + "t")) + " "
                row.append(cell.strip())
            rows.append(row)
```

要点：

- 必须**按文档顺序**同时处理段落和表格，把两者放进同一个序列，才能判断表格归属于哪道题。
- run 级别读取格式标记，段落级别拼接文本。
- 文本清洗：`\xa0`（不间断空格）在 LMS 导出里极常见，用于对齐数字列，必须替换为普通空格，否则题干里会出现大量不可见字符。
- `w:tbl` 内的单元格文本要按 `w:tc` → `w:p` → `w:t` 三层取，且单元格内可能有多个段落，需用空格连接。

