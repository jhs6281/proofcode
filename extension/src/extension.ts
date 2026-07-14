import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import * as vscode from "vscode";

import {
  BenchmarkEvidenceSummary,
  CandidateBenchmarkResult,
  CandidateEvidenceSummary,
  CandidateVerificationResult,
  CodeSymbol,
  DecisionRecord,
  DecisionSummary,
  DeveloperDecision,
  CoreClient,
  FileAnalysis,
  Hotspot,
  VerificationResult,
  WorkspaceAnalysis
} from "./coreClient";

let latestHotspots: Hotspot[] = [];


function workspaceRoot(): string {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  if (!root) {
    throw new Error(
      "ProofCode 저장소 폴더를 먼저 열어주세요."
    );
  }

  return root;
}


function createClient(): CoreClient {
  const config = vscode.workspace.getConfiguration("proofcode");

  return new CoreClient(
    config.get<string>("pythonPath", "auto"),
    workspaceRoot()
  );
}


function analysisOptions(): {
  includeTests: boolean;
  includeExamples: boolean;
} {
  const config = vscode.workspace.getConfiguration("proofcode");

  return {
    includeTests: config.get<boolean>(
      "includeTests",
      false
    ),
    includeExamples: config.get<boolean>(
      "includeExamples",
      false
    )
  };
}


function categoryLabel(
  category: Hotspot["category"]
): string {
  if (category === "test") {
    return "테스트 코드";
  }

  if (category === "example") {
    return "예제/Fixture";
  }

  return "제품 코드";
}


function formatSymbol(symbol: CodeSymbol): string {
  const parameters = symbol.parameters.length > 0
    ? symbol.parameters.join(", ")
    : "없음";

  return [
    `### ${symbol.name}`,
    "",
    `- 종류: ${symbol.symbol_type}`,
    `- 위치: ${symbol.line_start}~${symbol.line_end}줄`,
    `- 길이: ${symbol.line_count}줄`,
    `- 매개변수: ${parameters}`,
    `- 복잡도: ${symbol.complexity ?? "해당 없음"}`,
    ""
  ].join("\n");
}


function formatFileAnalysis(
  analysis: FileAnalysis
): string {
  const lines = [
    "# ProofCode File Analysis",
    "",
    "## 기본 정보",
    "",
    `- 파일: \`${analysis.file_name}\``,
    `- 언어: ${analysis.language}`,
    `- 전체 줄: ${analysis.total_lines}`,
    `- 비어 있지 않은 줄: ${analysis.non_empty_lines}`,
    `- SHA-256: \`${analysis.sha256}\``,
    "",
    "## 코드 구조",
    ""
  ];

  if (!analysis.structure.supported) {
    lines.push(
      `현재 ${analysis.language} 구조 분석은 아직 지원하지 않습니다.`
    );

    return lines.join("\n");
  }

  lines.push(
    `- Parser: ${analysis.structure.parser}`,
    `- 클래스: ${analysis.structure.classes.length}개`,
    `- 함수/메서드: ${analysis.structure.functions.length}개`,
    ""
  );

  if (analysis.structure.classes.length > 0) {
    lines.push("## 클래스", "");

    for (const symbol of analysis.structure.classes) {
      lines.push(formatSymbol(symbol));
    }
  }

  if (analysis.structure.functions.length > 0) {
    lines.push("## 함수와 메서드", "");

    for (const symbol of analysis.structure.functions) {
      lines.push(formatSymbol(symbol));
    }
  }

  return lines.join("\n");
}


function formatWorkspaceAnalysis(
  analysis: WorkspaceAnalysis
): string {
  const lines = [
    "# ProofCode Workspace Analysis",
    "",
    "## 프로젝트 요약",
    "",
    `- 분석 경로: \`${analysis.workspace_path}\``,
    `- 분석한 소스 파일: ${analysis.scanned_files}개`,
    `- 제품 코드 파일: ${analysis.category_counts.source}개`,
    `- 테스트 파일: ${analysis.category_counts.test}개`,
    `- 예제 파일: ${analysis.category_counts.example}개`,
    `- 전체 코드 줄 수: ${analysis.total_lines}`,
    `- 전체 클래스 수: ${analysis.total_classes}`,
    `- 전체 함수/메서드 수: ${analysis.total_functions}`,
    "",
    "## 정적 분석 기반 우선 검토 후보",
    ""
  ];

  if (analysis.hotspots.length === 0) {
    lines.push(
      "> 현재 설정으로 표시할 Hotspot이 없습니다."
    );

    return lines.join("\n");
  }

  analysis.hotspots.forEach((hotspot, index) => {
    lines.push(
      `### ${index + 1}. ${hotspot.symbol_name}`,
      "",
      `- 분류: ${categoryLabel(hotspot.category)}`,
      `- 파일: \`${hotspot.relative_path}\``,
      `- 위치: ${hotspot.line_start}~${hotspot.line_end}줄`,
      `- 길이: ${hotspot.line_count}줄`,
      `- 복잡도: ${hotspot.complexity}`,
      `- 근거: ${hotspot.reasons.join(", ")}`,
      ""
    );
  });

  lines.push(
    "---",
    "",
    "> 성능 병목을 확정한 결과가 아닙니다.",
    "> 정적 구조를 기준으로 먼저 검토할 후보입니다."
  );

  return lines.join("\n");
}


