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
        <el-select v-model="leadKindView" class="kind-select" :placeholder="t('marketplace.filters.leadKind')">
          <el-option :label="t('marketplace.filters.leadKindOptions.reviewable')" value="reviewable" />
          <el-option :label="t('marketplace.filters.leadKindOptions.project')" value="project" />
          <el-option :label="t('marketplace.filters.leadKindOptions.contract_role')" value="contract_role" />
          <el-option :label="t('marketplace.filters.leadKindOptions.full_time_job')" value="full_time_job" />
          <el-option :label="t('marketplace.filters.leadKindOptions.all')" value="all" />
        </el-select>
        <el-input
          v-model="search"
          class="search-input"
          :placeholder="t('marketplace.filters.searchPlaceholder')"
          clearable
        />
        <el-select v-model="statusFilter" class="status-select" :placeholder="t('marketplace.filters.status')">
          <el-option :label="t('marketplace.filters.statusOptions.all')" value="all" />
          <el-option
            v-for="option in leadStatusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
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
        <div class="metric-label">{{ t('marketplace.metrics.reviewable') }}</div>
        <div class="metric-value">{{ reviewableCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.expanded') }}</div>
        <div class="metric-value">{{ expandedCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.fullTimeJobs') }}</div>
        <div class="metric-value">{{ fullTimeJobCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.watching') }}</div>
        <div class="metric-value">{{ watchingCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.contacted') }}</div>
        <div class="metric-value">{{ contactedCount }}</div>
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
            <el-tag size="small" :type="sourceStatusTagType(source.status)" effect="plain">
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
        <el-table-column :label="t('marketplace.table.title')" min-width="340">
          <template #default="{ row }">
            <div class="title-cell">
              <a v-if="row.link" :href="row.link" class="lead-link" target="_blank" rel="noreferrer">
                {{ row.title }}
              </a>
              <span v-else>{{ row.title }}</span>
              <div class="tag-list">
                <el-tag
                  v-if="row.duplicate_count > 1"
                  size="small"
                  type="info"
                  effect="plain"
                >
                  {{ t('marketplace.table.duplicates', { count: row.duplicate_count }) }}
                </el-tag>
                <el-tag
                  v-if="row.link"
                  size="small"
                  type="success"
                  effect="plain"
                >
                  {{ t('marketplace.table.hasLink') }}
                </el-tag>
              </div>
              <div v-if="row.summary" class="summary-text">{{ row.summary }}</div>
              <div v-if="row.duplicate_count > 1" class="summary-text">
                {{ row.duplicate_sources.join(' / ') }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.budget')" width="180">
          <template #default="{ row }">
            <div>{{ row.normalized_budget || row.budget || '—' }}</div>
            <div v-if="row.normalized_budget && row.budget && row.normalized_budget !== row.budget" class="summary-text">
              {{ row.budget }}
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.timeline')" width="190">
          <template #default="{ row }">
            <div>{{ row.normalized_timeline || row.timeline || '—' }}</div>
            <div
              v-if="row.normalized_timeline && row.timeline && row.normalized_timeline !== row.timeline"
              class="summary-text"
            >
              {{ row.timeline }}
            </div>
          </template>
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
        <el-table-column :label="t('marketplace.table.leadKind')" width="170">
          <template #default="{ row }">
            <el-tag
              :type="row.lead_kind === 'project' ? 'success' : row.lead_kind === 'contract_role' ? 'warning' : 'info'"
              effect="plain"
            >
              {{ t(`marketplace.filters.leadKindOptions.${row.lead_kind}`) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.queue')" width="160">
          <template #default="{ row }">
            <el-tag :type="row.lead_tier === 'high_purity' ? 'success' : 'warning'" effect="plain">
              {{ t(`marketplace.filters.queueOptions.${row.lead_tier}`) }}
            </el-tag>
            <div class="summary-text">{{ row.tier_reason }}</div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.status')" width="190">
          <template #default="{ row }">
            <el-tag :type="leadStatusTagType(row.lead_status)" effect="plain">
              {{ leadStatusLabel(row.lead_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.published')" width="190">
          <template #default="{ row }">{{ formatDate(row.published_at || row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.actions')" min-width="210" fixed="right">
          <template #default="{ row }">
            <div class="actions-cell">
              <el-select
                :model-value="row.lead_status"
                size="small"
                class="row-status-select"
                @change="(value) => handleStatusChange(row.id, value)"
              >
                <el-option
                  v-for="option in leadStatusOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <el-button
                v-if="row.link"
                size="small"
                text
                @click="openExternal(row.link)"
              >
                {{ t('actions.view') }}
              </el-button>
            </div>
          </template>
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
import { computed, ref, watch } from 'vue';
import { useMutation, useQuery } from '@tanstack/vue-query';
import { ElMessage } from 'element-plus/es/components/message/index';
import { useI18n } from 'vue-i18n';
import {
  fetchMarketplaceLeads,
  fetchRssSources,
  updateMarketplaceLeadStatus,
  type MarketplaceLead
} from '../services/api';

const { t } = useI18n();
const pageSize = 15;
const page = ref(1);
const search = ref('');
const sourceId = ref<'all' | string>('all');
const statusFilter = ref<'all' | MarketplaceLead['lead_status']>('all');
const queueView = ref<'high_purity' | 'expanded' | 'all'>('high_purity');
const leadKindView = ref<'reviewable' | 'project' | 'contract_role' | 'full_time_job' | 'all'>('reviewable');

const leadStatusOptions = computed(() => [
  { value: 'new' as const, label: t('marketplace.filters.statusOptions.new') },
  { value: 'watching' as const, label: t('marketplace.filters.statusOptions.watching') },
  { value: 'contacted' as const, label: t('marketplace.filters.statusOptions.contacted') },
  { value: 'ignored' as const, label: t('marketplace.filters.statusOptions.ignored') }
]);

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
  tier: queueView.value === 'all' ? undefined : queueView.value,
  lead_kind:
    leadKindView.value === 'project' ||
    leadKindView.value === 'contract_role' ||
    leadKindView.value === 'full_time_job'
      ? leadKindView.value
      : undefined,
  reviewable_only: leadKindView.value === 'reviewable' ? true : undefined,
  lead_status: statusFilter.value === 'all' ? undefined : statusFilter.value
}));

const leadsQuery = useQuery({
  queryKey: computed(() => ['marketplace-leads', queryParams.value]),
  queryFn: () => fetchMarketplaceLeads(queryParams.value),
  keepPreviousData: true,
  staleTime: 30_000
});

const statusMutation = useMutation({
  mutationFn: ({ leadId, status }: { leadId: number; status: MarketplaceLead['lead_status'] }) =>
    updateMarketplaceLeadStatus(leadId, status),
  onSuccess: async (_, variables) => {
    ElMessage.success(
      t('marketplace.feedback.statusUpdated', {
        status: leadStatusLabel(variables.status)
      })
    );
    await leadsQuery.refetch();
  },
  onError: () => {
    ElMessage.error(t('feedback.genericError'));
  }
});

const leads = computed(() => leadsQuery.data.value?.items ?? []);
const total = computed(() => leadsQuery.data.value?.total ?? 0);
const highPurityCount = computed(() => leadsQuery.data.value?.tier_breakdown?.high_purity ?? 0);
const expandedCount = computed(() => leadsQuery.data.value?.tier_breakdown?.expanded ?? 0);
const projectCount = computed(() => leadsQuery.data.value?.kind_breakdown?.project ?? 0);
const contractRoleCount = computed(() => leadsQuery.data.value?.kind_breakdown?.contract_role ?? 0);
const reviewableCount = computed(() => projectCount.value + contractRoleCount.value);
const fullTimeJobCount = computed(() => leadsQuery.data.value?.kind_breakdown?.full_time_job ?? 0);
const watchingCount = computed(() => leadsQuery.data.value?.status_breakdown?.watching ?? 0);
const contactedCount = computed(() => leadsQuery.data.value?.status_breakdown?.contacted ?? 0);

watch([search, sourceId, statusFilter, queueView, leadKindView], () => {
  page.value = 1;
});

const handlePageChange = (value: number) => {
  page.value = value;
};

const refetch = () => {
  void leadsQuery.refetch();
  void sourcesQuery.refetch();
};

const sourceStatusTagType = (status: 'active' | 'paused' | 'disabled') => {
  if (status === 'active') return 'success';
  if (status === 'paused') return 'warning';
  return 'info';
};

const leadStatusTagType = (status: MarketplaceLead['lead_status']) => {
  if (status === 'contacted') return 'success';
  if (status === 'watching') return 'warning';
  if (status === 'ignored') return 'info';
  return '';
};

const leadStatusLabel = (status: MarketplaceLead['lead_status']) =>
  t(`marketplace.filters.statusOptions.${status}`);

const handleStatusChange = (leadId: number, value: string) => {
  void statusMutation.mutate({
    leadId,
    status: value as MarketplaceLead['lead_status']
  });
};

const openExternal = (link: string) => {
  window.open(link, '_blank', 'noopener,noreferrer');
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

.source-select,
.status-select,
.kind-select {
  width: 220px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(0, 220px));
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

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.actions-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.row-status-select {
  width: 124px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}

@media (max-width: 960px) {
  .page-header,
  .actions {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input,
  .source-select,
  .status-select,
  .kind-select {
    width: 100%;
  }
}
</style>
