<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('emailFollowups.title') }}</h1>
        <p class="subtitle">{{ t('emailFollowups.subtitle') }}</p>
      </div>
      <el-button type="primary" @click="followupsQuery.refetch()" :loading="followupsQuery.isFetching.value">
        {{ t('actions.refresh') }}
      </el-button>
    </header>

    <div class="summary-grid">
      <div class="metric-panel">
        <span>{{ t('emailFollowups.metrics.total') }}</span>
        <strong>{{ summary.total }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('emailFollowups.metrics.draftReady') }}</span>
        <strong>{{ summary.draft_ready }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('emailFollowups.metrics.needsRecipient') }}</span>
        <strong>{{ summary.needs_recipient }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('emailFollowups.metrics.waitingReply') }}</span>
        <strong>{{ summary.waiting_reply }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('emailFollowups.metrics.overdue') }}</span>
        <strong>{{ summary.overdue }}</strong>
      </div>
    </div>

    <el-card shadow="never">
      <div class="filters">
        <el-select v-model="sourceFilter" class="filters__select" :placeholder="t('emailFollowups.filters.source')">
          <el-option :label="t('emailFollowups.filters.all')" value="all" />
          <el-option
            v-for="option in sourceOptions"
            :key="option"
            :label="sourceLabel(option)"
            :value="option"
          />
        </el-select>
        <el-select v-model="statusFilter" class="filters__select" :placeholder="t('emailFollowups.filters.status')">
          <el-option :label="t('emailFollowups.filters.all')" value="all" />
          <el-option
            v-for="option in statusOptions"
            :key="option"
            :label="statusLabel(option)"
            :value="option"
          />
        </el-select>
        <div class="score-filter">
          <span>{{ t('emailFollowups.filters.minScore') }}</span>
          <el-slider v-model="minScore" :min="0" :max="100" :step="5" />
        </div>
        <el-checkbox v-model="includeReviewFirst">
          {{ t('emailFollowups.filters.includeReviewFirst') }}
        </el-checkbox>
      </div>

      <el-table
        :data="tasks"
        row-key="id"
        v-loading="followupsQuery.isFetching.value"
        :empty-text="t('emailFollowups.table.empty')"
        @row-click="openDetails"
      >
        <el-table-column :label="t('emailFollowups.table.lead')" min-width="320">
          <template #default="{ row }">
            <button class="title-button" type="button" @click.stop="openDetails(row)">
              {{ row.title }}
            </button>
            <p class="reason-text">{{ row.reason }}</p>
          </template>
        </el-table-column>
        <el-table-column :label="t('emailFollowups.table.source')" width="190">
          <template #default="{ row }">
            <div class="source-cell">
              <el-tag effect="plain" size="small">{{ sourceLabel(row.source) }}</el-tag>
              <span>{{ row.source_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('emailFollowups.table.score')" width="100">
          <template #default="{ row }">
            <span class="score">{{ row.priority_score }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('emailFollowups.table.status')" width="145">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" effect="plain">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('emailFollowups.table.action')" width="150">
          <template #default="{ row }">
            <el-tag :type="actionTag(row.recommended_action)" effect="plain">
              {{ actionLabel(row.recommended_action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('emailFollowups.table.recipient')" min-width="180">
          <template #default="{ row }">{{ row.recipient || '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('emailFollowups.table.nextFollowUp')" width="175">
          <template #default="{ row }">{{ formatDate(row.next_follow_up_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('emailFollowups.table.operations')" width="210" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" @click.stop="openDetails(row)">
                {{ t('actions.view') }}
              </el-button>
              <el-button
                v-if="row.source_url"
                size="small"
                tag="a"
                :href="row.source_url"
                target="_blank"
                rel="noreferrer"
                @click.stop
              >
                {{ t('emailFollowups.details.openSource') }}
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

    <el-drawer
      v-model="detailsVisible"
      :title="t('emailFollowups.details.title')"
      size="48%"
      destroy-on-close
    >
      <div v-if="selectedTask" class="details">
        <div class="details-header">
          <div>
            <h2>{{ selectedTask.title }}</h2>
            <p>{{ selectedTask.source_name }} · {{ sourceLabel(selectedTask.source) }}</p>
          </div>
          <div class="detail-tags">
            <el-tag :type="statusTag(selectedTask.status)" effect="plain">
              {{ statusLabel(selectedTask.status) }}
            </el-tag>
            <el-tag :type="actionTag(selectedTask.recommended_action)" effect="plain">
              {{ actionLabel(selectedTask.recommended_action) }}
            </el-tag>
          </div>
        </div>

        <section class="detail-section">
          <h3>{{ t('emailFollowups.details.reason') }}</h3>
          <p>{{ selectedTask.reason }}</p>
          <div v-if="selectedTask.risk_flags.length" class="tag-list">
            <el-tag v-for="flag in selectedTask.risk_flags" :key="flag" type="danger" effect="plain">
              {{ flag }}
            </el-tag>
          </div>
        </section>

        <section class="detail-section">
          <h3>{{ t('emailFollowups.details.recipient') }}</h3>
          <el-input
            v-model="recipientDraft"
            :placeholder="t('emailFollowups.details.recipientPlaceholder')"
            clearable
          />
        </section>

        <section class="detail-section">
          <h3>{{ t('emailFollowups.details.subject') }}</h3>
          <div class="draft-box">{{ selectedTask.draft.subject }}</div>
          <el-button size="small" type="primary" @click="copyText(selectedTask.draft.subject)">
            {{ t('emailFollowups.details.copySubject') }}
          </el-button>
        </section>

        <section class="detail-section">
          <h3>{{ t('emailFollowups.details.body') }}</h3>
          <div class="draft-box multiline">{{ selectedTask.draft.body }}</div>
          <div class="button-row">
            <el-button size="small" type="primary" @click="copyText(selectedTask.draft.body)">
              {{ t('emailFollowups.details.copyBody') }}
            </el-button>
            <el-button size="small" @click="copyText(selectedTask.draft.codex_handoff)">
              {{ t('emailFollowups.details.copyHandoff') }}
            </el-button>
            <el-button
              v-if="selectedTask.source_url"
              size="small"
              tag="a"
              :href="selectedTask.source_url"
              target="_blank"
              rel="noreferrer"
            >
              {{ t('emailFollowups.details.openSource') }}
            </el-button>
          </div>
        </section>

        <section v-if="selectedTask.evidence.length" class="detail-section">
          <h3>{{ t('emailFollowups.details.evidence') }}</h3>
          <ul class="evidence-list">
            <li v-for="item in selectedTask.evidence" :key="item">{{ item }}</li>
          </ul>
        </section>

        <section class="detail-section">
          <h3>{{ t('emailFollowups.details.note') }}</h3>
          <el-input
            v-model="noteDraft"
            type="textarea"
            :rows="3"
            :placeholder="t('emailFollowups.details.notePlaceholder')"
          />
          <div class="button-row">
            <el-button
              @click="updateStatus('drafted')"
              :loading="statusMutation.isPending.value"
            >
              {{ t('emailFollowups.details.markDrafted') }}
            </el-button>
            <el-button
              type="success"
              @click="updateStatus('sent')"
              :loading="statusMutation.isPending.value"
            >
              {{ t('emailFollowups.details.markSent') }}
            </el-button>
            <el-button
              type="primary"
              @click="updateStatus('replied')"
              :loading="statusMutation.isPending.value"
            >
              {{ t('emailFollowups.details.markReplied') }}
            </el-button>
            <el-button
              type="warning"
              @click="updateStatus('no_response')"
              :loading="statusMutation.isPending.value"
            >
              {{ t('emailFollowups.details.markNoResponse') }}
            </el-button>
            <el-button
              @click="updateStatus('closed')"
              :loading="statusMutation.isPending.value"
            >
              {{ t('emailFollowups.details.close') }}
            </el-button>
            <el-button
              @click="updateStatus('skipped')"
              :loading="statusMutation.isPending.value"
            >
              {{ t('emailFollowups.details.skip') }}
            </el-button>
          </div>
        </section>

        <section class="detail-section">
          <h3>{{ t('emailFollowups.details.events') }}</h3>
          <div v-if="selectedTask.events.length" class="event-list">
            <div v-for="event in selectedTask.events" :key="`${event.created_at}-${event.status_to}`" class="event-item">
              <span>{{ formatDate(event.created_at) }}</span>
              <strong>{{ event.status_to ? statusLabel(event.status_to) : event.event_type }}</strong>
              <p v-if="event.note">{{ event.note }}</p>
            </div>
          </div>
          <div v-else class="empty-note">{{ t('emailFollowups.details.emptyEvents') }}</div>
        </section>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useMutation, useQuery } from '@tanstack/vue-query';
import { ElMessage } from 'element-plus/es/components/message/index';

import {
  fetchEmailFollowUps,
  updateEmailFollowUpStatus,
  type EmailFollowUpAction,
  type EmailFollowUpQueryParams,
  type EmailFollowUpSource,
  type EmailFollowUpStatus,
  type EmailFollowUpTask,
  type EmailFollowUpTaskSource,
} from '../services/api';

const { t } = useI18n();
const pageSize = 20;
const page = ref(1);
const sourceFilter = ref<EmailFollowUpSource>('all');
const statusFilter = ref<EmailFollowUpStatus | 'all'>('all');
const minScore = ref(70);
const includeReviewFirst = ref(true);
const selectedTask = ref<EmailFollowUpTask | null>(null);
const detailsVisible = ref(false);
const recipientDraft = ref('');
const noteDraft = ref('');

const sourceOptions: EmailFollowUpTaskSource[] = ['marketplace', 'customer_radar'];
const statusOptions: EmailFollowUpStatus[] = [
  'draft_ready',
  'drafted',
  'sent',
  'replied',
  'no_response',
  'closed',
  'skipped',
];

const queryOptions = computed<EmailFollowUpQueryParams>(() => ({
  skip: (page.value - 1) * pageSize,
  limit: pageSize,
  source: sourceFilter.value,
  status: statusFilter.value === 'all' ? undefined : statusFilter.value,
  min_score: minScore.value,
  include_review_first: includeReviewFirst.value,
}));

const followupsQuery = useQuery({
  queryKey: computed(() => ['email-followups', queryOptions.value]),
  queryFn: () => fetchEmailFollowUps(queryOptions.value),
  keepPreviousData: true,
  refetchOnWindowFocus: false,
});

const tasks = computed(() => followupsQuery.data.value?.items ?? []);
const total = computed(() => followupsQuery.data.value?.total ?? 0);
const summary = computed(
  () =>
    followupsQuery.data.value?.summary ?? {
      total: 0,
      draft_ready: 0,
      drafted: 0,
      sent: 0,
      waiting_reply: 0,
      no_response: 0,
      replied: 0,
      closed: 0,
      skipped: 0,
      needs_recipient: 0,
      overdue: 0,
    },
);

watch([sourceFilter, statusFilter, minScore, includeReviewFirst], () => {
  page.value = 1;
});

const statusMutation = useMutation({
  mutationFn: ({ task, status }: { task: EmailFollowUpTask; status: EmailFollowUpStatus }) =>
    updateEmailFollowUpStatus(task.raw_entry_id, {
      status,
      recipient: recipientDraft.value.trim() || task.recipient,
      note: noteDraft.value.trim() || null,
    }),
  onSuccess: (task) => {
    selectedTask.value = task;
    recipientDraft.value = task.recipient ?? '';
    noteDraft.value = '';
    followupsQuery.refetch();
    ElMessage.success(t('emailFollowups.feedback.statusUpdated'));
  },
  onError: () => {
    ElMessage.error(t('feedback.genericError'));
  },
});

const handlePageChange = (value: number) => {
  page.value = value;
};

const openDetails = (task: EmailFollowUpTask) => {
  selectedTask.value = task;
  recipientDraft.value = task.recipient ?? '';
  noteDraft.value = '';
  detailsVisible.value = true;
};

const updateStatus = (status: EmailFollowUpStatus) => {
  if (!selectedTask.value) return;
  statusMutation.mutate({ task: selectedTask.value, status });
};

const copyText = async (value: string) => {
  await navigator.clipboard.writeText(value);
  ElMessage.success(t('emailFollowups.feedback.copied'));
};

const sourceLabel = (source: EmailFollowUpSource | EmailFollowUpTaskSource) => {
  if (source === 'all') return t('emailFollowups.filters.all');
  return t(`emailFollowups.source.${source}`);
};

const statusLabel = (status: EmailFollowUpStatus) => t(`emailFollowups.status.${status}`);
const actionLabel = (action: EmailFollowUpAction) => t(`emailFollowups.action.${action}`);

const statusTag = (status: EmailFollowUpStatus) => {
  if (status === 'sent') return 'warning';
  if (status === 'replied') return 'success';
  if (status === 'no_response') return 'danger';
  if (status === 'closed' || status === 'skipped') return 'info';
  return 'primary';
};

const actionTag = (action: EmailFollowUpAction) => {
  if (action === 'create_draft' || action === 'send_after_review') return 'primary';
  if (action === 'check_reply') return 'warning';
  if (action === 'close_or_retry') return 'danger';
  return 'info';
};

const formatDate = (value: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
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
  align-items: center;
  margin-bottom: 1rem;
}

.filters__select {
  width: 180px;
}

.score-filter {
  display: grid;
  grid-template-columns: auto 160px;
  align-items: center;
  gap: 0.75rem;
  min-width: 245px;
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

.reason-text {
  margin: 0.35rem 0 0;
  color: #64748b;
  line-height: 1.45;
}

.source-cell,
.row-actions,
.button-row,
.tag-list,
.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.score {
  color: #0f766e;
  font-weight: 700;
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

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.detail-section h3 {
  margin: 0;
  font-size: 1rem;
}

.detail-section p {
  margin: 0;
  color: #334155;
  line-height: 1.55;
}

.draft-box {
  padding: 0.85rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.multiline {
  white-space: pre-wrap;
}

.evidence-list {
  margin: 0;
  padding-left: 1.1rem;
  color: #334155;
  line-height: 1.55;
}

.event-list {
  display: grid;
  gap: 0.65rem;
}

.event-item {
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.event-item span {
  display: block;
  color: #64748b;
  font-size: 0.82rem;
}

.event-item strong {
  display: block;
  margin-top: 0.25rem;
  color: #0f172a;
}

.event-item p {
  margin: 0.25rem 0 0;
}

.empty-note {
  color: #94a3b8;
}

@media (max-width: 960px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .page-header,
  .details-header {
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .filters__select,
  .score-filter {
    width: 100%;
  }
}
</style>