function interpretationNotes(
  hotspot: Hotspot
): string[] {
  const notes: string[] = [];

  if (hotspot.evidence.max_nesting_depth >= 4) {
    notes.push(
      "중첩 깊이가 커서 흐름을 따라가기 어려울 가능성이 있습니다."
    );
  }

  if (hotspot.line_count >= 50) {
    notes.push(
      "함수가 길어 여러 책임을 함께 담당하는지 확인할 가치가 있습니다."
    );
  }

  if (hotspot.evidence.return_count >= 5) {
    notes.push(
      "return 지점이 많아 종료 흐름을 확인할 가치가 있습니다."
    );
  }

  if (hotspot.evidence.call_count >= 10) {
    notes.push(
      "함수 호출이 많아 의존 관계를 확인할 가치가 있습니다."
    );
  }

  return notes.length > 0
    ? notes
    : ["현재 규칙에서 추가 주의점은 발견되지 않았습니다."];
}


function formatEvidenceReport(
  hotspot: Hotspot
): string {
  const breakdown = hotspot.complexity_breakdown;
  const evidence = hotspot.evidence;
  const callNames = evidence.call_names.length > 0
    ? evidence.call_names.join(", ")
    : "없음";

  return [
    "# ProofCode Hotspot Evidence",
    "",
    "## 대상",
    "",
    `- 함수/메서드: **${hotspot.symbol_name}**`,
    `- 파일: \`${hotspot.relative_path}\``,
    `- 위치: ${hotspot.line_start}~${hotspot.line_end}줄`,
    `- 파일 지문: \`${hotspot.file_sha256}\``,
    `- 분류: ${categoryLabel(hotspot.category)}`,
    "",
    "## 확인된 사실",
    "",
    `- 함수 길이: ${hotspot.line_count}줄`,
    `- 복잡도: ${hotspot.complexity}`,
    `- 조건 분기: ${breakdown.conditions}개`,
    `- 반복문: ${breakdown.loops}개`,
    `- 논리 연산 분기: ${breakdown.boolean_branches}개`,
    `- 예외 처리 분기: ${breakdown.exception_handlers}개`,
    `- 컴프리헨션 반복: ${breakdown.comprehensions}개`,
    `- match case: ${breakdown.match_cases}개`,
    `- 최대 중첩 깊이: ${evidence.max_nesting_depth}`,
    `- return 문: ${evidence.return_count}개`,
    `- 함수 호출: ${evidence.call_count}개`,
    `- 호출 이름: ${callNames}`,
    `- raise 문: ${evidence.raise_count}개`,
    "",
    "## 해석 가능한 주의점",
    "",
    ...interpretationNotes(hotspot).map(
      (note) => `- ${note}`
    ),
    "",
    "## 아직 확인하지 않은 것",
    "",
    "- 실제 실행 속도",
    "- CPU와 메모리 사용량",
    "- 변경 후 테스트 통과 여부",
    "- 성능 병목 여부",
    "",
    "> 이 리포트는 정적 분석 Evidence입니다.",
    "> ProofCode는 코드를 자동 변경하지 않습니다."
  ].join("\n");
}


function formatVerificationReport(
  verification: VerificationResult
): string {
  const state = verification.passed
    ? "✅ 테스트 통과"
    : verification.timed_out
      ? "⏱️ 시간 초과"
      : "❌ 테스트 실패";

  const baselineState = verification.baseline_saved
    ? "✅ 유효한 Baseline 저장"
    : "❌ Baseline 저장 안 함";

  return [
    "# ProofCode Baseline Verification",
    "",
    "## 테스트 결과",
    "",
    `- 상태: **${state}**`,
    `- 테스트 도구: ${verification.command.name}`,
    `- 실행 명령: \`${verification.command.command.join(" ")}\``,
    `- 실행 위치: \`${verification.command.working_directory}\``,
    `- Python: \`${verification.command.interpreter_path}\``,
    `- Python 선택 근거: ${verification.command.interpreter_source}`,
    `- Python 버전: ${verification.python_version}`,
    `- 종료 코드: ${verification.exit_code ?? "없음"}`,
    `- 실행 시간: ${verification.duration_seconds}초`,
    "",
    "## Baseline 판정",
    "",
    `- 상태: **${baselineState}**`,
    `- 설명: ${verification.baseline_message}`,
    `- 저장 경로: \`${verification.baseline_path ?? "없음"}\``,
    `- 실행 전 지문: \`${verification.fingerprint_before}\``,
    `- 실행 후 지문: \`${verification.fingerprint_after}\``,
    `- 실행 중 소스 변경: ${
      verification.workspace_changed_during_run
        ? "예"
        : "아니요"
    }`,
    "",
    "## 표준 출력",
    "",
    "```text",
    verification.stdout.trim() || "(출력 없음)",
    "```",
    "",
    "## 오류 출력",
    "",
    "```text",
    verification.stderr.trim() || "(출력 없음)",
    "```",
    "",
    verification.baseline_saved
      ? "> 이 결과는 이후 후보 검증과 비교할 수 있는 유효한 기준점입니다."
      : "> 이 결과는 진단용이며 유효한 Baseline으로 저장되지 않았습니다."
  ].join("\n");
}



function pytestSummaryText(
  summary: CandidateVerificationResult["candidate_summary"]
): string {
  const parts: string[] = [];

  if (summary.passed) {
    parts.push(`${summary.passed} passed`);
  }

  if (summary.failed) {
    parts.push(`${summary.failed} failed`);
  }

  if (summary.errors) {
    parts.push(`${summary.errors} errors`);
  }

  if (summary.skipped) {
    parts.push(`${summary.skipped} skipped`);
  }

  if (summary.xfailed) {
    parts.push(`${summary.xfailed} xfailed`);
  }

  if (summary.xpassed) {
    parts.push(`${summary.xpassed} xpassed`);
  }

  return parts.length > 0
    ? parts.join(", ")
    : "요약을 찾지 못함";
}


function truncateOutput(
  text: string,
  maximumLength = 12000
): string {
  if (text.length <= maximumLength) {
    return text;
  }

  return (
    text.slice(0, maximumLength)
    + "\n... 출력이 길어 일부만 표시했습니다."
  );
}


