<template>
  <el-card class="sync-channel-card" shadow="never">
    <template #header>
      <div class="card-header">
        <div>
          <h3>{{ title }}</h3>
          <p v-if="description">{{ description }}</p>
        </div>
        <slot name="actions" />
      </div>
    </template>
    <el-table
      :data="stats"
      :empty-text="emptyText"
      v-loading="loading"
      size="small"
      @row-click="handleRowClick"
    >
      <el-table-column :label="t('alertsPage.syncLogs.channels.title')" min-width="140">
        <template #default="{ row }">
          <el-tag
            :type="row.channel === selectedChannel ? 'primary' : 'info'"
            effect="light"
            round
          >
            {{ channelLabel(row.channel) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('alertsPage.syncStats.successRate')" min-width="120">
        <template #default="{ row }">
          <span class="stat-value">{{ formatRate(row.success_rate) }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('alertsPage.syncStats.results')" min-width="200">
        <template #default="{ row }">
          <div class="stat-pills">
            <span class="pill success">{{ t('alertsPage.syncStats.success') }} {{ row.success }}</span>
            <span class="pill danger">{{ t('alertsPage.syncStats.failed') }} {{ row.failed }}</span>
            <span class="pill muted">{{ t('alertsPage.syncStats.pending') }} {{ row.pending }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('alertsPage.syncStats.lastAttempt')" min-width="200">
        <template #default="{ row }">
          <div class="last-attempt">
            <span>{{ formatDate(row.last_attempt_at) }}</span>
            <span class="error" v-if="row.last_error">{{ row.last_error }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('alertsPage.syncStats.filter')" width="120">
        <template #default="{ row }">
          <el-button
            text
            size="small"
            type="primary"
            :disabled="row.total_attempts === 0 && selectedChannel === row.channel"
            @click.stop="emitSelect(row.channel)"
          >
            {{ selectedChannel === row.channel ? t('alertsPage.syncStats.viewAll') : t('alertsPage.syncStats.focus') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { SyncChannel, SyncChannelStat } from '../../services/api';

const props = withDefaults(
  defineProps<{
    stats: SyncChannelStat[];
    loading?: boolean;
    title?: string;
    description?: string;
    emptyText?: string;
    selectedChannel?: SyncChannel | 'all';
  }>(),
  {
    stats: () => [],
    loading: false,
    title: '',
    description: '',
    emptyText: '',
    selectedChannel: 'all'
  }
);

const emit = defineEmits<{
  (event: 'select', value: SyncChannel | 'all'): void;
}>();

const { t } = useI18n();

const channelLabel = (channel: SyncChannel) => {
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

const formatRate = (value: number) => `${Math.round((value || 0) * 100)}%`;

const formatDate = (value: string | null | undefined) => {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value));
};

const emitSelect = (channel: SyncChannel) => {
  if (props.selectedChannel === channel) {
    emit('select', 'all');
  } else {
    emit('select', channel);
  }
};

const handleRowClick = (row: SyncChannelStat) => {
  emitSelect(row.channel);
};
</script>

<style scoped>
.sync-channel-card {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  font-size: 1rem;
}

.card-header p {
  margin: 0.25rem 0 0;
  color: var(--nr-muted);
}

.stat-value {
  font-weight: 600;
}

.stat-pills {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.pill {
  padding: 0.15rem 0.65rem;
  border-radius: 999px;
  font-size: 0.8125rem;
  background: var(--nr-tag-bg);
}

.pill.success {
  color: #15803d;
}

.pill.danger {
  color: #b91c1c;
}

.pill.muted {
  color: var(--nr-muted);
}

.last-attempt {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.last-attempt .error {
  color: #b91c1c;
  font-size: 0.8125rem;
}
</style>
