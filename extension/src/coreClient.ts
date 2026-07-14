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

export interface PytestSummary {
  passed: number;
  failed: number;
  skipped: number;
  errors: number;
  xfailed: number;
  xpassed: number;
}

export interface CandidateVerificationResult {
  verdict: "reviewable" | "failed" | "blocked";
  passed: boolean;
  timed_out: boolean;
  exit_code: number | null;
  duration_seconds: number;
  baseline_duration_seconds: number;
  duration_delta_seconds: number;
  duration_ratio: number | null;
  target_path: string;
  target_relative_path: string;
  candidate_path: string;
  original_sha256: string;
  candidate_sha256: string;
  baseline_fingerprint: string;
  original_fingerprint_before: string;
  original_fingerprint_after: string;
  isolated_fingerprint_before: string;
  isolated_fingerprint_after: string;
  original_workspace_changed_during_run: boolean;
  isolated_workspace_changed_during_run: boolean;
  command: string[];
  working_directory: string;
  interpreter_path: string;
  baseline_summary: PytestSummary;
  candidate_summary: PytestSummary;
  stdout: string;
  stderr: string;
  evidence_saved: boolean;
  evidence_path: string | null;
  message: string;
  security_scope: string;
}

export type DeveloperDecision = "apply" | "hold" | "reject";

export interface CandidateEvidenceSummary {
  evidence_path: string;
  created_at_utc: string;
  verdict: "reviewable" | "failed" | "blocked";
  passed: boolean;
  target_relative_path: string;
  candidate_path: string;
  candidate_sha256: string;
  message: string;
}

export interface BenchmarkEvidenceSummary {
  evidence_path: string;
  created_at_utc: string;
  verdict: "reviewable" | "failed" | "blocked";
  observed_change:
    | "faster"
    | "slower"
    | "similar"
    | "not_comparable";
  target_relative_path: string;
  candidate_path: string;
  candidate_sha256: string;
  candidate_evidence_path: string;
  measured_runs: number;
  baseline_median_seconds: number;
  candidate_median_seconds: number;
  observed_percent_change: number | null;
  message: string;
}

export interface DecisionRecord {
  decision_id: string;
  decision: DeveloperDecision;
  reason: string;
  created_at_utc: string;
  decision_path: string;
  candidate_evidence_path: string;
  candidate_evidence_sha256: string;
  source_verdict: string;
  source_passed: boolean;
  target_relative_path: string;
  candidate_path: string;
  candidate_sha256: string;
  workspace_fingerprint: string;
  candidate_context_fingerprint: string;
  workspace_matches_candidate_context: boolean;
  benchmark_evidence_path: string | null;
  benchmark_evidence_sha256: string | null;
  benchmark_verdict: string | null;
  benchmark_observed_change: string | null;
  benchmark_measured_runs: number | null;
  benchmark_baseline_median_seconds: number | null;
  benchmark_candidate_median_seconds: number | null;
  benchmark_observed_percent_change: number | null;
  benchmark_context_fingerprint: string | null;
  workspace_matches_benchmark_context: boolean | null;
  evidence_chain_complete: boolean;
  automatic_code_change_performed: boolean;
  apply_mode: string;
}

export interface DecisionSummary {
  decision_id: string;
  decision: DeveloperDecision;
  reason: string;
  created_at_utc: string;
  decision_path: string;
  target_relative_path: string;
  candidate_sha256: string;
  source_verdict: string;
  workspace_matches_candidate_context: boolean;
  benchmark_linked: boolean;
  benchmark_observed_change: string | null;
  evidence_chain_complete: boolean;
}

export interface BenchmarkRun {
  subject: "baseline" | "candidate";
  round_number: number;
  warmup: boolean;
  duration_seconds: number;
  exit_code: number | null;
  timed_out: boolean;
  stdout: string;
  stderr: string;
}

export interface BenchmarkStats {
  runs: number;
  mean_seconds: number;
  median_seconds: number;
  minimum_seconds: number;
  maximum_seconds: number;
  standard_deviation_seconds: number;
}

export interface CandidateBenchmarkResult {
  verdict: "reviewable" | "failed" | "blocked";
  observed_change:
    | "faster"
    | "slower"
    | "similar"
    | "not_comparable";
  message: string;
  measured_runs: number;
  warmup_runs: number;
  target_relative_path: string;
  candidate_path: string;
  candidate_sha256: string;
  candidate_evidence_path: string;
  candidate_evidence_sha256: string;
  baseline_fingerprint: string;
  workspace_fingerprint_before: string;
  workspace_fingerprint_after: string;
  workspace_changed_during_run: boolean;
  baseline_copy_changed_during_run: boolean;
  candidate_copy_changed_during_run: boolean;
  baseline_stats: BenchmarkStats;
  candidate_stats: BenchmarkStats;
  median_delta_seconds: number;
  median_ratio: number | null;
  observed_percent_change: number | null;
  command: string[];
  working_directory: string;
  interpreter_path: string;
  runs: BenchmarkRun[];
  evidence_saved: boolean;
  evidence_path: string | null;
  security_scope: string;
}

export interface SandboxPolicy {
  image: string;
  network_mode: "none";
  cpus: number;
  memory: string;
  memory_swap: string;
  pids_limit: number;
  timeout_seconds: number;
  read_only_root: boolean;
  no_new_privileges: boolean;
  cap_drop_all: boolean;
  container_user: string;
  tmpfs: string;
  init_process: boolean;
  original_workspace_mounted: boolean;
}

export interface SandboxReadiness {
  ready: boolean;
  docker_cli_available: boolean;
  docker_daemon_available: boolean;
  image_available: boolean;
  docker_cli_path: string | null;
  docker_server_version: string | null;
  docker_operating_system: string | null;
  image: string;
  image_id: string | null;
  image_repo_digests: string[];
  policy_valid: boolean;
  checks: Record<string, boolean>;
  errors: string[];
}

