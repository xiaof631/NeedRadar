<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('customerRadar.title') }}</h1>
        <p class="subtitle">{{ t('customerRadar.subtitle') }}</p>
      </div>
      <el-button type="primary" @click="radarQuery.refetch()" :loading="radarQuery.isFetching.value">
        {{ t('actions.refresh') }}
      </el-button>
    </header>

    <div class="summary-grid">
      <div class="metric-panel">
        <span>{{ t('customerRadar.metrics.total') }}</span>
        <strong>{{ summary.total_candidates }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('customerRadar.metrics.contactNow') }}</span>
        <strong>{{ summary.contact_now }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('customerRadar.metrics.reviewFirst') }}</span>
        <strong>{{ summary.review_first }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('customerRadar.metrics.averageScore') }}</span>
        <strong>{{ summary.average_fit_score }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('customerRadar.metrics.averageCredibility') }}</span>
        <strong>{{ summary.average_credibility_score }}</strong>
      </div>
    </div>

    <el-card shadow="never">
      <div class="filters">
        <el-input
          v-model="searchInput"
          class="filters__input"
          :placeholder="t('customerRadar.filters.searchPlaceholder')"
          clearable
          @keyup.enter="applySearch"
          @clear="handleClearSearch"
        />
        <el-select v-model="actionFilter" class="filters__select" :placeholder="t('customerRadar.filters.action')">
          <el-option :label="t('customerRadar.filters.all')" value="all" />
          <el-option
            v-for="option in actionOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="segmentFilter" class="filters__select" :placeholder="t('customerRadar.filters.segment')">
          <el-option :label="t('customerRadar.filters.all')" value="all" />
          <el-option
            v-for="option in segmentOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="sourceTypeFilter" class="filters__select" :placeholder="t('customerRadar.filters.sourceType')">
          <el-option :label="t('customerRadar.filters.all')" value="all" />
          <el-option
            v-for="option in sourceTypeOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <div class="score-filter">
          <span>{{ t('customerRadar.filters.minScore') }}</span>
          <el-slider v-model="minScore" :min="0" :max="100" :step="5" />
        </div>
      </div>

      <el-table
        :data="opportunities"
        row-key="id"
        v-loading="radarQuery.isFetching.value"
        :empty-text="t('customerRadar.table.empty')"
        @row-click="openDetails"
      >
        <el-table-column :label="t('customerRadar.table.opportunity')" min-width="300">
          <template #default="{ row }">
            <button class="title-button" type="button" @click.stop="openDetails(row)">
              {{ row.title }}
            </button>
            <p class="pain-text">{{ row.pain_summary }}</p>
          </template>
        </el-table-column>
        <el-table-column :label="t('customerRadar.table.score')" width="130">
          <template #default="{ row }">
            <div class="score-cell">
              <el-progress :percentage="row.fit_score" :stroke-width="8" :show-text="false" />
              <strong>{{ row.fit_score }}</strong>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('customerRadar.table.credibility')" width="160">
          <template #default="{ row }">
            <div class="credibility-cell">
              <strong>{{ row.credibility_score }}</strong>
              <el-tag :type="credibilityTag(row.credibility_level)" effect="plain">
                {{ credibilityLabel(row.credibility_level) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('customerRadar.table.action')" width="160">
          <template #default="{ row }">
            <el-tag :type="actionTag(row.recommended_action)" effect="plain">
              {{ actionLabel(row.recommended_action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('customerRadar.table.segment')" width="190">
          <template #default="{ row }">
            <el-tag effect="plain">{{ segmentLabel(row.customer_segment) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('customerRadar.table.source')" min-width="190">
          <template #default="{ row }">
            <div class="source-cell">
              <el-tag size="small" effect="plain">{{ row.source_type }}</el-tag>
              <span>{{ row.source_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('customerRadar.table.budget')" width="120">
          <template #default="{ row }">{{ row.budget_signal || '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('customerRadar.table.actions')" width="220" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" @click.stop="openDetails(row)">
                {{ t('actions.view') }}
              </el-button>
              <el-button
                v-if="row.link"
                size="small"
                tag="a"
                :href="row.link"
                target="_blank"
                rel="noreferrer"
                @click.stop
              >
                {{ t('customerRadar.details.openSource') }}
              </el-button>
              <el-button v-else size="small" disabled>
                {{ t('customerRadar.details.openSource') }}
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

    <el-drawer v-model="detailsVisible" :title="t('customerRadar.details.title')" size="46%">
      <div v-if="selectedOpportunity" class="details">
        <div class="details-header">
          <div>
            <h2>{{ selectedOpportunity.title }}</h2>
            <p>{{ selectedOpportunity.source_name }} · {{ segmentLabel(selectedOpportunity.customer_segment) }}</p>
          </div>
          <div class="detail-scores">
            <span>{{ t('customerRadar.table.score') }} <strong>{{ selectedOpportunity.fit_score }}</strong></span>
            <span>
              {{ t('customerRadar.table.credibility') }}
              <strong>{{ selectedOpportunity.credibility_score }}</strong>
            </span>
          </div>
        </div>

        <section class="detail-section">
          <h3>{{ t('customerRadar.details.recommendation') }}</h3>
          <p>{{ selectedOpportunity.product_angle }}</p>
          <el-tag :type="actionTag(selectedOpportunity.recommended_action)" effect="plain">
            {{ actionLabel(selectedOpportunity.recommended_action) }}
          </el-tag>
        </section>

        <section class="detail-section">
          <h3>{{ t('customerRadar.details.credibility') }}</h3>
          <el-tag :type="credibilityTag(selectedOpportunity.credibility_level)" effect="plain">
            {{ credibilityLabel(selectedOpportunity.credibility_level) }}
          </el-tag>
          <ul class="evidence-list">
            <li v-for="item in selectedOpportunity.credibility_reasons" :key="item">{{ item }}</li>
          </ul>
          <div v-if="selectedOpportunity.risk_flags.length" class="risk-list">
            <el-tag v-for="flag in selectedOpportunity.risk_flags" :key="flag" type="danger" effect="plain">
              {{ flag }}
            </el-tag>
          </div>
        </section>

        <section class="detail-section">
          <h3>{{ t('customerRadar.details.evidence') }}</h3>
          <ul class="evidence-list">
            <li v-for="item in selectedOpportunity.evidence" :key="item">{{ item }}</li>
          </ul>
          <div class="tag-list">
            <el-tag v-for="signal in selectedOpportunity.matched_signals" :key="signal" size="small" effect="plain">
              {{ signal }}
            </el-tag>
          </div>
        </section>

        <section class="detail-section">
          <h3>{{ t('customerRadar.details.outreachDraft') }}</h3>
          <div class="draft-box">{{ selectedOpportunity.outreach_draft }}</div>
          <el-button size="small" type="primary" @click="copyDraft">
            {{ t('customerRadar.details.copyDraft') }}
          </el-button>
          <el-button
            v-if="selectedOpportunity.link"
            size="small"
            tag="a"
            :href="selectedOpportunity.link"
            target="_blank"
            rel="noreferrer"
          >
            {{ t('customerRadar.details.openSource') }}
          </el-button>
        </section>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuery } from '@tanstack/vue-query';
import { ElMessage } from 'element-plus/es/components/message/index';

import {
  fetchCustomerOpportunities,
  type CustomerOpportunity,
  type CustomerCredibilityLevel,
  type CustomerRadarAction,
  type CustomerRadarQueryParams,
  type CustomerSegment,
  type SourceType,
} from '../services/api';

const { t } = useI18n();
const pageSize = 20;
const page = ref(1);
const searchInput = ref('');
const searchTerm = ref('');
const minScore = ref(80);

type ActionFilter = CustomerRadarAction | 'all';
type SegmentFilter = CustomerSegment | 'all';
type SourceTypeFilter = SourceType | 'all';

const actionFilter = ref<ActionFilter>('all');
const segmentFilter = ref<SegmentFilter>('all');
const sourceTypeFilter = ref<SourceTypeFilter>('freelance_marketplace');
const selectedOpportunity = ref<CustomerOpportunity | null>(null);
const detailsVisible = ref(false);

const actionOptions = computed(() => [
  { label: t('customerRadar.action.contact_now'), value: 'contact_now' as const },
  { label: t('customerRadar.action.review_first'), value: 'review_first' as const },
  { label: t('customerRadar.action.watch'), value: 'watch' as const },
]);

const segmentOptions = computed(() => [
  { label: t('customerRadar.segment.government_docs'), value: 'government_docs' as const },
  { label: t('customerRadar.segment.real_estate_docs'), value: 'real_estate_docs' as const },
  { label: t('customerRadar.segment.compliance_kyc'), value: 'compliance_kyc' as const },
  { label: t('customerRadar.segment.legal_contracts'), value: 'legal_contracts' as const },
  { label: t('customerRadar.segment.training_lms'), value: 'training_lms' as const },
  { label: t('customerRadar.segment.document_ops'), value: 'document_ops' as const },
  { label: t('customerRadar.segment.outreach_research'), value: 'outreach_research' as const },
]);

const sourceTypeOptions = computed(() => [
  { label: 'Freelance', value: 'freelance_marketplace' as const },
  { label: 'Reddit', value: 'reddit' as const },
  { label: 'Hacker News', value: 'hacker_news' as const },
  { label: 'RSS', value: 'rss' as const },
  { label: 'GitHub Issues', value: 'github_issues' as const },
]);

const queryOptions = computed<CustomerRadarQueryParams>(() => ({
  skip: (page.value - 1) * pageSize,
  limit: pageSize,
  search: searchTerm.value || undefined,
  action: actionFilter.value === 'all' ? undefined : actionFilter.value,
  segment: segmentFilter.value === 'all' ? undefined : segmentFilter.value,
  source_type: sourceTypeFilter.value === 'all' ? undefined : sourceTypeFilter.value,
  min_score: minScore.value,
}));

const radarQuery = useQuery({
  queryKey: computed(() => ['customer-radar', queryOptions.value]),
  queryFn: () => fetchCustomerOpportunities(queryOptions.value),
  keepPreviousData: true,
  refetchOnWindowFocus: false,
});

const opportunities = computed(() => radarQuery.data.value?.items ?? []);
const total = computed(() => radarQuery.data.value?.total ?? 0);
const summary = computed(
  () =>
    radarQuery.data.value?.summary ?? {
      total_candidates: 0,
      contact_now: 0,
      review_first: 0,
      watch: 0,
      average_fit_score: 0,
      average_credibility_score: 0,
      segment_breakdown: {},
      source_breakdown: {},
    },
);

watch([actionFilter, segmentFilter, sourceTypeFilter, minScore], () => {
  page.value = 1;
});

const applySearch = () => {
  page.value = 1;
  searchTerm.value = searchInput.value.trim();
};

const handleClearSearch = () => {
  searchInput.value = '';
  applySearch();
};

const handlePageChange = (value: number) => {
  page.value = value;
};

const openDetails = (item: CustomerOpportunity) => {
  selectedOpportunity.value = item;
  detailsVisible.value = true;
};

const actionLabel = (action: CustomerRadarAction) => t(`customerRadar.action.${action}`);
const segmentLabel = (segment: CustomerSegment) => t(`customerRadar.segment.${segment}`);
const credibilityLabel = (level: CustomerCredibilityLevel) => t(`customerRadar.credibility.${level}`);

const actionTag = (action: CustomerRadarAction) => {
  if (action === 'contact_now') return 'success';
  if (action === 'review_first') return 'warning';
  return 'info';
};

const credibilityTag = (level: CustomerCredibilityLevel) => {
  if (level === 'high') return 'success';
  if (level === 'medium') return 'warning';
  return 'danger';
};

const copyDraft = async () => {
  if (!selectedOpportunity.value) return;
  await navigator.clipboard.writeText(selectedOpportunity.value.outreach_draft);
  ElMessage.success(t('customerRadar.details.copied'));
};
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.page-header h1 {
  margin: 0;
  font-size: 1.55rem;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: #64748b;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.85rem;
}

.metric-panel {
  padding: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.metric-panel span {
  display: block;
  color: #64748b;
  font-size: 0.86rem;
}

.metric-panel strong {
  display: block;
  margin-top: 0.35rem;
  color: #0f172a;
  font-size: 1.45rem;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.filters__input {
  width: min(340px, 100%);
}

.filters__select {
  width: 190px;
}

.score-filter {
  display: grid;
  grid-template-columns: auto 160px;
  align-items: center;
  gap: 0.75rem;
  min-width: 250px;
  color: #475569;
  font-size: 0.9rem;
}

.title-button {
  border: 0;
  padding: 0;
  background: transparent;
  color: #2563eb;
  font: inherit;
  font-weight: 650;
  text-align: left;
  cursor: pointer;
}

.pain-text {
  margin: 0.35rem 0 0;
  color: #64748b;
  line-height: 1.45;
}

.score-cell {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.6rem;
  align-items: center;
}

.source-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.row-actions {
  display: flex;
  gap: 0.45rem;
  align-items: center;
}

.credibility-cell {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}

.details {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.details-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e2e8f0;
}

.details-header h2 {
  margin: 0;
  font-size: 1.2rem;
}

.details-header p {
  margin: 0.35rem 0 0;
  color: #64748b;
}

.detail-scores {
  display: grid;
  gap: 0.35rem;
  min-width: 110px;
  color: #64748b;
  text-align: right;
}

.detail-scores strong {
  color: #0f766e;
  font-size: 1.6rem;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.detail-section h3 {
  margin: 0;
  font-size: 1rem;
}

.evidence-list {
  margin: 0;
  padding-left: 1.1rem;
  color: #334155;
  line-height: 1.55;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.risk-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.draft-box {
  padding: 0.85rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  line-height: 1.55;
}

@media (max-width: 960px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .page-header {
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .filters__select,
  .filters__input,
  .score-filter {
    width: 100%;
  }
}
</style>
