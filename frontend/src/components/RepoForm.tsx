import { FormEvent, useState } from "react";

interface RepoFormProps {
  onSubmit: (repoUrl: string) => Promise<void>;
  loading: boolean;
}

export function RepoForm({ onSubmit, loading }: RepoFormProps) {
  const [repoUrl, setRepoUrl] = useState("https://github.com/tiangolo/fastapi");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(repoUrl.trim());
  }

  return (
    <section className="panel flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-4">
          <p className="section-title">Paste a repository URL and run a full review.</p>
          <p className="body-copy max-w-3xl">
            Public GitHub repositories are cloned, analyzed, grouped, and enriched with production-ready fixes without changing the existing backend flow.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
          <input
            type="url"
            value={repoUrl}
            onChange={(event) => setRepoUrl(event.target.value)}
            placeholder="https://github.com/owner/repository"
            className="control min-h-[56px] px-5"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="button-primary min-h-[56px] px-6"
          >
            {loading ? "Starting analysis..." : "Run Analysis"}
          </button>
        </form>
      </div>
    </section>
  );
}
