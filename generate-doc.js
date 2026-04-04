const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  TableOfContents, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, ImageRun
} = require("docx");

// ============ "Midnight Code" Color Palette ============
const C = {
  primary: "020617",
  body: "1E293B",
  secondary: "64748B",
  accent: "94A3B8",
  tableBg: "F8FAFC",
  tableHeader: "E2E8F0",
  white: "FFFFFF",
  codeBg: "F1F5F9",
  coverBg: "0F172A",
};

const bdr = { style: BorderStyle.SINGLE, size: 8, color: C.accent };
const cellB = { top: bdr, bottom: bdr, left: { style: BorderStyle.NIL }, right: { style: BorderStyle.NIL } };
const cellBFull = { top: bdr, bottom: bdr, left: bdr, right: bdr };

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 600, after: 300 }, children: [new TextRun({ text, font: "SimHei", size: 32, bold: true, color: C.primary })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 400, after: 200 }, children: [new TextRun({ text, font: "SimHei", size: 28, bold: true, color: C.primary })] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 300, after: 150 }, children: [new TextRun({ text, font: "SimHei", size: 24, bold: true, color: C.body })] });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120, line: 250 },
    indent: { firstLine: 420 },
    alignment: AlignmentType.JUSTIFIED,
    ...opts,
    children: [new TextRun({ text, font: "Microsoft YaHei", size: 21, color: C.body, ...(opts.run || {}) })]
  });
}
function pMulti(runs, opts = {}) {
  return new Paragraph({
    spacing: { after: 120, line: 250 },
    indent: { firstLine: 420 },
    alignment: AlignmentType.JUSTIFIED,
    ...opts,
    children: runs.map(r => typeof r === "string" ? new TextRun({ text: r, font: "Microsoft YaHei", size: 21, color: C.body }) : new TextRun({ font: "Microsoft YaHei", size: 21, color: C.body, ...r }))
  });
}
function codeBlock(lines) {
  return lines.map(line => new Paragraph({
    spacing: { after: 0, line: 240 },
    indent: { left: 400 },
    children: [new TextRun({ text: line, font: "SarasaMonoSC", size: 18, color: C.body })]
  }));
}
function emptyPara(h = 100) {
  return new Paragraph({ spacing: { before: h, after: 0 }, children: [new TextRun({ text: "", size: 2 })] });
}

function makeHeaderCell(text, width) {
  return new TableCell({
    borders: cellBFull, width: { size: width, type: WidthType.DXA },
    shading: { fill: C.tableHeader, type: ShadingType.CLEAR },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text, font: "SimHei", size: 20, bold: true, color: C.primary })] })]
  });
}
function makeCell(text, width, align) {
  return new TableCell({
    borders: cellBFull, width: { size: width, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ alignment: align || AlignmentType.CENTER, spacing: { line: 250 }, children: [new TextRun({ text, font: "Microsoft YaHei", size: 20, color: C.body })] })]
  });
}

