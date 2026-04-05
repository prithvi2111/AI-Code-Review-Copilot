import { AnalysisStatusResponse } from "../types/report";

interface StatusPanelProps {
  status?: AnalysisStatusResponse | null;
}

const steps = [
  "Queued for analysis",
  "Cloning and indexing repository",
  "Building code structure map",
  "Running static analysis",
  "Mapping findings to code locations",
  "Generating AI suggestions",
  "Assembling report",
  "Analysis completed",
];

export function StatusPanel({ status }: StatusPanelProps) {
  if (!status) {
    return null;
  }

  const activeIndex = Math.max(0, steps.findIndex((step) => step === status.progress));
  const isRunning = status.status === "queued" || status.status === "running";

  return (
    <section className="panel flex flex-col gap-6 p-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4">
            <p className="section-title">Analysis status</p>
            <p className="body-copy">{status.error ?? status.progress}</p>
          </div>
          {isRunning ? (
            <div className="panel-muted flex items-center justify-center p-8">
              <div className="flex flex-col items-center gap-4 text-center">
                <span className="h-10 w-10 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900 dark:border-slate-600 dark:border-t-white" />
                <div className="flex flex-col gap-4">
                  <p className="text-xl font-medium text-slate-900 dark:text-white">Analyzing your repository...</p>
                  <p className="body-copy max-w-xl">
                    The copilot is cloning the repository, building the structure map, scoring issues, and generating fixes.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <aside className="panel-muted flex flex-col gap-4 p-6">
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Run ID</p>
          <p className="break-all font-mono text-sm text-slate-900 dark:text-white">{status.run_id}</p>
          <p className="text-sm font-medium text-slate-900 dark:text-white">{status.status.toUpperCase()}</p>
        </aside>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {steps.map((step, index) => {
          const active = index <= activeIndex || status.status === "completed";
          return (
            <div
              key={step}
              className={`rounded-[28px] border px-4 py-4 text-sm transition duration-200 ${
                active
                  ? "border-slate-900 bg-slate-900 text-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                  : "border-slate-200 bg-slate-50 text-gray-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400"
              }`}
            >
              {step}
            </div>
          );
        })}
      </div>
    </section>
  );
}