function formatCandidateReport(
  result: CandidateVerificationResult
): string {
  const verdict = result.verdict === "reviewable"
    ? "✅ 테스트 관점에서 검토 가능"
    : result.verdict === "failed"
      ? "❌ 테스트 실패"
      : "⛔ 검증 중단";

  const ratio = result.duration_ratio === null
    ? "계산 불가"
    : `${result.duration_ratio}배`;

  return [
    "# ProofCode Candidate Verification",
    "",
    "## 판정",
    "",
    `- 상태: **${verdict}**`,
    `- 설명: ${result.message}`,
    `- 원본 파일: \`${result.target_relative_path}\``,
    `- 후보 파일: \`${result.candidate_path}\``,
    `- 원본 SHA-256: \`${result.original_sha256}\``,
    `- 후보 SHA-256: \`${result.candidate_sha256}\``,
    "",
    "## 테스트 비교",
    "",
    `- Baseline: ${pytestSummaryText(result.baseline_summary)}`,
    `- Candidate: ${pytestSummaryText(result.candidate_summary)}`,
    `- Baseline 실행 시간: ${result.baseline_duration_seconds}초`,
    `- Candidate 실행 시간: ${result.duration_seconds}초`,
    `- 시간 차이: ${result.duration_delta_seconds}초`,
    `- 시간 비율: ${ratio}`,
    "",
    "> 한 번의 실행 시간 차이는 성능 개선의 증거가 아닙니다.",
    "",
    "## 격리 및 원본 보호",
    "",
    "- 후보 파일은 임시 Workspace 복사본에만 적용했습니다.",
    `- 원본 Workspace 변경 감지: ${
      result.original_workspace_changed_during_run
        ? "예"
        : "아니요"
    }`,
    `- 임시 소스 변경 감지: ${
      result.isolated_workspace_changed_during_run
        ? "예"
        : "아니요"
    }`,
    `- 격리 범위: \`${result.security_scope}\``,
    "",
    "> 현재 격리는 임시 폴더 복사 방식입니다.",
    "> 컨테이너 수준의 보안 Sandbox는 아직 아닙니다.",
    "",
    "## 실행 정보",
    "",
    `- 명령: \`${result.command.join(" ")}\``,
    `- Python: \`${result.interpreter_path}\``,
    `- 종료 코드: ${result.exit_code ?? "없음"}`,
    `- 시간 초과: ${result.timed_out ? "예" : "아니요"}`,
    `- Evidence 저장: ${result.evidence_saved ? "예" : "아니요"}`,
    `- Evidence 경로: \`${result.evidence_path ?? "없음"}\``,
    "",
    "## 표준 출력",
    "",
    "```text",
    truncateOutput(result.stdout.trim() || "(출력 없음)"),
    "```",
    "",
    "## 오류 출력",
    "",
    "```text",
    truncateOutput(result.stderr.trim() || "(출력 없음)"),
    "```",
    "",
    "## 개발자 결정",
    "",
    "- Apply: 후보를 직접 검토한 뒤 개발자가 적용",
    "- Hold: 추가 테스트나 Benchmark 후 보류",
    "- Reject: 실패 또는 근거 부족으로 폐기",
    "",
    "> ProofCode는 후보 파일을 원본에 자동 적용하지 않습니다."
  ].join("\n");
}



function decisionLabel(
  decision: DeveloperDecision
): string {
  if (decision === "apply") {
    return "Apply";
  }

  if (decision === "hold") {
    return "Hold";
  }

  return "Reject";
}


function verdictLabel(verdict: string): string {
  if (verdict === "reviewable") {
    return "검토 가능";
  }

  if (verdict === "failed") {
    return "테스트 실패";
  }

  return "검증 중단";
}


function formatDecisionReport(
  record: DecisionRecord
): string {
  const candidateContext =
    record.workspace_matches_candidate_context
      ? "일치"
      : "불일치";
  const benchmarkLinked =
    record.benchmark_evidence_path !== null;
  const benchmarkContext =
    record.workspace_matches_benchmark_context === null
      ? "Benchmark 미연결"
      : record.workspace_matches_benchmark_context
        ? "일치"
        : "불일치";

  const lines = [
    "# ProofCode Developer Decision",
    "",
    "## 결정",
    "",
    `- 선택: **${decisionLabel(record.decision)}**`,
    `- 이유: ${record.reason}`,
    `- 기록 시각: ${record.created_at_utc}`,
    `- Decision ID: \`${record.decision_id}\``,
    "",
    "## Candidate Evidence",
    "",
    `- 대상 파일: \`${record.target_relative_path}\``,
    `- Candidate: \`${record.candidate_path}\``,
    `- Candidate SHA-256: \`${record.candidate_sha256}\``,
    `- 원래 판정: ${verdictLabel(record.source_verdict)}`,
    `- 테스트 통과: ${record.source_passed ? "예" : "아니요"}`,
    `- Evidence SHA-256: \`${record.candidate_evidence_sha256}\``,
    `- Evidence 경로: \`${record.candidate_evidence_path}\``,
    "",
    "## Benchmark Evidence",
    ""
  ];

  if (benchmarkLinked) {
    lines.push(
      `- 연결 상태: **연결됨**`,
      `- Benchmark 판정: ${record.benchmark_verdict}`,
      `- 관측 변화: ${record.benchmark_observed_change}`,
      `- 측정 횟수: ${record.benchmark_measured_runs}회`,
      `- Baseline 중앙값: ${record.benchmark_baseline_median_seconds}초`,
      `- Candidate 중앙값: ${record.benchmark_candidate_median_seconds}초`,
      `- 관측 변화율: ${record.benchmark_observed_percent_change ?? "없음"}%`,
      `- Evidence SHA-256: \`${record.benchmark_evidence_sha256}\``,
      `- Evidence 경로: \`${record.benchmark_evidence_path}\``
    );
  } else {
    lines.push(
      "- 연결 상태: 연결하지 않음",
      "- 테스트 Evidence만으로 기록된 결정입니다."
    );
  }

  lines.push(
    "",
    "## Evidence 연결 상태",
    "",
    `- Candidate 검증 시점과 Workspace: **${candidateContext}**`,
    `- Benchmark 시점과 Workspace: **${benchmarkContext}**`,
    `- Candidate + Benchmark 연결 완성: ${
      record.evidence_chain_complete
        ? "예"
        : "아니요"
    }`,
    "",
    "## 코드 적용 상태",
    "",
    `- 자동 코드 변경: ${
      record.automatic_code_change_performed
        ? "실행됨"
        : "실행하지 않음"
    }`,
    `- Apply 방식: \`${record.apply_mode}\``,
    "",
    "> Apply는 수동 적용 승인 기록입니다.",
    "> ProofCode는 원본 코드를 자동으로 변경하지 않습니다.",
    "",
    `- 저장 경로: \`${record.decision_path}\``
  );

  return lines.join("\n");
}

