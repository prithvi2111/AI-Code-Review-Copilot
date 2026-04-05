import { IssueCluster, SummaryMetrics } from "../types/report";

interface ClusterPanelProps {
  clusters: IssueCluster[];
  summary?: SummaryMetrics | null;
}

export function ClusterPanel({ clusters, summary }: ClusterPanelProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
      <div className="glass-panel rounded-[28px] p-6 shadow-card transition-all duration-300 dark:border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">Issue Clusters</p>
            <h3 className="mt-2 text-xl font-semibold text-ink">Related findings across the repo</h3>
          </div>
        </div>
        <div className="mt-5 space-y-3">
          {clusters.length === 0 ? (
            <p className="rounded-2xl bg-white/60 px-4 py-4 text-sm text-slate-500 dark:bg-slate-900/60 dark:text-slate-400">No repeated issue clusters were detected.</p>
          ) : null}
          {clusters.map((cluster) => (
            <div key={cluster.cluster_id} className="rounded-[22px] bg-white/65 p-4 transition-all duration-300 dark:bg-slate-900/60">
              <p className="font-semibold text-ink">{cluster.reason}</p>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                {cluster.affected_files.join(", ")}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="glass-panel rounded-[28px] p-6 shadow-card transition-all duration-300 dark:border-white/10">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">Hotspots</p>
        <h3 className="mt-2 text-xl font-semibold text-ink">Files with the most findings</h3>
        <div className="mt-5 space-y-3">
          {summary?.hotspots.map((hotspot) => (
            <div key={hotspot.file_path} className="rounded-[22px] bg-white/65 p-4 transition-all duration-300 dark:bg-slate-900/60">
              <div className="flex items-center justify-between gap-4">
                <p className="font-medium text-ink">{hotspot.file_path}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">{hotspot.issue_count} issues</p>
              </div>
            </div>
          )) ?? <p className="text-sm text-slate-500 dark:text-slate-400">Hotspots will appear when the report is ready.</p>}
        </div>
      </div>
    </div>
  );
}
