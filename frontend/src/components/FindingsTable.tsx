import { useDeferredValue, useState } from "react";

import { AnalysisStatusResponse, Finding, ImpactLevel, IssueCluster, Severity } from "../types/report";
import { SeverityBadge } from "./SeverityBadge";

interface FindingsTableProps {
  findings: Finding[];
  clusters: IssueCluster[];
  status?: AnalysisStatusResponse | null;
  selectedFindingId?: string | null;
  onSelect: (finding: Finding) => void;
  onApplyHighSeverity: () => Promise<void>;
  onApplyGroup: (cluster: IssueCluster) => Promise<void>;
  isApplyingBatch: boolean;
}

type ViewMode = "findings" | "groups";
type SortMode = "severity" | "impact" | "confidence" | "effort" | "file";

const ROW_HEIGHT = 132;
const OVERSCAN = 6;
const COMMAND_FIX_PATTERN = /^(pip install|poetry add|uv add|npm install|pnpm add|yarn add)/i;
const UNUSED_VARIABLE_PATTERN = /(unused-variable|w0612)/i;

const severityOrder: Record<Severity, number> = {
  Critical: 0,
  High: 1,
  Medium: 2,
  Low: 3,
};

const impactOrder: Record<ImpactLevel, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

const effortOrder = {
  low: 0,
  medium: 1,
  high: 2,
} as const;

