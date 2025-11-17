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

export default apiClient;
