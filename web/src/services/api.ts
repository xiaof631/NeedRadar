import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000
});

export interface SourcesSummary {
  total: number;
  active: number;
}

export interface StatusBreakdown {
  total: number;
  by_status: Record<string, number>;
}

export interface FetchLogSummary {
  total: number;
  failures: number;
}

export interface DashboardMetrics {
  sources: SourcesSummary;
  raw_entries: StatusBreakdown;
  candidate_needs: StatusBreakdown;
  pending_sync_needs: number;
  fetch_logs: FetchLogSummary;
}

export interface AlertItem {
  code: string;
  message: string;
  severity: 'info' | 'warning' | 'critical';
  details: Record<string, unknown>;
}

export async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
  const response = await apiClient.get('/api/v1/dashboard/metrics');
  return response.data;
}

export async function fetchRecentAlerts(): Promise<AlertItem[]> {
  const response = await apiClient.get('/api/v1/dashboard/alerts');
  return response.data;
}

export type SourceStatus = 'active' | 'paused' | 'disabled';

export interface RssSource {
  id: number;
  name: string;
  url: string;
  category: string | null;
  frequency: number;
  status: SourceStatus;
  last_fetched_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RssSourceListResponse {
  total: number;
  items: RssSource[];
}

export interface RssSourceQueryParams {
  skip?: number;
  limit?: number;
  status?: SourceStatus;
  category?: string;
  search?: string;
}

export async function fetchRssSources(
  params: RssSourceQueryParams = {}
): Promise<RssSourceListResponse> {
  const response = await apiClient.get('/api/v1/rss-sources/', {
    params
  });
  return response.data;
}

export type RawEntryStatus = 'pending' | 'filtered' | 'promoted' | 'ignored';

export interface RawEntry {
  id: number;
  source_id: number;
  guid: string;
  content_hash: string | null;
  title: string;
  summary: string | null;
  content: string | null;
  link: string | null;
  published_at: string | null;
  author: string | null;
  tags: string[];
  status: RawEntryStatus;
  created_at: string;
  updated_at: string;
}

export interface RawEntryListResponse {
  total: number;
  items: RawEntry[];
}

export interface RawEntryQueryParams {
  skip?: number;
  limit?: number;
  source_id?: number;
  status?: RawEntryStatus;
  search?: string;
}

export async function fetchRawEntries(
  params: RawEntryQueryParams = {}
): Promise<RawEntryListResponse> {
  const response = await apiClient.get('/api/v1/raw-entries/', {
    params
  });
  return response.data;
}

export interface SourceFilterMetric {
  source_id: number;
  source_name: string;
  total_entries: number;
  pending_entries: number;
  filtered_entries: number;
  promoted_entries: number;
  ignored_entries: number;
  promotion_rate: number;
}

export interface FilterPerformance {
  total_entries: number;
  pending_entries: number;
  processed_entries: number;
  filtered_entries: number;
  promoted_entries: number;
  ignored_entries: number;
  promotion_rate: number;
  average_rule_score: number | null;
  source_breakdown: SourceFilterMetric[];
}

export async function fetchFilterMetrics(): Promise<FilterPerformance> {
  const response = await apiClient.get('/api/v1/filter-metrics');
  return response.data;
}

export type FetchStatus = 'success' | 'failure';

export interface FetchLog {
  id: number;
  source_id: number;
  fetched_at: string;
  status: FetchStatus;
  http_status: number | null;
  error_message: string | null;
}

export interface FetchLogListResponse {
  total: number;
  items: FetchLog[];
}

export interface FetchLogQueryParams {
  skip?: number;
  limit?: number;
  status?: FetchStatus;
}

export async function fetchFetchLogs(
  params: FetchLogQueryParams = {}
): Promise<FetchLogListResponse> {
  const response = await apiClient.get('/api/v1/fetch-logs/', {
    params
  });
  return response.data;
}

export type SyncChannel = 'webhook' | 'mq' | 'export' | 'file_drop';

export interface SyncLog {
  id: number;
  need_id: number;
  channel: SyncChannel;
  status: string;
  attempt: number;
  message: string | null;
  metadata: Record<string, unknown>;
  delivered_at: string;
}

export interface SyncLogListResponse {
  total: number;
  items: SyncLog[];
}

export interface SyncLogQueryParams {
  need_id?: number;
  channel?: SyncChannel;
  limit?: number;
}

export async function fetchSyncLogs(
  params: SyncLogQueryParams = {}
): Promise<SyncLogListResponse> {
  const response = await apiClient.get('/api/v1/candidate-needs/sync-logs', {
    params
  });
  return response.data;
}

export interface SyncChannelStat {
  channel: SyncChannel;
  total_attempts: number;
  success: number;
  failed: number;
  pending: number;
  success_rate: number;
  last_attempt_at: string | null;
  last_error: string | null;
}

export interface SyncChannelStatQuery {
  limit?: number;
}

export async function fetchSyncChannelStats(
  params: SyncChannelStatQuery = {}
): Promise<SyncChannelStat[]> {
  const response = await apiClient.get('/api/v1/candidate-needs/sync-stats', {
    params
  });
  return response.data;
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