function impactBadgeTone(level: ImpactLevel) {
  const tones: Record<ImpactLevel, string> = {
    critical: "bg-rose-500/15 text-rose-700 dark:bg-rose-500/20 dark:text-rose-200",
    high: "bg-orange-500/15 text-orange-700 dark:bg-orange-500/20 dark:text-orange-200",
    medium: "bg-amber-400/15 text-amber-700 dark:bg-amber-400/20 dark:text-amber-100",
    low: "bg-sky-500/15 text-sky-700 dark:bg-sky-500/20 dark:text-sky-100",
  };
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

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function canApplyInlinePatch(finding: Finding) {
  const normalized = finding.fix_patch.trim();
  if (COMMAND_FIX_PATTERN.test(normalized)) {
    return false;
  }
  return normalized.length > 0 || UNUSED_VARIABLE_PATTERN.test(`${finding.rule_id} ${finding.title}`);
}

function truncatePreview(value: string) {
  if (!value) {
    return "No common fix generated for this group yet.";
  }
  return value.split("\n").slice(0, 3).join("\n");
}

export function FindingsTable({
  findings,
  clusters,
  status,
  selectedFindingId,
  onSelect,
  onApplyHighSeverity,
  onApplyGroup,
  isApplyingBatch,
}: FindingsTableProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("findings");
  const [sortMode, setSortMode] = useState<SortMode>("severity");
  const [severityFilter, setSeverityFilter] = useState<Severity | "All">("All");
  const [impactFilter, setImpactFilter] = useState<ImpactLevel | "All">("All");
  const [categoryFilter, setCategoryFilter] = useState<Finding["category"] | "All">("All");
  const [fileFilter, setFileFilter] = useState("All");
  const [searchTerm, setSearchTerm] = useState("");
  const [scrollTop, setScrollTop] = useState(0);

  const deferredSearchTerm = useDeferredValue(searchTerm.trim().toLowerCase());
  const fileOptions = Array.from(new Set(findings.map((finding) => finding.file_path))).sort();
  const highSeverityCount = findings.filter(
    (finding) => canApplyInlinePatch(finding) && severityOrder[finding.severity] <= severityOrder.High,
  ).length;
  const isLoading = status?.status === "queued" || status?.status === "running";

  const filteredFindings = findings
    .filter((finding) => severityFilter === "All" || finding.severity === severityFilter)
    .filter((finding) => impactFilter === "All" || finding.impact_level === impactFilter)
    .filter((finding) => categoryFilter === "All" || finding.category === categoryFilter)
    .filter((finding) => fileFilter === "All" || finding.file_path === fileFilter)
    .filter((finding) => {
      if (!deferredSearchTerm) {
        return true;
      }
      const haystack = [
        finding.title,
        finding.rule_id,
        finding.file_path,
        finding.symbol_name ?? "",
        finding.root_cause,
        finding.description,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(deferredSearchTerm);
    })
    .sort((left, right) => {
      if (sortMode === "impact") {
        return impactOrder[left.impact_level] - impactOrder[right.impact_level] || severityOrder[left.severity] - severityOrder[right.severity];
      }
      if (sortMode === "confidence") {
        return right.confidence - left.confidence || severityOrder[left.severity] - severityOrder[right.severity];
      }
      if (sortMode === "effort") {
        return effortOrder[left.fix_effort] - effortOrder[right.fix_effort] || severityOrder[left.severity] - severityOrder[right.severity];
      }
      if (sortMode === "file") {
        return left.file_path.localeCompare(right.file_path) || left.start_line - right.start_line;
      }
      return severityOrder[left.severity] - severityOrder[right.severity] || impactOrder[left.impact_level] - impactOrder[right.impact_level];
    });

  const filteredClusters = clusters
    .filter((cluster) => impactFilter === "All" || cluster.impact_level === impactFilter)
    .filter((cluster) => fileFilter === "All" || cluster.affected_files.includes(fileFilter))
    .filter((cluster) => {
      if (!deferredSearchTerm) {
        return true;
      }
      const haystack = [
        cluster.reason,
        cluster.type,
        cluster.common_fix,
        cluster.affected_files.join(" "),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(deferredSearchTerm);
    })
    .sort((left, right) => impactOrder[left.impact_level] - impactOrder[right.impact_level] || right.count - left.count);

  const viewportHeight = 660;
  const totalHeight = filteredFindings.length * ROW_HEIGHT;
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const endIndex = Math.min(filteredFindings.length, startIndex + Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2);
  const visibleFindings = filteredFindings.slice(startIndex, endIndex);

  return (
    <section className="panel flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-4">
              <p className="section-title">Findings workspace</p>
              <p className="body-copy max-w-3xl">
                Review every issue, sort by what matters most, switch to grouped patterns, and apply fixes without freezing the UI on large repositories.
              </p>
            </div>
            <div className="flex flex-wrap gap-4">
              <span className="pill bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                {findings.length.toLocaleString()} total findings
              </span>
              <span className="pill bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                {clusters.length.toLocaleString()} grouped patterns
              </span>
              <span className="pill bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                {filteredFindings.length.toLocaleString()} visible rows
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-4 xl:items-end">
            <div className="inline-flex rounded-full border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-800">
              <button
                type="button"
                onClick={() => setViewMode("findings")}
                className={`rounded-full px-4 py-2 text-sm font-medium transition duration-200 ${
                  viewMode === "findings"
                    ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                    : "text-slate-500 dark:text-slate-300"
                }`}
              >
                Findings
              </button>
              <button
                type="button"
                onClick={() => setViewMode("groups")}
                className={`rounded-full px-4 py-2 text-sm font-medium transition duration-200 ${
                  viewMode === "groups"
                    ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                    : "text-slate-500 dark:text-slate-300"
                }`}
              >
                Grouped view
              </button>
            </div>
            <button
              type="button"
              onClick={() => void onApplyHighSeverity()}
              disabled={isApplyingBatch || highSeverityCount === 0}
              className="button-primary"
            >
              {isApplyingBatch ? "Applying fixes..." : `Fix All High Issues (${highSeverityCount})`}
            </button>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_repeat(4,minmax(0,0.5fr))]">
          <label className="flex flex-col gap-4">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Search</span>
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search by issue, file, symbol, or rule"
              className="control"
            />
          </label>
          <label className="flex flex-col gap-4">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Severity</span>
            <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value as Severity | "All")} className="control">
              <option value="All">All</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </label>
          <label className="flex flex-col gap-4">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Impact</span>
            <select value={impactFilter} onChange={(event) => setImpactFilter(event.target.value as ImpactLevel | "All")} className="control">
              <option value="All">All</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </label>
          <label className="flex flex-col gap-4">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Category</span>
            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value as Finding["category"] | "All")}
              className="control"
            >
              <option value="All">All</option>
              <option value="bug">Bug</option>
              <option value="security">Security</option>
              <option value="code_smell">Code Smell</option>
              <option value="performance">Performance</option>
            </select>
          </label>
          <label className="flex flex-col gap-4">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">File</span>
            <select value={fileFilter} onChange={(event) => setFileFilter(event.target.value)} className="control">
              <option value="All">All files</option>
              {fileOptions.map((filePath) => (
                <option key={filePath} value={filePath}>
                  {filePath}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
          <label className="flex flex-col gap-4">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Sort by</span>
            <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)} className="control">
              <option value="severity">Severity</option>
              <option value="impact">Impact</option>
              <option value="confidence">Confidence</option>
              <option value="effort">Fix effort</option>
              <option value="file">File</option>
            </select>
          </label>
          <div className="panel-muted flex flex-col gap-4 p-4">
            <p className="text-sm font-medium text-slate-900 dark:text-white">Large dataset mode</p>
            <p className="body-copy">
              Findings rows are virtualized, so even repos with thousands of issues stay smooth while scrolling and filtering.
            </p>
          </div>
        </div>
      </div>

      {isLoading && findings.length === 0 ? (
        <div className="panel-muted flex min-h-[660px] items-center justify-center p-8">
          <div className="flex flex-col items-center gap-6 text-center">
            <span className="h-12 w-12 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900 dark:border-slate-600 dark:border-t-white" />
            <div className="flex flex-col gap-4">
              <p className="text-xl font-medium text-slate-900 dark:text-white">Analyzing your repository...</p>
              <p className="body-copy max-w-xl">
                The review workspace will populate as soon as the backend finishes scanning files, grouping issues, and generating fixes.
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {!isLoading && findings.length === 0 ? (
        <div className="panel-muted flex min-h-[660px] items-center justify-center p-8">
          <div className="flex flex-col items-center gap-4 text-center">
            <p className="text-xl font-medium text-slate-900 dark:text-white">No analysis loaded yet.</p>
            <p className="body-copy max-w-xl">
              Start with a public GitHub repository URL above. Once the report is ready, every finding and grouped pattern will appear here.
            </p>
          </div>
        </div>
      ) : null}

      {!isLoading && findings.length > 0 && viewMode === "groups" ? (
        <div className="grid gap-4">
          {filteredClusters.length === 0 ? (
            <div className="panel-muted flex min-h-[360px] items-center justify-center p-8">
              <div className="flex flex-col items-center gap-4 text-center">
                <p className="text-xl font-medium text-slate-900 dark:text-white">No groups match the current filters.</p>
                <p className="body-copy max-w-xl">Try widening the impact, file, or search filters to bring grouped issue patterns back into view.</p>
              </div>
            </div>
          ) : null}

          {filteredClusters.map((cluster) => {
            const leadFinding = findings.find((finding) => cluster.issue_ids.includes(finding.id)) ?? null;
            const groupFixableCount = findings.filter(
              (finding) => cluster.issue_ids.includes(finding.id) && canApplyInlinePatch(finding),
            ).length;

            return (
              <article key={cluster.cluster_id} className="panel-muted grid gap-6 p-6 lg:grid-cols-[minmax(0,1fr)_280px]">
                <div className="flex flex-col gap-6">
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-wrap gap-4">
                      <span className={`pill ${impactBadgeTone(cluster.impact_level)}`}>{capitalize(cluster.impact_level)} impact</span>
                      <span className="pill bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                        {cluster.count} findings
                      </span>
                      <span className="pill bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                        {cluster.type}
                      </span>
                    </div>
                    <div className="flex flex-col gap-4">
                      <p className="text-xl font-medium text-slate-900 dark:text-white">{cluster.reason}</p>
                      <p className="body-copy">
                        {cluster.affected_files.length} affected files. Common pattern: {cluster.affected_files.join(", ")}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-[28px] bg-slate-900 p-4 text-sm text-slate-200 dark:bg-slate-950">
                    <p className="font-medium text-white">Common fix</p>
                    <pre className="mt-4 overflow-x-auto whitespace-pre-wrap leading-6 text-slate-300">{truncatePreview(cluster.common_fix)}</pre>
                  </div>
                </div>

                <div className="flex flex-col gap-6">
                  <div className="flex flex-col gap-4">
                    <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Representative finding</p>
                    {leadFinding ? (
                      <button
                        type="button"
                        onClick={() => onSelect(leadFinding)}
                        className="rounded-[28px] border border-slate-200 bg-white p-4 text-left transition duration-200 hover:-translate-y-0.5 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900"
                      >
                        <div className="flex flex-col gap-4">
                          <div className="flex flex-wrap gap-4">
                            <SeverityBadge severity={leadFinding.severity} />
                            <span className={`pill ${impactBadgeTone(leadFinding.impact_level)}`}>{capitalize(leadFinding.impact_level)} impact</span>
                          </div>
                          <div className="flex flex-col gap-4">
                            <p className="text-sm font-medium text-slate-900 dark:text-white">{leadFinding.title}</p>
                            <p className="body-copy">{leadFinding.file_path}:{leadFinding.start_line}</p>
                          </div>
                        </div>
                      </button>
                    ) : (
                      <div className="rounded-[28px] border border-dashed border-slate-300 p-4 text-sm text-gray-400 dark:border-slate-700">
                        No representative issue is available for this group.
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => void onApplyGroup(cluster)}
                    disabled={isApplyingBatch || groupFixableCount === 0}
                    className="button-secondary"
                  >
                    {isApplyingBatch ? "Applying fixes..." : `Fix All in Group (${groupFixableCount})`}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}

      {!isLoading && findings.length > 0 && viewMode === "findings" ? (
        <div className="flex flex-col gap-4">
          {filteredFindings.length === 0 ? (
            <div className="panel-muted flex min-h-[360px] items-center justify-center p-8">
              <div className="flex flex-col items-center gap-4 text-center">
                <p className="text-xl font-medium text-slate-900 dark:text-white">No findings match the current filters.</p>
                <p className="body-copy max-w-xl">Try broadening the filters or clearing the search term to bring more issues back into view.</p>
              </div>
            </div>
          ) : (
            <div className="overflow-hidden rounded-[32px] border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
              <div className="hidden grid-cols-[120px_120px_120px_120px_minmax(0,1fr)_200px] gap-4 border-b border-slate-200 px-4 py-4 text-sm font-medium text-slate-500 dark:border-slate-800 dark:text-slate-400 lg:grid">
                <span>Severity</span>
                <span>Impact</span>
                <span>Confidence</span>
                <span>Fix effort</span>
                <span>Issue</span>
                <span>Location</span>
              </div>

              <div className="relative h-[660px] overflow-y-auto" onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}>
                <div className="relative" style={{ height: totalHeight }}>
                  {visibleFindings.map((finding, index) => {
                    const rowIndex = startIndex + index;
                    const selected = selectedFindingId === finding.id;

                    return (
                      <button
                        key={finding.id}
                        type="button"
                        onClick={() => onSelect(finding)}
                        className="absolute left-0 right-0 px-4 text-left"
                        style={{ top: rowIndex * ROW_HEIGHT, height: ROW_HEIGHT }}
                      >
                        <div
                          className={`grid h-full gap-4 rounded-[28px] border px-4 py-4 transition duration-200 hover:-translate-y-0.5 ${
                            selected
                              ? "border-slate-900 bg-slate-900 text-white dark:border-slate-700 dark:bg-slate-800"
                              : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50 dark:bg-slate-900 dark:hover:border-slate-700 dark:hover:bg-slate-800"
                          } lg:grid-cols-[120px_120px_120px_120px_minmax(0,1fr)_200px]`}
                        >
                          <div className="flex flex-wrap items-center gap-4">
                            <SeverityBadge severity={finding.severity} />
                            <span className={`pill ${impactBadgeTone(finding.impact_level)} lg:hidden`}>{capitalize(finding.impact_level)}</span>
                          </div>
                          <div className="hidden items-center lg:flex">
                            <span className={`pill ${impactBadgeTone(finding.impact_level)}`}>{capitalize(finding.impact_level)}</span>
                          </div>
                          <div className="flex items-center">
                            <span className={`pill ${selected ? "bg-white/10 text-white" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200"}`}>
                              {finding.confidence}%
                            </span>
                          </div>
                          <div className="flex items-center">
                            <span className={`pill ${effortBadgeTone(finding.fix_effort)}`}>{capitalize(finding.fix_effort)}</span>
                          </div>
                          <div className="flex min-w-0 flex-col gap-4">
                            <p className={`truncate text-sm font-medium ${selected ? "text-white" : "text-slate-900 dark:text-white"}`}>{finding.title}</p>
                            <p className={`truncate text-sm ${selected ? "text-slate-200" : "text-gray-400"}`}>
                              {finding.root_cause || finding.description}
                            </p>
                          </div>
                          <div className="flex min-w-0 flex-col gap-4">
                            <p className={`truncate text-sm font-medium ${selected ? "text-white" : "text-slate-900 dark:text-white"}`}>{finding.file_path}</p>
                            <p className={`text-sm ${selected ? "text-slate-200" : "text-gray-400"}`}>
                              {finding.symbol_name ? `${finding.symbol_name} · ` : ""}Line {finding.start_line}
                            </p>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
