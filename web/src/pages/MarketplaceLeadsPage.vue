<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('marketplace.title') }}</h1>
        <p>{{ t('marketplace.subtitle') }}</p>
      </div>
      <div class="actions">
        <el-radio-group v-model="queueView" size="small">
          <el-radio-button label="high_purity">
            {{ t('marketplace.filters.queueOptions.high_purity') }}
          </el-radio-button>
          <el-radio-button label="expanded">
            {{ t('marketplace.filters.queueOptions.expanded') }}
          </el-radio-button>
          <el-radio-button label="all">
            {{ t('marketplace.filters.queueOptions.all') }}
          </el-radio-button>
        </el-radio-group>
        <el-input
          v-model="search"
          class="search-input"
          :placeholder="t('marketplace.filters.searchPlaceholder')"
          clearable
        />
        <el-select v-model="sourceId" class="source-select" :placeholder="t('marketplace.filters.source')">
          <el-option :label="t('marketplace.filters.sourceOptions.all')" value="all" />
          <el-option
            v-for="source in marketplaceSources"
            :key="source.id"
            :label="source.name"
            :value="String(source.id)"
          />
        </el-select>
        <el-button type="primary" @click="refetch" :loading="leadsQuery.isFetching.value">
          {{ t('actions.refresh') }}
        </el-button>
      </div>
    </header>

    <div class="summary-grid">
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.total') }}</div>
        <div class="metric-value">{{ total }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.highPurity') }}</div>
        <div class="metric-value">{{ highPurityCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.expanded') }}</div>
        <div class="metric-value">{{ expandedCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.activeSources') }}</div>
        <div class="metric-value">{{ activeSourceCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.pausedSources') }}</div>
        <div class="metric-value">{{ pausedSourceCount }}</div>
      </el-card>
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="source-health-title">{{ t('marketplace.sourceHealth.title') }}</div>
      </template>
      <div class="source-health-list">
        <div v-for="source in marketplaceSources" :key="source.id" class="source-health-item">
          <div class="source-health-main">
            <span class="source-health-name">{{ source.name }}</span>
            <el-tag size="small" :type="statusTagType(source.status)" effect="plain">
              {{ t(`sources.status.${source.status}`) }}
            </el-tag>
          </div>
          <div class="source-health-meta">
            {{ t('marketplace.sourceHealth.lastFetched') }}: {{ formatDate(source.last_fetched_at) }}
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="leads" v-loading="leadsQuery.isFetching.value" :empty-text="t('marketplace.table.empty')">
        <el-table-column prop="platform" :label="t('marketplace.table.platform')" width="170" />
        <el-table-column :label="t('marketplace.table.title')" min-width="320">
          <template #default="{ row }">
            <div class="title-cell">
              <a v-if="row.link" :href="row.link" class="lead-link" target="_blank" rel="noreferrer">
                {{ row.title }}
              </a>
              <span v-else>{{ row.title }}</span>
              <div v-if="row.summary" class="summary-text">{{ row.summary }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.budget')" width="170">
          <template #default="{ row }">{{ row.budget || '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.timeline')" width="190">
          <template #default="{ row }">{{ row.timeline || '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.skills')" min-width="220">
          <template #default="{ row }">
            <div class="tag-list">
              <el-tag v-for="skill in row.skills.slice(0, 4)" :key="skill" size="small" effect="plain">
                {{ skill }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.source')" min-width="180">
          <template #default="{ row }">{{ row.source_name }}</template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.queue')" width="160">
          <template #default="{ row }">
            <el-tag :type="row.lead_tier === 'high_purity' ? 'success' : 'warning'" effect="plain">
              {{ t(`marketplace.filters.queueOptions.${row.lead_tier}`) }}
            </el-tag>
            <div class="summary-text">{{ row.tier_reason }}</div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.published')" width="190">
          <template #default="{ row }">{{ formatDate(row.published_at || row.created_at) }}</template>
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
import { fetchMarketplaceLeads, fetchRssSources } from '../services/api';

const { t } = useI18n();
const pageSize = 15;
const page = ref(1);
const search = ref('');
const sourceId = ref<'all' | string>('all');
const queueView = ref<'high_purity' | 'expanded' | 'all'>('high_purity');

const sourcesQuery = useQuery({
  queryKey: ['marketplace-sources'],
  queryFn: () =>
    fetchRssSources({
      limit: 100,
      source_type: 'freelance_marketplace'
    }),
  staleTime: 60_000
});

const marketplaceSources = computed(() => sourcesQuery.data.value?.items ?? []);
const activeSourceCount = computed(
  () => marketplaceSources.value.filter((source) => source.status === 'active').length
);
const pausedSourceCount = computed(
  () => marketplaceSources.value.filter((source) => source.status === 'paused').length
);

const queryParams = computed(() => ({
  skip: (page.value - 1) * pageSize,
  limit: pageSize,
  search: search.value.trim() || undefined,
  source_id: sourceId.value === 'all' ? undefined : Number(sourceId.value),
  tier: queueView.value === 'all' ? undefined : queueView.value
}));

const leadsQuery = useQuery({
  queryKey: computed(() => ['marketplace-leads', queryParams.value]),
  queryFn: () => fetchMarketplaceLeads(queryParams.value),
  keepPreviousData: true,
  staleTime: 30_000
});

const leads = computed(() => leadsQuery.data.value?.items ?? []);
const total = computed(() => leadsQuery.data.value?.total ?? 0);
const highPurityCount = computed(() => leadsQuery.data.value?.tier_breakdown?.high_purity ?? 0);
const expandedCount = computed(() => leadsQuery.data.value?.tier_breakdown?.expanded ?? 0);

const handlePageChange = (value: number) => {
  page.value = value;
};

const refetch = () => {
  void leadsQuery.refetch();
  void sourcesQuery.refetch();
};

const statusTagType = (status: 'active' | 'paused' | 'disabled') => {
  if (status === 'active') return 'success';
  if (status === 'paused') return 'warning';
  return 'info';
};

const formatDate = (value: string | null) => {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value));
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
  gap: 1rem;
}

.actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.search-input {
  width: 280px;
}

.source-select {
  width: 220px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 220px));
  gap: 1rem;
}

.metric-label {
  font-size: 0.875rem;
  color: #64748b;
}

.metric-value {
  margin-top: 0.5rem;
  font-size: 1.75rem;
  font-weight: 700;
  color: #0f172a;
}

.title-cell {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.summary-text {
  margin-top: 0.35rem;
  font-size: 0.8125rem;
  line-height: 1.4;
  color: #64748b;
}

.source-health-title {
  font-weight: 600;
  color: #0f172a;
}

.source-health-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.75rem;
}

.source-health-item {
  padding: 0.9rem 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.85rem;
  background: #f8fafc;
}

.source-health-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

@media (max-width: 1080px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.source-health-name {
  font-weight: 600;
  color: #0f172a;
}

.source-health-meta {
  margin-top: 0.45rem;
  color: #64748b;
  font-size: 0.875rem;
}

.lead-link {
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
}

.lead-link:hover {
  text-decoration: underline;
}

.summary-text {
  color: #64748b;
  font-size: 0.875rem;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}

@media (max-width: 960px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .page-header,
  .actions {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input,
  .source-select {
    width: 100%;
  }
}
</style>
