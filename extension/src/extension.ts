import * as vscode from "vscode";
import { CoreAnalyzeFileResponse, CoreClient } from "./coreClient";

function createCoreClient(): CoreClient {
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  if (!workspaceRoot) {
    throw new Error("ProofCode 저장소 폴더를 먼저 VS Code에서 열어주세요.");
  }

  const configuration = vscode.workspace.getConfiguration("proofcode");
  const pythonPath = configuration.get<string>("pythonPath", "python");

  return new CoreClient({ pythonPath, workspaceRoot });
}

function formatAnalysis(result: CoreAnalyzeFileResponse): string {
  const analysis = result.analysis;

  return [
    "# ProofCode File Analysis",
    "",
    `- **File:** ${analysis.file_name}`,
    `- **Language:** ${analysis.language}`,
    `- **Size:** ${analysis.size_bytes} bytes`,
    `- **Total lines:** ${analysis.total_lines}`,
    `- **Non-empty lines:** ${analysis.non_empty_lines}`,
    `- **Empty lines:** ${analysis.empty_lines}`,
    `- **SHA-256:** \`${analysis.sha256}\``,
    "",
    "> 현재 단계에서는 파일의 기본 정보만 분석합니다.",
    "> 다음 단계에서 함수, 클래스, 복잡도 분석을 추가합니다."
  ].join("\n");
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
        void vscode.window.showErrorMessage(`ProofCode Core 연결 실패: ${message}`);
      }
    }
  );

  const analyzeFileCommand = vscode.commands.registerCommand(
    "proofcode.analyzeCurrentFile",
    async () => {
      const editor = vscode.window.activeTextEditor;

      if (!editor) {
        void vscode.window.showWarningMessage("분석할 코드 파일을 먼저 열어주세요.");
        return;
      }

      if (editor.document.isUntitled) {
        void vscode.window.showWarningMessage("분석 전에 파일을 먼저 저장해주세요.");
        return;
      }

      try {
        const response = await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: "현재 파일 분석 중…",
            cancellable: false
          },
          () => createCoreClient().analyzeFile(editor.document.uri.fsPath)
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