function formatDecisionSummaryReport(
  summary: DecisionSummary
): string {
  return [
    "# ProofCode Decision History",
    "",
    `- 선택: **${decisionLabel(summary.decision)}**`,
    `- 이유: ${summary.reason}`,
    `- 대상 파일: \`${summary.target_relative_path}\``,
    `- Candidate SHA-256: \`${summary.candidate_sha256}\``,
    `- 원래 판정: ${verdictLabel(summary.source_verdict)}`,
    `- Candidate 검증 시점 일치: ${
      summary.workspace_matches_candidate_context
        ? "예"
        : "아니요"
    }`,
    `- Benchmark 연결: ${
      summary.benchmark_linked
        ? "예"
        : "아니요"
    }`,
    `- Benchmark 관측 결과: ${
      summary.benchmark_observed_change ?? "없음"
    }`,
    `- Evidence 연결 완성: ${
      summary.evidence_chain_complete
        ? "예"
        : "아니요"
    }`,
    `- 기록 시각: ${summary.created_at_utc}`,
    `- Decision ID: \`${summary.decision_id}\``,
    `- 저장 경로: \`${summary.decision_path}\``
  ].join("\n");
}

function evidenceQuickPickLabel(
  evidence: CandidateEvidenceSummary
): string {
  return (
    `${verdictLabel(evidence.verdict)} · `
    + evidence.target_relative_path
  );
}



function observedChangeLabel(
  change: CandidateBenchmarkResult["observed_change"]
): string {
  if (change === "faster") {
    return "Candidate가 더 빠르게 관측됨";
  }

  if (change === "slower") {
    return "Candidate가 더 느리게 관측됨";
  }

  if (change === "similar") {
    return "유사한 범위로 관측됨";
  }

  return "비교 불가";
}


function formatBenchmarkDurations(
  result: CandidateBenchmarkResult,
  subject: "baseline" | "candidate"
): string {
  return result.runs
    .filter(
      (run) =>
        run.subject === subject
        && !run.warmup
    )
    .map(
      (run) =>
        `${run.round_number}회: ${run.duration_seconds}초`
    )
    .join(", ");
}


function formatBenchmarkReport(
  result: CandidateBenchmarkResult
): string {
  const verdict = result.verdict === "reviewable"
    ? "✅ 반복 검증 완료"
    : result.verdict === "failed"
      ? "❌ Candidate 테스트 실패"
      : "⛔ Benchmark 중단";

  const percent = result.observed_percent_change === null
    ? "계산 불가"
    : `${result.observed_percent_change}%`;

  const ratio = result.median_ratio === null
    ? "계산 불가"
    : `${result.median_ratio}배`;

  return [
    "# ProofCode Candidate Benchmark",
    "",
    "## 판정",
    "",
    `- 상태: **${verdict}**`,
    `- 설명: ${result.message}`,
    `- 관측 결과: **${observedChangeLabel(result.observed_change)}**`,
    `- 측정 횟수: ${result.measured_runs}회`,
    `- Warm-up: ${result.warmup_runs}회`,
    "",
    "## 중앙값 비교",
    "",
    `- Baseline 중앙값: ${result.baseline_stats.median_seconds}초`,
    `- Candidate 중앙값: ${result.candidate_stats.median_seconds}초`,
    `- 시간 차이: ${result.median_delta_seconds}초`,
    `- 시간 비율: ${ratio}`,
    `- 관측 변화율: ${percent}`,
    "",
    "## Baseline 통계",
    "",
    `- 평균: ${result.baseline_stats.mean_seconds}초`,
    `- 최소: ${result.baseline_stats.minimum_seconds}초`,
    `- 최대: ${result.baseline_stats.maximum_seconds}초`,
    `- 표준편차: ${result.baseline_stats.standard_deviation_seconds}초`,
    `- 개별 측정: ${formatBenchmarkDurations(result, "baseline")}`,
    "",
    "## Candidate 통계",
    "",
    `- 평균: ${result.candidate_stats.mean_seconds}초`,
    `- 최소: ${result.candidate_stats.minimum_seconds}초`,
    `- 최대: ${result.candidate_stats.maximum_seconds}초`,
    `- 표준편차: ${result.candidate_stats.standard_deviation_seconds}초`,
    `- 개별 측정: ${formatBenchmarkDurations(result, "candidate")}`,
    "",
    "## 비교 조건",
    "",
    "- Baseline과 Candidate를 서로 다른 임시 Workspace에 복사했습니다.",
    "- 측정 순서를 번갈아 실행해 실행 순서 영향을 줄였습니다.",
    `- 원본 Workspace 변경: ${
      result.workspace_changed_during_run
        ? "감지됨"
        : "없음"
    }`,
    `- Baseline 임시 소스 변경: ${
      result.baseline_copy_changed_during_run
        ? "감지됨"
        : "없음"
    }`,
    `- Candidate 임시 소스 변경: ${
      result.candidate_copy_changed_during_run
        ? "감지됨"
        : "없음"
    }`,
    "",
    "## 대상과 Evidence",
    "",
    `- 대상 파일: \`${result.target_relative_path}\``,
    `- Candidate: \`${result.candidate_path}\``,
    `- Candidate SHA-256: \`${result.candidate_sha256}\``,
    `- Candidate Evidence: \`${result.candidate_evidence_path}\``,
    `- Benchmark Evidence: \`${result.evidence_path ?? "없음"}\``,
    `- 실행 명령: \`${result.command.join(" ")}\``,
    `- Python: \`${result.interpreter_path}\``,
    "",
    "## 해석 주의",
    "",
    "- 이 값은 전체 테스트 명령의 실행 시간입니다.",
    "- 특정 함수 하나의 순수 실행 속도는 아닙니다.",
    "- 5% 이내 또는 0.01초 미만 차이는 유사한 범위로 처리합니다.",
    "- 성능이 빨라 보여도 테스트 통과와 코드 리뷰가 먼저입니다.",
    "",
    `> 격리 범위: \`${result.security_scope}\``,
    "> ProofCode는 Benchmark 결과만으로 코드를 자동 적용하지 않습니다."
  ].join("\n");
}



