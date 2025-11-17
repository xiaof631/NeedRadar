<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('dashboard.welcome') }}</h1>
        <p class="subtitle">{{ formattedDate }}</p>
      </div>
      <el-button @click="refetch" :loading="isFetching" type="primary">
        {{ t('actions.refresh') }}
      </el-button>
    </header>
    <div class="stats-grid">
      <StatCard :label="t('dashboard.metrics.sources')" :value="sourcesCard" />
      <StatCard :label="t('dashboard.metrics.rawEntries')" :value="dashboardMetrics?.raw_entries.total ?? 0" />
      <StatCard :label="t('dashboard.metrics.candidates')" :value="dashboardMetrics?.candidate_needs.total ?? 0" />
      <StatCard :label="t('dashboard.metrics.pendingSync')" :value="dashboardMetrics?.pending_sync_needs ?? 0" />
    </div>
    <el-row :gutter="20" class="panels">
      <el-col :span="12">
        <DataTable :rows="recentAlerts" :title="t('dashboard.recentAlerts')">
          <template #default>
            <el-table-column prop="code" :label="t('dashboard.alertColumns.code')" width="160" />
            <el-table-column prop="message" :label="t('dashboard.alertColumns.message')" min-width="220" />
            <el-table-column :label="t('dashboard.alertColumns.severity')" width="140">
              <template #default="{ row }">
                <el-tag :type="mapType(row.severity)">
                  {{ alertSeverityLabel(row.severity) }}
                </el-tag>
              </template>
            </el-table-column>
          </template>
        </DataTable>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="title">{{ t('dashboard.timelineTitle') }}</div>
            <p class="subtitle">
              {{
                t('dashboard.fetchSummary', {
                  total: dashboardMetrics?.fetch_logs.total ?? 0,
                  failures: dashboardMetrics?.fetch_logs.failures ?? 0
                })
              }}
            </p>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="alert in recentAlerts"
              :key="alert.code"
              :type="mapType(alert.severity)"
              :timestamp="alert.details?.created_at ?? ''"
            >
              {{ alert.message }}
            </el-timeline-item>
            <el-timeline-item v-if="recentAlerts.length === 0">
              {{ t('dashboard.empty') }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { useI18n } from 'vue-i18n';
import StatCard from '../components/common/StatCard.vue';
import DataTable from '../components/common/DataTable.vue';
import { fetchDashboardMetrics, fetchRecentAlerts, type AlertItem } from '../services/api';

const { t } = useI18n();

const metricsQuery = useQuery({
  queryKey: ['dashboard-metrics'],
  queryFn: fetchDashboardMetrics,
  retry: false,
  staleTime: 30_000,
  initialData: {
    sources: { total: 0, active: 0 },
    raw_entries: { total: 0, by_status: {} },
    candidate_needs: { total: 0, by_status: {} },
    pending_sync_needs: 0,
    fetch_logs: { total: 0, failures: 0 }
  }
});

const alertsQuery = useQuery({
  queryKey: ['recent-alerts'],
  queryFn: fetchRecentAlerts,
  retry: false,
  staleTime: 30_000,
  initialData: [] as AlertItem[]
});

const dashboardMetrics = computed(() => metricsQuery.data.value);
const recentAlerts = computed(() => alertsQuery.data.value ?? []);
const isFetching = computed(
  () => metricsQuery.isFetching.value || alertsQuery.isFetching.value
);
const refetch = () => {
  metricsQuery.refetch();
  alertsQuery.refetch();
};

const formattedDate = computed(() => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'full', timeStyle: 'short' }).format(new Date()));

const mapType = (severity: AlertItem['severity']) => {
  if (severity === 'critical') return 'danger';
  if (severity === 'warning') return 'warning';
  return 'info';
};

const alertSeverityLabel = (severity: AlertItem['severity']) => {
  if (severity === 'critical') return t('dashboard.severity.critical');
  if (severity === 'warning') return t('dashboard.severity.warning');
  return t('dashboard.severity.info');
};

const sourcesCard = computed(() => {
  const sourceData = dashboardMetrics.value?.sources;
  if (!sourceData) return '0/0';
  return `${sourceData.active}/${sourceData.total}`;
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.subtitle {
  color: #6b7280;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
}

.panels {
  margin-top: 1rem;
}

.title {
  font-weight: 600;
}
</style>
