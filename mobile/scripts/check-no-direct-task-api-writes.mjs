import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const targets = [
  "app/(tabs)/tasks.tsx",
  "app/(tabs)/calendar.tsx",
  "components/CreateTask.tsx",
  "components/TaskDetail.tsx",
  "components/TaskReviewComposer.tsx",
  "components/RecordNote.tsx",
];

const bannedPatterns = [
  /lib\/api/,
  /api\.createTask\(/,
  /api\.updateTask\(/,
  /api\.deleteTask\(/,
  /api\.uploadTaskAttachment\(/,
  /api\.completeTaskWithReview\(/,
];

const violations = [];

for (const relativePath of targets) {
  const contents = readFileSync(join(root, relativePath), "utf8");
  for (const pattern of bannedPatterns) {
    if (pattern.test(contents)) {
      violations.push(`${relativePath}: ${pattern}`);
    }
  }
}

if (violations.length > 0) {
  console.error("Direct lib/api usage is blocked in task local-first surfaces:");
  for (const violation of violations) {
    console.error(`- ${violation}`);
  }
  process.exit(1);
}

console.log("PASS: no direct task API writes in guarded task local-first surfaces.");