export interface SandboxBuildResult {
  passed: boolean;
  image: string;
  image_id: string | null;
  image_repo_digests: string[];
  duration_seconds: number;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  message: string;
}

export interface SandboxRunResult {
  status:
    | "passed"
    | "failed"
    | "timeout"
    | "oom_killed"
    | "blocked"
    | "cleanup_failed"
    | "sandbox_error";
  passed: boolean;
  termination_reason: string;
  exit_code: number | null;
  timed_out: boolean;
  oom_killed: boolean;
  duration_seconds: number;
  container_id: string | null;
  container_name: string;
  image: string;
  image_id: string | null;
  image_repo_digests: string[];
  command: string[];
  container_working_directory: string;
  policy: SandboxPolicy;
  stdout: string;
  stderr: string;
  container_error: string | null;
  container_started_at: string | null;
  container_finished_at: string | null;
  original_workspace_fingerprint_before: string;
  original_workspace_fingerprint_after: string;
  original_workspace_changed: boolean;
  sandbox_workspace_fingerprint_before: string;
  sandbox_workspace_fingerprint_after: string;
  sandbox_source_changed: boolean;
  original_workspace_mounted: boolean;
  mounted_sources: string[];
  container_removed: boolean;
  temporary_directory_removed: boolean;
  cleanup_errors: string[];
  evidence_saved: boolean;
  evidence_path: string | null;
  message: string;
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

  public verifyCandidateFile(
    targetFilePath: string,
    candidateFilePath: string
  ): Promise<
    CoreEnvelope<{
      candidate_verification: CandidateVerificationResult;
    }>
  > {
    return this.run([
      "verify-candidate",
      this.workspaceRoot,
      targetFilePath,
      candidateFilePath,
      "--timeout",
      "60"
    ]);
  }

  public listCandidateEvidence(): Promise<
    CoreEnvelope<{
      candidate_evidence: CandidateEvidenceSummary[];
    }>
  > {
    return this.run([
      "list-candidate-evidence",
      this.workspaceRoot
    ]);
  }

  public listBenchmarkEvidence(): Promise<
    CoreEnvelope<{
      benchmark_evidence: BenchmarkEvidenceSummary[];
    }>
  > {
    return this.run([
      "list-benchmark-evidence",
      this.workspaceRoot
    ]);
  }

  public recordCandidateDecision(
    evidencePath: string,
    decision: DeveloperDecision,
    reason: string,
    benchmarkEvidencePath?: string
  ): Promise<
    CoreEnvelope<{
      developer_decision: DecisionRecord;
    }>
  > {
    const args = [
      "record-decision",
      this.workspaceRoot,
      evidencePath,
      decision,
      "--reason",
      reason
    ];

    if (benchmarkEvidencePath) {
      args.push(
        "--benchmark-evidence",
        benchmarkEvidencePath
      );
    }

    return this.run(args);
  }

  public listDecisions(): Promise<
    CoreEnvelope<{ decisions: DecisionSummary[] }>
  > {
    return this.run([
      "list-decisions",
      this.workspaceRoot
    ]);
  }

  public readDecision(
    decisionPath: string
  ): Promise<
    CoreEnvelope<{ developer_decision: DecisionRecord }>
  > {
    return this.run([
      "read-decision",
      this.workspaceRoot,
      decisionPath
    ]);
  }

  public benchmarkCandidate(
    evidencePath: string,
    measuredRuns: number,
    warmupRuns: number
  ): Promise<
    CoreEnvelope<{
      candidate_benchmark: CandidateBenchmarkResult;
    }>
  > {
    return this.run([
      "benchmark-candidate",
      this.workspaceRoot,
      evidencePath,
      "--runs",
      String(measuredRuns),
      "--warmups",
      String(warmupRuns),
      "--timeout",
      "60"
    ]);
  }

  public checkSandboxReadiness(
    image: string
  ): Promise<
    CoreEnvelope<{ sandbox_readiness: SandboxReadiness }>
  > {
    return this.run([
      "sandbox-status",
      this.workspaceRoot,
      "--image",
      image
    ]);
  }

  public buildSandboxImage(
    image: string
  ): Promise<
    CoreEnvelope<{ sandbox_image_build: SandboxBuildResult }>
  > {
    return this.run(
      [
        "build-sandbox-image",
        this.workspaceRoot,
        "--image",
        image
      ],
      700_000
    );
  }

  public verifyContainerSandbox(
    image: string,
    cpus: number,
    memory: string,
    pidsLimit: number,
    timeoutSeconds: number
  ): Promise<
    CoreEnvelope<{ sandbox_verification: SandboxRunResult }>
  > {
    return this.run(
      [
        "verify-sandbox",
        this.workspaceRoot,
        "--image",
        image,
        "--cpus",
        String(cpus),
        "--memory",
        memory,
        "--pids-limit",
        String(pidsLimit),
        "--timeout",
        String(timeoutSeconds)
      ],
      (timeoutSeconds + 120) * 1000
    );
  }

  private run<T>(
    args: string[],
    timeoutMs = this.timeoutMs
  ): Promise<CoreEnvelope<T>> {
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

      this.collect(
        child,
        resolve,
        reject,
        timeoutMs
      );
    });
  }

  private collect<T>(
    child: ChildProcessWithoutNullStreams,
    resolve: (value: CoreEnvelope<T>) => void,
    reject: (reason: Error) => void,
    timeoutMs: number
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
          `ProofCode Core timed out after ${timeoutMs}ms.`
        )
      );
    }, timeoutMs);

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
