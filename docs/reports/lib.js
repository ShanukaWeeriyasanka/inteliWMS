/*
 * Shared Word-document helpers for the IT3041 reports (docx-js).
 * Formatting rules: Times New Roman everywhere; topics 16 pt bold underlined; sub-topics 14 pt bold;
 * body 12 pt justified; page border on every page; borders on every table; "N | Page" footer.
 */
const D = require("docx");
const {
  Document, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, BorderStyle, AlignmentType,
  HeadingLevel, Footer, PageNumber, TableOfContents, ShadingType, LevelFormat, UnderlineType,
  PageBorderDisplay, PageBorderOffsetFrom, PageBorderZOrder, VerticalAlign, ImageRun,
} = D;

const FONT = "Times New Roman";
const BODY = 24;          // 12 pt
const CONTENT_W = 9026;   // A4 width 11906 − 2 × 1440 margins
const LINE = { style: BorderStyle.SINGLE, size: 6, color: "000000" };
const DASH = { style: BorderStyle.DASHED, size: 8, color: "7F7F7F" };
const TABLE_BORDERS = { top: LINE, bottom: LINE, left: LINE, right: LINE, insideHorizontal: LINE, insideVertical: LINE };
const HEAD_SHADE = { type: ShadingType.CLEAR, color: "auto", fill: "E7E6E6" };

let figureNo = 0;
const figures = [];  // {n, caption, test, steps}

function resetFigures() { figureNo = 0; figures.length = 0; Object.keys(shotIndex).forEach((k) => delete shotIndex[k]); }

/* "**bold**" inside a string becomes a bold run */
function runs(text, base = {}) {
  const out = [];
  String(text).split(/(\*\*[^*]+\*\*)/).forEach((part) => {
    if (!part) return;
    const bold = part.startsWith("**") && part.endsWith("**");
    out.push(new TextRun({ text: bold ? part.slice(2, -2) : part, font: FONT, size: BODY, ...base, ...(bold ? { bold: true } : {}) }));
  });
  return out;
}

function P(text, opts = {}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.JUSTIFIED,
    spacing: { after: opts.after ?? 120, before: opts.before ?? 0, line: 276 },
    keepNext: opts.keepNext,
    children: runs(text, opts.run || {}),
  });
}

function H1(text, first = false) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: !first, children: [new TextRun({ text, font: FONT })] });
}
function H2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, children: [new TextRun({ text, font: FONT })] });
}

function bullets(items, level = 0) {
  return items.map((t) => new Paragraph({
    numbering: { reference: "bullets", level }, alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 60, line: 276 }, children: runs(t),
  }));
}
let listInstance = 0;
/* Each call starts a new list at 1 (own numbering instance) */
function numbered(items, ref = "steps") {
  listInstance += 1;
  const instance = listInstance;
  return items.map((t) => new Paragraph({
    numbering: { reference: ref, level: 0, instance }, alignment: AlignmentType.LEFT, spacing: { after: 40 }, children: runs(t),
  }));
}

function cellParas(content, opts = {}) {
  const list = Array.isArray(content) ? content : [content];
  return list.map((t) => new Paragraph({
    alignment: opts.align || AlignmentType.LEFT, spacing: { after: 40 },
    children: runs(t, opts.bold ? { bold: true } : {}),
  }));
}

function cell(content, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: opts.shade ? HEAD_SHADE : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    verticalAlign: VerticalAlign.TOP,
    children: cellParas(content, opts),
  });
}

/* Two-column field/content table (test cases, vulnerabilities) */
function kv(rows, labelW = 2300) {
  const valueW = CONTENT_W - labelW;
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [labelW, valueW], borders: TABLE_BORDERS,
    rows: [
      new TableRow({ tableHeader: true, children: [cell("Field", labelW, { shade: true, bold: true }), cell("Content", valueW, { shade: true, bold: true })] }),
      ...rows.map(([k, v]) => new TableRow({ cantSplit: false, children: [cell(k, labelW, { bold: true }), cell(v, valueW)] })),
    ],
  });
}

/* Grid table with a shaded header row; widths in DXA must sum to CONTENT_W */
function grid(headers, rows, widths) {
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, borders: TABLE_BORDERS,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], { shade: true, bold: true })) }),
      ...rows.map((r) => new TableRow({ children: r.map((c, i) => cell(c, widths[i])) })),
    ],
  });
}

function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 },
    children: [new TextRun({ text, font: FONT, size: BODY, italics: true })],
  });
}

