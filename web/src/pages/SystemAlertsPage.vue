<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('alertsPage.title') }}</h1>
        <p>{{ t('alertsPage.subtitle') }}</p>
      </div>
      <el-button type="primary" @click="refresh" :loading="isFetching">
        {{ t('actions.refresh') }}
      </el-button>
    </header>
    <el-card shadow="never">
      <template #header>
        <div class="card-header">{{ t('alertsPage.fetchLogs.title') }}</div>
      </template>
      <el-table :data="fetchLogs" :empty-text="t('alertsPage.fetchLogs.empty')" v-loading="fetchLogsQuery.isFetching.value">
        <el-table-column prop="source_id" :label="t('alertsPage.fetchLogs.columns.source')" width="140" />
        <el-table-column :label="t('alertsPage.fetchLogs.columns.status')" width="140">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'">{{ fetchStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="http_status" :label="t('alertsPage.fetchLogs.columns.http')" width="140">
          <template #default="{ row }">{{ row.http_status ?? '—' }}</template>
        </el-table-column>
        <el-table-column prop="error_message" :label="t('alertsPage.fetchLogs.columns.message')" min-width="220">
          <template #default="{ row }">{{ row.error_message ?? '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('alertsPage.fetchLogs.columns.time')" min-width="200">
          <template #default="{ row }">{{ formatDate(row.fetched_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-card shadow="never">
      <template #header>
        <div class="card-header">{{ t('alertsPage.syncLogs.title') }}</div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="log in syncLogs"
          :key="log.id"
          :type="syncLogType(log.status)"
          :timestamp="formatDate(log.delivered_at)"
        >
          <div class="log-row">
            <strong>#{{ log.need_id }}</strong>
            <span>{{ syncChannelLabel(log.channel) }} · {{ log.status }}</span>
            <span v-if="log.message">— {{ log.message }}</span>
          </div>
        </el-timeline-item>
        <el-timeline-item v-if="syncLogs.length === 0">
          {{ t('alertsPage.syncLogs.empty') }}
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { useI18n } from 'vue-i18n';
import { fetchFetchLogs, fetchSyncLogs, type FetchLog, type SyncLog, type SyncChannel } from '../services/api';

const { t } = useI18n();

const fetchLogsQuery = useQuery({
  queryKey: ['fetch-logs'],
  queryFn: () => fetchFetchLogs({ limit: 20 }),
  staleTime: 30_000
});

const syncLogsQuery = useQuery({
  queryKey: ['sync-logs'],
  queryFn: () => fetchSyncLogs({ limit: 25 }),
  staleTime: 30_000
});

const fetchLogs = computed<FetchLog[]>(() => fetchLogsQuery.data.value?.items ?? []);
const syncLogs = computed<SyncLog[]>(() => syncLogsQuery.data.value?.items ?? []);
const isFetching = computed(() => fetchLogsQuery.isFetching.value || syncLogsQuery.isFetching.value);

const refresh = () => {
  fetchLogsQuery.refetch();
  syncLogsQuery.refetch();
};

const formatDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

const fetchStatusLabel = (status: FetchLog['status']) =>
  status === 'success' ? t('alertsPage.fetchLogs.status.success') : t('alertsPage.fetchLogs.status.failure');

const syncLogType = (status: string) => (status === 'success' ? 'success' : status === 'failed' ? 'danger' : 'warning');

const syncChannelLabel = (channel: SyncChannel) => {
  switch (channel) {
    case 'mq':
      return t('alertsPage.syncLogs.channels.mq');
    case 'export':
      return t('alertsPage.syncLogs.channels.export');
    default:
      return t('alertsPage.syncLogs.channels.webhook');
  }
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

.card-header {
  font-weight: 600;
}

.log-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
</style>