function formatBenchmarkHistoryReport(
  benchmark: BenchmarkEvidenceSummary
): string {
  return [
    "# ProofCode Benchmark Evidence",
    "",
    `- 상태: **${verdictLabel(benchmark.verdict)}**`,
    `- 관측 변화: ${benchmark.observed_change}`,
    `- 대상 파일: \`${benchmark.target_relative_path}\``,
    `- Candidate: \`${benchmark.candidate_path}\``,
    `- Candidate SHA-256: \`${benchmark.candidate_sha256}\``,
    `- 반복 측정: ${benchmark.measured_runs}회`,
    `- Baseline 중앙값: ${benchmark.baseline_median_seconds}초`,
    `- Candidate 중앙값: ${benchmark.candidate_median_seconds}초`,
    `- 관측 변화율: ${benchmark.observed_percent_change ?? "없음"}%`,
    `- 설명: ${benchmark.message}`,
    `- Candidate Evidence: \`${benchmark.candidate_evidence_path}\``,
    `- Benchmark Evidence: \`${benchmark.evidence_path}\``,
    `- 생성 시각: ${benchmark.created_at_utc}`,
    "",
    "> 이 결과는 관측된 테스트 실행 시간 비교입니다.",
    "> 특정 함수의 성능 개선을 확정하지 않습니다."
  ].join("\n");
}


async function showMarkdown(
  content: string
): Promise<void> {
  const document = await vscode.workspace.openTextDocument({
    language: "markdown",
    content
  });

  await vscode.window.showTextDocument(
    document,
    vscode.ViewColumn.Beside,
    true
  );
}


async function runWorkspaceAnalysis(): Promise<
  WorkspaceAnalysis
> {
  const options = analysisOptions();
  const response = await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "ProofCode 프로젝트 분석 중…",
      cancellable: false
    },
    () => createClient().analyzeWorkspace(
      options.includeTests,
      options.includeExamples
    )
  );

  const analysis = response.data?.workspace_analysis;

  if (!analysis) {
    throw new Error("Workspace 분석 데이터가 없습니다.");
  }

  latestHotspots = analysis.hotspots;
  return analysis;
}


async function selectHotspot(
  title: string
): Promise<Hotspot | undefined> {
  if (latestHotspots.length === 0) {
    await runWorkspaceAnalysis();
  }

  const selected = await vscode.window.showQuickPick(
    latestHotspots.map((hotspot) => ({
      label: hotspot.symbol_name,
      description:
        `${hotspot.relative_path}:${hotspot.line_start}`,
      detail:
        `복잡도 ${hotspot.complexity} · ` +
        `중첩 ${hotspot.evidence.max_nesting_depth} · ` +
        hotspot.reasons.join(", "),
      hotspot
    })),
    {
      title,
      placeHolder: "함수 또는 메서드를 선택하세요.",
      matchOnDescription: true,
      matchOnDetail: true
    }
  );

  return selected?.hotspot;
}


async function fileSha256(
  filePath: string
): Promise<string> {
  const bytes = await fs.readFile(filePath);

  return createHash("sha256")
    .update(bytes)
    .digest("hex");
}


async function refreshIfStale(
  hotspot: Hotspot
): Promise<Hotspot> {
  const currentHash = await fileSha256(
    hotspot.file_path
  );

  if (currentHash === hotspot.file_sha256) {
    return hotspot;
  }

  void vscode.window.showInformationMessage(
    "분석 후 파일이 변경되어 Hotspot을 다시 분석합니다."
  );

  const analysis = await runWorkspaceAnalysis();
  const refreshed = analysis.hotspots.find(
    (item) =>
      item.relative_path === hotspot.relative_path
      && item.symbol_name === hotspot.symbol_name
  );

  if (!refreshed) {
    throw new Error(
      "파일 변경 후 해당 함수 위치를 다시 찾지 못했습니다."
    );
  }

  return refreshed;
}