const fs = require("fs");
const path = require("path");
const IMG_DIR = path.join(__dirname, "capture", "img");
const MAX_W_PX = 600;    // ≈ 6.25 in, the text width
const MAX_H_PX = 790;    // ≈ 8.2 in, leaves room for the caption on the page
const shotIndex = {};    // test id -> number of figures used so far

function pngSize(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }

/* Dashed box with capture instructions; used only when the captured image is missing */
function placeholder(steps) {
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
    borders: { top: DASH, bottom: DASH, left: DASH, right: DASH, insideHorizontal: DASH, insideVertical: DASH },
    rows: [new TableRow({ children: [new TableCell({
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, color: "auto", fill: "F7F7F7" },
      margins: { top: 120, bottom: 120, left: 160, right: 160 },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
          children: [new TextRun({ text: `[ Insert screenshot — Figure ${figureNo} ]`, font: FONT, size: BODY, bold: true, color: "595959" })] }),
        new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: "How to capture:", font: FONT, size: BODY, bold: true })] }),
        ...steps.map((s, i) => new Paragraph({ spacing: { after: 30 }, alignment: AlignmentType.LEFT, children: runs(`${i + 1}. ${s}`) })),
      ],
    })] })],
  });
}

/* Screenshot: the captured image capture/img/fig_<test>_<n>.png (n = 1-based figure index within the test),
   scaled to the text width (or to the page height for tall captures), then a numbered caption */
function shot(test, captionText, steps = [], idx) {
  figureNo += 1;
  shotIndex[test] = idx || (shotIndex[test] || 0) + 1;
  const file = path.join(IMG_DIR, `fig_${test}_${shotIndex[test]}.png`);
  const embedded = fs.existsSync(file);
  figures.push({ n: figureNo, test, idx: shotIndex[test], caption: captionText, steps, file: embedded ? path.basename(file) : null });
  if (!embedded) return [placeholder(steps), caption(`Figure ${figureNo}: ${captionText}`)];
  // Multi-request exchanges (3+ requests) also exist as one image per request (…_p1.png, …_p2.png): embed those so each stays readable
  const stem = file.slice(0, -4);
  const parts = [];
  for (let i = 1; fs.existsSync(`${stem}_p${i}.png`); i += 1) parts.push(`${stem}_p${i}.png`);
  const files = parts.length ? parts : [file];
  const imgs = files.map((f, i) => {
    const data = fs.readFileSync(f);
    const { w, h } = pngSize(data);
    const scale = Math.min(MAX_W_PX / w, MAX_H_PX / h);
    return new Paragraph({
      alignment: AlignmentType.CENTER, keepNext: i === files.length - 1, spacing: { before: 60, after: 60 },
      children: [new ImageRun({ type: "png", data, transformation: { width: Math.round(w * scale), height: Math.round(h * scale) },
        altText: { title: `Figure ${figureNo}`, description: captionText, name: path.basename(f) } })],
    });
  });
  const note = parts.length ? ` (${parts.length} requests, shown in order)` : "";
  return [...imgs, caption(`Figure ${figureNo}: ${captionText}${note}`)];
}

function spacer() { return new Paragraph({ spacing: { after: 120 }, children: [] }); }

function footer() {
  return new Footer({ children: [new Paragraph({ alignment: AlignmentType.LEFT, children: [
    new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: BODY, bold: true }),
    new TextRun({ text: " | P a g e", font: FONT, size: BODY, color: "7F7F7F" }),
  ] })] });
}

function toc() {
  return [
    new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Table of Contents", font: FONT, size: 32, bold: true })] }),
    new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-2" }),
    P("(If the table of contents is empty or out of date: right-click it in Word → Update Field → Update entire table.)",
      { run: { italics: true, color: "7F7F7F" } }),
  ];
}

