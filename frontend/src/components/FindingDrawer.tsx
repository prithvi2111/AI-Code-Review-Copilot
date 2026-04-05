import { Finding, IssueCluster } from "../types/report";
import { SeverityBadge } from "./SeverityBadge";

interface FindingDrawerProps {
  finding: Finding | null;
  cluster?: IssueCluster | null;
  open: boolean;
  fileFixCount: number;
  groupFixCount: number;
  isApplyingFix: boolean;
  isApplyingBatch: boolean;
  isCreatingPr: boolean;
  hasAppliedFixes: boolean;
  actionMessage?: string | null;
  actionLink?: string | null;
  onClose: () => void;
  onApplyFix: (finding: Finding) => Promise<void>;
  onApplyAllInFile: (finding: Finding) => Promise<void>;
  onApplyAllInGroup: (cluster: IssueCluster) => Promise<void>;
  onCreatePr: () => Promise<void>;
}

const COMMAND_FIX_PATTERN = /^(pip install|poetry add|uv add|npm install|pnpm add|yarn add)/i;
const UNUSED_VARIABLE_PATTERN = /(unused-variable|w0612)/i;

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function impactBadgeTone(level: Finding["impact_level"]) {
  const tones = {
    critical: "bg-rose-500/15 text-rose-700 dark:bg-rose-500/20 dark:text-rose-200",
    high: "bg-orange-500/15 text-orange-700 dark:bg-orange-500/20 dark:text-orange-200",
    medium: "bg-amber-400/15 text-amber-700 dark:bg-amber-400/20 dark:text-amber-100",
    low: "bg-sky-500/15 text-sky-700 dark:bg-sky-500/20 dark:text-sky-100",
  } as const;
  return tones[level];
}

function effortBadgeTone(level: Finding["fix_effort"]) {
  const tones = {
    low: "bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200",
    medium: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
    high: "bg-violet-500/15 text-violet-700 dark:bg-violet-500/20 dark:text-violet-200",
  } as const;
  return tones[level];
}

function canApplyInlinePatch(finding: Finding) {
  const normalized = finding.fix_patch.trim();
  if (COMMAND_FIX_PATTERN.test(normalized)) {
    return false;
  }
  return normalized.length > 0 || UNUSED_VARIABLE_PATTERN.test(`${finding.rule_id} ${finding.title}`);
}

function codeLabel(finding: Finding) {
  return COMMAND_FIX_PATTERN.test(finding.fix_patch.trim()) ? "Suggested command" : "Suggested fix";
}

