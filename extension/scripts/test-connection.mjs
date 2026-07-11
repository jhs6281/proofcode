import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const extensionDir = path.resolve(currentDir, "..");
const repositoryRoot = path.resolve(extensionDir, "..");
const coreSrc = path.join(repositoryRoot, "core", "src");
const pythonPath = process.env.PROOFCODE_PYTHON ?? "python";

const child = spawn(
  pythonPath,
  ["-m", "proofcode_core", "ping"],
  {
    cwd: repositoryRoot,
    env: {
      ...process.env,
      PYTHONPATH: [coreSrc, process.env.PYTHONPATH]
        .filter(Boolean)
        .join(path.delimiter)
    },
    windowsHide: true
  }
);

let stdout = "";
let stderr = "";

child.stdout.setEncoding("utf8");
child.stderr.setEncoding("utf8");
child.stdout.on("data", (chunk) => {
  stdout += chunk;
});
child.stderr.on("data", (chunk) => {
  stderr += chunk;
});

child.on("error", (error) => {
  console.error(`Python 실행 실패: ${error.message}`);
  process.exitCode = 1;
});

child.on("close", (code) => {
  if (code !== 0) {
    console.error(stderr || `Core exited with code ${code}`);
    process.exitCode = 1;
    return;
  }

  try {
    const payload = JSON.parse(stdout.trim());

    if (payload.status !== "ok") {
      throw new Error(`Unexpected status: ${payload.status}`);
    }

    console.log(`PASS: ${payload.message}`);
  } catch (error) {
    console.error(`Invalid Core response: ${error.message}`);
    process.exitCode = 1;
  }
});
