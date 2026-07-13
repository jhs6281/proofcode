import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import * as path from "node:path";

export interface ComplexityBreakdown {
  conditions: number;
  loops: number;
  boolean_branches: number;
  exception_handlers: number;
  comprehensions: number;
  match_cases: number;
}

export interface FunctionEvidence {
  return_count: number;
  call_count: number;
  raise_count: number;
  max_nesting_depth: number;
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
  evidence: FunctionEvidence;
  reasons: string[];
}

export interface WorkspaceAnalysis {
  workspace_path: string;
  scanned_files: number;
  supported_structure_files: number;
  total_lines: number;
  total_classes: number;
  total_functions: number;
  category_counts: {
    source: number;
    test: number;
    example: number;
  };
  hotspots: Hotspot[];
}

export interface CoreAnalyzeWorkspaceResponse {
  status: "ok";
  protocol_version: string;
  workspace_analysis: WorkspaceAnalysis;
}

export class CoreClient {
  public constructor(
    private readonly pythonPath: string,
    private readonly workspaceRoot: string,
    private readonly timeoutMs = 30_000
  ) {}

  public analyzeWorkspace(
    includeTests: boolean,
    includeExamples: boolean
  ): Promise<CoreAnalyzeWorkspaceResponse> {
    const args = [
      "analyze-workspace",
      this.workspaceRoot,
      "--hotspot-limit",
      "20"
    ];

    if (includeTests) args.push("--include-tests");
    if (includeExamples) args.push("--include-examples");

    return this.run<CoreAnalyzeWorkspaceResponse>(args);
  }

  private run<T>(args: string[]): Promise<T> {
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

      this.collect(child, resolve, reject);
    });
  }

  private collect<T>(
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
      fail(new Error(`ProofCode Core timed out after ${this.timeoutMs}ms.`));
    }, this.timeoutMs);

    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => { stdout += chunk; });
    child.stderr.on("data", (chunk: string) => { stderr += chunk; });

    child.on("error", (error) => {
      clearTimeout(timer);
      fail(new Error(`Python 실행 실패: ${error.message}`));
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      if (settled) return;

      if (code !== 0) {
        fail(new Error(stderr.trim()));
        return;
      }

      try {
        settled = true;
        resolve(JSON.parse(stdout.trim()) as T);
      } catch (error) {
        fail(new Error(`Core JSON 해석 실패: ${String(error)}`));
      }
    });
  }
}
