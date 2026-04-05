interface ThemeToggleProps {
  theme: "light" | "dark";
  onToggle: () => void;
}

export function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex items-center gap-4 rounded-full border border-white/70 bg-white/85 px-4 py-3 text-sm font-medium text-slate-900 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_22px_56px_rgba(15,23,42,0.12)] dark:border-slate-700 dark:bg-slate-900/90 dark:text-white dark:shadow-none"
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
    >
      <span>{theme === "light" ? "Light" : "Dark"}</span>
      <span className="relative inline-flex h-7 w-12 items-center rounded-full bg-slate-200 p-1 dark:bg-slate-700">
        <span
          className={`h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200 dark:bg-slate-100 ${
            theme === "dark" ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </span>
    </button>
  );
}
