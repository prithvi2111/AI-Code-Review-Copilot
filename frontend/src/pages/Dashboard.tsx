import { startTransition, useEffect, useState } from "react";

import { FindingDrawer } from "../components/FindingDrawer";
import { FindingsTable } from "../components/FindingsTable";
import { RepoForm } from "../components/RepoForm";
import { StatusPanel } from "../components/StatusPanel";
import { SummaryCards } from "../components/SummaryCards";
import { ThemeToggle } from "../components/ThemeToggle";
import {
  ApiError,
  applyFix,
  applyFixBatch,
  createAnalysis,
  createPullRequest,
  getAnalysisReport,
  getAnalysisStatus,
} from "../lib/api";
import { AnalysisReport, AnalysisStatusResponse, Finding, IssueCluster } from "../types/report";

const COMMAND_FIX_PATTERN = /^(pip install|poetry add|uv add|npm install|pnpm add|yarn add)/i;
const UNUSED_VARIABLE_PATTERN = /(unused-variable|w0612)/i;

function canApplyInlinePatch(finding: Finding) {
  const normalized = finding.fix_patch.trim();
  if (COMMAND_FIX_PATTERN.test(normalized)) {
    return false;
  }
  return normalized.length > 0 || UNUSED_VARIABLE_PATTERN.test(`${finding.rule_id} ${finding.title}`);
}

