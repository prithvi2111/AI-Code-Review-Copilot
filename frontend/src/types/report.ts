export type RunStatus = "queued" | "running" | "completed" | "failed";
export type Severity = "Critical" | "High" | "Medium" | "Low";
export type Category = "bug" | "security" | "code_smell" | "performance";
export type ImpactLevel = "critical" | "high" | "medium" | "low";
export type FixEffort = "low" | "medium" | "high";

export interface RepositorySummary {
  repo_url: string;
  repo_name: string;
  default_branch: string;
  languages: Record<string, number>;
  total_files: number;
  total_loc: number;
}

export interface Hotspot {
  file_path: string;
  issue_count: number;
  severity_distribution: Record<string, number>;
}

export interface SummaryMetrics {
  total_issues: number;
  severity_distribution: Record<string, number>;
  impact_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
  hotspots: Hotspot[];
  overall_risk_score: number;
  repository_health_score: number;
  total_groups: number;
}

export interface Finding {
  id: string;
  category: Category;
  severity: Severity;
  title: string;
  description: string;
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name?: string | null;
  symbol_type?: string | null;
  snippet: string;
  tool_source: string;
  rule_id: string;
  explanation: string;
  root_cause: string;
  suggestion: string;
  impact: string;
  impact_level: ImpactLevel;
  confidence: number;
  fix_effort: FixEffort;
  fix_patch: string;
}

export interface IssueCluster {
  cluster_id: string;
  type: string;
  count: number;
  reason: string;
  common_fix: string;
  impact_level: ImpactLevel;
  issue_ids: string[];
  affected_files: string[];
  affected_symbols: string[];
}

export interface AnalysisReport {
  repository: RepositorySummary;
  summary: SummaryMetrics;
  findings: Finding[];
  clusters: IssueCluster[];
}

export interface AnalysisStatusResponse {
  run_id: string;
  status: RunStatus;
  progress: string;
  error?: string | null;
  created_at: string;
  updated_at: string;
  repo?: RepositorySummary | null;
  summary?: SummaryMetrics | null;
}

export interface ApplyFixRequest {
  run_id: string;
  file_path: string;
  fix_patch: string;
  finding_id?: string;
  start_line?: number;
  end_line?: number;
}

export interface ApplyFixResponse {
  run_id: string;
  file_path: string;
  applied: boolean;
  message: string;
  start_line?: number | null;
  end_line?: number | null;
  backup_path?: string | null;
}

export interface BatchApplyFixRequest {
  run_id: string;
  finding_ids: string[];
}

export interface BatchApplyFixResponse {
  run_id: string;
  applied_count: number;
  skipped_count: number;
  modified_files: string[];
  applied_finding_ids: string[];
  skipped_finding_ids: string[];
  message: string;
}

export interface CreatePullRequestRequest {
  run_id: string;
  title?: string;
  body?: string;
}

export interface CreatePullRequestResponse {
  run_id: string;
  mode: "pull_request" | "patch";
  message: string;
  branch_name?: string | null;
  pr_url?: string | null;
  patch_path?: string | null;
  modified_files: string[];
}
