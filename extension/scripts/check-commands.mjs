import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(
  fileURLToPath(import.meta.url)
);
const extensionRoot = path.resolve(
  scriptDirectory,
  ".."
);

const packageJson = JSON.parse(
  fs.readFileSync(
    path.join(extensionRoot, "package.json"),
    "utf8"
  )
);

const extensionSource = fs.readFileSync(
  path.join(extensionRoot, "src", "extension.ts"),
  "utf8"
);

const requiredCommands = [
  "proofcode.pingCore",
  "proofcode.analyzeCurrentFile",
  "proofcode.analyzeWorkspace",
  "proofcode.openHotspot",
  "proofcode.inspectHotspot",
  "proofcode.verifyBaseline",
  "proofcode.verifyCandidateFile",
  "proofcode.recordCandidateDecision",
  "proofcode.viewDecisionHistory",
  "proofcode.benchmarkCandidate"
];

const contributed = new Set(
  packageJson.contributes.commands.map(
    (item) => item.command
  )
);

const activated = new Set(
  packageJson.activationEvents
    .filter((item) => item.startsWith("onCommand:"))
    .map((item) => item.slice("onCommand:".length))
);

const missing = [];

for (const command of requiredCommands) {
  if (!contributed.has(command)) {
    missing.push(`${command}: package.json command 없음`);
  }

  if (!activated.has(command)) {
    missing.push(`${command}: activationEvent 없음`);
  }

  if (!extensionSource.includes(`"${command}"`)) {
    missing.push(`${command}: extension.ts 등록 없음`);
  }
}

if (missing.length > 0) {
  console.error("ProofCode command regression detected:");
  for (const item of missing) {
    console.error(`- ${item}`);
  }
  process.exit(1);
}

console.log(
  `ProofCode command check passed: ${requiredCommands.length} commands`
);