// ============ BUILD DOCUMENT ============
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 21, color: C.body } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, font: "SimHei", color: C.primary }, paragraph: { spacing: { before: 600, after: 300 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, font: "SimHei", color: C.primary }, paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true, font: "SimHei", color: C.body }, paragraph: { spacing: { before: 300, after: 150 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullet-main", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-deploy", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-vote", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-vote-steps", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-docker", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-api", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-wallet", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-web3", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-test", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "num-faq", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [
    // ========== COVER PAGE ==========
    {
      properties: {
        page: { margin: { top: 0, bottom: 0, left: 0, right: 0 }, size: { width: 11906, height: 16838 } },
        titlePage: true
      },
      children: [
        emptyPara(4500),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "AICoin", font: "SimHei", size: 72, bold: true, color: C.accent })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: "\u53bb\u4e2d\u5fc3\u5316 AI \u7b97\u529b\u6316\u77ff\u7f51\u7edc", font: "Microsoft YaHei", size: 36, color: C.accent })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 50 }, children: [new TextRun({ text: "Decentralized AI Compute Mining Network", font: "Microsoft YaHei", size: 24, color: C.secondary })] }),
        emptyPara(300),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 50 }, children: [new TextRun({ text: "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500", font: "Microsoft YaHei", size: 20, color: C.accent })] }),
        emptyPara(100),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "\u90e8\u7f72\u6307\u5357 & \u6cbb\u7406\u6295\u7968\u8bf4\u660e", font: "SimHei", size: 28, color: C.white })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "Deployment Guide & Governance Voting Manual", font: "Microsoft YaHei", size: 20, color: C.secondary })] }),
        emptyPara(2000),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 50 }, children: [new TextRun({ text: "\u7248\u672c: v1.0.0  |  \u66f4\u65b0\u65e5\u671f: 2026-04-04", font: "Microsoft YaHei", size: 18, color: C.secondary })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 50 }, children: [new TextRun({ text: "GitHub: https://github.com/ctz168/aicoin", font: "Microsoft YaHei", size: 18, color: C.secondary })] }),
      ]
    },
    // ========== TOC ==========
    {
      properties: {
        page: { margin: { top: 1800, bottom: 1440, left: 1440, right: 1440 } },
        titlePage: true
      },
      headers: {
        default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "AICoin \u90e8\u7f72\u6307\u5357", font: "Microsoft YaHei", size: 18, color: C.secondary })] })] })
      },
      footers: {
        default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u2014 ", font: "Microsoft YaHei", size: 18, color: C.secondary }), new TextRun({ children: [PageNumber.CURRENT], font: "Microsoft YaHei", size: 18, color: C.secondary }), new TextRun({ text: " \u2014", font: "Microsoft YaHei", size: 18, color: C.secondary })] })] })
      },
      children: [
        new Paragraph({ spacing: { before: 200, after: 300 }, children: [new TextRun({ text: "\u76ee\u5f55", font: "SimHei", size: 36, bold: true, color: C.primary })] }),
        new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 200 }, children: [new TextRun({ text: "\u63d0\u793a\uff1a\u53f3\u952e\u70b9\u51fb\u76ee\u5f55\uff0c\u9009\u62e9\u201c\u66f4\u65b0\u57df\u201d\u53ef\u83b7\u53d6\u51c6\u786e\u7684\u9875\u7801\u3002", font: "Microsoft YaHei", size: 18, color: "999999" })] }),
        new Paragraph({ children: [new PageBreak()] }),

        // ============================================================
        // PART 1: \u90e8\u7f72\u6307\u5357
        // ============================================================
        h1("\u7b2c\u4e00\u90e8\u5206\uff1a\u90e8\u7f72\u6307\u5357"),
        p("AICoin \u662f\u4e00\u4e2a\u57fa\u4e8e\u533a\u5757\u94fe\u7684\u53bb\u4e2d\u5fc3\u5316 AI \u7b97\u529b\u6316\u77ff\u7f51\u7edc\u3002\u7f51\u7edc\u901a\u8fc7\u4ee3\u5e01\u6fc0\u52b1\u673a\u5236\u5c06 AI \u7b97\u529b\u63d0\u4f9b\u8005\uff08\u6316\u77ff\u8282\u70b9\uff09\u3001API \u8c03\u7528\u8005\u548c\u6cbb\u7406\u53c2\u4e0e\u8005\u8fde\u63a5\u5728\u4e00\u8d77\uff0c\u6784\u5efa\u4e00\u4e2a\u53ef\u6301\u7eed\u7684\u53bb\u4e2d\u5fc3\u5316 AI \u57fa\u7840\u8bbe\u65bd\u3002\u672c\u6587\u6863\u5c06\u8be6\u7ec6\u8bf4\u660e\u5982\u4f55\u4ece\u96f6\u5f00\u59cb\u90e8\u7f72\u5e76\u8fd0\u884c\u4e00\u4e2a AICoin \u8282\u70b9\uff0c\u5305\u62ec\u73af\u5883\u51c6\u5907\u3001\u914d\u7f6e\u8bf4\u660e\u3001\u94b1\u5305\u521b\u5efa\u3001\u6316\u77ff\u542f\u52a8\u4ee5\u53ca\u7f51\u7edc\u6cbb\u7406\u6295\u7968\u7684\u5b8c\u6574\u6d41\u7a0b\u3002"),

        // === 1.1 \u73af\u5883\u8981\u6c42 ===
        h2("1.1 \u73af\u5883\u8981\u6c42"),
        p("\u5728\u5f00\u59cb\u90e8\u7f72\u4e4b\u524d\uff0c\u9700\u8981\u786e\u4fdd\u60a8\u7684\u7cfb\u7edf\u6ee1\u8db3\u4ee5\u4e0b\u6700\u4f4e\u8981\u6c42\u3002AICoin \u652f\u6301\u4e24\u79cd\u8fd0\u884c\u6a21\u5f0f\uff1a\u6a21\u62df\u6a21\u5f0f\uff08\u65e0\u9700 GPU\uff0c\u4ec5\u7528\u4e8e\u5f00\u53d1\u6d4b\u8bd5\uff09\u548c\u751f\u4ea7\u6a21\u5f0f\uff08\u9700\u8981 GPU \u52a0\u901f\u63a8\u7406\uff09\u3002\u5982\u679c\u60a8\u53ea\u662f\u60f3\u4f53\u9a8c\u6316\u77ff\u6d41\u7a0b\u6216\u5f00\u53d1\u6d4b\u8bd5\uff0c\u6a21\u62df\u6a21\u5f0f\u5c31\u5df2\u7ecf\u8db3\u591f\u3002"),

        new Table({
          alignment: AlignmentType.CENTER,
          columnWidths: [3000, 2000, 4360],
          margins: { top: 100, bottom: 100, left: 180, right: 180 },
          rows: [
            new TableRow({ tableHeader: true, children: [makeHeaderCell("\u4f9d\u8d56\u9879", 3000), makeHeaderCell("\u6700\u4f4e\u7248\u672c", 2000), makeHeaderCell("\u8bf4\u660e", 4360)] }),
            new TableRow({ children: [makeCell("Python", 3000), makeCell("3.10+", 2000), makeCell("\u63a8\u8350 3.11 \u6216 3.12", 4360)] }),
            new TableRow({ children: [makeCell("pip", 3000), makeCell("\u6700\u65b0\u7248", 2000), makeCell("pip install --upgrade pip", 4360)] }),
            new TableRow({ children: [makeCell("CUDA GPU", 3000), makeCell("\u53ef\u9009", 2000), makeCell("\u751f\u4ea7\u6a21\u5f0f\u4e0b\u63a8\u8350\u3001\u6a21\u62df\u6a21\u5f0f\u4e0d\u9700\u8981", 4360)] }),
            new TableRow({ children: [makeCell("\u78c1\u76d8\u7a7a\u95f4", 3000), makeCell("10GB+", 2000), makeCell("\u7528\u4e8e\u5b58\u50a8 AI \u6a21\u578b\u6587\u4ef6", 4360)] }),
            new TableRow({ children: [makeCell("\u5185\u5b58", 3000), makeCell("8GB+", 2000), makeCell("\u63a8\u8350 16GB \u4ee5\u4e0a", 4360)] }),
            new TableRow({ children: [makeCell("\u7f51\u7edc", 3000), makeCell("\u7a33\u5b9a\u8fde\u63a5", 2000), makeCell("P2P \u901a\u4fe1\u9700\u8981\u5f00\u653e\u7aef\u53e3", 4360)] }),
          ]
        }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 50, after: 200 }, children: [new TextRun({ text: "\u8868 1\uff1a\u7cfb\u7edf\u73af\u5883\u8981\u6c42", font: "Microsoft YaHei", size: 18, color: C.secondary, italics: true })] }),

        // === 1.2 \u5b89\u88c5\u90e8\u7f72 ===
        h2("1.2 \u5b89\u88c5\u90e8\u7f72"),
        p("\u4ee5\u4e0b\u6b65\u9aa4\u5c06\u5f15\u5bfc\u60a8\u5b8c\u6210 AICoin \u8282\u70b9\u7684\u5b89\u88c5\u548c\u57fa\u7840\u914d\u7f6e\u3002\u6574\u4e2a\u8fc7\u7a0b\u5927\u7ea6\u9700\u8981 5-10 \u5206\u949f\uff0c\u4e3b\u8981\u65f6\u95f4\u82b1\u8d39\u5728\u4f9d\u8d56\u5305\u7684\u4e0b\u8f7d\u548c\u5b89\u88c5\u4e0a\u3002"),

        h3("1.2.1 \u514b\u9686\u9879\u76ee"),
        p("\u9996\u5148\u4ece GitHub \u514b\u9686 AICoin \u9879\u76ee\u4ee3\u7801\u5230\u672c\u5730\uff0c\u7136\u540e\u8fdb\u5165\u9879\u76ee\u76ee\u5f55\uff1a"),
        ...codeBlock([
          "# \u514b\u9686\u4ee3\u7801\u4ed3\u5e93",
          "git clone https://github.com/ctz168/aicoin.git",
          "",
          "# \u8fdb\u5165\u9879\u76ee\u76ee\u5f55",
          "cd aicoin",
        ]),

        h3("1.2.2 \u521b\u5efa\u865a\u62df\u73af\u5883"),
        p("\u5f3a\u70c8\u5efa\u8bae\u4f7f\u7528 Python \u865a\u62df\u73af\u5883\uff08venv\uff09\u6765\u9694\u79bb\u9879\u76ee\u4f9d\u8d56\uff0c\u907f\u514d\u4e0e\u7cfb\u7edf\u5176\u4ed6 Python \u5305\u53d1\u751f\u51b2\u7a81\u3002\u865a\u62df\u73af\u5883\u662f Python \u81ea\u5e26\u7684\u529f\u80fd\uff0c\u65e0\u9700\u989d\u5916\u5b89\u88c5\u4efb\u4f55\u5de5\u5177\uff1a"),
        ...codeBlock([
          "# \u521b\u5efa\u865a\u62df\u73af\u5883",
          "python -m venv .venv",
          "",
          "# \u6fc0\u6d3b\u865a\u62df\u73af\u5883 (Linux/macOS)",
          "source .venv/bin/activate",
          "",
          "# \u6fc0\u6d3b\u865a\u62df\u73af\u5883 (Windows)",
          ".venv\\Scripts\\activate",
        ]),

        h3("1.2.3 \u5b89\u88c5\u4f9d\u8d56\u5305"),
        p("\u6fc0\u6d3b\u865a\u62df\u73af\u5883\u540e\uff0c\u8fd0\u884c\u4ee5\u4e0b\u547d\u4ee4\u5b89\u88c5\u6240\u6709\u5fc5\u8981\u7684 Python \u4f9d\u8d56\u5305\u3002\u8fd9\u4e9b\u4f9d\u8d56\u5305\u62ec AI \u63a8\u7406\u6846\u67b6\uff08transformers\u3001torch\uff09\u3001Web \u670d\u52a1\u6846\u67b6\uff08aiohttp\uff09\u3001\u533a\u5757\u94fe\u4ea4\u4e92\u5e93\uff08web3\uff09\u7b49\uff1a"),
        ...codeBlock([
          "# \u5b89\u88c5\u6240\u6709\u4f9d\u8d56",
          "pip install -r requirements.txt",
        ]),
        p("\u4ee5\u4e0b\u662f requirements.txt \u4e2d\u5305\u542b\u7684\u4e3b\u8981\u4f9d\u8d56\u53ca\u5176\u7528\u9014\u8bf4\u660e\uff1a"),
        new Table({
          alignment: AlignmentType.CENTER,
          columnWidths: [2500, 1500, 5360],
          margins: { top: 100, bottom: 100, left: 180, right: 180 },
          rows: [
            new TableRow({ tableHeader: true, children: [makeHeaderCell("\u4f9d\u8d56\u5305", 2500), makeHeaderCell("\u7248\u672c\u8981\u6c42", 1500), makeHeaderCell("\u7528\u9014\u8bf4\u660e", 5360)] }),
            new TableRow({ children: [makeCell("torch", 2500), makeCell(">=2.0.0", 1500), makeCell("PyTorch \u6df1\u5ea6\u5b66\u4e60\u6846\u67b6\uff0c\u7528\u4e8e AI \u6a21\u578b\u63a8\u7406", 5360)] }),
            new TableRow({ children: [makeCell("transformers", 2500), makeCell(">=4.36.0", 1500), makeCell("HuggingFace \u6a21\u578b\u52a0\u8f7d\u4e0e\u63a8\u7406\u6846\u67b6", 5360)] }),
            new TableRow({ children: [makeCell("accelerate", 2500), makeCell(">=0.25.0", 1500), makeCell("\u6a21\u578b\u63a8\u7406\u52a0\u901f\u5e93", 5360)] }),
            new TableRow({ children: [makeCell("aiohttp", 2500), makeCell(">=3.9.0", 1500), makeCell("\u5f02\u6b65 HTTP \u670d\u52a1\u6846\u67b6\uff0c\u7528\u4e8e API \u7f51\u5173", 5360)] }),
            new TableRow({ children: [makeCell("web3", 2500), makeCell(">=6.15.0", 1500), makeCell("\u4ee5\u592a\u574a\u533a\u5757\u94fe\u4ea4\u4e92\u5e93\uff08Web3 \u6a21\u5f0f\u4e13\u7528\uff09", 5360)] }),
            new TableRow({ children: [makeCell("psutil", 2500), makeCell(">=5.9.0", 1500), makeCell("\u7cfb\u7edf\u8d44\u6e90\u76d1\u63a7\uff0c\u7528\u4e8e\u7b97\u529b\u8ba1\u91cf", 5360)] }),
          ]
        }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 50, after: 200 }, children: [new TextRun({ text: "\u8868 2\uff1a\u4e3b\u8981\u4f9d\u8d56\u5305\u8bf4\u660e", font: "Microsoft YaHei", size: 18, color: C.secondary, italics: true })] }),

        // === 1.3 \u914d\u7f6e\u8bf4\u660e ===
        h2("1.3 \u914d\u7f6e\u8bf4\u660e"),
        p("AICoin \u7684\u6240\u6709\u914d\u7f6e\u5747\u901a\u8fc7\u9879\u76ee\u6839\u76ee\u5f55\u4e0b\u7684 config.json \u6587\u4ef6\u7ba1\u7406\u3002\u9ed8\u8ba4\u914d\u7f6e\u5df2\u7ecf\u9884\u8bbe\u4e3a\u6a21\u62df\u6a21\u5f0f\uff0c\u53ef\u4ee5\u76f4\u63a5\u8fd0\u884c\u3002\u914d\u7f6e\u652f\u6301\u4e09\u79cd\u52a0\u8f7d\u65b9\u5f0f\uff0c\u4f18\u5148\u7ea7\u4ece\u9ad8\u5230\u4f4e\u4f9d\u6b21\u4e3a\uff1a\u73af\u5883\u53d8\u91cf\uff08AICOIN_ \u524d\u7f00\uff09\u3001\u914d\u7f6e\u6587\u4ef6\uff08config.json\uff09\u3001\u9ed8\u8ba4\u503c\u3002"),
        p("\u4ee5\u4e0b\u662f\u914d\u7f6e\u6587\u4ef6\u4e2d\u6700\u91cd\u8981\u7684\u914d\u7f6e\u9879\u8bf4\u660e\uff1a"),
        new Table({
          alignment: AlignmentType.CENTER,
          columnWidths: [2600, 1200, 1600, 3960],
          margins: { top: 100, bottom: 100, left: 180, right: 180 },
          rows: [
            new TableRow({ tableHeader: true, children: [makeHeaderCell("\u914d\u7f6e\u8def\u5f84", 2600), makeHeaderCell("\u7c7b\u578b", 1200), makeHeaderCell("\u9ed8\u8ba4\u503c", 1600), makeHeaderCell("\u8bf4\u660e", 3960)] }),
            new TableRow({ children: [makeCell("node.node_id", 2600), makeCell("string", 1200), makeCell("\u81ea\u52a8\u751f\u6210", 1600), makeCell("\u8282\u70b9\u552f\u4e00\u6807\u8bc6\u7b26", 3960)] }),
            new TableRow({ children: [makeCell("node.wallet_address", 2600), makeCell("string", 1200), makeCell("\u7a7a", 1600), makeCell("\u94b1\u5305\u5730\u5740\uff0c\u7528\u4e8e\u63a5\u6536\u6316\u77ff\u5956\u52b1", 3960)] }),
            new TableRow({ children: [makeCell("network.api_port", 2600), makeCell("int", 1200), makeCell("8080", 1600), makeCell("API \u7f51\u5173\u76d1\u542c\u7aef\u53e3", 3960)] }),
            new TableRow({ children: [makeCell("network.p2p_port", 2600), makeCell("int", 1200), makeCell("5000", 1600), makeCell("P2P \u7f51\u7edc\u901a\u4fe1\u7aef\u53e3", 3960)] }),
            new TableRow({ children: [makeCell("blockchain.mode", 2600), makeCell("string", 1200), makeCell("simulation", 1600), makeCell("simulation \u6216 web3", 3960)] }),
            new TableRow({ children: [makeCell("mining.auto_mine", 2600), makeCell("bool", 1200), makeCell("true", 1600), makeCell("\u662f\u5426\u81ea\u52a8\u5f00\u59cb\u6316\u77ff", 3960)] }),
            new TableRow({ children: [makeCell("mining.mining_interval", 2600), makeCell("int", 1200), makeCell("60", 1600), makeCell("\u7b97\u529b\u8bc1\u660e\u63d0\u4ea4\u95f4\u9694\uff08\u79d2\uff09", 3960)] }),
            new TableRow({ children: [makeCell("governance.enabled", 2600), makeCell("bool", 1200), makeCell("true", 1600), makeCell("\u662f\u5426\u542f\u7528\u94fe\u4e0a\u6cbb\u7406", 3960)] }),
            new TableRow({ children: [makeCell("model.name", 2600), makeCell("string", 1200), makeCell("Qwen2.5-0.5B", 1600), makeCell("\u63a8\u7406\u6a21\u578b\u540d\u79f0", 3960)] }),
            new TableRow({ children: [makeCell("routing.strategy", 2600), makeCell("string", 1200), makeCell("BALANCED", 1600), makeCell("BALANCED/LATENCY_FIRST/\u2026", 3960)] }),
          ]
        }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 50, after: 200 }, children: [new TextRun({ text: "\u8868 3\uff1a\u6838\u5fc3\u914d\u7f6e\u9879\u8bf4\u660e", font: "Microsoft YaHei", size: 18, color: C.secondary, italics: true })] }),

        // === 1.4 \u94b1\u5305\u7ba1\u7406 ===
        h2("1.4 \u94b1\u5305\u7ba1\u7406"),
        p("AICoin \u5185\u7f6e\u4e86\u5b89\u5168\u7684 HD \u94b1\u5305\u7cfb\u7edf\uff0c\u652f\u6301 BIP39 \u52a9\u8bb0\u8bcd\u6807\u51c6\u548c BIP44 \u8def\u5f84\u6d3e\u751f\u3002\u94b1\u5305\u662f\u53c2\u4e0e AICoin \u7f51\u7edc\u7684\u524d\u63d0\u6761\u4ef6\uff0c\u60a8\u9700\u8981\u5148\u521b\u5efa\u94b1\u5305\u624d\u80fd\u63a5\u6536\u6316\u77ff\u5956\u52b1\u3001\u53c2\u4e0e\u6cbb\u7406\u6295\u7968\u6216\u4f7f\u7528 API \u670d\u52a1\u3002\u94b1\u5305\u6587\u4ef6\u4f1a\u4ee5\u52a0\u5bc6\u5f62\u5f0f\u4fdd\u5b58\u5728 data/ \u76ee\u5f55\u4e0b\uff0c\u786e\u4fdd\u79c1\u94a5\u5b89\u5168\u3002"),
        p("\u60a8\u53ef\u4ee5\u901a\u8fc7\u4ee5\u4e0b\u4e24\u79cd\u65b9\u5f0f\u7ba1\u7406\u94b1\u5305\uff1a"),
        h3("1.4.1 \u5feb\u901f\u4f53\u9a8c\uff08\u6f14\u793a\u6a21\u5f0f\uff09"),
        p("\u6f14\u793a\u6a21\u5f0f\u4f1a\u81ea\u52a8\u521b\u5efa\u94b1\u5305\u5e76\u6a21\u62df\u6316\u77ff\u6d41\u7a0b\uff0c\u65e0\u9700\u4efb\u4f55\u624b\u52a8\u64cd\u4f5c\u3002\u8fd0\u884c\u4ee5\u4e0b\u547d\u4ee4\u5373\u53ef\uff1a"),
        ...codeBlock([
          "python run.py --demo",
        ]),
        p("\u8be5\u547d\u4ee4\u4f1a\u81ea\u52a8\u6267\u884c\u4ee5\u4e0b\u64cd\u4f5c\uff1a\u521b\u5efa/\u52a0\u8f7d\u94b1\u5305\u3001\u521d\u59cb\u5316\u6a21\u62df\u533a\u5757\u94fe\u3001\u9884\u5145 5000 AIC \u7528\u4e8e\u6295\u7968\u8d28\u62bc\u3001\u542f\u52a8\u6316\u77ff\u5f15\u64ce\u3001\u6a21\u62df 10 \u4e2a AI \u63a8\u7406\u4efb\u52a1\u3001\u63d0\u4ea4\u7b97\u529b\u8bc1\u660e\u3001\u8ba1\u7b97\u5e76\u9886\u53d6\u6316\u77ff\u5956\u52b1\u3002\u6316\u5230\u7684\u4ee3\u5e01\u4f1a\u76f4\u63a5\u8fdb\u5165\u60a8\u7684\u94b1\u5305\u5730\u5740\u3002"),

        h3("1.4.2 \u94b1\u5305\u7ba1\u7406\u754c\u9762"),
        p("\u5982\u679c\u9700\u8981\u521b\u5efa\u65b0\u94b1\u5305\u3001\u5bfc\u5165\u5df2\u6709\u94b1\u5305\u6216\u67e5\u770b\u94b1\u5305\u4fe1\u606f\uff0c\u53ef\u4ee5\u8fdb\u5165\u94b1\u5305\u7ba1\u7406\u754c\u9762\uff1a"),
        ...codeBlock([
          "python run.py --wallet",
        ]),
        p("\u5728\u94b1\u5305\u7ba1\u7406\u754c\u9762\u4e2d\uff0c\u60a8\u53ef\u4ee5\u6267\u884c\u4ee5\u4e0b\u64cd\u4f5c\uff1a"),
        new Paragraph({ numbering: { reference: "num-wallet", level: 0 }, spacing: { after: 80, line: 250 }, alignment: AlignmentType.LEFT, children: [new TextRun({ text: "\u521b\u5efa\u65b0\u94b1\u5305\uff1a\u8f93\u5165\u81f3\u5c11 8 \u4f4d\u5bc6\u7801\uff0c\u7cfb\u7edf\u4f1a\u81ea\u52a8\u751f\u6210 12 \u4e2a\u82f1\u6587\u5355\u8bcd\u7684 BIP39 \u52a9\u8bb0\u8bcd\uff0c\u8bf7\u52a1\u5fc5\u5b89\u5168\u4fdd\u7ba1\u8fd9\u4e9b\u52a9\u8bb0\u8bcd\uff0c\u4e22\u5931\u540e\u65e0\u6cd5\u6062\u590d\u94b1\u5305", font: "Microsoft YaHei", size: 21, color: C.body })] }),
        new Paragraph({ numbering: { reference: "num-wallet", level: 0 }, spacing: { after: 80, line: 250 }, alignment: AlignmentType.LEFT, children: [new TextRun({ text: "\u52a0\u8f7d\u94b1\u5305\uff1a\u4f7f\u7528\u521b\u5efa\u65f6\u8bbe\u7f6e\u7684\u5bc6\u7801\u89e3\u9501\u94b1\u5305\uff0c\u94b1\u5305\u6587\u4ef6\u4fdd\u5b58\u5728 data/wallet.dat", font: "Microsoft YaHei", size: 21, color: C.body })] }),
        new Paragraph({ numbering: { reference: "num-wallet", level: 0 }, spacing: { after: 80, line: 250 }, alignment: AlignmentType.LEFT, children: [new TextRun({ text: "\u67e5\u770b\u5730\u5740\uff1a\u94b1\u5305\u52a0\u8f7d\u540e\u4f1a\u663e\u793a\u60a8\u7684\u4ee5\u592a\u574a\u517c\u5bb9\u5730\u5740\uff0c\u7528\u4e8e\u63a5\u6536\u6316\u77ff\u5956\u52b1\u548c\u53c2\u4e0e\u6cbb\u7406", font: "Microsoft YaHei", size: 21, color: C.body })] }),
        new Paragraph({ numbering: { reference: "num-wallet", level: 0 }, spacing: { after: 200, line: 250 }, alignment: AlignmentType.LEFT, children: [new TextRun({ text: "\u67e5\u770b\u52a9\u8bb0\u8bcd\uff1a\u9700\u8981\u518d\u6b21\u8f93\u5165\u5bc6\u7801\u9a8c\u8bc1\u624d\u80fd\u67e5\u770b\u52a9\u8bb0\u8bcd", font: "Microsoft YaHei", size: 21, color: C.body })] }),

        // === 1.5 \u542f\u52a8\u6316\u77ff ===
        h2("1.5 \u542f\u52a8\u6316\u77ff\u8282\u70b9"),
        p("\u6316\u77ff\u662f AICoin \u7f51\u7edc\u7684\u6838\u5fc3\u529f\u80fd\u3002\u8282\u70b9\u901a\u8fc7\u8d21\u732e GPU/CPU \u7b97\u529b\u8fd0\u884c AI \u6a21\u578b\u63a8\u7406\u6765\u83b7\u53d6 AICoin \u5956\u52b1\u3002\u6316\u77ff\u5956\u52b1\u91c7\u7528\u6bd4\u7279\u5e01\u5f0f\u7684\u51cf\u534a\u673a\u5236\uff1a\u521d\u59cb\u5956\u52b1\u4e3a 50 AIC/\u533a\u5757\uff0c\u6bcf 210,000 \u4e2a\u533a\u5757\u51cf\u534a\u4e00\u6b21\uff0c\u6700\u5927\u4f9b\u5e94\u91cf 21,000,000 AIC\u3002\u60a8\u8d21\u732e\u7684\u7b97\u529b\u8d8a\u591a\uff0c\u5728\u5168\u7f51\u7b97\u529b\u4e2d\u5360\u6bd4\u8d8a\u9ad8\uff0c\u83b7\u5f97\u7684\u5956\u52b1\u5c31\u8d8a\u591a\u3002"),
        h3("1.5.1 \u4ea4\u4e92\u5f0f\u542f\u52a8"),
        p("\u8fd0\u884c\u4ee5\u4e0b\u547d\u4ee4\u8fdb\u5165\u4ea4\u4e92\u5f0f\u83dc\u5355\uff0c\u9009\u62e9\u5bf9\u5e94\u529f\u80fd\u5373\u53ef\uff1a"),
        ...codeBlock([
          "python run.py",
        ]),
        p("\u7cfb\u7edf\u4f1a\u663e\u793a\u4ee5\u4e0b\u83dc\u5355\uff1a"),
        ...codeBlock([
          "\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2555",
          "\u2551          AICoin \u8282\u70b9 v1.0                   \u2551",
          "\u2551     \u53bb\u4e2d\u5fc3\u5316 AI \u7b97\u529b\u6316\u77ff\u7f51\u7edc                  \u2551",
          "\u2560\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2563",
          "\u2551  1. \u6f14\u793a\u6316\u77ff (\u6a21\u62df\u6a21\u5f0f, \u65e0\u9700GPU)            \u2551",
          "\u2551  2. \u94b1\u5305\u7ba1\u7406 (\u521b\u5efa/\u5bfc\u5165\u94b1\u5305)                  \u2551",
          "\u2551  3. \u67e5\u770b\u72b6\u6001                                \u2551",
          "\u2551  4. \u9000\u51fa                                    \u2551",
          "\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2562",
        ]),

        h3("1.5.2 \u67e5\u770b\u8282\u70b9\u72b6\u6001"),
        p("\u968f\u65f6\u67e5\u770b\u60a8\u7684\u8282\u70b9\u72b6\u6001\uff0c\u5305\u62ec\u94b1\u5305\u4f59\u989d\u3001\u7d2f\u8ba1\u6316\u77ff\u91cf\u3001\u7b97\u529b\u8d21\u732e\u3001\u5168\u7f51\u603b\u7b97\u529b\u7b49\u4fe1\u606f\uff1a"),
        ...codeBlock([
          "python run.py --status",
        ]),

        h3("1.5.3 \u6316\u77ff\u5956\u52b1\u673a\u5236\u8be6\u89e3"),
        p("AICoin \u7684\u6316\u77ff\u5956\u52b1\u8ba1\u7b97\u516c\u5f0f\u5982\u4e0b\uff1a"),
        pMulti([
          { text: "node_reward = block_reward \u00d7 (node_power / total_network_power)", bold: true, font: "SarasaMonoSC", size: 19 }
        ], { indent: { left: 720, firstLine: 0 }, alignment: AlignmentType.LEFT }),
        p("\u5176\u4e2d block_reward \u662f\u5f53\u524d\u533a\u5757\u5956\u52b1\uff08\u521d\u59cb 50 AIC\uff0c\u6bcf 210,000 \u533a\u5757\u51cf\u534a\uff09\uff0cnode_power \u662f\u60a8\u7684\u7b97\u529b\u8d21\u732e\uff0ctotal_network_power \u662f\u5168\u7f51\u603b\u7b97\u529b\u3002\u60a8\u8d21\u732e\u7684\u7b97\u529b\u8d8a\u591a\uff0c\u5360\u6bd4\u8d8a\u9ad8\uff0c\u83b7\u5f97\u7684\u5956\u52b1\u5c31\u8d8a\u591a\u3002\u6316\u77ff\u5956\u52b1\u7684 80% \u5206\u914d\u7ed9\u7b97\u529b\u8282\u70b9\uff0c20% \u8fdb\u5165 DAO \u91d1\u5e93\u3002"),
        p("\u53e6\u5916\uff0c\u5f53\u5176\u4ed6\u7528\u6237\u901a\u8fc7 API \u8c03\u7528\u60a8\u8282\u70b9\u8fd0\u884c\u7684\u6a21\u578b\u65f6\uff0c\u8c03\u7528\u8005\u71c3\u70e7\u7684 AIC \u4ee3\u5e01\u4e5f\u4f1a\u6309 80% \u7684\u6bd4\u4f8b\u5206\u914d\u7ed9\u60a8\u3002\u8fd9\u610f\u5473\u7740\u60a8\u7684\u6536\u5165\u6765\u6e90\u6709\u4e24\u4e2a\uff1a\u6316\u77ff\u5956\u52b1 + API \u8c03\u7528\u5206\u6210\u3002"),

        // === 1.6 API \u8c03\u7528 ===
        h2("1.6 API \u8c03\u7528"),
        p("AICoin \u63d0\u4f9b\u4e0e OpenAI \u5b8c\u5168\u517c\u5bb9\u7684 API \u63a5\u53e3\uff0c\u60a8\u53ef\u4ee5\u76f4\u63a5\u5c06 AICoin \u8282\u70b9\u4f5c\u4e3a OpenAI API \u7684\u66ff\u4ee3\u54c1\u4f7f\u7528\u3002\u8c03\u7528 API \u9700\u8981\u71c3\u70e7 AICoin \u4ee3\u5e01\uff0c\u5206\u4e3a\u4e09\u4e2a\u4f18\u5148\u7ea7\u6863\u4f4d\uff0c\u4ef7\u683c\u4ece\u4f4e\u5230\u9ad8\u3002"),
        new Table({
          alignment: AlignmentType.CENTER,
          columnWidths: [2200, 2200, 2000, 2960],
          margins: { top: 100, bottom: 100, left: 180, right: 180 },
          rows: [
            new TableRow({ tableHeader: true, children: [makeHeaderCell("\u6863\u4f4d", 2200), makeHeaderCell("\u4ef7\u683c", 2200), makeHeaderCell("\u4f18\u5148\u7ea7", 2000), makeHeaderCell("\u9002\u7528\u573a\u666f", 2960)] }),
            new TableRow({ children: [makeCell("Basic", 2200), makeCell("0.01 AIC / 1K tokens", 2200), makeCell("\u6807\u51c6", 2000), makeCell("\u65e5\u5e38\u5f00\u53d1\u6d4b\u8bd5", 2960)] }),
            new TableRow({ children: [makeCell("Premium", 2200), makeCell("0.05 AIC / 1K tokens", 2200), makeCell("\u9ad8", 2000), makeCell("\u751f\u4ea7\u73af\u5883\u5e94\u7528", 2960)] }),
            new TableRow({ children: [makeCell("Priority", 2200), makeCell("0.10 AIC / 1K tokens", 2200), makeCell("\u6700\u9ad8", 2000), makeCell("\u4f4e\u5ef6\u8fdf\u5173\u952e\u4efb\u52a1", 2960)] }),
          ]
        }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 50, after: 200 }, children: [new TextRun({ text: "\u8868 4\uff1aAPI \u8c03\u7528\u5b9a\u4ef7", font: "Microsoft YaHei", size: 18, color: C.secondary, italics: true })] }),

        h3("1.6.1 \u4f7f\u7528 Python requests \u8c03\u7528"),
        ...codeBlock([
          "import requests",
          "",
          "# \u8c03\u7528\u804a\u5929\u63a5\u53e3\uff08\u9700\u8981\u71c3\u70e7 AIC\uff09",
          "response = requests.post(",
          '    "http://localhost:8080/v1/chat/completions",',
          '    headers={"x-aicoin-address": "\u60a8\u7684\u94b1\u5305\u5730\u5740",',
          '               "Content-Type": "application/json"},',
          '    json={"model": "Qwen/Qwen2.5-0.5B-Instruct",',
          '          "messages": [{"role": "user", "content": "\u4f60\u597d"}],',
          '          "max_tokens": 100}',
          ")",
          "print(response.json())",
        ]),

        h3("1.6.2 \u4f7f\u7528 OpenAI SDK\uff08\u76f4\u63a5\u517c\u5bb9\uff09"),
        ...codeBlock([
          "from openai import OpenAI",
          "",
          "client = OpenAI(",
          '    base_url="http://localhost:8080/v1",',
          '    api_key="\u60a8\u7684\u94b1\u5305\u5730\u5740"',
          ")",
          "",
          "response = client.chat.completions.create(",
          '    model="Qwen/Qwen2.5-0.5B-Instruct",',
          '    messages=[{"role": "user", "content": "\u4f60\u597d"}]',
          ")",
          "print(response.choices[0].message.content)",
        ]),

        // === 1.7 Web3 \u751f\u4ea7\u6a21\u5f0f ===
        h2("1.7 Web3 \u751f\u4ea7\u6a21\u5f0f\u90e8\u7f72"),
        p("\u5982\u679c\u60a8\u5e0c\u671b\u5728\u771f\u5b9e\u7684\u533a\u5757\u94fe\u4e0a\u8fd0\u884c AICoin \u8282\u70b9\uff08\u800c\u975e\u6a21\u62df\u6a21\u5f0f\uff09\uff0c\u9700\u8981\u8fdb\u884c\u989d\u5916\u7684\u914d\u7f6e\u3002Web3 \u6a21\u5f0f\u9700\u8981\u8fde\u63a5\u5230\u4ee5\u592a\u574a\u517c\u5bb9\u7684\u533a\u5757\u94fe\u8282\u70b9\uff0c\u5e76\u90e8\u7f72\u5bf9\u5e94\u7684\u667a\u80fd\u5408\u7ea6\u3002"),
        h3("1.7.1 \u4fee\u6539\u914d\u7f6e\u6587\u4ef6"),
        ...codeBlock([
          "// config.json \u4e2d\u4fee\u6539\u4ee5\u4e0b\u5b57\u6bb5",
          "{",
          '  "blockchain": {',
          '    "mode": "web3",',
          '    "web3_rpc_url": "https://your-rpc-url.com",',
          '    "contract_address": "0x...",',
          '    "chain_id": 1',
          "  }",
          "}",
        ]),
        h3("1.7.2 \u90e8\u7f72\u667a\u80fd\u5408\u7ea6"),
        p("\u5728 Web3 \u6a21\u5f0f\u4e0b\uff0c\u9700\u8981\u5148\u5c06 Solidity \u667a\u80fd\u5408\u7ea6\u90e8\u7f72\u5230\u533a\u5757\u94fe\u4e0a\u3002\u9879\u76ee\u5305\u542b 5 \u4e2a Solidity \u5408\u7ea6\uff0c\u5747\u4f4d\u4e8e contracts/ \u76ee\u5f55\uff1a"),
        new Table({
          alignment: AlignmentType.CENTER,
          columnWidths: [2800, 6560],
          margins: { top: 100, bottom: 100, left: 180, right: 180 },
          rows: [
            new TableRow({ tableHeader: true, children: [makeHeaderCell("\u5408\u7ea6\u6587\u4ef6", 2800), makeHeaderCell("\u529f\u80fd\u8bf4\u660e", 6560)] }),
            new TableRow({ children: [makeCell("AICoinToken.sol", 2800), makeCell("ERC20 \u4ee3\u5e01\u5408\u7ea6\uff0c21,000,000 AIC \u6700\u5927\u4f9b\u5e94\u91cf", 6560, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("Mining.sol", 2800), makeCell("\u7b97\u529b\u8bc1\u660e\u6316\u77ff\u5408\u7ea6\uff0c\u5185\u7f6e\u6bd4\u7279\u5e01\u51cf\u534a\u5956\u52b1\u673a\u5236", 6560, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("Governance.sol", 2800), makeCell("DAO \u6cbb\u7406\u5408\u7ea6\uff0c\u652f\u6301\u63d0\u6848\u521b\u5efa\u3001\u6295\u7968\u3001\u6267\u884c", 6560, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("APIAccess.sol", 2800), makeCell("API \u8bbf\u95ee\u63a7\u5236\u5408\u7ea6\uff0c\u4ee3\u5e01\u71c3\u70e7\u8ba1\u8d39\u903b\u8f91", 6560, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("AICoinDAO.sol", 2800), makeCell("DAO \u805a\u5408\u5408\u7ea6\uff0c\u7edf\u4e00\u7ba1\u7406\u6240\u6709\u5b50\u5408\u7ea6\u4ea4\u4e92", 6560, AlignmentType.LEFT)] }),
          ]
        }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 50, after: 200 }, children: [new TextRun({ text: "\u8868 5\uff1a\u667a\u80fd\u5408\u7ea6\u6e05\u5355", font: "Microsoft YaHei", size: 18, color: C.secondary, italics: true })] }),

        // === 1.8 \u8fd0\u884c\u6d4b\u8bd5 ===
        h2("1.8 \u8fd0\u884c\u6d4b\u8bd5"),
        p("\u9879\u76ee\u5185\u7f6e\u4e86\u5b8c\u6574\u7684\u6d4b\u8bd5\u5957\u4ef6\uff0c\u5305\u542b 106 \u4e2a\u6d4b\u8bd5\u7528\u4f8b\uff0c\u8986\u76d6\u4e86\u533a\u5757\u94fe\u3001\u6316\u77ff\u5f15\u64ce\u3001\u6cbb\u7406\u7cfb\u7edf\u3001\u8def\u7531\u5f15\u64ce\u3001API \u7f51\u5173\u7b49\u6240\u6709\u6838\u5fc3\u6a21\u5757\u3002\u5efa\u8bae\u5728\u90e8\u7f72\u524d\u5148\u8fd0\u884c\u6d4b\u8bd5\u786e\u4fdd\u4e00\u5207\u6b63\u5e38\uff1a"),
        ...codeBlock([
          "# \u8fd0\u884c\u5168\u90e8\u6d4b\u8bd5",
          "python -m pytest tests/test_all.py -v",
          "",
          "# \u8fd0\u884c\u5e76\u663e\u793a\u8be6\u7ec6\u8f93\u51fa",
          "python -m pytest tests/test_all.py -v --tb=short",
        ]),

        // ============================================================
        // PART 2: \u6295\u7968\u9009\u6a21\u578b\u8bf4\u660e
        // ============================================================
        h1("\u7b2c\u4e8c\u90e8\u5206\uff1a\u6295\u7968\u9009\u5b9a\u6a21\u578b\u8bf4\u660e"),
        p("AICoin \u7f51\u7edc\u91c7\u7528 DAO \u6cbb\u7406\u673a\u5236\uff0c\u4ee3\u5e01\u6301\u6709\u8005\u53ef\u4ee5\u901a\u8fc7\u6295\u7968\u51b3\u5b9a\u7f51\u7edc\u8fd0\u884c\u54ea\u4e2a AI \u6a21\u578b\u3002\u8fd9\u662f AICoin \u533a\u522b\u4e8e\u5176\u4ed6\u53bb\u4e2d\u5fc3\u5316 AI \u7f51\u7edc\u7684\u6838\u5fc3\u7279\u8272\u2014\u2014\u7531\u793e\u533a\u5171\u540c\u51b3\u5b9a\u7f51\u7edc\u5e94\u8be5\u63d0\u4f9b\u4ec0\u4e48\u6837\u7684 AI \u670d\u52a1\u3002\u672c\u90e8\u5206\u5c06\u8be6\u7ec6\u89e3\u91ca\u6cbb\u7406\u6295\u7968\u7684\u5b8c\u6574\u6d41\u7a0b\u3001\u6295\u7968\u89c4\u5219\u3001\u53ef\u7528\u6a21\u578b\u5217\u8868\u4ee5\u53ca\u5177\u4f53\u7684\u64cd\u4f5c\u6b65\u9aa4\u3002"),

        // === 2.1 \u6cbb\u7406\u673a\u5236\u6982\u8ff0 ===
        h2("2.1 \u6cbb\u7406\u673a\u5236\u6982\u8ff0"),
        p("AICoin \u6cbb\u7406\u7cfb\u7edf\u7684\u8bbe\u8ba1\u501f\u9274\u4e86\u4ee5\u592a\u574a DAO \u548c Compound \u6cbb\u7406\u7684\u6210\u719f\u7ecf\u9a8c\uff0c\u786e\u4fdd\u53bb\u4e2d\u5fc3\u5316\u7f51\u7edc\u80fd\u591f\u900f\u660e\u3001\u516c\u5e73\u5730\u505a\u51fa\u91cd\u5927\u51b3\u7b56\u3002\u6cbb\u7406\u7cfb\u7edf\u652f\u6301\u56db\u79cd\u63d0\u6848\u7c7b\u578b\uff1a\u8fd0\u884c\u6a21\u578b\u9009\u62e9\uff08RUN_MODEL\uff09\u3001\u53c2\u6570\u4fee\u6539\uff08PARAM_CHANGE\uff09\u3001\u7d27\u6025\u64cd\u4f5c\uff08EMERGENCY\uff09\u548c\u534f\u8bae\u5347\u7ea7\uff08UPGRADE\uff09\u3002\u5176\u4e2d\u4e0e\u6a21\u578b\u9009\u62e9\u6700\u76f8\u5173\u7684\u662f RUN_MODEL \u63d0\u6848\u7c7b\u578b\u3002"),
        p("\u6295\u7968\u91c7\u7528\u4ee3\u5e01\u52a0\u6743\u673a\u5236\uff0c\u5373 1 AIC = 1 \u7968\u3002\u60a8\u6301\u6709\u7684 AICoin \u8d8a\u591a\uff0c\u60a8\u7684\u6295\u7968\u6743\u91cd\u5c31\u8d8a\u5927\u3002\u8fd9\u786e\u4fdd\u4e86\u771f\u6b63\u5173\u5fc3\u7f51\u7edc\u53d1\u5c55\u7684\u53c2\u4e0e\u8005\u80fd\u591f\u5bf9\u7f51\u7edc\u65b9\u5411\u4ea7\u751f\u66f4\u5927\u7684\u5f71\u54cd\u529b\u3002\u540c\u65f6\uff0c\u7cfb\u7edf\u8fd8\u652f\u6301\u6295\u7968\u59d4\u6258\u673a\u5236\uff0c\u5982\u679c\u60a8\u4e0d\u4fbf\u76f4\u63a5\u53c2\u4e0e\u6295\u7968\uff0c\u53ef\u4ee5\u5c06\u6295\u7968\u6743\u59d4\u6258\u7ed9\u5176\u4ed6\u60a8\u4fe1\u4efb\u7684\u5730\u5740\u3002"),

        h3("2.1.1 \u6295\u7968\u89c4\u5219\u8be6\u89e3"),
        new Table({
          alignment: AlignmentType.CENTER,
          columnWidths: [3400, 5960],
          margins: { top: 100, bottom: 100, left: 180, right: 180 },
          rows: [
            new TableRow({ tableHeader: true, children: [makeHeaderCell("\u89c4\u5219\u9879", 3400), makeHeaderCell("\u8bf4\u660e", 5960)] }),
            new TableRow({ children: [makeCell("\u6295\u7968\u6743\u91cd", 3400), makeCell("1 AIC = 1 \u7968\uff0c\u6309\u6301\u6709\u4ee3\u5e01\u6570\u91cf\u52a0\u6743", 5960, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u901a\u8fc7\u95e8\u69db", 3400), makeCell("\u8d5e\u6210\u7968\u5360\u603b\u7968\u6570\u7684 51% \u4ee5\u4e0a", 5960, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u6cd5\u5b9a\u4eba\u6570", 3400), makeCell("\u603b\u4f9b\u5e94\u91cf\u7684 10% \u53c2\u4e0e\u6295\u7968\u624d\u7b97\u6709\u6548", 5960, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u6807\u51c6\u6295\u7968\u5468\u671f", 3400), makeCell("7 \u5929\uff08\u666e\u901a\u63d0\u6848\uff09", 5960, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u7d27\u6025\u6295\u7968\u5468\u671f", 3400), makeCell("24 \u5c0f\u65f6\uff08\u7d27\u6025\u63d0\u6848\uff09", 5960, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u63d0\u6848\u6700\u4f4e\u8d28\u62bc", 3400), makeCell("1,000 AIC\uff0c\u63d0\u6848\u8005\u9700\u6301\u6709\u8db3\u591f\u4ee3\u5e01", 5960, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u6295\u7968\u59d4\u6258", 3400), makeCell("\u652f\u6301\u5c06\u6295\u7968\u6743\u59d4\u6258\u7ed9\u5176\u4ed6\u5730\u5740", 5960, AlignmentType.LEFT)] }),
          ]
        }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 50, after: 200 }, children: [new TextRun({ text: "\u8868 6\uff1a\u6cbb\u7406\u6295\u7968\u89c4\u5219", font: "Microsoft YaHei", size: 18, color: C.secondary, italics: true })] }),

        // === 2.2 \u53ef\u7528\u6a21\u578b\u5217\u8868 ===
        h2("2.2 \u53ef\u7528\u6a21\u578b\u5217\u8868"),
        p("AICoin \u7f51\u7edc\u9884\u6ce8\u518c\u4e86 6 \u4e2a AI \u6a21\u578b\uff0c\u8986\u76d6\u4e86\u4ece\u8d85\u8f7b\u91cf\u5bf9\u8bdd\u6a21\u578b\u5230\u5927\u578b\u8bed\u8a00\u6a21\u578b\uff0c\u4ee5\u53ca\u56fe\u50cf\u751f\u6210\u6a21\u578b\u3002\u793e\u533a\u53ef\u4ee5\u901a\u8fc7\u6cbb\u7406\u6295\u7968\u51b3\u5b9a\u7f51\u7edc\u5f53\u524d\u8fd0\u884c\u54ea\u4e2a\u6a21\u578b\uff0c\u4e5f\u53ef\u4ee5\u901a\u8fc7\u63d0\u6848\u6ce8\u518c\u65b0\u7684\u6a21\u578b\u3002"),
        new Table({
          alignment: AlignmentType.CENTER,
          columnWidths: [3200, 1800, 1600, 2760],
          margins: { top: 100, bottom: 100, left: 180, right: 180 },
          rows: [
            new TableRow({ tableHeader: true, children: [makeHeaderCell("\u6a21\u578b\u540d\u79f0", 3200), makeHeaderCell("\u6700\u5c0f\u5185\u5b58", 1800), makeHeaderCell("GPU\u663e\u5b58", 1600), makeHeaderCell("\u63a8\u8350\u8282\u70b9\u6570", 2760)] }),
            new TableRow({ children: [makeCell("Qwen2.5-0.5B-Instruct", 3200), makeCell("2 GB", 1800), makeCell("0 GB", 1600), makeCell("1 \u8282\u70b9", 2760)] }),
            new TableRow({ children: [makeCell("Qwen2.5-1.5B-Instruct", 3200), makeCell("4 GB", 1800), makeCell("0 GB", 1600), makeCell("1 \u8282\u70b9", 2760)] }),
            new TableRow({ children: [makeCell("Qwen2.5-7B-Instruct", 3200), makeCell("16 GB", 1800), makeCell("8 GB", 1600), makeCell("1 \u8282\u70b9", 2760)] }),
            new TableRow({ children: [makeCell("Qwen2.5-72B-Instruct", 3200), makeCell("144 GB", 1800), makeCell("72 GB", 1600), makeCell("4 \u8282\u70b9", 2760)] }),
            new TableRow({ children: [makeCell("Llama-3-70B", 3200), makeCell("140 GB", 1800), makeCell("70 GB", 1600), makeCell("4 \u8282\u70b9", 2760)] }),
            new TableRow({ children: [makeCell("Stable Diffusion XL", 3200), makeCell("12 GB", 1800), makeCell("8 GB", 1600), makeCell("1 \u8282\u70b9", 2760)] }),
          ]
        }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 50, after: 200 }, children: [new TextRun({ text: "\u8868 7\uff1a\u5df2\u6ce8\u518c AI \u6a21\u578b\u5217\u8868", font: "Microsoft YaHei", size: 18, color: C.secondary, italics: true })] }),
        p("\u5f53\u524d\u7f51\u7edc\u9ed8\u8ba4\u8fd0\u884c\u7684\u6d3b\u8dc3\u6a21\u578b\u662f Qwen2.5-7B-Instruct\u3002\u5982\u679c\u793e\u533a\u5e0c\u671b\u5207\u6362\u5230\u5176\u4ed6\u6a21\u578b\uff08\u4f8b\u5982 Llama-3-70B \u6216\u8005 Stable Diffusion XL\uff09\uff0c\u5c31\u9700\u8981\u53d1\u8d77\u4e00\u4e2a RUN_MODEL \u7c7b\u578b\u7684\u6cbb\u7406\u63d0\u6848\uff0c\u7ecf\u8fc7\u793e\u533a\u6295\u7968\u901a\u8fc7\u540e\uff0c\u6240\u6709\u8282\u70b9\u5c06\u81ea\u52a8\u5207\u6362\u5230\u65b0\u6a21\u578b\u3002"),

        // === 2.3 \u6295\u7968\u64cd\u4f5c\u6d41\u7a0b ===
        h2("2.3 \u6295\u7968\u64cd\u4f5c\u6d41\u7a0b"),
        p("\u4ee5\u4e0b\u662f\u901a\u8fc7\u6cbb\u7406\u6295\u7968\u6765\u9009\u5b9a\u6a21\u578b\u7684\u5b8c\u6574\u6d41\u7a0b\uff0c\u5206\u4e3a\u53d1\u8d77\u63d0\u6848\u3001\u793e\u533a\u6295\u7968\u3001\u63d0\u6848\u6267\u884c\u4e09\u4e2a\u9636\u6bb5\uff1a"),

        h3("2.3.1 \u7b2c\u4e00\u6b65\uff1a\u53d1\u8d77\u6a21\u578b\u5207\u6362\u63d0\u6848"),
        p("\u4efb\u4f55\u6301\u6709\u81f3\u5c11 1,000 AIC \u7684\u5730\u5740\u90fd\u53ef\u4ee5\u53d1\u8d77\u6a21\u578b\u5207\u6362\u63d0\u6848\u3002\u63d0\u6848\u53d1\u8d77\u540e\u4f1a\u8fdb\u5165 7 \u5929\u7684\u6295\u7968\u671f\uff0c\u671f\u95f4\u6240\u6709\u4ee3\u5e01\u6301\u6709\u8005\u90fd\u53ef\u4ee5\u53c2\u4e0e\u6295\u7968\u3002\u53d1\u8d77\u63d0\u6848\u7684\u5177\u4f53\u64cd\u4f5c\u5982\u4e0b\uff1a"),
        pMulti([
          { text: "\u2460 \u786e\u4fdd\u60a8\u7684\u94b1\u5305\u5730\u5740\u6301\u6709\u81f3\u5c11 1,000 AIC\uff08\u53ef\u901a\u8fc7\u6316\u77ff\u6216\u63a5\u6536\u8f6c\u8d26\u83b7\u5f97\uff09\u3002" },
        ]),
        pMulti([
          { text: "\u2461 \u786e\u8ba4\u60a8\u60f3\u8981\u5207\u6362\u7684\u76ee\u6807\u6a21\u578b\u5df2\u5728\u6a21\u578b\u6ce8\u518c\u8868\u4e2d\uff08\u53c2\u89c1\u4e0a\u65b9\u6a21\u578b\u5217\u8868\uff09\u3002" },
        ]),
        pMulti([
          { text: "\u2462 \u901a\u8fc7 API \u6216 Python \u4ee3\u7801\u53d1\u8d77\u63d0\u6848\uff1a" },
        ]),
        ...codeBlock([
          "# \u901a\u8fc7 API \u53d1\u8d77\u6a21\u578b\u5207\u6362\u63d0\u6848",
          "import requests",
          "",
          "response = requests.post(",
          '    "http://localhost:8080/v1/governance/proposals",',
          '    json={',
          '        "proposer": "\u60a8\u7684\u94b1\u5305\u5730\u5740",',
          '        "type": "RUN_MODEL",',
          '        "title": "\u5207\u6362\u5230 Llama-3-70B \u6a21\u578b",',
          '        "description": "\u63d0\u8bae\u5c06\u7f51\u7edc\u6d3b\u8dc3\u6a21\u578b\u5207\u6362\u4e3a Meta Llama-3-70B\uff0c',
          '                         \u4ee5\u63d0\u5347\u63a8\u7406\u8d28\u91cf\uff0c\u9002\u5408\u9700\u8981\u9ad8\u8d28\u91cf\u5bf9\u8bdd\u670d\u52a1\u7684\u573a\u666f",',
          '        "model_name": "meta-llama/Llama-3-70B"',
          "    }",
          ")",
          'proposal_id = response.json()["proposal_id"]',
          'print(f"\u63d0\u6848\u5df2\u521b\u5efa\uff0cID: {proposal_id}")',
        ]),
        pMulti([
          { text: "\u2463 \u63d0\u6848\u521b\u5efa\u6210\u529f\u540e\uff0c\u7cfb\u7edf\u4f1a\u8fd4\u56de\u63d0\u6848 ID\uff0c\u8bf7\u8bb0\u5f55\u8be5 ID \u7528\u4e8e\u540e\u7eed\u6295\u7968\u3002" },
        ]),

        h3("2.3.2 \u7b2c\u4e8c\u6b65\uff1a\u793e\u533a\u6295\u7968"),
        p("\u63d0\u6848\u8fdb\u5165\u6295\u7968\u671f\u540e\uff0c\u6240\u6709 AICoin \u6301\u6709\u8005\u90fd\u53ef\u4ee5\u53c2\u4e0e\u6295\u7968\u3002\u6295\u7968\u6743\u91cd\u7b49\u4e8e\u60a8\u6301\u6709\u7684 AICoin \u6570\u91cf\uff0c\u6bcf\u4e2a\u5730\u5740\u5bf9\u6bcf\u4e2a\u63d0\u6848\u53ea\u80fd\u6295\u7968\u4e00\u6b21\u3002\u5177\u4f53\u6295\u7968\u64cd\u4f5c\u5982\u4e0b\uff1a"),
        ...codeBlock([
          "# \u8d5e\u6210\u63d0\u6848",
          "response = requests.post(",
          '    "http://localhost:8080/v1/governance/vote",',
          '    json={',
          '        "voter": "\u60a8\u7684\u94b1\u5305\u5730\u5740",',
          '        "proposal_id": 1,',
          '        "support": true',
          "    }",
          ")",
          "",
          "# \u67e5\u8be2\u63d0\u6848\u72b6\u6001\u548c\u6295\u7968\u7ed3\u679c",
          "status = requests.get(",
          '    "http://localhost:8080/v1/governance/proposals"',
          ").json()",
          "for prop in status:",
          '    print(f"\u63d0\u6848 #{prop[\'id\']}: {prop[\'title\']}")',
          '    print(f"  \u72b6\u6001: {prop[\'status\']}, ',
          '          f"\u8d5e\u6210: {prop[\'votes_for\']}, ',
          '          f"\u53cd\u5bf9: {prop[\'votes_against\']}")',
        ]),

        h3("2.3.3 \u63d0\u6848\u751f\u547d\u5468\u671f\u8bf4\u660e"),
        p("\u63d0\u6848\u4ece\u521b\u5efa\u5230\u6267\u884c\u4f1a\u7ecf\u5386\u4ee5\u4e0b\u72b6\u6001\u53d8\u5316\uff1a"),
        new Table({
          alignment: AlignmentType.CENTER,
          columnWidths: [2000, 2000, 5360],
          margins: { top: 100, bottom: 100, left: 180, right: 180 },
          rows: [
            new TableRow({ tableHeader: true, children: [makeHeaderCell("\u72b6\u6001", 2000), makeHeaderCell("\u82f1\u6587", 2000), makeHeaderCell("\u8bf4\u660e", 5360)] }),
            new TableRow({ children: [makeCell("\u6d3b\u8dc3", 2000), makeCell("ACTIVE", 2000), makeCell("\u6295\u7968\u8fdb\u884c\u4e2d\uff0c\u6240\u6709\u4ee3\u5e01\u6301\u6709\u8005\u5747\u53ef\u6295\u7968", 5360, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u5df2\u901a\u8fc7", 2000), makeCell("PASSED", 2000), makeCell("\u6295\u7968\u671f\u7ed3\u675f\uff0c\u8d5e\u6210\u7387\u226551%\u4e14\u8fbe\u5230\u6cd5\u5b9a\u4eba\u6570", 5360, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u5df2\u62d2\u7edd", 2000), makeCell("REJECTED", 2000), makeCell("\u6295\u7968\u671f\u7ed3\u675f\uff0c\u8d5e\u6210\u7387<51%", 5360, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u5df2\u8fc7\u671f", 2000), makeCell("EXPIRED", 2000), makeCell("\u6295\u7968\u671f\u7ed3\u675f\uff0c\u672a\u8fbe\u5230\u6cd5\u5b9a\u4eba\u6570\uff0810%\uff09", 5360, AlignmentType.LEFT)] }),
            new TableRow({ children: [makeCell("\u5df2\u6267\u884c", 2000), makeCell("EXECUTED", 2000), makeCell("\u63d0\u6848\u901a\u8fc7\u540e\u5df2\u6267\u884c\uff0c\u6a21\u578b\u5df2\u5207\u6362", 5360, AlignmentType.LEFT)] }),
          ]
        }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 50, after: 200 }, children: [new TextRun({ text: "\u8868 8\uff1a\u63d0\u6848\u72b6\u6001\u8bf4\u660e", font: "Microsoft YaHei", size: 18, color: C.secondary, italics: true })] }),

        h3("2.3.4 \u63d0\u6848\u901a\u8fc7\u540e\u7684\u6267\u884c\u673a\u5236"),
        p("\u5f53\u63d0\u6848\u6295\u7968\u901a\u8fc7\u540e\uff08\u8d5e\u6210\u7387\u8fbe\u5230 51% \u4e14\u8fbe\u5230\u6cd5\u5b9a\u4eba\u6570\uff09\uff0c\u7cfb\u7edf\u4f1a\u81ea\u52a8\u6267\u884c\u6a21\u578b\u5207\u6362\u64cd\u4f5c\u3002\u5177\u4f53\u6d41\u7a0b\u5982\u4e0b\uff1a"),
        pMulti([
          { text: "\u2460 ProposalExecutor \u63a5\u6536\u5230\u901a\u8fc7\u7684\u63d0\u6848\uff0c\u8c03\u7528 _execute_model_switch() \u65b9\u6cd5\u3002" },
        ]),
        pMulti([
          { text: "\u2461 \u8c03\u7528 ModelRegistry.set_active_model() \u66f4\u65b0\u5f53\u524d\u6d3b\u8dc3\u6a21\u578b\u3002" },
        ]),
        pMulti([
          { text: "\u2462 \u901a\u8fc7 P2P \u7f51\u7edc\u5411\u6240\u6709\u5df2\u8fde\u63a5\u8282\u70b9\u5e7f\u64ad\u6a21\u578b\u5207\u6362\u901a\u77e5\u3002" },
        ]),
        pMulti([
          { text: "\u2463 \u5404\u8282\u70b9\u6536\u5230\u901a\u77e5\u540e\u81ea\u52a8\u4e0b\u8f7d\u5e76\u52a0\u8f7d\u65b0\u6a21\u578b\u3002" },
        ]),
        pMulti([
          { text: "\u2464 \u6a21\u578b\u52a0\u8f7d\u5b8c\u6210\u540e\uff0c\u65b0\u7684\u6a21\u578b\u5373\u53ef\u901a\u8fc7 API \u63a5\u53e3\u8bbf\u95ee\u3002" },
        ]),
        p("\u6574\u4e2a\u8fc7\u7a0b\u662f\u5168\u81ea\u52a8\u7684\uff0c\u4e0d\u9700\u8981\u4eba\u5de5\u5e72\u9884\u3002\u4f46\u9700\u8981\u6ce8\u610f\u7684\u662f\uff0c\u8282\u70b9\u9700\u8981\u6709\u8db3\u591f\u7684\u786c\u4ef6\u8d44\u6e90\uff08\u5185\u5b58\u3001GPU \u663e\u5b58\uff09\u624d\u80fd\u8fd0\u884c\u65b0\u6a21\u578b\u3002\u5982\u679c\u7f51\u7edc\u603b\u8d44\u6e90\u4e0d\u8db3\uff0c\u53ef\u4ee5\u5728\u53d1\u8d77\u63d0\u6848\u524d\u901a\u8fc7 ModelRegistry.can_network_run_model() \u65b9\u6cd5\u68c0\u67e5\u7f51\u7edc\u662f\u5426\u6709\u8db3\u591f\u8d44\u6e90\u8fd0\u884c\u76ee\u6807\u6a21\u578b\u3002"),

        // === 2.4 \u6295\u7968\u59d4\u6258 ===
        h2("2.4 \u6295\u7968\u59d4\u6258\u673a\u5236"),
        p("\u5982\u679c\u60a8\u4e0d\u65b9\u4fbf\u76f4\u63a5\u53c2\u4e0e\u6295\u7968\uff0c\u53ef\u4ee5\u5c06\u60a8\u7684\u6295\u7968\u6743\u59d4\u6258\u7ed9\u5176\u4ed6\u60a8\u4fe1\u4efb\u7684\u5730\u5740\u3002\u88ab\u59d4\u6258\u8005\u5728\u6295\u7968\u65f6\u5c06\u83b7\u5f97\u60a8\u7684\u4ee3\u5e01\u6743\u91cd\uff0c\u4ece\u800c\u589e\u52a0\u5176\u6295\u7968\u5f71\u54cd\u529b\u3002\u59d4\u6258\u64cd\u4f5c\u662f\u53ef\u9006\u7684\uff0c\u60a8\u53ef\u4ee5\u968f\u65f6\u64a4\u9500\u59d4\u6258\u3002\u9700\u8981\u6ce8\u610f\u7684\u662f\uff0c\u59d4\u6258\u4e0d\u4f1a\u5f71\u54cd\u5df2\u7ecf\u5b8c\u6210\u7684\u6295\u7968\u3002"),
        ...codeBlock([
          "# \u59d4\u6258\u6295\u7968\u6743",
          "requests.post(",
          '    "http://localhost:8080/v1/governance/delegate",',
          '    json={"delegator": "\u60a8\u7684\u5730\u5740", "delegate": "\u88ab\u59d4\u6258\u8005\u5730\u5740"}',
          ")",
          "",
          "# \u64a4\u9500\u59d4\u6258",
          'requests.post("http://localhost:8080/v1/governance/revoke_delegation",',
          '    json={"delegator": "\u60a8\u7684\u5730\u5740"}',
          ")",
        ]),

        // === 2.5 \u5b8c\u6574\u793a\u4f8b ===
        h2("2.5 \u5b8c\u6574\u6295\u7968\u793a\u4f8b"),
        p("\u4ee5\u4e0b\u662f\u4e00\u4e2a\u5b8c\u6574\u7684\u6295\u7968\u793a\u4f8b\uff0c\u6f14\u793a\u4e86\u5982\u4f55\u4ece\u53d1\u8d77\u63d0\u6848\u5230\u6a21\u578b\u5207\u6362\u7684\u5168\u8fc7\u7a0b\u3002\u5047\u8bbe\u793e\u533a\u5e0c\u671b\u5c06\u5f53\u524d\u6d3b\u8dc3\u6a21\u578b\u4ece Qwen2.5-7B-Instruct \u5207\u6362\u4e3a Qwen2.5-72B-Instruct\uff1a"),
        ...codeBlock([
          "from core.wallet import AICoinWallet",
          "from core.blockchain import BlockchainManager",
          "from core.governance import GovernanceManager",
          "",
          "# 1. \u521d\u59cb\u5316",
          "wallet = AICoinWallet(\"data/wallet.dat\")",
          "wallet.load(\"\u60a8\u7684\u5bc6\u7801\")",
          "my_addr = wallet.get_address()",
          "",
          "blockchain = BlockchainManager({\"mode\": \"simulation\"})",
          "governance = GovernanceManager(blockchain)",
          "",
          "# 2. \u786e\u4fdd\u94b1\u5305\u6709\u8db3\u591f\u4ee3\u5e01 (\u81f3\u5c11 1000 AIC)",
          "balance = blockchain.get_balance(my_addr)",
          'print(f"\u94b1\u5305\u4f59\u989d: {balance / 10**18} AIC")',
          "",
          "# 3. \u53d1\u8d77\u6a21\u578b\u5207\u6362\u63d0\u6848",
          'proposal_id = governance.create_model_proposal(',
          '    proposer=my_addr,',
          '    model_name="Qwen/Qwen2.5-72B-Instruct",',
          '    description="\u5207\u6362\u5230 72B \u6a21\u578b\u4ee5\u63d0\u5347\u63a8\u7406\u8d28\u91cf"',
          ")",
          'print(f"\u63d0\u6848 ID: {proposal_id}")',
          "",
          "# 4. \u6295\u7968\u8d5e\u6210",
          "governance.vote(my_addr, proposal_id, support=True)",
          "",
          "# 5. \u67e5\u770b\u63d0\u6848\u72b6\u6001",
          "proposal = governance.get_proposal(proposal_id)",
          'print(f"\u63d0\u6848\u72b6\u6001: {proposal[\'status\']}")',
          'print(f"\u8d5e\u6210\u7387: {proposal[\'approval_rate\']*100:.1f}%")',
        ]),

        // ============================================================
        // PART 3: \u5e38\u89c1\u95ee\u9898
        // ============================================================
        h1("\u7b2c\u4e09\u90e8\u5206\uff1a\u5e38\u89c1\u95ee\u9898"),
        p("\u672c\u90e8\u5206\u6574\u7406\u4e86\u90e8\u7f72\u548c\u4f7f\u7528 AICoin \u8fc7\u7a0b\u4e2d\u53ef\u80fd\u9047\u5230\u7684\u5e38\u89c1\u95ee\u9898\u53ca\u89e3\u51b3\u65b9\u6848\uff0c\u5e2e\u52a9\u60a8\u5feb\u901f\u6392\u67e5\u548c\u89e3\u51b3\u95ee\u9898\u3002"),

        h2("3.1 \u6316\u77ff\u76f8\u5173"),
        pMulti([
          { text: "\u95ee\uff1a\u6316\u77ff\u7684\u4ee3\u5e01\u5230\u5e95\u53bb\u54ea\u91cc\u4e86\uff1f", bold: true },
        ]),
        p("\u7b54\uff1a\u6316\u77ff\u5956\u52b1\u4f1a\u81ea\u52a8\u53d1\u9001\u5230\u60a8\u7684 AICoin \u94b1\u5305\u5730\u5740\u3002\u5728\u6a21\u62df\u6a21\u5f0f\u4e0b\uff0c\u4f59\u989d\u4fe1\u606f\u4fdd\u5b58\u5728\u672c\u5730\u533a\u5757\u94fe\u72b6\u6001\u4e2d\uff1b\u5728 Web3 \u6a21\u5f0f\u4e0b\uff0c\u4f59\u989d\u76f4\u63a5\u8bb0\u5f55\u5728\u94fe\u4e0a\u3002\u60a8\u53ef\u4ee5\u968f\u65f6\u901a\u8fc7 python run.py --status \u67e5\u770b\u4f59\u989d\u3002"),
        pMulti([
          { text: "\u95ee\uff1a\u6316\u77ff\u6536\u5165\u6765\u6e90\u6709\u54ea\u4e9b\uff1f", bold: true },
        ]),
        p("\u7b54\uff1a\u6316\u77ff\u6536\u5165\u6709\u4e24\u4e2a\u6765\u6e90\u3002\u7b2c\u4e00\uff0c\u533a\u5757\u6316\u77ff\u5956\u52b1\uff0c\u6839\u636e\u60a8\u7684\u7b97\u529b\u5360\u6bd4\u5206\u914d\u65b0\u94f8\u9020\u7684 AICoin\uff0c\u80fd\u5f97\u591a\u5c11\u53d6\u51b3\u4e8e\u60a8\u7684\u7b97\u529b\u5728\u5168\u7f51\u4e2d\u7684\u5360\u6bd4\u3002\u7b2c\u4e8c\uff0cAPI \u8c03\u7528\u5206\u6210\uff0c\u5f53\u5176\u4ed6\u7528\u6237\u901a\u8fc7 API \u8c03\u7528\u60a8\u8282\u70b9\u63d0\u4f9b\u7684\u63a8\u7406\u670d\u52a1\u65f6\uff0c\u71c3\u70e7\u7684 AICoin \u4e2d\u7684 80% \u4f1a\u5206\u914d\u7ed9\u60a8\u3002"),

        h2("3.2 \u6cbb\u7406\u76f8\u5173"),
        pMulti([
          { text: "\u95ee\uff1a\u6295\u7968\u671f\u95f4\u53ef\u4ee5\u4fee\u6539\u5417\uff1f", bold: true },
        ]),
        p("\u7b54\uff1a\u6295\u7968\u671f\u4e00\u65e6\u5f00\u59cb\u5c31\u65e0\u6cd5\u4fee\u6539\u3002\u6807\u51c6\u63d0\u6848\u7684\u6295\u7968\u671f\u56fa\u5b9a\u4e3a 7 \u5929\uff0c\u7d27\u6025\u63d0\u6848\u4e3a 24 \u5c0f\u65f6\u3002\u5982\u679c\u60a8\u9700\u8981\u8c03\u6574\u6295\u7968\u671f\uff0c\u53ef\u4ee5\u5148\u53d1\u8d77\u4e00\u4e2a PARAM_CHANGE \u7c7b\u578b\u7684\u63d0\u6848\u6765\u4fee\u6539\u6295\u7968\u5468\u671f\u53c2\u6570\u3002"),
        pMulti([
          { text: "\u95ee\uff1a\u53ef\u4ee5\u6ce8\u518c\u81ea\u5b9a\u4e49\u6a21\u578b\u5417\uff1f", bold: true },
        ]),
        p("\u7b54\uff1a\u53ef\u4ee5\u3002\u60a8\u53ef\u4ee5\u901a\u8fc7 ModelRegistry.register_model() \u65b9\u6cd5\u6ce8\u518c\u65b0\u7684\u6a21\u578b\uff0c\u7136\u540e\u518d\u53d1\u8d77 RUN_MODEL \u63d0\u6848\u8ba9\u793e\u533a\u6295\u7968\u51b3\u5b9a\u662f\u5426\u8fd0\u884c\u8be5\u6a21\u578b\u3002\u6ce8\u518c\u65b0\u6a21\u578b\u65f6\u9700\u8981\u63d0\u4f9b\u6700\u5c0f\u5185\u5b58\u3001GPU \u663e\u5b58\u3001\u63a8\u8350\u8282\u70b9\u6570\u548c\u5206\u7c7b\u7b49\u4fe1\u606f\u3002"),

        h2("3.3 \u7f51\u7edc\u76f8\u5173"),
        pMulti([
          { text: "\u95ee\uff1a\u5982\u4f55\u8fde\u63a5\u5230\u5176\u4ed6\u8282\u70b9\uff1f", bold: true },
        ]),
        p("\u7b54\uff1a\u5728 config.json \u7684 network.seeds \u5b57\u6bb5\u4e2d\u914d\u7f6e\u79cd\u5b50\u8282\u70b9\u5730\u5740\uff08\u683c\u5f0f\u4e3a host:port\uff09\uff0c\u8282\u70b9\u542f\u52a8\u65f6\u4f1a\u81ea\u52a8\u5c1d\u8bd5\u8fde\u63a5\u8fd9\u4e9b\u79cd\u5b50\u8282\u70b9\u3002\u786e\u4fdd\u60a8\u7684\u9632\u706b\u5899\u5f00\u653e\u4e86 P2P \u7aef\u53e3\uff08\u9ed8\u8ba4 5000\uff09\u548c API \u7aef\u53e3\uff08\u9ed8\u8ba4 8080\uff09\u3002\u5982\u679c\u8282\u70b9\u5728\u5bb6\u5eAD\u7f51\u7edc\u73af\u5883\u4e0b\uff0c\u53ef\u4ee5\u5229\u7528 servermodel \u7684 NAT \u7a7f\u900f\u529f\u80fd\u3002"),
      ]
    }
  ]
});

// ============ GENERATE ============
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/home/z/my-project/download/AICoin_\u90e8\u7f72\u6307\u5357_\u6295\u7968\u8bf4\u660e.docx", buffer);
  console.log("Document generated successfully!");
});
