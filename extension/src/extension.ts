import * as vscode from "vscode";
import {
  CoreAnalyzeWorkspaceResponse,
  CoreClient,
  Hotspot
} from "./coreClient";

function getWorkspaceRoot(): string {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) {
    throw new Error("ProofCode 저장소 폴더를 먼저 열어주세요.");
  }
  return root;
}

function createCoreClient(): CoreClient {
  const config = vscode.workspace.getConfiguration("proofcode");
  const pythonPath = config.get<string>("pythonPath", "python");

  return new CoreClient({
    pythonPath,
    workspaceRoot: getWorkspaceRoot()
  });
}

function hotspotRiskLabel(hotspot: Hotspot): string {
  if (hotspot.complexity >= 10) return "높음";
  if (hotspot.complexity >= 6) return "중간";
  return "낮음";
}

function formatWorkspaceAnalysis(
  result: CoreAnalyzeWorkspaceResponse
): string {
  const analysis = result.workspace_analysis;
  const lines: string[] = [
    "# ProofCode Workspace Analysis",
    "",
    "## 프로젝트 요약",
    "",
    `- 분석 경로: \`${analysis.workspace_path}\``,
    `- 분석한 소스 파일: ${analysis.scanned_files}개`,
    `- 구조 분석 지원 파일: ${analysis.supported_structure_files}개`,
    `- 전체 코드 줄 수: ${analysis.total_lines}`,
    `- 전체 클래스 수: ${analysis.total_classes}`,
    `- 전체 함수/메서드 수: ${analysis.total_functions}`,
    "",
    "## 복잡도 우선 확인 후보",
    ""
  ];

  if (analysis.hotspots.length === 0) {
    lines.push("> 분석 가능한 Python 함수가 없습니다.");
    return lines.join("\n");
  }

  analysis.hotspots.forEach((hotspot, index) => {
    lines.push(
      `### ${index + 1}. ${hotspot.symbol_name}`,
      "",
      `- 파일: \`${hotspot.file_name}\``,
      `- 위치: ${hotspot.line_start}~${hotspot.line_end}줄`,
      `- 길이: ${hotspot.line_count}줄`,
      `- 복잡도: ${hotspot.complexity}`,
      `- 단순 위험 표시: ${hotspotRiskLabel(hotspot)}`,
      ""
    );
  });

  lines.push(
    "---",
    "",
    "> 이 순위는 나쁜 코드 순위가 아닙니다.",
    "> 먼저 검토할 가치가 있는 후보를 보여줍니다.",
    "> 아직 AI 추천이나 실제 성능 측정은 포함하지 않습니다."
  );

  return lines.join("\n");
}

async function showMarkdown(content: string): Promise<void> {
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

export function activate(context: vscode.ExtensionContext): void {
  const analyzeWorkspaceCommand = vscode.commands.registerCommand(
    "proofcode.analyzeWorkspace",
    async () => {
      try {
        const response = await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: "ProofCode 프로젝트 전체 분석 중…",
            cancellable: false
          },
          () => createCoreClient().analyzeWorkspace(getWorkspaceRoot())
        );

        await showMarkdown(formatWorkspaceAnalysis(response));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        void vscode.window.showErrorMessage(
          `프로젝트 분석 실패: ${message}`
        );
      }
    }
  );

  context.subscriptions.push(analyzeWorkspaceCommand);
}

export function deactivate(): void {}
