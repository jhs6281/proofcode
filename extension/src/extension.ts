import * as vscode from "vscode";
import {
  CoreAnalyzeWorkspaceResponse,
  CoreClient,
  Hotspot
} from "./coreClient";

let latestHotspots: Hotspot[] = [];

function workspaceRoot(): string {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) throw new Error("ProofCode 저장소 폴더를 먼저 열어주세요.");
  return root;
}

function client(): CoreClient {
  const config = vscode.workspace.getConfiguration("proofcode");
  return new CoreClient(
    config.get<string>("pythonPath", "python"),
    workspaceRoot()
  );
}

function categoryLabel(category: Hotspot["category"]): string {
  if (category === "test") return "테스트 코드";
  if (category === "example") return "예제/Fixture";
  return "제품 코드";
}

function interpretationNotes(hotspot: Hotspot): string[] {
  const notes: string[] = [];

  if (hotspot.evidence.max_nesting_depth >= 4) {
    notes.push(
      "중첩 깊이가 커서 코드 흐름을 따라가기 어려울 가능성이 있습니다."
    );
  }

  if (hotspot.line_count >= 50) {
    notes.push(
      "함수가 길어 여러 작업을 함께 담당하는지 확인할 가치가 있습니다."
    );
  }

  if (hotspot.evidence.return_count >= 5) {
    notes.push(
      "return 지점이 많아 종료 흐름을 확인할 가치가 있습니다."
    );
  }

  if (hotspot.evidence.call_count >= 10) {
    notes.push(
      "다른 함수 호출이 많아 의존 관계를 확인할 가치가 있습니다."
    );
  }

  return notes.length > 0
    ? notes
    : ["현재 규칙에서 추가 주의점은 발견되지 않았습니다."];
}

function formatEvidenceReport(hotspot: Hotspot): string {
  const breakdown = hotspot.complexity_breakdown;
  const evidence = hotspot.evidence;
  const notes = interpretationNotes(hotspot);

  return [
    "# ProofCode Hotspot Evidence",
    "",
    "## 대상",
    "",
    `- 함수/메서드: **${hotspot.symbol_name}**`,
    `- 파일: \`${hotspot.relative_path}\``,
    `- 위치: ${hotspot.line_start}~${hotspot.line_end}줄`,
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
    `- raise 문: ${evidence.raise_count}개`,
    "",
    "## 해석 가능한 주의점",
    "",
    ...notes.map((note) => `- ${note}`),
    "",
    "## 아직 확인하지 않은 것",
    "",
    "- 실제 실행 속도",
    "- CPU와 메모리 사용량",
    "- 테스트 통과 여부",
    "- 리팩터링 후 동작 동일성",
    "- 성능 병목 여부",
    "",
    "---",
    "",
    "> 이 리포트는 정적 분석 Evidence입니다.",
    "> 코드를 실행하지 않았으므로 성능 문제를 확정하지 않습니다.",
    "> ProofCode는 이 단계에서 코드를 자동 변경하지 않습니다."
  ].join("\n");
}

async function analyze(): Promise<CoreAnalyzeWorkspaceResponse> {
  const config = vscode.workspace.getConfiguration("proofcode");

  return vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "ProofCode Evidence 수집 중…",
      cancellable: false
    },
    () => client().analyzeWorkspace(
      config.get<boolean>("includeTests", false),
      config.get<boolean>("includeExamples", false)
    )
  );
}

async function selectHotspot(): Promise<Hotspot | undefined> {
  if (latestHotspots.length === 0) {
    const result = await analyze();
    latestHotspots = result.workspace_analysis.hotspots;
  }

  const selected = await vscode.window.showQuickPick(
    latestHotspots.map((hotspot) => ({
      label: hotspot.symbol_name,
      description: `${hotspot.relative_path}:${hotspot.line_start}`,
      detail:
        `복잡도 ${hotspot.complexity} · ` +
        `중첩 ${hotspot.evidence.max_nesting_depth} · ` +
        hotspot.reasons.join(", "),
      hotspot
    })),
    {
      title: "ProofCode Hotspot 선택",
      placeHolder: "상세 Evidence를 확인할 함수를 선택하세요.",
      matchOnDescription: true,
      matchOnDetail: true
    }
  );

  return selected?.hotspot;
}

async function openCode(hotspot: Hotspot): Promise<void> {
  const document = await vscode.workspace.openTextDocument(
    vscode.Uri.file(hotspot.file_path)
  );
  const editor = await vscode.window.showTextDocument(
    document,
    vscode.ViewColumn.One
  );

  const start = Math.max(0, hotspot.line_start - 1);
  const end = Math.max(start, hotspot.line_end - 1);
  const range = new vscode.Range(
    new vscode.Position(start, 0),
    new vscode.Position(end, document.lineAt(end).text.length)
  );

  editor.selection = new vscode.Selection(range.start, range.end);
  editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
}

async function showReport(hotspot: Hotspot): Promise<void> {
  const report = await vscode.workspace.openTextDocument({
    language: "markdown",
    content: formatEvidenceReport(hotspot)
  });

  await vscode.window.showTextDocument(
    report,
    vscode.ViewColumn.Beside,
    true
  );
}

export function activate(context: vscode.ExtensionContext): void {
  const analyzeCommand = vscode.commands.registerCommand(
    "proofcode.analyzeWorkspace",
    async () => {
      try {
        const result = await analyze();
        latestHotspots = result.workspace_analysis.hotspots;
        void vscode.window.showInformationMessage(
          `ProofCode 분석 완료: Hotspot ${latestHotspots.length}개`
        );
      } catch (error) {
        void vscode.window.showErrorMessage(
          `프로젝트 분석 실패: ${String(error)}`
        );
      }
    }
  );

  const inspectCommand = vscode.commands.registerCommand(
    "proofcode.inspectHotspot",
    async () => {
      try {
        const hotspot = await selectHotspot();
        if (!hotspot) return;

        await openCode(hotspot);
        await showReport(hotspot);
      } catch (error) {
        void vscode.window.showErrorMessage(
          `Evidence 리포트 생성 실패: ${String(error)}`
        );
      }
    }
  );

  context.subscriptions.push(analyzeCommand, inspectCommand);
}

export function deactivate(): void {}
