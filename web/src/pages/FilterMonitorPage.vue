<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('filterMonitor.title') }}</h1>
        <p>{{ t('filterMonitor.subtitle') }}</p>
      </div>
      <el-button @click="metricsQuery.refetch()" :loading="metricsQuery.isFetching.value">
        {{ t('actions.refresh') }}
      </el-button>
    </header>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <h3>{{ t('filterMonitor.metrics.ruleHits') }}</h3>
          <el-progress :percentage="ruleHitRate" :stroke-width="18" status="success" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <h3>{{ t('filterMonitor.metrics.promotionRate') }}</h3>
          <el-progress :percentage="promotionRate" :stroke-width="18" />
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <h3>{{ t('filterMonitor.metrics.averageScore') }}</h3>
          <p class="metric-value">{{ averageRuleScore }}</p>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <h3>{{ t('filterMonitor.metrics.processed') }}</h3>
          <p class="metric-value">{{ metrics.processed_entries }}</p>
        </el-card>
      </el-col>
    </el-row>
    <el-card shadow="never">
      <template #header>
        <div class="title">{{ t('filterMonitor.sources.title') }}</div>
      </template>
      <el-table :data="metrics.source_breakdown" :empty-text="t('filterMonitor.sources.empty')" v-loading="metricsQuery.isFetching.value">
        <el-table-column prop="source_name" :label="t('filterMonitor.sources.columns.source')" min-width="200" />
        <el-table-column prop="total_entries" :label="t('filterMonitor.sources.columns.total')" width="140" />
        <el-table-column prop="filtered_entries" :label="t('filterMonitor.sources.columns.filtered')" width="140" />
        <el-table-column prop="promoted_entries" :label="t('filterMonitor.sources.columns.promoted')" width="160" />
        <el-table-column :label="t('filterMonitor.sources.columns.promotionRate')" width="160">
          <template #default="{ row }">{{ formatPercent(row.promotion_rate) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { useI18n } from 'vue-i18n';
import { fetchFilterMetrics, type FilterPerformance } from '../services/api';

const { t } = useI18n();

const metricsQuery = useQuery({
  queryKey: ['filter-metrics'],
  queryFn: fetchFilterMetrics,
  staleTime: 60_000,
  initialData: {
    total_entries: 0,
    pending_entries: 0,
    processed_entries: 0,
    filtered_entries: 0,
    promoted_entries: 0,
    ignored_entries: 0,
    promotion_rate: 0,
    average_rule_score: null,
    source_breakdown: []
  } as FilterPerformance
});

const metrics = computed(() => metricsQuery.data.value!);

const ruleHitRate = computed(() => {
  if (!metrics.value.processed_entries) return 0;
  return Math.round((metrics.value.filtered_entries / metrics.value.processed_entries) * 100);
});

const promotionRate = computed(() => Math.round(metrics.value.promotion_rate * 100));

const averageRuleScore = computed(() => {
  if (metrics.value.average_rule_score == null) return '—';
  return metrics.value.average_rule_score.toFixed(2);
});

const formatPercent = (value: number) => `${Math.round(value * 100)}%`;
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-value {
  font-size: 2rem;
  font-weight: 600;
  margin: 0;
}

.title {
  font-weight: 600;
}
</style>