async function openCode(
  originalHotspot: Hotspot
): Promise<Hotspot> {
  const hotspot = await refreshIfStale(
    originalHotspot
  );

  const document = await vscode.workspace.openTextDocument(
    vscode.Uri.file(hotspot.file_path)
  );

  const editor = await vscode.window.showTextDocument(
    document,
    vscode.ViewColumn.One
  );

  const start = Math.max(0, hotspot.line_start - 1);
  const end = Math.min(
    document.lineCount - 1,
    Math.max(start, hotspot.line_end - 1)
  );

  const range = new vscode.Range(
    new vscode.Position(start, 0),
    new vscode.Position(
      end,
      document.lineAt(end).text.length
    )
  );

  editor.selection = new vscode.Selection(
    range.start,
    range.end
  );

  editor.revealRange(
    range,
    vscode.TextEditorRevealType.InCenter
  );

  return hotspot;
}


export function activate(
  context: vscode.ExtensionContext
): void {
  const pingCommand = vscode.commands.registerCommand(
    "proofcode.pingCore",
    async () => {
      try {
        const core = createClient();
        const response = await core.ping();
        const message = response.data?.message
          ?? "ProofCode Core is running";

        void vscode.window.showInformationMessage(
          `${message} · App ${response.app_version} · ` +
          `Protocol ${response.protocol_version} · ` +
          `Python ${core.getInterpreterPath()}`
        );
      } catch (error) {
        void vscode.window.showErrorMessage(
          `Core 연결 실패: ${String(error)}`
        );
      }
    }
  );

  const analyzeFileCommand = vscode.commands.registerCommand(
    "proofcode.analyzeCurrentFile",
    async () => {
      const editor = vscode.window.activeTextEditor;

      if (!editor || editor.document.isUntitled) {
        void vscode.window.showWarningMessage(
          "저장된 코드 파일을 먼저 열어주세요."
        );
        return;
      }

      try {
        const response = await createClient().analyzeFile(
          editor.document.uri.fsPath
        );
        const analysis = response.data?.analysis;

        if (!analysis) {
          throw new Error("파일 분석 데이터가 없습니다.");
        }

        await showMarkdown(
          formatFileAnalysis(analysis)
        );
      } catch (error) {
        void vscode.window.showErrorMessage(
          `파일 분석 실패: ${String(error)}`
        );
      }
    }
  );

  const analyzeWorkspaceCommand =
    vscode.commands.registerCommand(
      "proofcode.analyzeWorkspace",
      async () => {
        try {
          const analysis = await runWorkspaceAnalysis();

          await showMarkdown(
            formatWorkspaceAnalysis(analysis)
          );
        } catch (error) {
          void vscode.window.showErrorMessage(
            `프로젝트 분석 실패: ${String(error)}`
          );
        }
      }
    );

  const openHotspotCommand =
    vscode.commands.registerCommand(
      "proofcode.openHotspot",
      async () => {
        try {
          const hotspot = await selectHotspot(
            "ProofCode Hotspot 열기"
          );

          if (hotspot) {
            await openCode(hotspot);
          }
        } catch (error) {
          void vscode.window.showErrorMessage(
            `Hotspot 열기 실패: ${String(error)}`
          );
        }
      }
    );

  const inspectHotspotCommand =
    vscode.commands.registerCommand(
      "proofcode.inspectHotspot",
      async () => {
        try {
          const selected = await selectHotspot(
            "ProofCode Hotspot Evidence"
          );

          if (!selected) {
            return;
          }

          const current = await openCode(selected);

          await showMarkdown(
            formatEvidenceReport(current)
          );
        } catch (error) {
          void vscode.window.showErrorMessage(
            `Evidence 생성 실패: ${String(error)}`
          );
        }
      }
    );

  const verifyBaselineCommand =
    vscode.commands.registerCommand(
      "proofcode.verifyBaseline",
      async () => {
        try {
          const response = await vscode.window.withProgress(
            {
              location: vscode.ProgressLocation.Notification,
              title: "ProofCode Baseline 검증 중…",
              cancellable: false
            },
            () => createClient().verifyWorkspace()
          );

          const verification =
            response.data?.verification;

          if (!verification) {
            throw new Error(
              "Baseline 검증 데이터가 없습니다."
            );
          }

          await showMarkdown(
            formatVerificationReport(verification)
          );
        } catch (error) {
          void vscode.window.showErrorMessage(
            `Baseline 검증 실패: ${String(error)}`
          );
        }
      }
    );


  const verifyCandidateCommand =
    vscode.commands.registerCommand(
      "proofcode.verifyCandidateFile",
      async () => {
        const editor = vscode.window.activeTextEditor;

        if (!editor || editor.document.isUntitled) {
          void vscode.window.showWarningMessage(
            "후보가 대체할 원본 코드 파일을 먼저 열어주세요."
          );
          return;
        }

        const targetPath = editor.document.uri.fsPath;
        const extensionName = targetPath
          .split(".")
          .pop();

        const selected = await vscode.window.showOpenDialog({
          canSelectFiles: true,
          canSelectFolders: false,
          canSelectMany: false,
          title: "검증할 후보 파일 선택",
          openLabel: "후보 파일 선택",
          filters: extensionName
            ? {
                "같은 확장자": [extensionName],
                "모든 파일": ["*"]
              }
            : undefined
        });

        const candidateUri = selected?.[0];

        if (!candidateUri) {
          return;
        }

        try {
          const response = await vscode.window.withProgress(
            {
              location: vscode.ProgressLocation.Notification,
              title: "ProofCode Candidate 검증 중…",
              cancellable: false
            },
            () => createClient().verifyCandidateFile(
              targetPath,
              candidateUri.fsPath
            )
          );

          const result =
            response.data?.candidate_verification;

          if (!result) {
            throw new Error(
              "Candidate 검증 데이터가 없습니다."
            );
          }

          await showMarkdown(
            formatCandidateReport(result)
          );

          const selection =
            await vscode.window.showInformationMessage(
              result.verdict === "reviewable"
                ? "Candidate가 테스트를 통과했습니다."
                : "Candidate 검증 결과를 확인하세요.",
              "Diff 열기"
            );

          if (selection === "Diff 열기") {
            await vscode.commands.executeCommand(
              "vscode.diff",
              vscode.Uri.file(targetPath),
              candidateUri,
              `ProofCode Candidate: ${result.target_relative_path}`
            );
          }
        } catch (error) {
          void vscode.window.showErrorMessage(
            `Candidate 검증 실패: ${String(error)}`
          );
        }
      }
    );


  const recordDecisionCommand =
    vscode.commands.registerCommand(
      "proofcode.recordCandidateDecision",
      async () => {
        try {
          const response =
            await createClient().listCandidateEvidence();
          const evidenceList =
            response.data?.candidate_evidence ?? [];

          if (evidenceList.length === 0) {
            void vscode.window.showInformationMessage(
              "기록할 Candidate Evidence가 없습니다. " +
              "먼저 Candidate 파일을 검증하세요."
            );
            return;
          }

          const selectedEvidence =
            await vscode.window.showQuickPick(
              evidenceList.map((evidence) => ({
                label: evidenceQuickPickLabel(evidence),
                description:
                  evidence.created_at_utc || "시간 정보 없음",
                detail:
                  `${evidence.message} · ` +
                  `SHA ${evidence.candidate_sha256.slice(0, 12)}`,
                evidence
              })),
              {
                title: "결정할 Candidate Evidence 선택",
                placeHolder:
                  "Apply / Hold / Reject를 기록할 결과를 선택하세요.",
                matchOnDescription: true,
                matchOnDetail: true
              }
            );

          if (!selectedEvidence) {
            return;
          }

          const evidence = selectedEvidence.evidence;
          const choices: Array<{
            label: string;
            description: string;
            decision: DeveloperDecision;
          }> = [];

          if (
            evidence.verdict === "reviewable"
            && evidence.passed
          ) {
            choices.push({
              label: "Apply",
              description:
                "수동 적용 승인으로 기록하며 코드는 바꾸지 않습니다.",
              decision: "apply"
            });
          }

          choices.push(
            {
              label: "Hold",
              description:
                "추가 Benchmark 또는 검토가 필요해 보류합니다.",
              decision: "hold"
            },
            {
              label: "Reject",
              description:
                "근거 부족 또는 실패로 후보를 거절합니다.",
              decision: "reject"
            }
          );

          const selectedDecision =
            await vscode.window.showQuickPick(
              choices,
              {
                title: "개발자 결정 선택",
                placeHolder:
                  "최종 결정은 개발자가 선택합니다."
              }
            );

          if (!selectedDecision) {
            return;
          }

          const reason = await vscode.window.showInputBox({
            title:
              `${selectedDecision.label} 결정 이유`,
            prompt:
              "Evidence를 보고 판단한 이유를 기록하세요.",
            placeHolder:
              "예: 테스트는 통과했지만 반복 Benchmark가 필요함",
            ignoreFocusOut: true,
            validateInput: (value) =>
              value.trim()
                ? undefined
                : "결정 이유를 입력해야 합니다."
          });

          if (reason === undefined) {
            return;
          }

          const benchmarkResponse =
            await createClient().listBenchmarkEvidence();
          const matchingBenchmarks = (
            benchmarkResponse.data?.benchmark_evidence ?? []
          ).filter(
            (item) =>
              item.candidate_sha256
                === evidence.candidate_sha256
              && item.target_relative_path
                === evidence.target_relative_path
              && item.candidate_evidence_path
                === evidence.evidence_path
          );

          let benchmarkEvidencePath:
            string | undefined;

          if (matchingBenchmarks.length > 0) {
            const benchmarkChoice =
              await vscode.window.showQuickPick(
                [
                  ...matchingBenchmarks.map(
                    (benchmark) => ({
                      label:
                        `${benchmark.observed_change} · ` +
                        `${benchmark.measured_runs}회`,
                      description:
                        benchmark.created_at_utc
                        || "시간 정보 없음",
                      detail:
                        `Baseline ${benchmark.baseline_median_seconds}초 · ` +
                        `Candidate ${benchmark.candidate_median_seconds}초`,
                      benchmark
                    })
                  ),
                  {
                    label: "Benchmark 연결 없이 기록",
                    description:
                      "Candidate 테스트 Evidence만 연결",
                    detail:
                      "Benchmark를 아직 실행하지 않았거나 연결하지 않습니다.",
                    benchmark: undefined
                  }
                ],
                {
                  title: "Benchmark Evidence 연결",
                  placeHolder:
                    "Decision에 연결할 Benchmark를 선택하세요."
                }
              );

            if (!benchmarkChoice) {
              return;
            }

            benchmarkEvidencePath =
              benchmarkChoice.benchmark?.evidence_path;
          }

          const recordResponse =
            await createClient().recordCandidateDecision(
              evidence.evidence_path,
              selectedDecision.decision,
              reason,
              benchmarkEvidencePath
            );
          const record =
            recordResponse.data?.developer_decision;

          if (!record) {
            throw new Error(
              "Developer Decision 데이터가 없습니다."
            );
          }

          await showMarkdown(
            formatDecisionReport(record)
          );

          void vscode.window.showInformationMessage(
            `${selectedDecision.label} 결정이 기록되었습니다. ` +
            "원본 코드는 변경하지 않았습니다."
          );
        } catch (error) {
          void vscode.window.showErrorMessage(
            `Decision 기록 실패: ${String(error)}`
          );
        }
      }
    );

  const viewDecisionHistoryCommand =
    vscode.commands.registerCommand(
      "proofcode.viewDecisionHistory",
      async () => {
        try {
          const response =
            await createClient().listDecisions();
          const decisions =
            response.data?.decisions ?? [];

          if (decisions.length === 0) {
            void vscode.window.showInformationMessage(
              "저장된 Developer Decision이 없습니다."
            );
            return;
          }

          const selected =
            await vscode.window.showQuickPick(
              decisions.map((decision) => ({
                label:
                  `${decisionLabel(decision.decision)} · ` +
                  decision.target_relative_path,
                description: decision.created_at_utc,
                detail: decision.reason,
                decision
              })),
              {
                title: "ProofCode Decision History",
                placeHolder:
                  "확인할 Developer Decision을 선택하세요.",
                matchOnDescription: true,
                matchOnDetail: true
              }
            );

          if (!selected) {
            return;
          }

          const detailResponse =
            await createClient().readDecision(
              selected.decision.decision_path
            );
          const record =
            detailResponse.data?.developer_decision;

          if (record) {
            await showMarkdown(
              formatDecisionReport(record)
            );
          } else {
            await showMarkdown(
              formatDecisionSummaryReport(
                selected.decision
              )
            );
          }
        } catch (error) {
          void vscode.window.showErrorMessage(
            `Decision History 확인 실패: ${String(error)}`
          );
        }
      }
    );


  const benchmarkCandidateCommand =
    vscode.commands.registerCommand(
      "proofcode.benchmarkCandidate",
      async () => {
        try {
          const evidenceResponse =
            await createClient().listCandidateEvidence();
          const evidenceList =
            evidenceResponse.data?.candidate_evidence ?? [];
          const reviewable = evidenceList.filter(
            (item) =>
              item.verdict === "reviewable"
              && item.passed
          );

          if (reviewable.length === 0) {
            void vscode.window.showInformationMessage(
              "Benchmark할 reviewable Candidate가 없습니다. " +
              "먼저 Candidate 파일을 검증하세요."
            );
            return;
          }

          const selected =
            await vscode.window.showQuickPick(
              reviewable.map((evidence) => ({
                label:
                  `${evidence.target_relative_path} · ` +
                  evidence.candidate_sha256.slice(0, 12),
                description:
                  evidence.created_at_utc || "시간 정보 없음",
                detail: evidence.message,
                evidence
              })),
              {
                title: "Benchmark할 Candidate 선택",
                placeHolder:
                  "반복 비교할 Candidate Evidence를 선택하세요.",
                matchOnDescription: true,
                matchOnDetail: true
              }
            );

          if (!selected) {
            return;
          }

          const config =
            vscode.workspace.getConfiguration("proofcode");
          const measuredRuns = config.get<number>(
            "benchmarkRuns",
            5
          );
          const warmupRuns = config.get<number>(
            "benchmarkWarmups",
            1
          );

          const response =
            await vscode.window.withProgress(
              {
                location:
                  vscode.ProgressLocation.Notification,
                title:
                  `ProofCode Benchmark 실행 중 ` +
                  `(${measuredRuns}회)…`,
                cancellable: false
              },
              () => createClient().benchmarkCandidate(
                selected.evidence.evidence_path,
                measuredRuns,
                warmupRuns
              )
            );

          const result =
            response.data?.candidate_benchmark;

          if (!result) {
            throw new Error(
              "Candidate Benchmark 데이터가 없습니다."
            );
          }

          await showMarkdown(
            formatBenchmarkReport(result)
          );
        } catch (error) {
          void vscode.window.showErrorMessage(
            `Candidate Benchmark 실패: ${String(error)}`
          );
        }
      }
    );


  const viewBenchmarkHistoryCommand =
    vscode.commands.registerCommand(
      "proofcode.viewBenchmarkHistory",
      async () => {
        try {
          const response =
            await createClient().listBenchmarkEvidence();
          const benchmarks =
            response.data?.benchmark_evidence ?? [];

          if (benchmarks.length === 0) {
            void vscode.window.showInformationMessage(
              "저장된 Benchmark Evidence가 없습니다."
            );
            return;
          }

          const selected =
            await vscode.window.showQuickPick(
              benchmarks.map((benchmark) => ({
                label:
                  `${benchmark.observed_change} · ` +
                  benchmark.target_relative_path,
                description:
                  benchmark.created_at_utc
                  || "시간 정보 없음",
                detail:
                  `${benchmark.measured_runs}회 · ` +
                  `Baseline ${benchmark.baseline_median_seconds}초 · ` +
                  `Candidate ${benchmark.candidate_median_seconds}초`,
                benchmark
              })),
              {
                title: "ProofCode Benchmark History",
                placeHolder:
                  "확인할 Benchmark Evidence를 선택하세요.",
                matchOnDescription: true,
                matchOnDetail: true
              }
            );

          if (selected) {
            await showMarkdown(
              formatBenchmarkHistoryReport(
                selected.benchmark
              )
            );
          }
        } catch (error) {
          void vscode.window.showErrorMessage(
            `Benchmark History 확인 실패: ${String(error)}`
          );
        }
      }
    );

  context.subscriptions.push(
    pingCommand,
    analyzeFileCommand,
    analyzeWorkspaceCommand,
    openHotspotCommand,
    inspectHotspotCommand,
    verifyBaselineCommand,
    verifyCandidateCommand,
    recordDecisionCommand,
    viewDecisionHistoryCommand,
    benchmarkCandidateCommand,
    viewBenchmarkHistoryCommand
  );
}


export function deactivate(): void {
  // 현재 단계에서는 종료할 장기 실행 프로세스가 없습니다.
}
