/*
 * Builds the two IT3041 assessment reports as Word documents.
 *   node docs/reports/build_reports.js            (needs the npm package "docx")
 * Output: docs/reports/IT3041_Student1_Prompt_Injection_Report.docx
 *         docs/reports/IT3041_Student3_Responsible_AI_Report.docx
 */
const fs = require("fs");
const path = require("path");
const { Packer } = require("docx");

const OUT = process.env.REPORT_OUT || __dirname;
const jobs = [
  ["IT3041_Student1_Prompt_Injection_Report.docx", require("./student1")],
  ["IT3041_Student3_Responsible_AI_Report.docx", require("./student3")],
];

(async () => {
  for (const [name, mod] of jobs) {
    const doc = mod.build();
    const buf = await Packer.toBuffer(doc);
    fs.writeFileSync(path.join(OUT, name), buf);
    console.log("wrote", name, `${Math.round(buf.length / 1024)} KB`, "tests:", mod.TESTS.length);
  }
})().catch((e) => { console.error(e); process.exit(1); });
