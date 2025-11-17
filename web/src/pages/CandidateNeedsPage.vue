<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('candidates.title') }}</h1>
        <p class="subtitle">{{ t('candidates.subtitle') }}</p>
      </div>
      <div class="actions">
        <el-button @click="refreshNeeds" :loading="needsQuery.isFetching.value">
          {{ t('actions.refresh') }}
        </el-button>
        <el-button type="primary" @click="openExportDialog">
          {{ t('actions.export') }}
        </el-button>
      </div>
    </header>

    <el-card shadow="never">
      <div class="filters">
        <el-input
          v-model="searchInput"
          class="filters__input"
          :placeholder="t('candidates.filters.searchPlaceholder')"
          clearable
          @keyup.enter="applySearch"
          @clear="handleClearSearch"
        />
        <el-select v-model="statusFilter" class="filters__select" :placeholder="t('candidates.filters.status')">
          <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-select v-model="syncFilter" class="filters__select" :placeholder="t('candidates.filters.synced')">
          <el-option v-for="option in syncOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </div>
      <el-table
        :data="needs"
        row-key="id"
        v-loading="needsQuery.isFetching.value"
        :empty-text="t('candidates.table.empty')"
      >
        <el-table-column prop="summary" :label="t('candidates.table.summary')" min-width="220" show-overflow-tooltip />
        <el-table-column :label="t('candidates.table.status')" width="140">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('candidates.table.ruleScore')" width="140">
          <template #default="{ row }">{{ formatScore(row.rule_score) }}</template>
        </el-table-column>
        <el-table-column :label="t('candidates.table.confidence')" width="140">
          <template #default="{ row }">{{ formatScore(row.confidence) }}</template>
        </el-table-column>
        <el-table-column :label="t('candidates.table.synced')" width="160">
          <template #default="{ row }">
            <el-tooltip v-if="row.sync_error" :content="row.sync_error">
              <el-tag :type="syncState(row).type" effect="plain">
                {{ syncState(row).label }}
              </el-tag>
            </el-tooltip>
            <el-tag v-else :type="syncState(row).type" effect="plain">
              {{ syncState(row).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('candidates.table.updated')" min-width="180">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
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

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ t('candidates.export.sectionTitle') }}</span>
          <el-button text size="small" @click="exportJobsQuery.refetch()" :loading="exportJobsQuery.isFetching.value">
            {{ t('actions.refresh') }}
          </el-button>
        </div>
      </template>
      <el-table
        size="small"
        :data="exportJobs"
        v-loading="exportJobsQuery.isFetching.value"
        :empty-text="t('candidates.export.empty')"
      >
        <el-table-column prop="id" :label="t('candidates.jobs.columns.id')" width="120" />
        <el-table-column prop="format" :label="t('candidates.jobs.columns.format')" width="100" />
        <el-table-column :label="t('candidates.jobs.columns.status')" width="140">
          <template #default="{ row }">
            <el-tag :type="jobStatusTag(row.status)">
              {{ jobStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="record_count" :label="t('candidates.jobs.columns.records')" width="140">
          <template #default="{ row }">{{ row.record_count ?? '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('candidates.jobs.columns.finishedAt')" min-width="180">
          <template #default="{ row }">
            {{ row.finished_at ? formatDate(row.finished_at) : '—' }}
          </template>
        </el-table-column>
        <el-table-column :label="t('candidates.jobs.columns.download')" min-width="200">
          <template #default="{ row }">
            <el-link v-if="row.file_path" :href="row.file_path" target="_blank">{{ row.file_path }}</el-link>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="exportDialogVisible"
      :title="t('candidates.export.dialogTitle')"
      width="520px"
      @close="resetExportForm"
    >
      <el-form label-width="120px" class="export-form">
        <el-form-item :label="t('candidates.export.fields.format')">
          <el-radio-group v-model="exportForm.format">
            <el-radio-button label="csv">CSV</el-radio-button>
            <el-radio-button label="json">JSON</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('candidates.export.fields.status')">
          <el-select v-model="exportForm.status">
            <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('candidates.export.fields.synced')">
          <el-select v-model="exportForm.synced">
            <el-option v-for="option in syncOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('candidates.export.fields.limit')">
          <div class="limit-field">
            <el-input-number v-model="exportForm.limit" :min="1" :max="5000" />
            <small>{{ t('candidates.export.tips.limit') }}</small>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="closeExportDialog">{{ t('actions.cancel') }}</el-button>
          <el-button type="primary" :loading="exportMutation.isPending.value" @click="submitExport">
            {{ t('actions.confirm') }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useMutation, useQuery } from '@tanstack/vue-query';
import { ElMessage } from 'element-plus';
import type { AxiosError } from 'axios';

import {
  createCandidateNeedExportJob,
  fetchCandidateNeedExportJobs,
  fetchCandidateNeeds,
  type CandidateNeed,
  type CandidateNeedExportJob,
  type CandidateNeedExportJobPayload,
  type CandidateNeedQueryParams,
  type ExportJobStatus,
} from '../services/api';

const { t } = useI18n();
const pageSize = 20;
const page = ref(1);
const searchInput = ref('');
const searchTerm = ref('');

type StatusFilter = CandidateNeed['status'] | 'all';
type SyncFilter = 'all' | 'synced' | 'unsynced';

type ExportFormat = 'csv' | 'json';

const statusFilter = ref<StatusFilter>('all');
const syncFilter = ref<SyncFilter>('all');

const statusOptions = computed(() => [
  { label: t('candidates.filters.statusOptions.all'), value: 'all' as const },
  { label: t('candidates.statusLabels.pending_review'), value: 'pending_review' as const },
  { label: t('candidates.statusLabels.approved'), value: 'approved' as const },
  { label: t('candidates.statusLabels.rejected'), value: 'rejected' as const },
  { label: t('candidates.statusLabels.in_discovery'), value: 'in_discovery' as const },
  { label: t('candidates.statusLabels.completed'), value: 'completed' as const },
]);

const syncOptions = computed(() => [
  { label: t('candidates.filters.syncedOptions.all'), value: 'all' as const },
  { label: t('candidates.filters.syncedOptions.synced'), value: 'synced' as const },
  { label: t('candidates.filters.syncedOptions.unsynced'), value: 'unsynced' as const },
]);

const queryOptions = computed<CandidateNeedQueryParams>(() => ({
  skip: (page.value - 1) * pageSize,
  limit: pageSize,
  search: searchTerm.value || undefined,
  statuses: statusFilter.value === 'all' ? undefined : [statusFilter.value],
  synced: syncFilter.value === 'all' ? undefined : syncFilter.value === 'synced',
}));

const needsQuery = useQuery({
  queryKey: computed(() => ['candidate-needs', queryOptions.value]),
  queryFn: () => fetchCandidateNeeds(queryOptions.value),
  keepPreviousData: true,
  refetchOnWindowFocus: false,
});

const needs = computed(() => needsQuery.data.value?.items ?? []);
const total = computed(() => needsQuery.data.value?.total ?? 0);

const exportJobsQuery = useQuery({
  queryKey: ['candidate-need-export-jobs'],
  queryFn: () => fetchCandidateNeedExportJobs({ limit: 8 }),
  refetchOnWindowFocus: false,
  refetchInterval: 30000,
});

const exportJobs = computed(() => exportJobsQuery.data.value?.items ?? []);

watch([statusFilter, syncFilter], () => {
  page.value = 1;
});

const handlePageChange = (value: number) => {
  page.value = value;
};

const applySearch = () => {
  page.value = 1;
  searchTerm.value = searchInput.value.trim();
};

const handleClearSearch = () => {
  searchInput.value = '';
  applySearch();
};

const refreshNeeds = () => {
  needsQuery.refetch();
};

const statusLabel = (status: CandidateNeed['status']) => {
  switch (status) {
    case 'approved':
      return t('candidates.statusLabels.approved');
    case 'rejected':
      return t('candidates.statusLabels.rejected');
    case 'in_discovery':
      return t('candidates.statusLabels.in_discovery');
    case 'completed':
      return t('candidates.statusLabels.completed');
    default:
      return t('candidates.statusLabels.pending_review');
  }
};

const statusTag = (status: CandidateNeed['status']) => {
  switch (status) {
    case 'approved':
      return 'success';
    case 'rejected':
      return 'danger';
    case 'in_discovery':
      return 'info';
    case 'completed':
      return 'success';
    default:
      return 'warning';
  }
};

const syncState = (need: CandidateNeed) => {
  if (need.synced_at) {
    return { label: t('candidates.syncState.synced'), type: 'success' as const };
  }
  if (need.sync_error) {
    return { label: t('candidates.syncState.failed'), type: 'danger' as const };
  }
  return { label: t('candidates.syncState.pending'), type: 'warning' as const };
};

const jobStatusLabel = (status: ExportJobStatus) => {
  switch (status) {
    case 'completed':
      return t('candidates.jobs.status.completed');
    case 'running':
      return t('candidates.jobs.status.running');
    case 'failed':
      return t('candidates.jobs.status.failed');
    default:
      return t('candidates.jobs.status.pending');
  }
};

const jobStatusTag = (status: ExportJobStatus) => {
  switch (status) {
    case 'completed':
      return 'success';
    case 'running':
      return 'info';
    case 'failed':
      return 'danger';
    default:
      return 'warning';
  }
};

const formatScore = (value: number | null) => {
  return typeof value === 'number' ? value.toFixed(2) : '—';
};

const formatDate = (value: string) => {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
};

const exportDialogVisible = ref(false);
const exportForm = reactive({
  format: 'csv' as ExportFormat,
  status: 'all' as StatusFilter,
  synced: 'all' as SyncFilter,
  limit: 500,
});

const openExportDialog = () => {
  exportForm.status = statusFilter.value;
  exportForm.synced = syncFilter.value;
  exportDialogVisible.value = true;
};

const closeExportDialog = () => {
  exportDialogVisible.value = false;
};

const resetExportForm = () => {
  exportForm.format = 'csv';
  exportForm.status = 'all';
  exportForm.synced = 'all';
  exportForm.limit = 500;
};

const exportMutation = useMutation({
  mutationFn: (payload: CandidateNeedExportJobPayload) => createCandidateNeedExportJob(payload),
  onSuccess: (job: CandidateNeedExportJob) => {
    ElMessage.success(t('candidates.export.jobToast', { id: job.id }));
    exportDialogVisible.value = false;
    exportJobsQuery.refetch();
  },
  onError: (error: unknown) => {
    const err = error as AxiosError<{ detail?: string }>;
    const message = err.response?.data?.detail;
    ElMessage.error(message ?? t('feedback.genericError'));
  },
});

const submitExport = () => {
  const payload: CandidateNeedExportJobPayload = {
    format: exportForm.format,
    limit: exportForm.limit,
    search: searchTerm.value || undefined,
  };
  if (exportForm.status !== 'all') {
    payload.statuses = [exportForm.status];
  }
  if (exportForm.synced !== 'all') {
    payload.synced = exportForm.synced === 'synced';
  }
  exportMutation.mutate(payload);
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

.subtitle {
  color: #6b7280;
  margin-top: 0.25rem;
}

.actions {
  display: flex;
  gap: 0.75rem;
}

.filters {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.filters__input {
  flex: 1;
  min-width: 200px;
}

.filters__select {
  width: 180px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  padding-top: 1rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.limit-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.limit-field small {
  color: #9ca3af;
}
</style>
