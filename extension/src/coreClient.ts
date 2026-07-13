import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import * as path from "node:path";

export interface CorePingResponse {
  status: "ok";
  message: string;
  protocol_version: string;
}

export interface ComplexityBreakdown {
  conditions: number;
  loops: number;
  boolean_branches: number;
  exception_handlers: number;
  comprehensions: number;
  match_cases: number;
}

export interface Hotspot {
  file_path: string;
  relative_path: string;
  file_name: string;
  category: "source" | "test" | "example";
  symbol_name: string;
  symbol_type: string;
  line_start: number;
  line_end: number;
  line_count: number;
  complexity: number;
  complexity_breakdown: ComplexityBreakdown;
  reasons: string[];
}

export interface CategoryCounts {
  source: number;
  test: number;
  example: number;
}

export interface WorkspaceAnalysis {
  workspace_path: string;
  scanned_files: number;
  supported_structure_files: number;
  total_lines: number;
  total_classes: number;
  total_functions: number;
  category_counts: CategoryCounts;
  hotspots: Hotspot[];
}

export interface CoreAnalyzeWorkspaceResponse {
  status: "ok";
  protocol_version: string;
  workspace_analysis: WorkspaceAnalysis;
}

export interface CoreClientOptions {
  pythonPath: string;
  workspaceRoot: string;
  timeoutMs?: number;
}

export interface AnalyzeWorkspaceOptions {
  includeTests: boolean;
  includeExamples: boolean;
}

export class CoreClient {
  private readonly pythonPath: string;
  private readonly workspaceRoot: string;
  private readonly timeoutMs: number;

  public constructor(options: CoreClientOptions) {
    this.pythonPath = options.pythonPath;
    this.workspaceRoot = options.workspaceRoot;
    this.timeoutMs = options.timeoutMs ?? 30_000;
  }

  public ping(): Promise<CorePingResponse> {
    return this.runCoreCommand<CorePingResponse>(["ping"]);
  }

  public analyzeWorkspace(
    workspacePath: string,
    options: AnalyzeWorkspaceOptions
  ): Promise<CoreAnalyzeWorkspaceResponse> {
    const args = [
      "analyze-workspace",
      workspacePath,
      "--hotspot-limit",
      "20"
    ];

    if (options.includeTests) {
      args.push("--include-tests");
    }

    if (options.includeExamples) {
      args.push("--include-examples");
    }

    return this.runCoreCommand<CoreAnalyzeWorkspaceResponse>(args);
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
              PYTHONUTF8: "1",
              PYTHONIOENCODING: "utf-8",
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

    const fail = (error: Error): void => {
      if (!settled) {
        settled = true;
        reject(error);
      }
    };

    const timer = setTimeout(() => {
      child.kill();
      fail(new Error(
        `ProofCode Core timed out after ${this.timeoutMs}ms.`
      ));
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
      fail(new Error(
        `Could not start Python process "${this.pythonPath}": ${error.message}`
      ));
    });

    child.on("close", (code) => {
      clearTimeout(timer);

      if (settled) {
        return;
      }

      if (code !== 0) {
        let message = stderr.trim();

        try {
          const payload = JSON.parse(message) as {
            error?: { message?: string };
          };
          message = payload.error?.message ?? message;
        } catch {
          // stderr가 JSON이 아니면 원문을 사용합니다.
        }

        fail(new Error(
          `ProofCode Core exited with code ${code}. ${message}`
        ));
        return;
      }

      try {
        settled = true;
        resolve(JSON.parse(stdout.trim()) as T);
      } catch (error) {
        const reason = error instanceof Error
          ? error.message
          : String(error);

        fail(new Error(
          `ProofCode Core returned invalid JSON: ${reason}`
        ));
      }
    });
  }
}
