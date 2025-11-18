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
    <FilterPanel
      :title="t('alertsPage.filters.title')"
      :description="t('alertsPage.filters.description')"
      :active-filters="activeFilters"
      :active-text="t('alertsPage.filters.activeLabel')"
      clearable
      :clear-text="t('alertsPage.filters.clear')"
      collapsible
      :collapse-text="t('alertsPage.filters.collapse')"
      :expand-text="t('alertsPage.filters.expand')"
      @clear="resetFilters"
    >
      <div class="filter-row">
        <label>{{ t('alertsPage.filters.channel') }}</label>
        <el-select v-model="channelFilter" size="small" class="channel-select">
          <el-option
            v-for="option in channelOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </div>
    </FilterPanel>
    <SyncChannelBreakdownCard
      :title="t('alertsPage.syncStats.title')"
      :description="t('alertsPage.syncStats.subtitle')"
      :stats="channelStats"
      :loading="syncStatsQuery.isFetching.value"
      :empty-text="t('alertsPage.syncStats.empty')"
      :selected-channel="channelFilter"
      @select="handleChannelSelect"
    >
      <template #actions>
        <el-button text size="small" @click="syncStatsQuery.refetch()" :loading="syncStatsQuery.isFetching.value">
          {{ t('actions.refresh') }}
        </el-button>
      </template>
    </SyncChannelBreakdownCard>
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
    <OperationLogCard
      :title="t('alertsPage.syncLogs.title')"
      :description="t('alertsPage.syncLogs.subtitle')"
      :logs="operationLogs"
      :loading="syncLogsQuery.isFetching.value"
      :empty-text="t('alertsPage.syncLogs.empty')"
      :status-labels="statusLabels"
    >
      <template #actions>
        <el-button text size="small" @click="syncLogsQuery.refetch()" :loading="syncLogsQuery.isFetching.value">
          {{ t('actions.refresh') }}
        </el-button>
      </template>
    </OperationLogCard>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { useI18n } from 'vue-i18n';
import FilterPanel from '../components/common/FilterPanel.vue';
import SyncChannelBreakdownCard from '../components/analytics/SyncChannelBreakdownCard.vue';
import {
  fetchFetchLogs,
  fetchSyncChannelStats,
  fetchSyncLogs,
  type FetchLog,
  type SyncLog,
  type SyncChannel,
  type SyncChannelStat,
  type SyncLogQueryParams,
} from '../services/api';
import OperationLogCard, {
  type OperationLogEntry,
  type OperationLogMetadata,
  type OperationLogStatus,
} from '../components/common/OperationLogCard.vue';

const { t } = useI18n();

type ChannelFilter = SyncChannel | 'all';
const CHANNEL_STORAGE_KEY = 'needradar-alerts-channel-filter';

const loadChannelFilter = (): ChannelFilter => {
  if (typeof window === 'undefined') return 'all';
  const stored = window.localStorage.getItem(CHANNEL_STORAGE_KEY);
  if (stored === 'webhook' || stored === 'mq' || stored === 'export' || stored === 'file_drop') {
    return stored;
  }
  return 'all';
};

const channelFilter = ref<ChannelFilter>(loadChannelFilter());

watch(
  channelFilter,
  (value) => {
    if (typeof window === 'undefined') return;
    if (value === 'all') {
      window.localStorage.removeItem(CHANNEL_STORAGE_KEY);
    } else {
      window.localStorage.setItem(CHANNEL_STORAGE_KEY, value);
    }
  },
  { immediate: true },
);

const channelOptions = computed(() => [
  { label: t('alertsPage.filters.options.all'), value: 'all' },
  { label: t('alertsPage.syncLogs.channels.webhook'), value: 'webhook' },
  { label: t('alertsPage.syncLogs.channels.mq'), value: 'mq' },
  { label: t('alertsPage.syncLogs.channels.export'), value: 'export' },
  { label: t('alertsPage.syncLogs.channels.file'), value: 'file_drop' },
]);

const fetchLogsQuery = useQuery({
  queryKey: ['fetch-logs'],
  queryFn: () => fetchFetchLogs({ limit: 20 }),
  staleTime: 30_000
});

