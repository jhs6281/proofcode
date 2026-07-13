import * as fs from "node:fs";
import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import * as path from "node:path";

export const SUPPORTED_PROTOCOL_VERSION = "1";

export interface CoreEnvelope<T> {
  status: "ok" | "error";
  kind: string;
  app_version: string;
  protocol_version: string;
  data?: T;
  error?: {
    type: string;
    message: string;
  };
}

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
  call_names: string[];
  raise_count: number;
  max_nesting_depth: number;
}

export interface CodeSymbol {
  symbol_type: string;
  name: string;
  line_start: number;
  line_end: number;
  line_count: number;
  complexity: number | null;
  complexity_breakdown: ComplexityBreakdown | null;
  evidence: FunctionEvidence | null;
  parameters: string[];
}

export interface StructureAnalysis {
  supported: boolean;
  parser: string | null;
  classes: CodeSymbol[];
  functions: CodeSymbol[];
  total_symbols: number;
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
  structure: StructureAnalysis;
}

export interface Hotspot {
  file_path: string;
  relative_path: string;
  file_name: string;
  file_sha256: string;
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
  files: FileAnalysis[];
}

export interface TestCommand {
  name: string;
  command: string[];
  working_directory: string;
  interpreter_path: string;
  interpreter_source: string;
}

export interface VerificationResult {
  status: "passed" | "failed" | "timeout";
  passed: boolean;
  timed_out: boolean;
  exit_code: number | null;
  duration_seconds: number;
  command: TestCommand;
  python_version: string;
  stdout: string;
  stderr: string;
  fingerprint_before: string;
  fingerprint_after: string;
  workspace_changed_during_run: boolean;
  baseline_saved: boolean;
  baseline_path: string | null;
  baseline_message: string;
}

export function resolvePythonPath(
  configuredPath: string,
  workspaceRoot: string
): string {
  const configured = configuredPath.trim();

  if (configured && configured.toLowerCase() !== "auto") {
    return configured;
  }

  const relativeCandidates = process.platform === "win32"
    ? [
        ["core", ".venv", "Scripts", "python.exe"],
        [".venv", "Scripts", "python.exe"]
      ]
    : [
        ["core", ".venv", "bin", "python"],
        [".venv", "bin", "python"]
      ];

  for (const parts of relativeCandidates) {
    const candidate = path.join(workspaceRoot, ...parts);

    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return process.platform === "win32" ? "python" : "python3";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function validateEnvelope<T>(value: unknown): CoreEnvelope<T> {
  if (!isRecord(value)) {
    throw new Error("Core 응답이 JSON 객체가 아닙니다.");
  }

  if (value.status !== "ok" && value.status !== "error") {
    throw new Error("Core 응답에 올바른 status가 없습니다.");
  }

  if (typeof value.kind !== "string") {
    throw new Error("Core 응답에 kind가 없습니다.");
  }

  if (typeof value.app_version !== "string") {
    throw new Error("Core 응답에 app_version이 없습니다.");
  }

  if (value.protocol_version !== SUPPORTED_PROTOCOL_VERSION) {
    throw new Error(
      "Core와 Extension의 프로토콜 버전이 다릅니다. " +
      `Extension=${SUPPORTED_PROTOCOL_VERSION}, ` +
      `Core=${String(value.protocol_version)}`
    );
  }

  if (value.status === "ok" && !isRecord(value.data)) {
    throw new Error("성공한 Core 응답에 data가 없습니다.");
  }

  if (value.status === "error" && !isRecord(value.error)) {
    throw new Error("실패한 Core 응답에 error가 없습니다.");
  }

  return value as unknown as CoreEnvelope<T>;
}

export class CoreClient {
  private readonly pythonPath: string;

  public constructor(
    configuredPythonPath: string,
    private readonly workspaceRoot: string,
    private readonly timeoutMs = 90_000
  ) {
    this.pythonPath = resolvePythonPath(
      configuredPythonPath,
      workspaceRoot
    );
  }

  public getInterpreterPath(): string {
    return this.pythonPath;
  }

  public ping(): Promise<
    CoreEnvelope<{ message: string }>
  > {
    return this.run(["ping"]);
  }

  public analyzeFile(
    filePath: string
  ): Promise<
    CoreEnvelope<{ analysis: FileAnalysis }>
  > {
    return this.run(["analyze-file", filePath]);
  }

  public analyzeWorkspace(
    includeTests: boolean,
    includeExamples: boolean
  ): Promise<
    CoreEnvelope<{ workspace_analysis: WorkspaceAnalysis }>
  > {
    const args = [
      "analyze-workspace",
      this.workspaceRoot,
      "--hotspot-limit",
      "20"
    ];

    if (includeTests) {
      args.push("--include-tests");
    }

    if (includeExamples) {
      args.push("--include-examples");
    }

    return this.run(args);
  }

  public verifyWorkspace(): Promise<
    CoreEnvelope<{ verification: VerificationResult }>
  > {
    return this.run([
      "verify-workspace",
      this.workspaceRoot,
      "--timeout",
      "60"
    ]);
  }

  private run<T>(args: string[]): Promise<CoreEnvelope<T>> {
    const coreSrc = path.join(
      this.workspaceRoot,
      "core",
      "src"
    );

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
            PYTHONPATH: [
              coreSrc,
              process.env.PYTHONPATH
            ]
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
    resolve: (value: CoreEnvelope<T>) => void,
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
      fail(
        new Error(
          `ProofCode Core timed out after ${this.timeoutMs}ms.`
        )
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
      fail(
        new Error(
          `Python 실행 실패 (${this.pythonPath}): ` +
          error.message
        )
      );
    });

    child.on("close", (code) => {
      clearTimeout(timer);

      if (settled) {
        return;
      }

      const raw = code === 0
        ? stdout.trim()
        : stderr.trim();

      try {
        const envelope = validateEnvelope<T>(
          JSON.parse(raw)
        );

        if (envelope.status === "error") {
          fail(
            new Error(
              envelope.error?.message
              ?? "Core에서 알 수 없는 오류가 발생했습니다."
            )
          );
          return;
        }

        settled = true;
        resolve(envelope);
      } catch (error) {
        fail(
          error instanceof Error
            ? error
            : new Error(String(error))
        );
      }
    });
  }
}
