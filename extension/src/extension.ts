import * as vscode from "vscode";
import { CoreClient } from "./coreClient";

export function activate(context: vscode.ExtensionContext): void {
  const disposable = vscode.commands.registerCommand(
    "proofcode.pingCore",
    async () => {
      const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

      if (!workspaceRoot) {
        void vscode.window.showErrorMessage(
          "ProofCode 저장소 폴더를 먼저 VS Code에서 열어주세요."
        );
        return;
      }

      const configuration = vscode.workspace.getConfiguration("proofcode");
      const pythonPath = configuration.get<string>("pythonPath", "python");
      const client = new CoreClient({ pythonPath, workspaceRoot });

      try {
        const response = await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: "ProofCode Core 연결 확인 중…",
            cancellable: false
          },
          () => client.ping()
        );

        void vscode.window.showInformationMessage(
          `${response.message} (protocol ${response.protocol_version})`
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        void vscode.window.showErrorMessage(`ProofCode Core 연결 실패: ${message}`);
      }
    }
  );

  context.subscriptions.push(disposable);
}

export function deactivate(): void {
  // 현재 단계에서는 종료할 장기 실행 프로세스가 없습니다.
}
