import { execFileSync } from "node:child_process";
import { readdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = dirname(__dirname);
const buildRoot = join(repoRoot, ".mobile-core-tests");
const testsDir = join(repoRoot, "lib", "__tests__");

rmSync(buildRoot, { recursive: true, force: true });

execFileSync(
  "npx",
  ["tsc", "-p", "tsconfig.tests.json"],
  {
    cwd: repoRoot,
    stdio: "inherit",
  },
);

const testFiles = readdirSync(testsDir)
  .filter((file) => file.endsWith(".test.mjs"))
  .sort()
  .map((file) => join("lib", "__tests__", file));

if (testFiles.length === 0) {
  throw new Error("No core test files found.");
}

execFileSync(
  process.execPath,
  ["--test", ...testFiles],
  {
    cwd: repoRoot,
    stdio: "inherit",
  },
);