const syncLogParams = computed<SyncLogQueryParams>(() => ({
  limit: 25,
  channel: channelFilter.value === 'all' ? undefined : channelFilter.value,
}));

const syncLogsQuery = useQuery({
  queryKey: computed(() => ['sync-logs', syncLogParams.value]),
  queryFn: () => fetchSyncLogs(syncLogParams.value),
  staleTime: 30_000,
});

const syncStatsQuery = useQuery({
  queryKey: ['sync-channel-stats'],
  queryFn: () => fetchSyncChannelStats({ limit: 150 }),
  staleTime: 60_000,
});

const fetchLogs = computed<FetchLog[]>(() => fetchLogsQuery.data.value?.items ?? []);
const syncLogs = computed<SyncLog[]>(() => syncLogsQuery.data.value?.items ?? []);
const channelStats = computed<SyncChannelStat[]>(() => syncStatsQuery.data.value ?? []);
const isFetching = computed(
  () =>
    fetchLogsQuery.isFetching.value ||
    syncLogsQuery.isFetching.value ||
    syncStatsQuery.isFetching.value,
);
const activeFilters = computed(() => (channelFilter.value === 'all' ? 0 : 1));

const refresh = () => {
  fetchLogsQuery.refetch();
  syncLogsQuery.refetch();
  syncStatsQuery.refetch();
};

const formatDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

const fetchStatusLabel = (status: FetchLog['status']) =>
  status === 'success' ? t('alertsPage.fetchLogs.status.success') : t('alertsPage.fetchLogs.status.failure');

const syncChannelLabel = (channel: SyncChannel) => {
  switch (channel) {
    case 'mq':
      return t('alertsPage.syncLogs.channels.mq');
    case 'export':
      return t('alertsPage.syncLogs.channels.export');
    case 'file_drop':
      return t('alertsPage.syncLogs.channels.file');
    default:
      return t('alertsPage.syncLogs.channels.webhook');
  }
};

const statusLabels = computed(() => ({
  success: t('components.operationLog.status.success'),
  warning: t('components.operationLog.status.warning'),
  danger: t('components.operationLog.status.danger'),
  info: t('components.operationLog.status.info'),
}));

const operationLogs = computed<OperationLogEntry[]>(() =>
  syncLogs.value.map((log) => ({
    id: log.id,
    title: `#${log.need_id} · ${syncChannelLabel(log.channel)}`,
    description: log.message ?? undefined,
    status: mapLogStatus(log.status),
    timestamp: log.delivered_at,
    tags: [syncChannelLabel(log.channel), syncStatusLabel(log.status)],
    metadata: buildMetadata(log),
  }))
);

const mapLogStatus = (status: string): OperationLogStatus => {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'pending') return 'info';
  return 'warning';
};

const syncStatusLabel = (status: string) => {
  switch (status) {
    case 'success':
      return t('alertsPage.syncLogs.statusLabels.success');
    case 'failed':
      return t('alertsPage.syncLogs.statusLabels.failed');
    default:
      return t('alertsPage.syncLogs.statusLabels.pending');
  }
};

const buildMetadata = (log: SyncLog): OperationLogMetadata[] => {
  const metadata: OperationLogMetadata[] = [
    { label: t('alertsPage.syncLogs.metadata.attempt'), value: `#${log.attempt}` },
  ];
  const filePath = log.metadata?.file_path;
  if (filePath) {
    metadata.push({ label: t('alertsPage.syncLogs.metadata.file'), value: String(filePath) });
  }
  const statusCode = log.metadata?.status_code;
  if (statusCode) {
    metadata.push({ label: t('alertsPage.syncLogs.metadata.http'), value: String(statusCode) });
  }
  return metadata;
};

const handleChannelSelect = (value: SyncChannel | 'all') => {
  channelFilter.value = value;
};

const resetFilters = () => {
  channelFilter.value = 'all';
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

.filter-row {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.filter-row label {
  font-weight: 500;
  width: 120px;
}

.channel-select {
  max-width: 240px;
}

</style>
