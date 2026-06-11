import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = dirname(__dirname);
const localDbSource = readFileSync(join(repoRoot, "lib", "local-db.ts"), "utf8");
const runtimeFlagsSource = readFileSync(join(repoRoot, "lib", "runtime-flags.ts"), "utf8");

function run(command, args) {
  try {
    const output = execFileSync(command, args, {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
    return { ok: true, output };
  } catch (error) {
    const stdout = error?.stdout ? String(error.stdout).trim() : "";
    const stderr = error?.stderr ? String(error.stderr).trim() : "";
    return {
      ok: false,
      output: [stdout, stderr].filter(Boolean).join("\n").trim(),
    };
  }
}

function extractSchemaVersion(source) {
  const match = source.match(/CURRENT_SCHEMA_VERSION\s*=\s*(\d+)/);
  return match?.[1] ?? "unknown";
}

function extractDefaultFlags(source) {
  const match = source.match(/const DEFAULT_FLAGS:[\s\S]+?=\s*\{([\s\S]*?)\n\};/);
  if (!match) {
    return [];
  }
  return match[1]
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/,$/, ""));
}

const branch = run("git", ["rev-parse", "--abbrev-ref", "HEAD"]);
const commit = run("git", ["rev-parse", "HEAD"]);
const status = run("git", ["status", "--short"]);
const tsc = run("npx", ["tsc", "--noEmit"]);
const coreTests = run("npm", ["run", "test:core"]);
const noDirectWrites = run("npm", ["run", "check:no-direct-task-api-writes"]);
const inventory = run("npm", ["run", "inventory:direct-api-usage"]);

const timestamp = new Date().toISOString();
const outputPath = join(repoRoot, "scripts", "checkpoint-snapshot.md");

const contents = `# Checkpoint Snapshot

Generated at: \`${timestamp}\`

## Baseline

- Branch: \`${branch.output || "unknown"}\`
- Commit: \`${commit.output || "unknown"}\`
- Schema version: \`${extractSchemaVersion(localDbSource)}\`

## Runtime Flags Default

${extractDefaultFlags(runtimeFlagsSource).map((line) => `- \`${line}\``).join("\n")}

## Gate Summary

- \`npx tsc --noEmit\`: ${tsc.ok ? "PASS" : "FAIL"}
- \`npm run test:core\`: ${coreTests.ok ? "PASS" : "FAIL"}
- \`npm run check:no-direct-task-api-writes\`: ${noDirectWrites.ok ? "PASS" : "FAIL"}
- \`npm run inventory:direct-api-usage\`: ${inventory.ok ? "PASS" : "FAIL"}

## Inventory Snapshot

\`\`\`text
${inventory.output || "(no output)"}
\`\`\`

## Git Status

\`\`\`text
${status.output || "(clean)"}
\`\`\`
`;

writeFileSync(outputPath, contents);
console.log(outputPath);
