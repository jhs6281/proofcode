import * as vscode from "vscode";
import {
  CodeSymbol,
  CoreAnalyzeFileResponse,
  CoreClient
} from "./coreClient";

function createCoreClient(): CoreClient {
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  if (!workspaceRoot) {
    throw new Error(
      "ProofCode 저장소 폴더를 먼저 VS Code에서 열어주세요."
    );
  }

  const configuration = vscode.workspace.getConfiguration("proofcode");
  const pythonPath = configuration.get<string>("pythonPath", "python");

  return new CoreClient({ pythonPath, workspaceRoot });
}

function formatSymbol(symbol: CodeSymbol): string {
  const parameters = symbol.parameters.length > 0
    ? symbol.parameters.join(", ")
    : "없음";

  const complexity = symbol.complexity === null
    ? "해당 없음"
    : String(symbol.complexity);

  return [
    `### ${symbol.name}`,
    "",
    `- 종류: ${symbol.symbol_type}`,
    `- 위치: ${symbol.line_start}~${symbol.line_end}줄`,
    `- 길이: ${symbol.line_count}줄`,
    `- 매개변수: ${parameters}`,
    `- 복잡도: ${complexity}`,
    ""
  ].join("\n");
}

function formatAnalysis(result: CoreAnalyzeFileResponse): string {
  const analysis = result.analysis;
  const structure = analysis.structure;

  const sections: string[] = [
    "# ProofCode File Analysis",
    "",
    "## 기본 정보",
    "",
    `- **File:** ${analysis.file_name}`,
    `- **Language:** ${analysis.language}`,
    `- **Size:** ${analysis.size_bytes} bytes`,
    `- **Total lines:** ${analysis.total_lines}`,
    `- **Non-empty lines:** ${analysis.non_empty_lines}`,
    `- **Empty lines:** ${analysis.empty_lines}`,
    `- **SHA-256:** \`${analysis.sha256}\``,
    ""
  ];

  if (!structure.supported) {
    sections.push(
      "## 코드 구조",
      "",
      `현재 ${analysis.language} 구조 분석은 아직 지원하지 않습니다.`,
      "",
      "> 이번 단계에서는 Python AST 분석만 지원합니다."
    );

    return sections.join("\n");
  }

  sections.push(
    "## 코드 구조",
    "",
    `- Parser: ${structure.parser}`,
    `- 발견한 구조: ${structure.total_symbols}개`,
    `- 클래스: ${structure.classes.length}개`,
    `- 함수/메서드: ${structure.functions.length}개`,
    ""
  );

  if (structure.classes.length > 0) {
    sections.push("## 클래스", "");
    for (const item of structure.classes) {
      sections.push(formatSymbol(item));
    }
  }

  if (structure.functions.length > 0) {
    sections.push("## 함수와 메서드", "");
    for (const item of structure.functions) {
      sections.push(formatSymbol(item));
    }
  }

  if (structure.total_symbols === 0) {
    sections.push(
      "> 이 Python 파일에서는 클래스나 함수를 찾지 못했습니다."
    );
  }

  sections.push(
    "",
    "> 복잡도는 조건문과 반복문이 많아질수록 증가하는 간단한 학습용 값입니다."
  );

  return sections.join("\n");
}

export function activate(context: vscode.ExtensionContext): void {
  const pingCommand = vscode.commands.registerCommand(
    "proofcode.pingCore",
    async () => {
      try {
        const response = await createCoreClient().ping();

        void vscode.window.showInformationMessage(
          `${response.message} (protocol ${response.protocol_version})`
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        void vscode.window.showErrorMessage(
          `ProofCode Core 연결 실패: ${message}`
        );
      }
    }
  );

  const analyzeFileCommand = vscode.commands.registerCommand(
    "proofcode.analyzeCurrentFile",
    async () => {
      const editor = vscode.window.activeTextEditor;

      if (!editor) {
        void vscode.window.showWarningMessage(
          "분석할 코드 파일을 먼저 열어주세요."
        );
        return;
      }

      if (editor.document.isUntitled) {
        void vscode.window.showWarningMessage(
          "분석 전에 파일을 먼저 저장해주세요."
        );
        return;
      }

      try {
        const response = await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: "현재 파일 구조 분석 중…",
            cancellable: false
          },
          () => createCoreClient().analyzeFile(
            editor.document.uri.fsPath
          )
        );

        const document = await vscode.workspace.openTextDocument({
          language: "markdown",
          content: formatAnalysis(response)
        });

        await vscode.window.showTextDocument(
          document,
          vscode.ViewColumn.Beside,
          true
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        void vscode.window.showErrorMessage(`파일 분석 실패: ${message}`);
      }
    }
  );

  context.subscriptions.push(pingCommand, analyzeFileCommand);
}

export function deactivate(): void {
  // 현재 단계에서는 종료할 장기 실행 프로세스가 없습니다.
}
