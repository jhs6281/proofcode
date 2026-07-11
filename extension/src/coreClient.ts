import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import * as path from "node:path";

export interface CorePingResponse {
  status: "ok";
  message: string;
  protocol_version: string;
}

export interface CoreClientOptions {
  pythonPath: string;
  workspaceRoot: string;
  timeoutMs?: number;
}

export class CoreClient {
  private readonly pythonPath: string;
  private readonly workspaceRoot: string;
  private readonly timeoutMs: number;

  public constructor(options: CoreClientOptions) {
    this.pythonPath = options.pythonPath;
    this.workspaceRoot = options.workspaceRoot;
    this.timeoutMs = options.timeoutMs ?? 10_000;
  }

  public ping(): Promise<CorePingResponse> {
    const coreSrc = path.join(this.workspaceRoot, "core", "src");

    return new Promise((resolve, reject) => {
      const child = spawn(
        this.pythonPath,
        ["-m", "proofcode_core", "ping"],
        {
          cwd: this.workspaceRoot,
          env: {
            ...process.env,
            PYTHONPATH: [coreSrc, process.env.PYTHONPATH]
              .filter(Boolean)
              .join(path.delimiter)
          },
          windowsHide: true
        }
      );

      this.collectPingResult(child, resolve, reject);
    });
  }

  private collectPingResult(
    child: ChildProcessWithoutNullStreams,
    resolve: (value: CorePingResponse) => void,
    reject: (reason: Error) => void
  ): void {
    let stdout = "";
    let stderr = "";
    let settled = false;

    const finishWithError = (error: Error): void => {
      if (!settled) {
        settled = true;
        reject(error);
      }
    };

    const timer = setTimeout(() => {
      child.kill();
      finishWithError(new Error(`ProofCode Core timed out after ${this.timeoutMs}ms.`));
    }, this.timeoutMs);

    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });

    child.on("error", (error) => {
      clearTimeout(timer);
      finishWithError(
        new Error(`Could not start Python process "${this.pythonPath}": ${error.message}`)
      );
    });

    child.on("close", (code) => {
      clearTimeout(timer);

      if (settled) {
        return;
      }

      if (code !== 0) {
        finishWithError(
          new Error(`ProofCode Core exited with code ${code}. ${stderr.trim()}`)
        );
        return;
      }

      try {
        const response = JSON.parse(stdout.trim()) as CorePingResponse;

        if (response.status !== "ok") {
          finishWithError(new Error("ProofCode Core returned an unexpected status."));
          return;
        }

        settled = true;
        resolve(response);
      } catch (error) {
        const reason = error instanceof Error ? error.message : String(error);
        finishWithError(
          new Error(`ProofCode Core returned invalid JSON: ${reason}\n${stdout}`)
        );
      }
    });
  }
}
