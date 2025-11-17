<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('sources.title') }}</h1>
        <p>{{ t('sources.subtitle') }}</p>
      </div>
      <div class="actions">
        <el-button>{{ t('actions.create') }}</el-button>
        <el-button type="primary" @click="handleRefresh" :loading="sourcesQuery.isFetching.value">
          {{ t('actions.refresh') }}
        </el-button>
      </div>
    </header>
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ t('sources.table.title') }}</span>
          <el-input
            v-model="search"
            class="search-input"
            :placeholder="t('sources.filters.searchPlaceholder')"
            clearable
          />
        </div>
      </template>
      <el-table :data="sources" v-loading="sourcesQuery.isFetching.value" :empty-text="t('sources.table.empty')">
        <el-table-column prop="name" :label="t('sources.table.name')" min-width="200" />
        <el-table-column prop="category" :label="t('sources.table.category')" min-width="160">
          <template #default="{ row }">{{ row.category ?? '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('sources.table.frequency')" width="160">
          <template #default="{ row }">{{ formatFrequency(row.frequency) }}</template>
        </el-table-column>
        <el-table-column :label="t('sources.table.status')" width="140">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ sourceStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('sources.table.lastFetched')" min-width="200">
          <template #default="{ row }">{{ formatDate(row.last_fetched_at) }}</template>
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
import { fetchRssSources, type RssSourceQueryParams, type SourceStatus } from '../services/api';

const { t } = useI18n();
const pageSize = 10;
const page = ref(1);
const search = ref('');

const queryParams = computed<RssSourceQueryParams>(() => ({
  skip: (page.value - 1) * pageSize,
  limit: pageSize,
  search: search.value.trim() || undefined
}));

const sourcesQuery = useQuery({
  queryKey: computed(() => ['rss-sources', queryParams.value]),
  queryFn: () => fetchRssSources(queryParams.value),
  keepPreviousData: true,
  staleTime: 30_000
});

const sources = computed(() => sourcesQuery.data.value?.items ?? []);
const total = computed(() => sourcesQuery.data.value?.total ?? 0);

const handlePageChange = (value: number) => {
  page.value = value;
};

const handleRefresh = () => {
  sourcesQuery.refetch();
};

const formatDate = (value: string | null) => {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value));
};

const formatFrequency = (seconds: number) => {
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)} min`;
  }
  return `${Math.round(seconds / 3600)} h`;
};

const statusType = (status: SourceStatus) => {
  if (status === 'active') return 'success';
  if (status === 'paused') return 'warning';
  return 'info';
};

const sourceStatusLabel = (status: SourceStatus) => {
  if (status === 'active') return t('sources.status.active');
  if (status === 'paused') return t('sources.status.paused');
  return t('sources.status.disabled');
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
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-input {
  width: 240px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}
</style>
