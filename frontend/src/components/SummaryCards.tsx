import { SummaryMetrics } from "../types/report";

interface SummaryCardsProps {
  summary?: SummaryMetrics | null;
  languages?: Record<string, number>;
}

export function SummaryCards({ summary, languages }: SummaryCardsProps) {
  const topSeverity = summary
    ? Object.entries(summary.severity_distribution).sort((left, right) => right[1] - left[1])[0]?.[0] ?? "None"
    : "None";
  const hotspot = summary?.hotspots[0]?.file_path ?? "No pressure yet";
  const languageSummary = languages ? Object.keys(languages).join(", ") || "Unknown" : "Unknown";

  const cards = [
    {
      label: "Repository Health",
      value: summary ? `${summary.repository_health_score.toFixed(0)}/100` : "100/100",
      detail: "Higher means the repo is easier to ship with confidence.",
      tone: "text-emerald-500 dark:text-emerald-300",
    },
    {
      label: "Total Findings",
      value: summary ? `${summary.total_issues}` : "0",
      detail: "Every finding is returned. Nothing is truncated.",
      tone: "text-slate-900 dark:text-white",
    },
    {
      label: "Highest Pressure",
      value: topSeverity,
      detail: `Top hotspot: ${hotspot}`,
      tone: "text-orange-500 dark:text-orange-300",
    },
    {
      label: "Issue Groups",
      value: summary ? `${summary.total_groups}` : "0",
      detail: "Repeated patterns are clustered for faster cleanup.",
      tone: "text-sky-500 dark:text-sky-300",
    },
    {
      label: "Languages",
      value: languageSummary,
      detail: "Python gets deep analysis. Other languages are inventoried.",
      tone: "text-slate-900 dark:text-white",
    },
  ];

  return (
    <section className="grid gap-4 lg:grid-cols-5">
      {cards.map((card) => (
        <article key={card.label} className="panel flex min-h-[172px] flex-col gap-6 p-6">
          <div className="flex flex-col gap-4">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{card.label}</p>
            <p className={`text-3xl font-semibold tracking-tight ${card.tone}`}>{card.value}</p>
          </div>
          <p className="body-copy">{card.detail}</p>
        </article>
      ))}
    </section>
  );
}
