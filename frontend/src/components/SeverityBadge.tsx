import { Severity } from "../types/report";

const toneMap: Record<Severity, string> = {
  Critical: "bg-rose-500/15 text-rose-700 ring-rose-200 dark:bg-rose-500/20 dark:text-rose-200 dark:ring-rose-400/30",
  High: "bg-orange-500/15 text-orange-700 ring-orange-200 dark:bg-orange-500/20 dark:text-orange-200 dark:ring-orange-400/30",
  Medium: "bg-amber-400/15 text-amber-700 ring-amber-200 dark:bg-amber-400/20 dark:text-amber-100 dark:ring-amber-300/30",
  Low: "bg-sky-500/15 text-sky-700 ring-sky-200 dark:bg-sky-500/20 dark:text-sky-100 dark:ring-sky-300/30",
};

interface SeverityBadgeProps {
  severity: Severity;
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 transition-colors duration-300 ${toneMap[severity]}`}>
      {severity}
    </span>
  );
}
