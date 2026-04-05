import {
  AnalysisReport,
  AnalysisStatusResponse,
  ApplyFixRequest,
  ApplyFixResponse,
  BatchApplyFixRequest,
  BatchApplyFixResponse,
  CreatePullRequestRequest,
  CreatePullRequestResponse,
} from "../types/report";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.detail ?? "Request failed.", response.status);
  }

  return response.json() as Promise<T>;
}

export function createAnalysis(repoUrl: string) {
  return request<{ run_id: string; status: "queued" }>("/api/analyses", {
    method: "POST",
    body: JSON.stringify({ repo_url: repoUrl }),
  });
}

export function getAnalysisStatus(runId: string) {
  return request<AnalysisStatusResponse>(`/api/analyses/${runId}`);
}

export function getAnalysisReport(runId: string) {
  return request<AnalysisReport>(`/api/analyses/${runId}/report`);
}

export function applyFix(payload: ApplyFixRequest) {
  return request<ApplyFixResponse>("/api/apply-fix", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createPullRequest(payload: CreatePullRequestRequest) {
  return request<CreatePullRequestResponse>("/api/create-pr", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function applyFixBatch(payload: BatchApplyFixRequest) {
  return request<BatchApplyFixResponse>("/api/apply-fixes/batch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
