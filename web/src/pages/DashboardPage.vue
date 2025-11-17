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
      <StatCard :label="t('dashboard.metrics.sources')" :value="metrics.value.active_sources" />
      <StatCard :label="t('dashboard.metrics.entries')" :value="metrics.value.entries_today" />
      <StatCard :label="t('dashboard.metrics.candidates')" :value="metrics.value.candidate_needs" />
      <StatCard :label="t('dashboard.metrics.alerts')" :value="metrics.value.open_alerts" />
    </div>
    <el-row :gutter="20" class="panels">
      <el-col :span="12">
        <DataTable :rows="recentAlerts" :title="t('dashboard.recentAlerts')">
          <template #default>
            <el-table-column prop="title" label="描述" />
            <el-table-column prop="severity" label="级别" />
            <el-table-column prop="created_at" label="时间" />
          </template>
        </DataTable>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="title">队列健康状态</div>
          </template>
          <el-timeline>
            <el-timeline-item v-for="alert in recentAlerts" :key="alert.id" :type="mapType(alert.severity)" :timestamp="alert.created_at">
              {{ alert.title }}
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

const metrics = useQuery({
  queryKey: ['dashboard-metrics'],
  queryFn: fetchDashboardMetrics,
  retry: false,
  staleTime: 30_000,
  initialData: {
    active_sources: 0,
    entries_today: 0,
    candidate_needs: 0,
    open_alerts: 0
  }
});

const alerts = useQuery({
  queryKey: ['recent-alerts'],
  queryFn: fetchRecentAlerts,
  retry: false,
  staleTime: 30_000,
  initialData: [] as AlertItem[]
});

const recentAlerts = computed(() => alerts.data.value ?? []);
const isFetching = computed(() => metrics.isFetching.value || alerts.isFetching.value);
const refetch = () => {
  metrics.refetch();
  alerts.refetch();
};

const formattedDate = computed(() => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'full', timeStyle: 'short' }).format(new Date()));

const mapType = (severity: AlertItem['severity']) => {
  if (severity === 'critical') return 'danger';
  if (severity === 'warning') return 'warning';
  return 'info';
};
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
