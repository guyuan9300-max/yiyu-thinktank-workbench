// Lighthouse runner for 益语智库 brand mirror website audit.
// Usage: node run_audit.mjs <url> [--max-wait=120000]
// Outputs a single JSON line on stdout with shape:
// { url, fetchedAt, scores: {performance, accessibility, bestPractices, seo}, mobileFriendly,
//   downloadableDocs: [{url, type}], stats: {requests, transferKb}, error?: string }

import lighthouse from "lighthouse";
import * as chromeLauncher from "chrome-launcher";

const args = process.argv.slice(2);
const url = args.find((a) => !a.startsWith("--"));
if (!url) {
  process.stderr.write("missing target url\n");
  process.exit(2);
}
const maxWaitArg = args.find((a) => a.startsWith("--max-wait="));
const maxWait = maxWaitArg ? Number(maxWaitArg.split("=")[1]) : 90000;

async function main() {
  const chrome = await chromeLauncher.launch({
    chromeFlags: [
      "--headless=new",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-dev-shm-usage",
    ],
  });
  try {
    const options = {
      logLevel: "error",
      output: "json",
      onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
      port: chrome.port,
      maxWaitForLoad: maxWait,
      formFactor: "mobile",
      screenEmulation: {
        mobile: true,
        width: 360,
        height: 640,
        deviceScaleFactor: 2,
        disabled: false,
      },
      throttling: {
        rttMs: 150,
        throughputKbps: 1638.4,
        cpuSlowdownMultiplier: 4,
        requestLatencyMs: 0,
        downloadThroughputKbps: 0,
        uploadThroughputKbps: 0,
      },
    };
    const result = await lighthouse(url, options);
    if (!result) throw new Error("lighthouse returned empty result");
    const lhr = result.lhr;
    const cats = lhr.categories || {};
    const scoreOf = (key) => {
      const cat = cats[key];
      if (!cat || cat.score == null) return null;
      return Math.round(cat.score * 100);
    };

    // 文档可下载性扫描: 看 network-requests audit, 找 PDF / DOC / XLS / PPT 链接.
    const downloadableDocs = [];
    const netRequests = lhr.audits?.["network-requests"]?.details?.items || [];
    for (const item of netRequests) {
      const itemUrl = item.url || "";
      const mt = (item.mimeType || "").toLowerCase();
      const ext = itemUrl.split("?")[0].split("#")[0].split(".").pop().toLowerCase();
      const docExts = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"];
      if (mt.includes("pdf") || docExts.includes(ext)) {
        downloadableDocs.push({ url: itemUrl, type: ext || "unknown" });
      }
    }

    const stats = {
      requests: netRequests.length,
      transferKb: Math.round(
        netRequests.reduce((sum, r) => sum + (r.transferSize || 0), 0) / 1024,
      ),
      finalUrl: lhr.finalDisplayedUrl || lhr.finalUrl || url,
    };

    const result_payload = {
      url,
      fetchedAt: new Date().toISOString(),
      scores: {
        performance: scoreOf("performance"),
        accessibility: scoreOf("accessibility"),
        bestPractices: scoreOf("best-practices"),
        seo: scoreOf("seo"),
      },
      mobileFriendly: lhr.configSettings?.formFactor === "mobile",
      downloadableDocs,
      stats,
    };
    process.stdout.write(JSON.stringify(result_payload) + "\n");
  } finally {
    await chrome.kill();
  }
}

main().catch((err) => {
  process.stdout.write(
    JSON.stringify({ url, fetchedAt: new Date().toISOString(), error: String(err?.message || err) }) +
      "\n",
  );
  process.exit(1);
});