function cover(info) {
  const rows = info.rows.map(([k, v]) => new TableRow({ children: [cell(k, 2800, { bold: true }), cell(v, CONTENT_W - 2800)] }));
  return [
    new Paragraph({ spacing: { before: 600, after: 120 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "IT3041 – Information Retrieval and Web Analytics", font: FONT, size: 36 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
      children: [new TextRun({ text: "Individual Assignment", font: FONT, size: 28 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
      children: [new TextRun({ text: info.title, font: FONT, size: 32, bold: true })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
      children: [new TextRun({ text: "[ Insert SLIIT logo here ]", font: FONT, size: BODY, color: "7F7F7F", italics: true })] }),
    new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [2800, CONTENT_W - 2800], borders: TABLE_BORDERS, rows }),
  ];
}

function makeDocument(children, title) {
  const pageBorder = { style: BorderStyle.SINGLE, size: 12, color: "000000", space: 24 };
  return new Document({
    creator: "IT3041 student", title, features: { updateFields: true },
    styles: {
      // Overriding the built-in heading styles (not adding new ones) keeps a single definition of each
      default: {
        document: { run: { font: FONT, size: BODY }, paragraph: { alignment: AlignmentType.JUSTIFIED } },
        heading1: { run: { font: FONT, size: 32, bold: true, underline: { type: UnderlineType.SINGLE }, color: "000000" },
          paragraph: { spacing: { before: 120, after: 200 }, outlineLevel: 0, alignment: AlignmentType.LEFT } },
        heading2: { run: { font: FONT, size: 28, bold: true, color: "000000" },
          paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1, alignment: AlignmentType.LEFT } },
      },
    },
    numbering: { config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
      ] },
      { reference: "steps", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ] },
    ] },
    sections: [{
      properties: {
        titlePage: true,
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440, footer: 600 },
          borders: {
            pageBorderTop: pageBorder, pageBorderBottom: pageBorder, pageBorderLeft: pageBorder, pageBorderRight: pageBorder,
            pageBorders: { display: PageBorderDisplay.ALL_PAGES, offsetFrom: PageBorderOffsetFrom.PAGE, zOrder: PageBorderZOrder.FRONT },
          },
        },
      },
      footers: { default: footer(), first: new Footer({ children: [new Paragraph({ children: [] })] }) },
      children,
    }],
  });
}

/* One test case: H2 heading, field table, screenshot boxes */
function testCase(sectionNo, t) {
  const out = [H2(`${sectionNo} Test Case ${t.id}: ${t.title}`)];
  const n = (t.shots || []).length;
  const own = n ? [rangeText(Array.from({ length: n }, (_, i) => figureNo + 1 + i)) + " (below)"] : [];
  const ev = [...(Array.isArray(t.evidence) ? t.evidence : [t.evidence]).map(resolve), ...own];
  out.push(kv([
    ["Test ID", t.id + (t.source ? ` (source: ${t.source})` : "")],
    ["Area / framework", t.area],
    ["Objective", t.objective],
    ["Input / attack scenario", t.input],
    ["Expected result", t.expected],
    ["Actual result – BEFORE", t.before],
    ["Actual result – AFTER (re-test)", t.after],
    ["Evidence", ev],
    ["Observations", t.observations],
    ["Outcome", t.outcome],
    ["Conclusion", t.conclusion],
  ]));
  out.push(spacer());
  (t.shots || []).forEach((s) => out.push(...shot(t.id, s.caption, s.steps, s.n)));
  return out;
}

/* "{fig:PI-04#1}" -> "Figure 12" once that figure has been placed; "{figs:PI-04}" -> all figures of a test */
function figNos(test) { return figures.filter((f) => f.test === test).map((f) => f.n); }
function rangeText(ns) {
  if (!ns.length) return "[figure not found]";
  if (ns.length === 1) return `Figure ${ns[0]}`;
  const contiguous = ns.every((n, i) => i === 0 || n === ns[i - 1] + 1);
  return contiguous ? `Figures ${ns[0]}–${ns[ns.length - 1]}` : `Figures ${ns.join(", ")}`;
}
function resolve(v) {
  if (Array.isArray(v)) return v.map(resolve);
  if (typeof v !== "string") return v;
  return v.replace(/\{fig:([A-Z0-9-]+)#(\d+)\}/g, (m, t, i) => {
    const f = figures.find((x) => x.test === t && x.idx === Number(i));
    return f ? `Figure ${f.n}` : "[figure not found]";
  }).replace(/\{figs:([A-Z0-9-]+)\}/g, (m, t) => rangeText(figNos(t)));
}

/* Appendix table listing every screenshot placeholder in the report */
function figureChecklist() {
  return grid(["Fig.", "Test", "What the figure shows", "Image file (docs/reports/capture/img)"],
    figures.map((f) => [String(f.n), f.test, f.caption, f.file || "[not captured]"]), [700, 1300, CONTENT_W - 4600, 2600]);
}

module.exports = {
  D, FONT, BODY, CONTENT_W, P, H1, H2, bullets, numbered, kv, grid, shot, spacer, caption, toc, cover, makeDocument,
  testCase, figureChecklist, resetFigures, figures, resolve, rangeText,
};