export function Dashboard() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") {
      return "light";
    }
    return window.localStorage.getItem("copilot-theme") === "dark" ? "dark" : "light";
  });
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatusResponse | null>(null);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isApplyingFix, setIsApplyingFix] = useState(false);
  const [isApplyingBatch, setIsApplyingBatch] = useState(false);
  const [isCreatingPr, setIsCreatingPr] = useState(false);
  const [hasAppliedFixes, setHasAppliedFixes] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionLink, setActionLink] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem("copilot-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!runId || !status || status.status === "completed" || status.status === "failed") {
      return undefined;
    }

    const timer = window.setInterval(async () => {
      try {
        const nextStatus = await getAnalysisStatus(runId);
        setStatus(nextStatus);
        if (nextStatus.status === "completed") {
          const nextReport = await getAnalysisReport(runId);
          startTransition(() => {
            setReport(nextReport);
          });
          window.clearInterval(timer);
        }
        if (nextStatus.status === "failed") {
          window.clearInterval(timer);
        }
      } catch (nextError) {
        window.clearInterval(timer);
        setError(nextError instanceof Error ? nextError.message : "Unable to refresh analysis status.");
      }
    }, 2500);

    return () => window.clearInterval(timer);
  }, [runId, status]);

  async function handleSubmit(repoUrl: string) {
    setLoading(true);
    setError(null);
    setStatus(null);
    setHasAppliedFixes(false);
    setActionMessage(null);
    setActionLink(null);
    startTransition(() => {
      setReport(null);
      setSelectedFinding(null);
    });

    try {
      const created = await createAnalysis(repoUrl);
      setRunId(created.run_id);
      const nextStatus = await getAnalysisStatus(created.run_id);
      setStatus(nextStatus);

      if (nextStatus.status === "completed") {
        const nextReport = await getAnalysisReport(created.run_id);
        startTransition(() => {
          setReport(nextReport);
        });
      }
    } catch (submitError) {
      if (submitError instanceof ApiError) {
        setError(submitError.message);
      } else {
        setError("Unable to start analysis. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  function updateAppliedFindings(appliedFindingIds: string[]) {
    const appliedSet = new Set(appliedFindingIds);
    startTransition(() => {
      setReport((currentReport) =>
        currentReport
          ? {
              ...currentReport,
              findings: currentReport.findings.map((item) =>
                appliedSet.has(item.id)
                  ? {
                      ...item,
                      snippet: item.fix_patch,
                    }
                  : item,
              ),
            }
          : currentReport,
      );
      setSelectedFinding((currentFinding) =>
        currentFinding && appliedSet.has(currentFinding.id)
          ? {
              ...currentFinding,
              snippet: currentFinding.fix_patch,
            }
          : currentFinding,
      );
    });
  }

  async function handleApplyFix(finding: Finding) {
    if (!runId) {
      return;
    }

    setIsApplyingFix(true);
    setActionMessage(null);
    setActionLink(null);
    setError(null);

    try {
      const response = await applyFix({
        run_id: runId,
        file_path: finding.file_path,
        finding_id: finding.id,
        start_line: finding.start_line,
        end_line: finding.end_line,
        fix_patch: finding.fix_patch,
      });
      setHasAppliedFixes(response.applied);
      setActionMessage(response.message);
      updateAppliedFindings([finding.id]);
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "Unable to apply the suggested fix.");
    } finally {
      setIsApplyingFix(false);
    }
  }

  async function handleBatchApply(findingIds: string[], label: string) {
    if (!runId || findingIds.length === 0) {
      return;
    }

    setIsApplyingBatch(true);
    setActionMessage(null);
    setActionLink(null);
    setError(null);

    try {
      const response = await applyFixBatch({
        run_id: runId,
        finding_ids: findingIds,
      });
      setHasAppliedFixes((currentValue) => currentValue || response.applied_count > 0);
      setActionMessage(`${label}: ${response.message}`);
      updateAppliedFindings(response.applied_finding_ids);
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "Unable to apply the selected fixes.");
    } finally {
      setIsApplyingBatch(false);
    }
  }

  async function handleCreatePr() {
    if (!runId) {
      return;
    }

    setIsCreatingPr(true);
    setActionMessage(null);
    setActionLink(null);
    setError(null);

    try {
      const response = await createPullRequest({
        run_id: runId,
        title: report ? `Apply ${report.repository.repo_name} copilot fixes` : undefined,
      });
      const extra = response.pr_url ? ` ${response.pr_url}` : response.patch_path ? ` Patch saved at ${response.patch_path}` : "";
      setActionMessage(`${response.message}${extra}`);
      setActionLink(response.pr_url ?? null);
    } catch (createPrError) {
      setError(createPrError instanceof Error ? createPrError.message : "Unable to create a pull request or patch.");
    } finally {
      setIsCreatingPr(false);
    }
  }

  const findings = report?.findings ?? [];
  const clusters = report?.clusters ?? [];
  const selectedCluster =
    selectedFinding && report
      ? report.clusters.find((cluster) => cluster.issue_ids.includes(selectedFinding.id)) ?? null
      : null;

  const highSeverityFixIds = findings
    .filter((finding) => canApplyInlinePatch(finding) && (finding.severity === "Critical" || finding.severity === "High"))
    .map((finding) => finding.id);

  const fileFixIds = selectedFinding
    ? findings
        .filter((finding) => finding.file_path === selectedFinding.file_path && canApplyInlinePatch(finding))
        .map((finding) => finding.id)
    : [];

  const groupFixIds = selectedCluster
    ? findings
        .filter((finding) => selectedCluster.issue_ids.includes(finding.id) && canApplyInlinePatch(finding))
        .map((finding) => finding.id)
    : [];

  return (
    <main className="relative min-h-screen overflow-hidden text-slate-900 dark:text-white">
      <div className="grid-fade absolute inset-0 opacity-50" />

      <div className="app-shell relative flex flex-col gap-8 py-8">
        <section className="panel flex flex-col gap-8 p-8">
          <div className="flex flex-col gap-8 xl:flex-row xl:items-start xl:justify-between">
            <div className="flex max-w-3xl flex-col gap-6">
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
                AI-Powered Code Review Copilot
              </p>
              <div className="flex flex-col gap-6">
                <h1 className="text-5xl font-semibold tracking-tight text-slate-900 dark:text-white">
                  Understand your codebase. Fix issues instantly.
                </h1>
                <p className="body-copy max-w-2xl">
                  AI-powered code review that detects bugs, explains them clearly, and generates production-ready fixes in seconds.
                </p>
              </div>
            </div>

            <ThemeToggle theme={theme} onToggle={() => setTheme((currentTheme) => (currentTheme === "light" ? "dark" : "light"))} />
          </div>
        </section>

        <RepoForm onSubmit={handleSubmit} loading={loading} />

        {error ? (
          <section className="panel flex flex-col gap-4 border-rose-200 bg-rose-50/90 p-6 dark:border-rose-500/20 dark:bg-rose-500/10">
            <p className="section-title text-rose-700 dark:text-rose-200">Something needs attention</p>
            <p className="text-sm leading-7 text-rose-700 dark:text-rose-200">{error}</p>
          </section>
        ) : null}

        <StatusPanel status={status} />
        <SummaryCards summary={report?.summary} languages={report?.repository.languages} />

        <FindingsTable
          findings={findings}
          clusters={clusters}
          status={status}
          selectedFindingId={selectedFinding?.id ?? null}
          onSelect={(finding) => {
            startTransition(() => {
              setSelectedFinding(finding);
            });
          }}
          onApplyHighSeverity={() => handleBatchApply(highSeverityFixIds, "High issue batch")}
          onApplyGroup={(cluster: IssueCluster) =>
            handleBatchApply(
              findings
                .filter((finding) => cluster.issue_ids.includes(finding.id) && canApplyInlinePatch(finding))
                .map((finding) => finding.id),
              `Group ${cluster.type}`,
            )
          }
          isApplyingBatch={isApplyingBatch}
        />
      </div>

      <FindingDrawer
        finding={selectedFinding}
        cluster={selectedCluster}
        open={Boolean(selectedFinding)}
        fileFixCount={fileFixIds.length}
        groupFixCount={groupFixIds.length}
        isApplyingFix={isApplyingFix}
        isApplyingBatch={isApplyingBatch}
        isCreatingPr={isCreatingPr}
        hasAppliedFixes={hasAppliedFixes}
        actionMessage={actionMessage}
        actionLink={actionLink}
        onClose={() => setSelectedFinding(null)}
        onApplyFix={handleApplyFix}
        onApplyAllInFile={(finding) => handleBatchApply(fileFixIds, `File ${finding.file_path}`)}
        onApplyAllInGroup={(cluster) => handleBatchApply(groupFixIds, `Group ${cluster.type}`)}
        onCreatePr={handleCreatePr}
      />
    </main>
  );
}
