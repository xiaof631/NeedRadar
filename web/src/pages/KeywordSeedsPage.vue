<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('keywordSeeds.title') }}</h1>
        <p class="subtitle">{{ t('keywordSeeds.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <el-button
          type="primary"
          :loading="extractMutation.isPending.value"
          @click="extractMutation.mutate()"
        >
          {{ t('keywordSeeds.actions.extract') }}
        </el-button>
        <el-button
          :loading="validatePendingMutation.isPending.value"
          @click="validatePendingMutation.mutate()"
        >
          {{ t('keywordSeeds.actions.validatePending') }}
        </el-button>
        <el-button @click="seedsQuery.refetch()" :loading="seedsQuery.isFetching.value">
          {{ t('actions.refresh') }}
        </el-button>
      </div>
    </header>

    <div class="summary-grid">
      <div class="metric-panel">
        <span>{{ t('keywordSeeds.metrics.total') }}</span>
        <strong>{{ total }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('keywordSeeds.metrics.new') }}</span>
        <strong>{{ statusBreakdown.new ?? 0 }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('keywordSeeds.metrics.validated') }}</span>
        <strong>{{ statusBreakdown.validated ?? 0 }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('keywordSeeds.metrics.shortlisted') }}</span>
        <strong>{{ statusBreakdown.shortlisted ?? 0 }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('keywordSeeds.metrics.noVolume') }}</span>
        <strong>{{ statusBreakdown.no_volume ?? 0 }}</strong>
      </div>
    </div>

    <el-card shadow="never">
      <div class="filters">
        <el-input
          v-model="searchInput"
          class="filters__input"
          :placeholder="t('keywordSeeds.filters.searchPlaceholder')"
          clearable
          @keyup.enter="applySearch"
          @clear="handleClearSearch"
        />
        <el-select v-model="statusFilter" class="filters__select" :placeholder="t('keywordSeeds.filters.status')">
          <el-option :label="t('keywordSeeds.filters.all')" value="all" />
          <el-option
            v-for="option in statusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <div class="score-filter">
          <span>{{ t('keywordSeeds.filters.minScore') }}</span>
          <el-slider v-model="minScore" :min="0" :max="100" :step="5" />
        </div>
      </div>

      <el-table
        :data="seeds"
        row-key="id"
        v-loading="seedsQuery.isFetching.value"
        :empty-text="t('keywordSeeds.table.empty')"
        @row-click="openDetails"
      >
        <el-table-column :label="t('keywordSeeds.table.phrase')" min-width="280">
          <template #default="{ row }">
            <button class="title-button" type="button" @click.stop="openDetails(row)">
              {{ row.phrase }}
            </button>
            <p class="pattern-text">{{ patternLabel(row.pattern_kind) }}</p>
          </template>
        </el-table-column>
        <el-table-column :label="t('keywordSeeds.table.occurrences')" width="100" sortable :sort-by="'occurrence_count'">
          <template #default="{ row }">{{ row.occurrence_count }}</template>
        </el-table-column>
        <el-table-column :label="t('keywordSeeds.table.volume')" width="120">
          <template #default="{ row }">
            {{ row.search_volume === null ? '—' : row.search_volume.toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column :label="t('keywordSeeds.table.difficulty')" width="90">
          <template #default="{ row }">{{ row.keyword_difficulty ?? '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('keywordSeeds.table.cpc')" width="90">
          <template #default="{ row }">{{ row.cpc === null ? '—' : `$${row.cpc}` }}</template>
        </el-table-column>
        <el-table-column :label="t('keywordSeeds.table.score')" width="130">
          <template #default="{ row }">
            <div class="score-cell">
              <el-progress :percentage="row.opportunity_score" :stroke-width="8" :show-text="false" />
              <strong>{{ row.opportunity_score }}</strong>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('keywordSeeds.table.status')" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" effect="plain">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('keywordSeeds.table.actions')" width="230" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button
                size="small"
                :loading="validatingSeedId === row.id"
                @click.stop="validateOne(row)"
              >
                {{ t('keywordSeeds.actions.validateOne') }}
              </el-button>
              <el-button
                v-if="row.status !== 'shortlisted'"
                size="small"
                type="success"
                plain
                @click.stop="changeStatus(row, 'shortlisted')"
              >
                {{ t('keywordSeeds.actions.shortlist') }}
              </el-button>
              <el-button
                v-else
                size="small"
                @click.stop="changeStatus(row, 'new')"
              >
                {{ t('keywordSeeds.actions.restore') }}
              </el-button>
              <el-button
                v-if="row.status !== 'dismissed'"
                size="small"
                type="info"
                plain
                @click.stop="changeStatus(row, 'dismissed')"
              >
                {{ t('keywordSeeds.actions.dismiss') }}
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

    <el-drawer v-model="detailsVisible" :title="t('keywordSeeds.details.title')" size="46%">
      <div v-if="selectedSeed" class="details">
        <div class="details-header">
          <div>
            <h2>{{ selectedSeed.phrase }}</h2>
            <p>{{ patternLabel(selectedSeed.pattern_kind) }}</p>
          </div>
          <div class="detail-scores">
            <span>{{ t('keywordSeeds.table.score') }} <strong>{{ selectedSeed.opportunity_score }}</strong></span>
            <span>{{ t('keywordSeeds.table.occurrences') }} <strong>{{ selectedSeed.occurrence_count }}</strong></span>
          </div>
        </div>

        <section class="detail-section">
          <h3>{{ t('keywordSeeds.details.metrics') }}</h3>
          <div class="metrics-row">
            <el-tag effect="plain">
              {{ t('keywordSeeds.table.volume') }}:
              {{ selectedSeed.search_volume === null ? '—' : selectedSeed.search_volume.toLocaleString() }}
            </el-tag>
            <el-tag effect="plain">
              {{ t('keywordSeeds.table.difficulty') }}: {{ selectedSeed.keyword_difficulty ?? '—' }}
            </el-tag>
            <el-tag effect="plain">
              {{ t('keywordSeeds.table.cpc') }}:
              {{ selectedSeed.cpc === null ? '—' : `$${selectedSeed.cpc}` }}
            </el-tag>
            <el-tag v-if="selectedSeed.competition === 'confirmed_by_suggest'" type="success" effect="plain">
              {{ t('keywordSeeds.details.confirmedBySuggest') }}
            </el-tag>
            <el-tag :type="statusTag(selectedSeed.status)" effect="plain">
              {{ statusLabel(selectedSeed.status) }}
            </el-tag>
          </div>
          <p v-if="selectedSeed.validated_at" class="muted">
            {{ t('keywordSeeds.table.validatedAt') }}: {{ formatTime(selectedSeed.validated_at) }}
          </p>
          <p v-else class="muted">{{ t('keywordSeeds.details.notValidated') }}</p>
          <p v-if="selectedSeed.validation_error" class="error-text">
            {{ t('keywordSeeds.details.validationError') }}: {{ selectedSeed.validation_error }}
          </p>
        </section>

        <section class="detail-section">
          <h3>{{ t('keywordSeeds.details.evidence') }}</h3>
          <ul class="evidence-list">
            <li v-for="item in selectedSeed.evidence" :key="item.raw_entry_id">
              <a v-if="item.link" :href="item.link" target="_blank" rel="noreferrer">{{ item.title }}</a>
              <span v-else>{{ item.title }}</span>
              <span class="muted"> · {{ item.source_name }}</span>
            </li>
          </ul>
        </section>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { ElMessage } from 'element-plus/es/components/message/index';

import {
  fetchKeywordSeeds,
  triggerKeywordSeedExtraction,
  validateKeywordSeed,
  validatePendingKeywordSeeds,
  updateKeywordSeedStatus,
  type KeywordSeed,
  type KeywordSeedStatus,
  type KeywordSeedsQueryParams,
} from '../services/api';

const { t } = useI18n();
const queryClient = useQueryClient();
const pageSize = 20;
const page = ref(1);
const searchInput = ref('');
const searchTerm = ref('');
const minScore = ref(0);
const statusFilter = ref<KeywordSeedStatus | 'all'>('all');
const selectedSeed = ref<KeywordSeed | null>(null);
const detailsVisible = ref(false);
const validatingSeedId = ref<number | null>(null);

const statusOptions = computed(() => [
  { label: t('keywordSeeds.status.new'), value: 'new' as const },
  { label: t('keywordSeeds.status.validated'), value: 'validated' as const },
  { label: t('keywordSeeds.status.no_volume'), value: 'no_volume' as const },
  { label: t('keywordSeeds.status.shortlisted'), value: 'shortlisted' as const },
  { label: t('keywordSeeds.status.dismissed'), value: 'dismissed' as const },
  { label: t('keywordSeeds.status.error'), value: 'error' as const },
]);

const queryOptions = computed<KeywordSeedsQueryParams>(() => ({
  skip: (page.value - 1) * pageSize,
  limit: pageSize,
  search: searchTerm.value || undefined,
  status: statusFilter.value === 'all' ? undefined : statusFilter.value,
  min_score: minScore.value || undefined,
}));

const seedsQuery = useQuery({
  queryKey: computed(() => ['keyword-seeds', queryOptions.value]),
  queryFn: () => fetchKeywordSeeds(queryOptions.value),
  keepPreviousData: true,
  refetchOnWindowFocus: false,
});

const seeds = computed(() => seedsQuery.data.value?.items ?? []);
const total = computed(() => seedsQuery.data.value?.total ?? 0);
const statusBreakdown = computed<Record<string, number>>(
  () => seedsQuery.data.value?.status_breakdown ?? {},
);

const refreshList = () => {
  queryClient.invalidateQueries({ queryKey: ['keyword-seeds'] });
};

const extractMutation = useMutation({
  mutationFn: triggerKeywordSeedExtraction,
  onSuccess: (result) => {
    ElMessage.success(
      t('keywordSeeds.messages.extractDone', {
        scanned: result.scanned,
        created: result.created,
        merged: result.merged,
      }),
    );
    refreshList();
  },
  onError: () => ElMessage.error(t('keywordSeeds.messages.error')),
});

const validatePendingMutation = useMutation({
  mutationFn: () => validatePendingKeywordSeeds(),
  onSuccess: (result) => {
    if (result.reason) {
      ElMessage.warning(t('keywordSeeds.messages.validateSkipped'));
      return;
    }
    ElMessage.success(
      t('keywordSeeds.messages.validateDone', {
        validated: result.validated,
        noVolume: result.no_volume,
        errors: result.errors,
      }),
    );
    refreshList();
  },
  onError: () => ElMessage.error(t('keywordSeeds.messages.error')),
});

const validateOne = async (seed: KeywordSeed) => {
  validatingSeedId.value = seed.id;
  try {
    await validateKeywordSeed(seed.id);
    ElMessage.success(t('keywordSeeds.messages.validateDone', { validated: 1, noVolume: 0, errors: 0 }));
    refreshList();
  } catch (error) {
    const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    ElMessage.warning(detail || t('keywordSeeds.messages.error'));
  } finally {
    validatingSeedId.value = null;
  }
};

const changeStatus = async (seed: KeywordSeed, status: KeywordSeedStatus) => {
  try {
    await updateKeywordSeedStatus(seed.id, status);
    ElMessage.success(t('keywordSeeds.messages.statusUpdated'));
    refreshList();
  } catch {
    ElMessage.error(t('keywordSeeds.messages.error'));
  }
};

watch([statusFilter, minScore], () => {
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

const openDetails = (item: KeywordSeed) => {
  selectedSeed.value = item;
  detailsVisible.value = true;
};

const statusLabel = (status: KeywordSeedStatus) => t(`keywordSeeds.status.${status}`);
const patternLabel = (kind: string) =>
  t(`keywordSeeds.pattern.${kind}`);

const statusTag = (status: KeywordSeedStatus) => {
  if (status === 'validated') return 'success';
  if (status === 'shortlisted') return 'warning';
  if (status === 'error') return 'danger';
  if (status === 'dismissed') return 'info';
  return 'info';
};

const formatTime = (value: string) => new Date(value).toLocaleString();
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

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
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

.pattern-text {
  margin: 0.35rem 0 0;
  color: #94a3b8;
  font-size: 0.85rem;
}

.score-cell {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.6rem;
  align-items: center;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
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

.metrics-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.evidence-list {
  margin: 0;
  padding-left: 1.1rem;
  color: #334155;
  line-height: 1.55;
}

.evidence-list a {
  color: #2563eb;
}

.muted {
  margin: 0;
  color: #64748b;
  font-size: 0.9rem;
}

.error-text {
  margin: 0;
  color: #dc2626;
  font-size: 0.9rem;
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
