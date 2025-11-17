import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000
});

export interface DashboardMetrics {
  active_sources: number;
  entries_today: number;
  candidate_needs: number;
  open_alerts: number;
}

export interface AlertItem {
  id: string;
  title: string;
  severity: 'info' | 'warning' | 'critical';
  created_at: string;
}

export async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
  const response = await apiClient.get('/api/v1/dashboard');
  return response.data;
}

export async function fetchRecentAlerts(): Promise<AlertItem[]> {
  const response = await apiClient.get('/api/v1/alerts');
  return response.data.items;
}

export type CandidateNeedStatus =
  | 'pending_review'
  | 'approved'
  | 'rejected'
  | 'in_discovery'
  | 'completed';

export interface CandidateNeed {
  id: number;
  raw_entry_id: number;
  summary: string;
  problem_statement: string | null;
  target_users: string | null;
  value_proposition: string | null;
  competition: string | null;
  confidence: number | null;
  rule_score: number | null;
  status: CandidateNeedStatus;
  notes: string | null;
  synced_at: string | null;
  sync_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateNeedListResponse {
  total: number;
  items: CandidateNeed[];
}

export interface CandidateNeedQueryParams {
  skip?: number;
  limit?: number;
  statuses?: CandidateNeedStatus[];
  search?: string;
  synced?: boolean;
}

export async function fetchCandidateNeeds(
  params: CandidateNeedQueryParams = {}
): Promise<CandidateNeedListResponse> {
  const response = await apiClient.get('/api/v1/candidate-needs', {
    params: buildCandidateNeedParams(params)
  });
  return response.data;
}

export type ExportJobStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface CandidateNeedExportJob {
  id: number;
  job_type: string;
  format: 'json' | 'csv';
  status: ExportJobStatus;
  filters: Record<string, unknown>;
  record_count: number | null;
  file_path: string | null;
  error_message: string | null;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface CandidateNeedExportJobListResponse {
  total: number;
  items: CandidateNeedExportJob[];
}

export interface CandidateNeedExportJobPayload {
  format: 'json' | 'csv';
  statuses?: CandidateNeedStatus[];
  search?: string;
  raw_entry_id?: number;
  synced?: boolean;
  limit?: number;
}

export async function createCandidateNeedExportJob(
  payload: CandidateNeedExportJobPayload
): Promise<CandidateNeedExportJob> {
  const response = await apiClient.post('/api/v1/candidate-needs/export-tasks', payload);
  return response.data;
}

export async function fetchCandidateNeedExportJobs(params?: {
  status?: ExportJobStatus;
  limit?: number;
}): Promise<CandidateNeedExportJobListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) {
    searchParams.set('status', params.status);
  }
  if (params?.limit) {
    searchParams.set('limit', String(params.limit));
  }
  const response = await apiClient.get('/api/v1/candidate-needs/export-tasks', {
    params: searchParams
  });
  return response.data;
}

function buildCandidateNeedParams(params: CandidateNeedQueryParams): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (typeof params.skip === 'number') {
    searchParams.set('skip', String(params.skip));
  }
  if (typeof params.limit === 'number') {
    searchParams.set('limit', String(params.limit));
  }
  if (params.search) {
    searchParams.set('search', params.search);
  }
  if (params.statuses) {
    params.statuses.forEach((status) => searchParams.append('statuses', status));
  }
  if (typeof params.synced === 'boolean') {
    searchParams.set('synced', String(params.synced));
  }
  return searchParams;
}

export default apiClient;
