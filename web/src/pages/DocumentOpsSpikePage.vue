<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('documentOps.title') }}</h1>
        <p class="subtitle">{{ t('documentOps.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <el-button @click="runReconciliation" :loading="isLoading">
          {{ t('documentOps.actions.run') }}
        </el-button>
        <el-button
          type="primary"
          @click="exportCsv"
          :loading="isExporting"
          :disabled="!editableExceptions.length"
        >
          {{ t('documentOps.actions.exportCsv') }}
        </el-button>
      </div>
    </header>

    <div class="summary-grid">
      <div class="metric-panel">
        <span>{{ t('documentOps.metrics.reference') }}</span>
        <strong>{{ summary?.reference_count ?? 0 }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('documentOps.metrics.invoice') }}</span>
        <strong>{{ summary?.invoice_count ?? 0 }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('documentOps.metrics.matched') }}</span>
        <strong>{{ summary?.matched_count ?? 0 }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('documentOps.metrics.exceptions') }}</span>
        <strong>{{ summary?.exception_count ?? 0 }}</strong>
      </div>
      <div class="metric-panel">
        <span>{{ t('documentOps.metrics.needsReview') }}</span>
        <strong>{{ summary?.needs_review_count ?? 0 }}</strong>
      </div>
    </div>

    <el-card shadow="never">
      <div class="controls">
        <el-select v-model="selectedCaseId" class="case-select" @change="runReconciliation">
          <el-option
            v-for="item in sampleCases"
            :key="item.id"
            :label="item.label"
            :value="item.id"
          />
        </el-select>
        <div v-if="summary" class="total-strip">
          <span>{{ t('documentOps.metrics.referenceTotal') }} {{ formatMoney(summary.reference_total) }}</span>
          <span>{{ t('documentOps.metrics.invoiceTotal') }} {{ formatMoney(summary.invoice_total) }}</span>
          <span>{{ t('documentOps.metrics.totalDifference') }} {{ formatMoney(summary.total_difference) }}</span>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('documentOps.tabs.exceptions')" name="exceptions">
          <el-table
            :data="editableExceptions"
            row-key="id"
            v-loading="isLoading"
            :empty-text="t('documentOps.table.empty')"
          >
            <el-table-column :label="t('documentOps.table.type')" width="190">
              <template #default="{ row }">
                <el-tag :type="severityTag(row.severity)" effect="plain">
                  {{ exceptionTypeLabel(row.type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.lines')" width="170">
              <template #default="{ row }">
                <div class="line-pair">
                  <span>{{ row.reference_line_id || '-' }}</span>
                  <span>{{ row.invoice_line_id || '-' }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.message')" min-width="280">
              <template #default="{ row }">
                <p class="message-cell">{{ row.message }}</p>
                <span class="subtle">
                  {{ row.expected || '-' }} / {{ row.actual || '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.confidence')" width="120">
              <template #default="{ row }">{{ formatConfidence(row.confidence) }}</template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.status')" width="170">
              <template #default="{ row }">
                <el-select v-model="row.review_status" size="small">
                  <el-option
                    v-for="option in reviewStatusOptions"
                    :key="option"
                    :label="reviewStatusLabel(option)"
                    :value="option"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.note')" min-width="220">
              <template #default="{ row }">
                <el-input
                  v-model="row.reviewer_note"
                  size="small"
                  :placeholder="t('documentOps.table.notePlaceholder')"
                  clearable
                />
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('documentOps.tabs.matches')" name="matches">
          <el-table
            :data="editableMatches"
            row-key="id"
            v-loading="isLoading"
            :empty-text="t('documentOps.table.empty')"
          >
            <el-table-column :label="t('documentOps.table.reference')" min-width="230">
              <template #default="{ row }">
                <strong>{{ row.reference_item.line_id }}</strong>
                <p class="message-cell">{{ row.reference_item.description }}</p>
              </template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.invoice')" min-width="230">
              <template #default="{ row }">
                <strong>{{ row.invoice_item.line_id }}</strong>
                <p class="message-cell">{{ row.invoice_item.description }}</p>
              </template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.matchType')" width="160">
              <template #default="{ row }">{{ matchTypeLabel(row.match_type) }}</template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.confidence')" width="120">
              <template #default="{ row }">{{ formatConfidence(row.confidence) }}</template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.status')" width="170">
              <template #default="{ row }">
                <el-select v-model="row.review_status" size="small">
                  <el-option
                    v-for="option in reviewStatusOptions"
                    :key="option"
                    :label="reviewStatusLabel(option)"
                    :value="option"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column :label="t('documentOps.table.note')" min-width="220">
              <template #default="{ row }">
                <el-input
                  v-model="row.reviewer_note"
                  size="small"
                  :placeholder="t('documentOps.table.notePlaceholder')"
                  clearable
                />
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('documentOps.tabs.inputs')" name="inputs">
          <div class="input-grid">
            <section>
              <h2>{{ t('documentOps.table.reference') }}</h2>
              <el-table :data="currentCase.reference_items" row-key="line_id" size="small">
                <el-table-column prop="line_id" :label="t('documentOps.table.lineId')" width="95" />
                <el-table-column prop="description" :label="t('documentOps.table.description')" min-width="210" />
                <el-table-column prop="quantity" :label="t('documentOps.table.quantity')" width="110" />
                <el-table-column prop="unit_price" :label="t('documentOps.table.unitPrice')" width="120" />
                <el-table-column prop="amount" :label="t('documentOps.table.amount')" width="120" />
              </el-table>
            </section>
            <section>
              <h2>{{ t('documentOps.table.invoice') }}</h2>
              <el-table :data="currentCase.invoice_items" row-key="line_id" size="small">
                <el-table-column prop="line_id" :label="t('documentOps.table.lineId')" width="95" />
                <el-table-column prop="description" :label="t('documentOps.table.description')" min-width="210" />
                <el-table-column prop="quantity" :label="t('documentOps.table.quantity')" width="110" />
                <el-table-column prop="unit_price" :label="t('documentOps.table.unitPrice')" width="120" />
                <el-table-column prop="amount" :label="t('documentOps.table.amount')" width="120" />
              </el-table>
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="t('documentOps.tabs.conclusion')" name="conclusion">
          <div v-if="result" class="conclusion">
            <el-tag :type="result.spike_conclusion.feasible ? 'success' : 'warning'" effect="plain">
              {{ result.spike_conclusion.feasible ? t('documentOps.conclusion.feasible') : t('documentOps.conclusion.needsMore') }}
            </el-tag>
            <p>{{ result.spike_conclusion.recommendation }}</p>
            <h2>{{ t('documentOps.conclusion.validated') }}</h2>
            <ul>
              <li v-for="item in result.spike_conclusion.validated" :key="item">{{ item }}</li>
            </ul>
            <h2>{{ t('documentOps.conclusion.risks') }}</h2>
            <ul>
              <li v-for="item in result.spike_conclusion.remaining_risks" :key="item">{{ item }}</li>
            </ul>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessage } from 'element-plus/es/components/message/index';

import {
  exportDocumentOpsExceptions,
  reconcileDocumentOps,
  type DocumentOpsException,
  type DocumentOpsExceptionType,
  type DocumentOpsLineItemInput,
  type DocumentOpsMatch,
  type DocumentOpsMatchType,
  type DocumentOpsReconcileResponse,
  type DocumentOpsReviewStatus
} from '../services/api';

interface SampleCase {
  id: string;
  label: string;
  reference_items: DocumentOpsLineItemInput[];
  invoice_items: DocumentOpsLineItemInput[];
}

const { t } = useI18n();

const sampleCases: SampleCase[] = [
  {
    id: 'case_001',
    label: 'Case 001 - Groundworks payment application',
    reference_items: [
      { line_id: 'A100', description: 'Site setup', quantity: 1, unit: 'item', unit_price: 1250, amount: 1250 },
      { line_id: 'A110', description: 'Concrete slab preparation', quantity: 120, unit: 'm2', unit_price: 18, amount: 2160 },
      { line_id: 'A120', description: 'Rebar installation', quantity: 450, unit: 'kg', unit_price: 2.5, amount: 1125 },
      { line_id: 'A130', description: 'Waste disposal', quantity: 1, unit: 'item', unit_price: 300, amount: 300 }
    ],
    invoice_items: [
      { line_id: 'A100', description: 'Site setup', quantity: 1, unit: 'item', unit_price: 1250, amount: 1250 },
      { line_id: 'A110', description: 'Concrete slab preparation', quantity: 120, unit: 'm2', unit_price: 19, amount: 2280 },
      { line_id: 'A120', description: 'Rebar installation', quantity: 500, unit: 'kg', unit_price: 2.5, amount: 1250 },
      { line_id: 'A140', description: 'Temporary fencing', quantity: 1, unit: 'item', unit_price: 420, amount: 420 }
    ]
  },
  {
    id: 'case_002',
    label: 'Case 002 - Civils rate schedule',
    reference_items: [
      { line_id: 'B200', description: 'Excavation', quantity: 80, unit: 'm3', unit_price: 22, amount: 1760 },
      { line_id: 'B210', description: 'Drainage pipe', quantity: 60, unit: 'm', unit_price: 35, amount: 2100 },
      { line_id: 'B220', description: 'Asphalt patching', quantity: 30, unit: 'm2', unit_price: 45, amount: 1350 }
    ],
    invoice_items: [
      { line_id: 'B200', description: 'Excavation', quantity: 80, unit: 'm3', unit_price: 22, amount: 1760 },
      { line_id: 'B210', description: 'Drainage pipe', quantity: 60, unit: 'm', unit_price: 35, amount: 1950 },
      { line_id: 'B221', description: 'Asphalt repairs', quantity: 30, unit: 'm2', unit_price: 45, amount: 1350 }
    ]
  },
  {
    id: 'case_003',
    label: 'Case 003 - Fit-out final account',
    reference_items: [
      { line_id: 'C300', description: 'Interior painting', quantity: 300, unit: 'm2', unit_price: 6, amount: 1800 },
      { line_id: 'C310', description: 'Door hardware', quantity: 24, unit: 'set', unit_price: 18, amount: 432 },
      { line_id: 'C320', description: 'Final clean', quantity: 1, unit: 'item', unit_price: 250, amount: 250 }
    ],
    invoice_items: [
      { line_id: 'C301', description: 'Interior wall painting', quantity: 300, unit: 'm2', unit_price: 6, amount: 1800 },
      { line_id: 'C310', description: 'Door hardware', quantity: 24, unit: 'set', unit_price: 20, amount: 480 },
      { line_id: 'C321', description: 'Final cleaning', quantity: 1, unit: 'item', unit_price: 250, amount: 250 },
      { line_id: 'C340', description: 'Additional signage', quantity: 2, unit: 'item', unit_price: 85, amount: 170 }
    ]
  }
];

const reviewStatusOptions: DocumentOpsReviewStatus[] = ['pending', 'accepted', 'dismissed', 'resolved'];
const selectedCaseId = ref(sampleCases[0].id);
const activeTab = ref('exceptions');
const result = ref<DocumentOpsReconcileResponse | null>(null);
const editableExceptions = ref<DocumentOpsException[]>([]);
const editableMatches = ref<DocumentOpsMatch[]>([]);
const isLoading = ref(false);
const isExporting = ref(false);

const currentCase = computed(() => {
  return sampleCases.find((item) => item.id === selectedCaseId.value) ?? sampleCases[0];
});

const summary = computed(() => result.value?.summary ?? null);

const runReconciliation = async () => {
  isLoading.value = true;
  try {
    const response = await reconcileDocumentOps({
      scenario: 'contractor_invoice_reconciliation',
      reference_items: currentCase.value.reference_items,
      invoice_items: currentCase.value.invoice_items
    });
    result.value = response;
    editableExceptions.value = cloneRows(response.exceptions);
    editableMatches.value = cloneRows(response.matched_items);
  } catch (error) {
    ElMessage.error(t('feedback.genericError'));
  } finally {
    isLoading.value = false;
  }
};

const exportCsv = async () => {
  isExporting.value = true;
  try {
    const csvPayload = await exportDocumentOpsExceptions(editableExceptions.value);
    downloadCsv(csvPayload);
  } catch (error) {
    ElMessage.error(t('feedback.genericError'));
  } finally {
    isExporting.value = false;
  }
};

const cloneRows = <T,>(rows: T[]): T[] => {
  return JSON.parse(JSON.stringify(rows)) as T[];
};

const downloadCsv = (payload: string) => {
  const blob = new Blob([payload], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${selectedCaseId.value}-exceptions.csv`;
  link.click();
  URL.revokeObjectURL(url);
};

const formatMoney = (value: number) => {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2
  }).format(value);
};

const formatConfidence = (value: number) => `${Math.round(value * 100)}%`;

const severityTag = (severity: string) => {
  if (severity === 'high') {
    return 'danger';
  }
  if (severity === 'medium') {
    return 'warning';
  }
  return 'info';
};

const exceptionTypeLabel = (type: DocumentOpsExceptionType) => {
  if (!type) {
    return '-';
  }
  return t(`documentOps.exceptionTypes.${type}`);
};

const reviewStatusLabel = (status: DocumentOpsReviewStatus) => {
  if (!status) {
    return '-';
  }
  return t(`documentOps.reviewStatus.${status}`);
};

const matchTypeLabel = (type: DocumentOpsMatchType) => {
  if (!type) {
    return '-';
  }
  return t(`documentOps.matchTypes.${type}`);
};

onMounted(() => {
  void runReconciliation();
});
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
  font-size: 1.6rem;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: #64748b;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.85rem;
}

.metric-panel {
  min-height: 86px;
  padding: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.metric-panel span {
  display: block;
  color: #64748b;
  font-size: 0.84rem;
}

.metric-panel strong {
  display: block;
  margin-top: 0.45rem;
  color: #0f172a;
  font-size: 1.55rem;
}

.controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.case-select {
  width: min(100%, 360px);
}

.total-strip {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  color: #475569;
  font-size: 0.9rem;
}

.line-pair {
  display: grid;
  gap: 0.25rem;
  color: #475569;
  font-size: 0.86rem;
}

.message-cell {
  margin: 0;
  color: #0f172a;
}

.subtle {
  display: block;
  margin-top: 0.25rem;
  color: #64748b;
  font-size: 0.82rem;
}

.input-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.input-grid h2,
.conclusion h2 {
  margin: 0 0 0.75rem;
  color: #334155;
  font-size: 1rem;
}

.conclusion {
  display: grid;
  gap: 0.9rem;
  max-width: 820px;
}

.conclusion p,
.conclusion ul {
  margin: 0;
}

.conclusion ul {
  padding-left: 1.25rem;
  color: #475569;
}

@media (max-width: 1100px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .input-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