export function FindingDrawer({
  finding,
  cluster,
  open,
  fileFixCount,
  groupFixCount,
  isApplyingFix,
  isApplyingBatch,
  isCreatingPr,
  hasAppliedFixes,
  actionMessage,
  actionLink,
  onClose,
  onApplyFix,
  onApplyAllInFile,
  onApplyAllInGroup,
  onCreatePr,
}: FindingDrawerProps) {
  if (!open || !finding) {
    return null;
  }

  const canApplyInlineFix = canApplyInlinePatch(finding);
  const isCommandFix = COMMAND_FIX_PATTERN.test(finding.fix_patch.trim());

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/55 backdrop-blur-md">
      <div className="absolute right-0 top-0 h-full w-full max-w-2xl overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.2)] dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-6">
          <div className="flex items-start justify-between gap-6">
            <div className="flex min-w-0 flex-col gap-4">
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{finding.tool_source}</p>
              <h2 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">{finding.title}</h2>
              <p className="text-sm text-gray-400">{finding.explanation || finding.description}</p>
            </div>
            <button type="button" onClick={onClose} className="button-secondary">
              Close
            </button>
          </div>

          <section className="panel-muted flex flex-col gap-6 p-6">
            <p className="section-title">Metadata</p>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex flex-wrap gap-4">
                <SeverityBadge severity={finding.severity} />
                <span className={`pill ${impactBadgeTone(finding.impact_level)}`}>{capitalize(finding.impact_level)} impact</span>
                <span className={`pill ${effortBadgeTone(finding.fix_effort)}`}>{capitalize(finding.fix_effort)} effort</span>
              </div>
              <div className="flex flex-wrap gap-4">
                <span className="pill bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200">{finding.confidence}% confidence</span>
                <span className="pill bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200">{finding.category.replace("_", " ")}</span>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-4">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Location</p>
                <p className="text-sm text-slate-900 dark:text-white">
                  {finding.file_path}:{finding.start_line}
                  {finding.symbol_name ? ` · ${finding.symbol_name}` : ""}
                </p>
              </div>
              <div className="flex flex-col gap-4">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Rule</p>
                <p className="text-sm text-slate-900 dark:text-white">{finding.rule_id}</p>
              </div>
            </div>
          </section>

          <section className="panel-muted flex flex-col gap-4 p-6">
            <p className="section-title">Why it matters</p>
            <p className="text-sm leading-7 text-slate-700 dark:text-gray-300">{finding.explanation || finding.description}</p>
          </section>

          <section className="panel-muted flex flex-col gap-4 p-6">
            <p className="section-title">Root cause</p>
            <p className="text-sm leading-7 text-slate-700 dark:text-gray-300">{finding.root_cause}</p>
          </section>

          <section className="panel-muted flex flex-col gap-4 p-6">
            <p className="section-title">Impact</p>
            <p className="text-sm leading-7 text-slate-700 dark:text-gray-300">{finding.impact}</p>
          </section>

          <section className="flex flex-col gap-4 rounded-[28px] bg-slate-800 p-6 dark:bg-slate-800">
            <div className="flex flex-col gap-4">
              <p className="text-xl font-medium text-white">{codeLabel(finding)}</p>
              <p className="text-sm leading-7 text-gray-300">{finding.suggestion}</p>
            </div>
            <pre className="overflow-x-auto rounded-[24px] bg-slate-900 p-4 text-sm leading-7 text-white">
              {finding.fix_patch || "No code patch available."}
            </pre>
            {isCommandFix ? (
              <p className="text-sm text-gray-300">This fix is a dependency or environment command, so it is shown for guidance and cannot be applied inline.</p>
            ) : null}
          </section>

          <section className="flex flex-col gap-4 rounded-[28px] bg-slate-900 p-6 dark:bg-slate-950">
            <p className="text-xl font-medium text-white">Code snippet</p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-[24px] bg-slate-800 p-4 text-sm leading-7 text-gray-300 dark:bg-slate-900">
              {finding.snippet || "No snippet available."}
            </pre>
          </section>

          <section className="panel-muted flex flex-col gap-6 p-6">
            <p className="section-title">Actions</p>
            <div className="grid gap-4">
              <button
                type="button"
                onClick={() => void onApplyFix(finding)}
                disabled={!canApplyInlineFix || isApplyingFix}
                className="button-primary"
              >
                {isApplyingFix ? "Applying fix..." : "Apply Fix"}
              </button>
              <button
                type="button"
                onClick={() => void onApplyAllInFile(finding)}
                disabled={isApplyingBatch || fileFixCount === 0}
                className="button-secondary"
              >
                {isApplyingBatch ? "Applying fixes..." : `Fix All in File (${fileFixCount})`}
              </button>
              <button
                type="button"
                onClick={() => {
                  if (cluster) {
                    void onApplyAllInGroup(cluster);
                  }
                }}
                disabled={isApplyingBatch || !cluster || groupFixCount === 0}
                className="button-secondary"
              >
                {isApplyingBatch ? "Applying fixes..." : `Fix All in Group (${groupFixCount})`}
              </button>
              <button
                type="button"
                onClick={() => void onCreatePr()}
                disabled={!hasAppliedFixes || isCreatingPr}
                className="button-secondary"
              >
                {isCreatingPr ? "Creating PR..." : "Create PR"}
              </button>
            </div>

            {!hasAppliedFixes ? (
              <p className="text-sm text-gray-400">Apply at least one inline fix before opening a pull request or generating a patch bundle.</p>
            ) : null}

            {actionMessage ? (
              <div className="rounded-[24px] bg-slate-900 p-4 dark:bg-slate-800">
                <div className="flex flex-col gap-4">
                  <p className="text-sm leading-7 text-white">{actionMessage}</p>
                  {actionLink ? (
                    <a href={actionLink} target="_blank" rel="noreferrer" className="text-sm font-medium text-sky-300 underline underline-offset-4">
                      Open Pull Request
                    </a>
                  ) : null}
                </div>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
