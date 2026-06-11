import { execFileSync } from "node:child_process";

const cwd = process.cwd();

// Patterns to hand to ripgrep. Use String.raw so backslashes reach rg
// verbatim, and avoid escaping characters that don't need it (e.g. `"`).
const patterns = [
  String.raw`import \* as api from`,
  String.raw`from "[^"]*lib/api"`,
  String.raw`api\.createTask\(`,
  String.raw`api\.updateTask\(`,
  String.raw`api\.deleteTask\(`,
  String.raw`api\.uploadTaskAttachment\(`,
  String.raw`api\.completeTaskWithReview\(`,
];

let output = "";

try {
  output = execFileSync(
    "rg",
    ["-n", patterns.join("|"), "app", "components", "lib"],
    { cwd, encoding: "utf8" },
  );
} catch (error) {
  if (error && typeof error === "object" && "status" in error && error.status === 1) {
    output = "";
  } else {
    throw error;
  }
}

const lines = output
  .split("\n")
  .map((line) => line.trim())
  .filter(Boolean);

const directWrites = lines.filter((line) =>
  /api\.(createTask|updateTask|deleteTask|uploadTaskAttachment|completeTaskWithReview)\(/.test(line),
);
const directImports = lines.filter((line) => /lib\/api/.test(line) && !directWrites.includes(line));

if (directWrites.length > 0) {
  process.stdout.write("=== direct-task-writes ===\n");
  process.stdout.write(`${directWrites.join("\n")}\n`);
}

if (directImports.length > 0) {
  process.stdout.write("=== direct-api-imports ===\n");
  process.stdout.write(`${directImports.join("\n")}\n`);
}
