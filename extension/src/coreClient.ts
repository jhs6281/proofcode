import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import * as path from "node:path";

export interface CorePingResponse {
  status: "ok";
  message: string;
  protocol_version: string;
}

export interface FileAnalysis {
  path: string;
  file_name: string;
  language: string;
  size_bytes: number;
  total_lines: number;
  non_empty_lines: number;
  empty_lines: number;
  sha256: string;
}

export interface CoreAnalyzeFileResponse {
  status: "ok";
  protocol_version: string;
  analysis: FileAnalysis;
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
    return this.runCoreCommand<CorePingResponse>(["ping"]);
  }

  public analyzeFile(filePath: string): Promise<CoreAnalyzeFileResponse> {
    return this.runCoreCommand<CoreAnalyzeFileResponse>(["analyze-file", filePath]);
  }

  private runCoreCommand<T>(args: string[]): Promise<T> {
    const coreSrc = path.join(this.workspaceRoot, "core", "src");

    return new Promise((resolve, reject) => {
      const child = spawn(
        this.pythonPath,
        ["-m", "proofcode_core", ...args],
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

      this.collectJsonResult<T>(child, resolve, reject);
    });
  }

  private collectJsonResult<T>(
    child: ChildProcessWithoutNullStreams,
    resolve: (value: T) => void,
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
      finishWithError(
        new Error(`ProofCode Core timed out after ${this.timeoutMs}ms.`)
      );
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
        settled = true;
        resolve(JSON.parse(stdout.trim()) as T);
      } catch (error) {
        const reason = error instanceof Error ? error.message : String(error);
        finishWithError(
          new Error(`ProofCode Core returned invalid JSON: ${reason}\n${stdout}`)
        );
      }
    });
  }
}
