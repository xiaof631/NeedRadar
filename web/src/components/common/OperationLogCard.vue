<template>
  <el-card class="operation-log-card" shadow="never">
    <template #header>
      <div class="card-header">
        <div>
          <h3>{{ title }}</h3>
          <p v-if="description">{{ description }}</p>
        </div>
        <slot name="actions" />
      </div>
    </template>
    <el-table :data="logs" :empty-text="emptyText" v-loading="loading" size="small">
      <el-table-column prop="title" min-width="200" :label="title">
        <template #default="{ row }">
          <div class="log-title">
            <strong>{{ row.title }}</strong>
            <p v-if="row.description">{{ row.description }}</p>
          </div>
        </template>
      </el-table-column>
      <el-table-column min-width="140" label="Status">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" effect="light">
            {{ statusLabels[row.status] ?? row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column min-width="180" label="Tags">
        <template #default="{ row }">
          <div class="tag-list">
            <el-tag v-for="tag in row.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column min-width="240" label="Metadata">
        <template #default="{ row }">
          <div class="metadata-list">
            <span v-for="item in row.metadata" :key="`${item.label}:${item.value}`">
              {{ item.label }}: {{ item.value }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column min-width="180" label="Time">
        <template #default="{ row }">{{ formatDate(row.timestamp) }}</template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
export type OperationLogStatus = 'success' | 'warning' | 'danger' | 'info';

export interface OperationLogMetadata {
  label: string;
  value: string;
}

export interface OperationLogEntry {
  id: number | string;
  title: string;
  description?: string;
  status: OperationLogStatus;
  timestamp: string;
  tags: string[];
  metadata: OperationLogMetadata[];
}

withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    logs?: OperationLogEntry[];
    loading?: boolean;
    emptyText?: string;
    statusLabels?: Partial<Record<OperationLogStatus, string>>;
  }>(),
  {
    title: '',
    description: '',
    logs: () => [],
    loading: false,
    emptyText: '',
    statusLabels: () => ({})
  }
);

const statusTag = (status: OperationLogStatus) => {
  switch (status) {
    case 'success':
      return 'success';
    case 'danger':
      return 'danger';
    case 'warning':
      return 'warning';
    default:
      return 'info';
  }
};

const formatDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value));
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.card-header h3 {
  margin: 0;
  font-size: 1rem;
}

.card-header p {
  margin: 0.25rem 0 0;
  color: var(--nr-muted);
}

.log-title {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.log-title p {
  margin: 0;
  color: var(--nr-muted);
}

.tag-list,
.metadata-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.metadata-list span {
  color: var(--nr-muted);
  font-size: 0.875rem;
}
</style>
