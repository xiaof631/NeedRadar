import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
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
export type SourceType =
  | 'rss'
  | 'hacker_news'
  | 'github_issues'
  | 'reddit'
  | 'youtube'
  | 'freelance_marketplace';

export interface RssSource {
  id: number;
  name: string;
  url: string;
  category: string | null;
  frequency: number;
  source_type: SourceType;
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
  source_type?: SourceType;
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
  metadata: Record<string, unknown>;
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
  source_type?: SourceType;
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

export type CandidateNeedSourceType =
  | SourceType;

export interface MarketplaceLead {
  id: number;
  source_id: number;
  source_name: string;
  platform: string;
  title: string;
  summary: string | null;
  description: string | null;
  category: string | null;
  budget: string | null;
  normalized_budget: string | null;
  engagement: string | null;
  timeline: string | null;
  normalized_timeline: string | null;
  location: string | null;
  published_at: string | null;
  author: string | null;
  tags: string[];
  skills: string[];
  link: string | null;
  lead_kind: 'project' | 'contract_role' | 'full_time_job';
  lead_tier: 'high_purity' | 'expanded';
  tier_reason: string;
  lead_status: 'new' | 'watching' | 'contacted' | 'ignored';
  notes: string | null;
  duplicate_count: number;
  duplicate_sources: string[];
  created_at: string;
  updated_at: string;
}

export interface MarketplaceLeadSourceMetric {
  source_id: number;
  source_name: string;
  total: number;
  high_purity: number;
  expanded: number;
  reviewable: number;
  full_time_job: number;
  watching: number;
  contacted: number;
}

export interface MarketplaceLeadListResponse {
  total: number;
  tier_breakdown: Record<string, number>;
  kind_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  source_breakdown: MarketplaceLeadSourceMetric[];
  items: MarketplaceLead[];
}

export interface MarketplaceLeadQueryParams {
  skip?: number;
  limit?: number;
  source_id?: number;
  search?: string;
  tier?: 'high_purity' | 'expanded';
  lead_kind?: 'project' | 'contract_role' | 'full_time_job';
  reviewable_only?: boolean;
  lead_status?: 'new' | 'watching' | 'contacted' | 'ignored';
}

export async function fetchMarketplaceLeads(
  params: MarketplaceLeadQueryParams = {}
): Promise<MarketplaceLeadListResponse> {
  const response = await apiClient.get('/api/v1/marketplace-leads/', {
    params
  });
  return response.data;
}

export async function updateMarketplaceLeadStatus(
  leadId: number,
  status: MarketplaceLead['lead_status']
): Promise<MarketplaceLead> {
  const response = await apiClient.put(`/api/v1/marketplace-leads/${leadId}/status`, {
    status
  });
  return response.data;
}

export async function fetchMarketplaceLead(leadId: number): Promise<MarketplaceLead> {
  const response = await apiClient.get(`/api/v1/marketplace-leads/${leadId}`);
  return response.data;
}

export async function updateMarketplaceLeadNotes(
  leadId: number,
  notes: string | null
): Promise<MarketplaceLead> {
  const response = await apiClient.put(`/api/v1/marketplace-leads/${leadId}/notes`, {
    notes
  });
  return response.data;
}

export type CandidateNeedType =
  | 'workflow_pain'
  | 'feature_gap'
  | 'tool_seeking'
  | 'bug_report'
  | 'market_signal';

export interface CandidateNeed {
  id: number;
  raw_entry_id: number;
  summary: string;
  problem_statement: string | null;
  target_users: string | null;
  value_proposition: string | null;
  competition: string | null;
  candidate_type: CandidateNeedType | null;
  review_readiness: number | null;
  review_explanation: string | null;
  review_signals: string[];
  confidence: number | null;
  rule_score: number | null;
  status: CandidateNeedStatus;
  notes: string | null;
  synced_at: string | null;
  sync_error: string | null;
  source_name: string | null;
  source_type: CandidateNeedSourceType | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateNeedListResponse {
  total: number;
  items: CandidateNeed[];
}

export interface CandidateNeedCluster {
  cluster_id: string;
  representative_need_id: number;
  representative_summary: string;
  representative_problem_statement: string | null;
  signal_count: number;
  source_count: number;
  cross_source: boolean;
  source_names: string[];
  source_types: string[];
  need_ids: number[];
  statuses: CandidateNeedStatus[];
  avg_confidence: number | null;
  avg_rule_score: number | null;
  complaint_signal_count: number;
  alternative_request_count: number;
  reddit_comment_count: number;
  priority_score: number;
  latest_seen_at: string;
}

export interface CandidateNeedClusterListResponse {
  total: number;
  items: CandidateNeedCluster[];
}

export interface CandidateNeedQueryParams {
  skip?: number;
  limit?: number;
  statuses?: CandidateNeedStatus[];
  search?: string;
  source_type?: CandidateNeedSourceType;
  candidate_type?: CandidateNeedType;
  review_ready_only?: boolean;
  min_review_readiness?: number;
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

export async function fetchCandidateNeed(needId: number): Promise<CandidateNeed> {
  const response = await apiClient.get(`/api/v1/candidate-needs/${needId}`);
  return response.data;
}

export async function updateCandidateNeedStatus(
  needId: number,
  status: CandidateNeedStatus
): Promise<CandidateNeed> {
  const response = await apiClient.put(`/api/v1/candidate-needs/${needId}/status`, {
    status
  });
  return response.data;
}

export async function fetchCandidateNeedClusters(
  params: CandidateNeedQueryParams & {
    min_cluster_size?: number;
    similarity_threshold?: number;
  } = {}
): Promise<CandidateNeedClusterListResponse> {
  const searchParams = buildCandidateNeedParams(params);
  if (typeof params.min_cluster_size === 'number') {
    searchParams.set('min_cluster_size', String(params.min_cluster_size));
  }
  if (typeof params.similarity_threshold === 'number') {
    searchParams.set('similarity_threshold', String(params.similarity_threshold));
  }
  const response = await apiClient.get('/api/v1/candidate-needs/clusters', {
    params: searchParams
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
  source_type?: CandidateNeedSourceType;
  candidate_type?: CandidateNeedType;
  review_ready_only?: boolean;
  min_review_readiness?: number;
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
  if (params.source_type) {
    searchParams.set('source_type', params.source_type);
  }
  if (params.candidate_type) {
    searchParams.set('candidate_type', params.candidate_type);
  }
  if (params.statuses) {
    params.statuses.forEach((status) => searchParams.append('statuses', status));
  }
  if (typeof params.review_ready_only === 'boolean') {
    searchParams.set('review_ready_only', String(params.review_ready_only));
  }
  if (typeof params.min_review_readiness === 'number') {
    searchParams.set('min_review_readiness', String(params.min_review_readiness));
  }
  if (typeof params.synced === 'boolean') {
    searchParams.set('synced', String(params.synced));
  }
  return searchParams;
}

export default apiClient;
