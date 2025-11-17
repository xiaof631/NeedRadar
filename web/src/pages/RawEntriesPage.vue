<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('entries.title') }}</h1>
        <p>{{ t('entries.subtitle') }}</p>
      </div>
      <div class="actions">
        <el-input
          v-model="search"
          class="search-input"
          :placeholder="t('entries.filters.searchPlaceholder')"
          clearable
        />
        <el-select v-model="status" class="status-select" :placeholder="t('entries.filters.status')">
          <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-button type="primary" @click="refetch" :loading="entriesQuery.isFetching.value">
          {{ t('actions.refresh') }}
        </el-button>
      </div>
    </header>
    <el-card shadow="never">
      <el-table :data="entries" v-loading="entriesQuery.isFetching.value" :empty-text="t('entries.table.empty')">
        <el-table-column prop="title" :label="t('entries.table.title')" min-width="240" show-overflow-tooltip />
        <el-table-column prop="source_id" :label="t('entries.table.source')" width="140" />
        <el-table-column :label="t('entries.table.status')" width="140">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('entries.table.published')" min-width="200">
          <template #default="{ row }">{{ formatDate(row.published_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('entries.table.ingested')" min-width="200">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <div class="pagination-row">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { useI18n } from 'vue-i18n';
import { fetchRawEntries, type RawEntryQueryParams, type RawEntryStatus } from '../services/api';

const { t } = useI18n();
const pageSize = 15;
const page = ref(1);
const search = ref('');
const status = ref<'all' | RawEntryStatus>('all');

const statusOptions = computed(() => [
  { label: t('entries.filters.statusOptions.all'), value: 'all' },
  { label: t('entries.status.pending'), value: 'pending' },
  { label: t('entries.status.filtered'), value: 'filtered' },
  { label: t('entries.status.promoted'), value: 'promoted' },
  { label: t('entries.status.ignored'), value: 'ignored' }
]);

const queryParams = computed<RawEntryQueryParams>(() => ({
  skip: (page.value - 1) * pageSize,
  limit: pageSize,
  search: search.value.trim() || undefined,
  status: status.value === 'all' ? undefined : status.value
}));

const entriesQuery = useQuery({
  queryKey: computed(() => ['raw-entries', queryParams.value]),
  queryFn: () => fetchRawEntries(queryParams.value),
  keepPreviousData: true,
  staleTime: 30_000
});

const entries = computed(() => entriesQuery.data.value?.items ?? []);
const total = computed(() => entriesQuery.data.value?.total ?? 0);

const handlePageChange = (value: number) => {
  page.value = value;
};

const refetch = () => {
  entriesQuery.refetch();
};

const formatDate = (value: string | null) => {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value));
};

const statusLabel = (value: RawEntryStatus) => {
  switch (value) {
    case 'filtered':
      return t('entries.status.filtered');
    case 'promoted':
      return t('entries.status.promoted');
    case 'ignored':
      return t('entries.status.ignored');
    default:
      return t('entries.status.pending');
  }
};

const statusTag = (value: RawEntryStatus) => {
  switch (value) {
    case 'promoted':
      return 'success';
    case 'filtered':
      return 'warning';
    case 'ignored':
      return 'info';
    default:
      return 'primary';
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

.actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.search-input {
  width: 240px;
}

.status-select {
  width: 200px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}
</style>
