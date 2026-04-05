import { Category, Severity } from "../types/report";

interface FiltersBarProps {
  severity: string;
  category: string;
  filePath: string;
  files: string[];
  onSeverityChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onFileChange: (value: string) => void;
}

const severityOptions: Array<Severity | "All"> = ["All", "Critical", "High", "Medium", "Low"];
const categoryOptions: Array<Category | "All"> = ["All", "bug", "security", "code_smell", "performance"];

export function FiltersBar({
  severity,
  category,
  filePath,
  files,
  onSeverityChange,
  onCategoryChange,
  onFileChange,
}: FiltersBarProps) {
  return (
    <div className="glass-panel rounded-[24px] p-5 shadow-card transition-all duration-300 dark:border-white/10">
      <div className="grid gap-4 md:grid-cols-3">
        <label className="text-sm text-slate-600 dark:text-slate-300">
          <span className="mb-2 block font-medium">Severity</span>
          <select
            value={severity}
            onChange={(event) => onSeverityChange(event.target.value)}
            className="w-full rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 outline-none transition-all duration-300 focus:border-sky-300 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:focus:border-sky-500 dark:focus:ring-sky-500/20"
          >
            {severityOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-600 dark:text-slate-300">
          <span className="mb-2 block font-medium">Category</span>
          <select
            value={category}
            onChange={(event) => onCategoryChange(event.target.value)}
            className="w-full rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 outline-none transition-all duration-300 focus:border-sky-300 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:focus:border-sky-500 dark:focus:ring-sky-500/20"
          >
            {categoryOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-600 dark:text-slate-300">
          <span className="mb-2 block font-medium">File</span>
          <select
            value={filePath}
            onChange={(event) => onFileChange(event.target.value)}
            className="w-full rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 outline-none transition-all duration-300 focus:border-sky-300 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:focus:border-sky-500 dark:focus:ring-sky-500/20"
          >
            <option value="All">All</option>
            {files.map((file) => (
              <option key={file} value={file}>
                {file}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
