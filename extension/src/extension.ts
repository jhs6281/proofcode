import * as vscode from "vscode";
import {
  CoreAnalyzeWorkspaceResponse,
  CoreClient,
  Hotspot
} from "./coreClient";

let latestHotspots: Hotspot[] = [];

function getWorkspaceRoot(): string {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  if (!root) {
    throw new Error(
      "ProofCode 저장소 폴더를 먼저 VS Code에서 열어주세요."
    );
  }

  return root;
}

function getAnalysisOptions(): {
  includeTests: boolean;
  includeExamples: boolean;
} {
  const config = vscode.workspace.getConfiguration("proofcode");

  return {
    includeTests: config.get<boolean>("includeTests", false),
    includeExamples: config.get<boolean>("includeExamples", false)
  };
}

function createCoreClient(): CoreClient {
  const config = vscode.workspace.getConfiguration("proofcode");
  const pythonPath = config.get<string>("pythonPath", "python");

  return new CoreClient({
    pythonPath,
    workspaceRoot: getWorkspaceRoot()
  });
}

function categoryLabel(category: Hotspot["category"]): string {
  switch (category) {
    case "test":
      return "테스트";
    case "example":
      return "예제";
    default:
      return "제품 코드";
  }
}

function riskLabel(hotspot: Hotspot): string {
  if (hotspot.complexity >= 10) {
    return "높음";
  }

  if (hotspot.complexity >= 6) {
    return "중간";
  }

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
    `- 제품 코드 파일: ${analysis.category_counts.source}개`,
    `- 테스트 파일: ${analysis.category_counts.test}개`,
    `- 예제/Fixture 파일: ${analysis.category_counts.example}개`,
    `- 구조 분석 지원 파일: ${analysis.supported_structure_files}개`,
    `- 전체 코드 줄 수: ${analysis.total_lines}`,
    `- 전체 클래스 수: ${analysis.total_classes}`,
    `- 전체 함수/메서드 수: ${analysis.total_functions}`,
    "",
    "## 정적 분석 기반 우선 검토 후보",
    ""
  ];

  if (analysis.hotspots.length === 0) {
    lines.push(
      "> 현재 설정으로 표시할 Python 함수가 없습니다."
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
      `- 단순 위험 표시: ${riskLabel(hotspot)}`,
      `- 근거: ${hotspot.reasons.join(", ")}`,
      ""
    );
  });

  lines.push(
    "---",
    "",
    "> 이 결과는 성능 병목 확정이 아닙니다.",
    "> 정적 구조를 기준으로 먼저 검토할 후보를 보여줍니다.",
    "> 후보로 이동하려면 `ProofCode: Open Hotspot` 명령을 실행하세요."
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

async function runWorkspaceAnalysis(): Promise<
  CoreAnalyzeWorkspaceResponse
> {
  const options = getAnalysisOptions();

  return vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "ProofCode 프로젝트 전체 분석 중…",
      cancellable: false
    },
    () => createCoreClient().analyzeWorkspace(
      getWorkspaceRoot(),
      options
    )
  );
}

async function openHotspot(hotspot: Hotspot): Promise<void> {
  const document = await vscode.workspace.openTextDocument(
    vscode.Uri.file(hotspot.file_path)
  );

  const editor = await vscode.window.showTextDocument(
    document,
    vscode.ViewColumn.One
  );

  const startLine = Math.max(0, hotspot.line_start - 1);
  const endLine = Math.max(startLine, hotspot.line_end - 1);

  const range = new vscode.Range(
    new vscode.Position(startLine, 0),
    new vscode.Position(
      endLine,
      document.lineAt(endLine).text.length
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
}

export function activate(
  context: vscode.ExtensionContext
): void {
  const analyzeWorkspaceCommand = vscode.commands.registerCommand(
    "proofcode.analyzeWorkspace",
    async () => {
      try {
        const response = await runWorkspaceAnalysis();
        latestHotspots = response.workspace_analysis.hotspots;

        await showMarkdown(
          formatWorkspaceAnalysis(response)
        );
      } catch (error) {
        const message = error instanceof Error
          ? error.message
          : String(error);

        void vscode.window.showErrorMessage(
          `프로젝트 분석 실패: ${message}`
        );
      }
    }
  );

  const openHotspotCommand = vscode.commands.registerCommand(
    "proofcode.openHotspot",
    async () => {
      try {
        if (latestHotspots.length === 0) {
          const response = await runWorkspaceAnalysis();
          latestHotspots = response.workspace_analysis.hotspots;
        }

        if (latestHotspots.length === 0) {
          void vscode.window.showInformationMessage(
            "현재 설정으로 표시할 Hotspot이 없습니다."
          );
          return;
        }

        const selected = await vscode.window.showQuickPick(
          latestHotspots.map((hotspot) => ({
            label: hotspot.symbol_name,
            description:
              `${hotspot.relative_path}:${hotspot.line_start}`,
            detail:
              `복잡도 ${hotspot.complexity} · ` +
              `${categoryLabel(hotspot.category)} · ` +
              hotspot.reasons.join(", "),
            hotspot
          })),
          {
            title: "ProofCode Hotspot 선택",
            placeHolder: "이동할 함수 또는 메서드를 선택하세요.",
            matchOnDescription: true,
            matchOnDetail: true
          }
        );

        if (selected) {
          await openHotspot(selected.hotspot);
        }
      } catch (error) {
        const message = error instanceof Error
          ? error.message
          : String(error);

        void vscode.window.showErrorMessage(
          `Hotspot 열기 실패: ${message}`
        );
      }
    }
  );

  context.subscriptions.push(
    analyzeWorkspaceCommand,
    openHotspotCommand
  );
}

export function deactivate(): void {
  // 현재 단계에서는 종료할 장기 실행 프로세스가 없습니다.
}
