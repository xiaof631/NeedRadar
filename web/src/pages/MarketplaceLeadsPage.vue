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
        <el-select v-model="outcomeFilter" class="status-select" :placeholder="t('marketplace.filters.outcome')">
          <el-option :label="t('marketplace.filters.outcomeOptions.all')" value="all" />
          <el-option
            v-for="option in leadOutcomeOptions"
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
        <div class="metric-label">{{ t('marketplace.metrics.won') }}</div>
        <div class="metric-value">{{ wonCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.noResponse') }}</div>
        <div class="metric-value">{{ noResponseCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.resolved') }}</div>
        <div class="metric-value">{{ resolvedCount }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="metric-label">{{ t('marketplace.metrics.winRate') }}</div>
        <div class="metric-value">{{ formatPercent(overallWinRate) }}</div>
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
        <div class="todo-header">
          <div>
            <div class="source-health-title">{{ t('marketplace.todo.title') }}</div>
            <div class="todo-subtitle">{{ t('marketplace.todo.subtitle') }}</div>
          </div>
          <div class="tag-list">
            <el-tag type="danger" effect="plain">
              {{ t('marketplace.todo.highSeverity', { count: highSeverityTodoCount }) }}
            </el-tag>
            <el-tag type="warning" effect="plain">
              {{ t('marketplace.todo.mediumSeverity', { count: mediumSeverityTodoCount }) }}
            </el-tag>
          </div>
        </div>
      </template>
      <div v-if="todoQueue.length" class="todo-list">
        <div v-for="item in todoQueue" :key="`${item.lead_id}-${item.reminder_type}`" class="todo-item">
          <div class="todo-main">
            <div class="todo-title-row">
              <button class="todo-link" type="button" @click="openLeadDetails(item.lead_id)">
                {{ item.title }}
              </button>
              <div class="tag-list">
                <el-tag size="small" :type="reminderSeverityTagType(item.severity)" effect="plain">
                  {{ t(`marketplace.todo.severity.${item.severity}`) }}
                </el-tag>
                <el-tag size="small" effect="plain">
                  {{ reminderTypeLabel(item.reminder_type) }}
                </el-tag>
              </div>
            </div>
            <div class="summary-text">{{ item.source_name }} · {{ item.message }}</div>
            <div class="summary-text">
              {{ t('marketplace.todo.lastActionAt') }}: {{ formatDate(item.last_action_at) }}
            </div>
          </div>
          <div class="todo-side">
            <span class="priority-score">{{ item.priority_score }}</span>
            <span class="summary-text">{{ leadStatusLabel(item.lead_status) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="todo-empty">{{ t('marketplace.todo.empty') }}</div>
    </el-card>

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
      <template #header>
        <div class="source-health-title">{{ t('marketplace.effectiveness.title') }}</div>
      </template>
      <el-table
        :data="sourceBreakdown"
        size="small"
        :empty-text="t('marketplace.effectiveness.empty')"
      >
        <el-table-column prop="source_name" :label="t('marketplace.effectiveness.columns.source')" min-width="220" />
        <el-table-column prop="total" :label="t('marketplace.effectiveness.columns.total')" width="100" />
        <el-table-column prop="high_purity" :label="t('marketplace.effectiveness.columns.highPurity')" width="120" />
        <el-table-column prop="reviewable" :label="t('marketplace.effectiveness.columns.reviewable')" width="120" />
        <el-table-column prop="full_time_job" :label="t('marketplace.effectiveness.columns.fullTime')" width="120" />
        <el-table-column prop="contacted" :label="t('marketplace.effectiveness.columns.contacted')" width="110" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="source-health-title">{{ t('marketplace.recommendations.title') }}</div>
      </template>
      <div v-if="sourceRecommendations.length" class="recommendation-list">
        <div
          v-for="item in sourceRecommendations"
          :key="`${item.source_id}-${item.action}`"
          class="recommendation-item"
        >
          <div class="recommendation-main">
            <div class="recommendation-title-row">
              <span class="source-health-name">{{ item.source_name }}</span>
              <div class="tag-list">
                <el-tag size="small" :type="recommendationSeverityTagType(item.severity)" effect="plain">
                  {{ t(`marketplace.recommendations.severity.${item.severity}`) }}
                </el-tag>
                <el-tag size="small" effect="plain">
                  {{ t(`marketplace.recommendations.actions.${item.action}`) }}
                </el-tag>
              </div>
            </div>
            <div class="summary-text">{{ item.reason }}</div>
          </div>
        </div>
      </div>
      <div v-else class="todo-empty">{{ t('marketplace.recommendations.empty') }}</div>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="source-health-title">{{ t('marketplace.retrospective.title') }}</div>
      </template>
      <p class="summary-text retrospective-summary">{{ t('marketplace.retrospective.subtitle') }}</p>
      <el-table
        :data="sourceConversionBreakdown"
        size="small"
        :empty-text="t('marketplace.retrospective.empty')"
      >
        <el-table-column prop="label" :label="t('marketplace.retrospective.columns.segment')" min-width="220" />
        <el-table-column prop="total" :label="t('marketplace.retrospective.columns.total')" width="90" />
        <el-table-column prop="resolved" :label="t('marketplace.retrospective.columns.resolved')" width="100" />
        <el-table-column prop="won" :label="t('marketplace.retrospective.columns.won')" width="90" />
        <el-table-column prop="lost" :label="t('marketplace.retrospective.columns.lost')" width="90" />
        <el-table-column prop="no_response" :label="t('marketplace.retrospective.columns.noResponse')" width="110" />
        <el-table-column prop="not_fit" :label="t('marketplace.retrospective.columns.notFit')" width="100" />
        <el-table-column :label="t('marketplace.retrospective.columns.winRate')" width="110">
          <template #default="{ row }">{{ formatPercent(row.win_rate) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="source-health-title">{{ t('marketplace.retrospective.segmentTitle') }}</div>
      </template>
      <el-table
        :data="segmentConversionBreakdown"
        size="small"
        :empty-text="t('marketplace.retrospective.empty')"
      >
        <el-table-column :label="t('marketplace.retrospective.columns.segment')" min-width="220">
          <template #default="{ row }">{{ conversionSegmentLabel(row.key, row.label) }}</template>
        </el-table-column>
        <el-table-column prop="total" :label="t('marketplace.retrospective.columns.total')" width="90" />
        <el-table-column prop="resolved" :label="t('marketplace.retrospective.columns.resolved')" width="100" />
        <el-table-column prop="won" :label="t('marketplace.retrospective.columns.won')" width="90" />
        <el-table-column :label="t('marketplace.retrospective.columns.resolutionRate')" width="120">
          <template #default="{ row }">{{ formatPercent(row.resolution_rate) }}</template>
        </el-table-column>
        <el-table-column :label="t('marketplace.retrospective.columns.winRate')" width="110">
          <template #default="{ row }">{{ formatPercent(row.win_rate) }}</template>
        </el-table-column>
      </el-table>
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
        <el-table-column :label="t('marketplace.table.priority')" width="120">
          <template #default="{ row }">
            <div class="priority-cell">
              <span class="priority-score">{{ row.priority_score }}</span>
              <div class="summary-text">{{ row.priority_reason }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.status')" width="190">
          <template #default="{ row }">
            <el-tag :type="leadStatusTagType(row.lead_status)" effect="plain">
              {{ leadStatusLabel(row.lead_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.outcome')" width="170">
          <template #default="{ row }">
            <el-tag
              v-if="row.lead_outcome"
              :type="leadOutcomeTagType(row.lead_outcome)"
              effect="plain"
            >
              {{ leadOutcomeLabel(row.lead_outcome) }}
            </el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.published')" width="190">
          <template #default="{ row }">{{ formatDate(row.published_at || row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.actions')" min-width="210" fixed="right">
          <template #default="{ row }">
            <div class="actions-cell">
              <el-button size="small" text @click="openLeadDetails(row.id)">
                {{ t('marketplace.table.details') }}
              </el-button>
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
                {{ t('marketplace.table.openLink') }}
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
      :title="t('marketplace.details.title')"
      size="40%"
      destroy-on-close
    >
      <div v-loading="detailsQuery.isFetching.value" class="details-drawer">
        <template v-if="selectedLead">
          <div class="details-header">
            <div>
              <h3>{{ selectedLead.title }}</h3>
              <div class="tag-list">
                <el-tag
                  :type="selectedLead.lead_kind === 'project' ? 'success' : selectedLead.lead_kind === 'contract_role' ? 'warning' : 'info'"
                  effect="plain"
                >
                  {{ t(`marketplace.filters.leadKindOptions.${selectedLead.lead_kind}`) }}
                </el-tag>
                <el-tag :type="selectedLead.lead_tier === 'high_purity' ? 'success' : 'warning'" effect="plain">
                  {{ t(`marketplace.filters.queueOptions.${selectedLead.lead_tier}`) }}
                </el-tag>
                <el-tag :type="leadStatusTagType(selectedLead.lead_status)" effect="plain">
                  {{ leadStatusLabel(selectedLead.lead_status) }}
                </el-tag>
              </div>
            </div>
            <el-button
              v-if="selectedLead.link"
              text
              type="primary"
              @click="openExternal(selectedLead.link)"
            >
              {{ t('marketplace.table.openLink') }}
            </el-button>
          </div>

          <div class="details-grid">
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.platform') }}</span>
              <span>{{ selectedLead.platform }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.source') }}</span>
              <span>{{ selectedLead.source_name }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.author') }}</span>
              <span>{{ selectedLead.author || '—' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.location') }}</span>
              <span>{{ selectedLead.location || '—' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.budget') }}</span>
              <span>{{ selectedLead.normalized_budget || selectedLead.budget || '—' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.timeline') }}</span>
              <span>{{ selectedLead.normalized_timeline || selectedLead.timeline || '—' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.published') }}</span>
              <span>{{ formatDate(selectedLead.published_at || selectedLead.created_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.updated') }}</span>
              <span>{{ formatDate(selectedLead.updated_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.lastActionAt') }}</span>
              <span>{{ formatDate(selectedLead.last_action_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.outcome') }}</span>
              <span>{{ selectedLead.lead_outcome ? leadOutcomeLabel(selectedLead.lead_outcome) : '—' }}</span>
            </div>
          </div>

          <div class="details-section">
            <div class="detail-label">{{ t('marketplace.details.reason') }}</div>
            <p class="detail-paragraph">{{ selectedLead.tier_reason }}</p>
          </div>

          <div class="details-section">
            <div class="detail-label">{{ t('marketplace.details.priority') }}</div>
            <p class="detail-paragraph">
              {{ t('marketplace.details.priorityScore', { score: selectedLead.priority_score }) }}
            </p>
            <p class="detail-paragraph">{{ selectedLead.priority_reason }}</p>
          </div>

          <div class="details-section">
            <div class="detail-label">{{ t('marketplace.details.outcome') }}</div>
            <el-select
              v-model="outcomeDraft"
              clearable
              class="outcome-select"
              :placeholder="t('marketplace.details.outcomePlaceholder')"
            >
              <el-option
                v-for="option in leadOutcomeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <div class="details-actions">
              <el-button
                type="primary"
                size="small"
                :loading="outcomeMutation.isPending.value"
                @click="saveLeadOutcome"
              >
                {{ t('marketplace.details.saveOutcome') }}
              </el-button>
            </div>
          </div>

          <div v-if="selectedLead.skills.length" class="details-section">
            <div class="detail-label">{{ t('marketplace.details.skills') }}</div>
            <div class="tag-list">
              <el-tag v-for="skill in selectedLead.skills" :key="skill" size="small" effect="plain">
                {{ skill }}
              </el-tag>
            </div>
          </div>

          <div v-if="selectedLead.duplicate_count > 1" class="details-section">
            <div class="detail-label">{{ t('marketplace.details.duplicates') }}</div>
            <p class="detail-paragraph">
              {{ t('marketplace.table.duplicates', { count: selectedLead.duplicate_count }) }}
            </p>
            <div class="tag-list">
              <el-tag v-for="source in selectedLead.duplicate_sources" :key="source" size="small" effect="plain">
                {{ source }}
              </el-tag>
            </div>
          </div>

          <div v-if="selectedLead.summary" class="details-section">
            <div class="detail-label">{{ t('marketplace.details.summary') }}</div>
            <p class="detail-paragraph">{{ selectedLead.summary }}</p>
          </div>

          <div v-if="selectedLead.description" class="details-section">
            <div class="detail-label">{{ t('marketplace.details.description') }}</div>
            <p class="detail-paragraph">{{ selectedLead.description }}</p>
          </div>

          <div class="details-section">
            <div class="detail-label">{{ t('marketplace.activity.title') }}</div>
            <el-timeline v-if="selectedLead.lead_events.length" class="activity-timeline">
              <el-timeline-item
                v-for="event in selectedLead.lead_events"
                :key="`${event.event_type}-${event.created_at}-${event.status_from || ''}-${event.status_to || ''}-${event.note || ''}`"
                :timestamp="formatDate(event.created_at)"
              >
                <div class="timeline-title">{{ formatLeadEvent(event) }}</div>
                <p v-if="event.note" class="detail-paragraph timeline-note">{{ event.note }}</p>
              </el-timeline-item>
            </el-timeline>
            <p v-else class="detail-paragraph">{{ t('marketplace.activity.empty') }}</p>
          </div>

          <div class="details-section">
            <div class="detail-label">{{ t('marketplace.details.notes') }}</div>
            <el-input
              v-model="notesDraft"
              type="textarea"
              :rows="5"
              :placeholder="t('marketplace.details.notesPlaceholder')"
            />
            <div class="details-actions">
              <el-button
                type="primary"
                size="small"
                :loading="notesMutation.isPending.value"
                @click="saveLeadNotes"
              >
                {{ t('marketplace.details.saveNotes') }}
              </el-button>
            </div>
          </div>
        </template>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useMutation, useQuery } from '@tanstack/vue-query';
import { ElMessage } from 'element-plus/es/components/message/index';
import { useI18n } from 'vue-i18n';
import {
  fetchMarketplaceLead,
  fetchMarketplaceLeads,
  fetchRssSources,
  updateMarketplaceLeadNotes,
  updateMarketplaceLeadOutcome,
  updateMarketplaceLeadStatus,
  type MarketplaceLead,
  type MarketplaceLeadEvent,
  type MarketplaceLeadReminder,
  type MarketplaceSourceRecommendation
} from '../services/api';

const { t } = useI18n();
const pageSize = 15;
const page = ref(1);
const search = ref('');
const sourceId = ref<'all' | string>('all');
const statusFilter = ref<'all' | MarketplaceLead['lead_status']>('all');
const outcomeFilter = ref<'all' | NonNullable<MarketplaceLead['lead_outcome']>>('all');
const queueView = ref<'high_purity' | 'expanded' | 'all'>('high_purity');
const leadKindView = ref<'reviewable' | 'project' | 'contract_role' | 'full_time_job' | 'all'>('reviewable');
const detailsVisible = ref(false);
const selectedLeadId = ref<number | null>(null);
const notesDraft = ref('');
const outcomeDraft = ref<MarketplaceLead['lead_outcome']>(null);

const leadStatusOptions = computed(() => [
  { value: 'new' as const, label: t('marketplace.filters.statusOptions.new') },
  { value: 'watching' as const, label: t('marketplace.filters.statusOptions.watching') },
  { value: 'contacted' as const, label: t('marketplace.filters.statusOptions.contacted') },
  { value: 'ignored' as const, label: t('marketplace.filters.statusOptions.ignored') }
]);

const leadOutcomeOptions = computed(() => [
  { value: 'won' as const, label: t('marketplace.filters.outcomeOptions.won') },
  { value: 'lost' as const, label: t('marketplace.filters.outcomeOptions.lost') },
  { value: 'no_response' as const, label: t('marketplace.filters.outcomeOptions.no_response') },
  { value: 'not_fit' as const, label: t('marketplace.filters.outcomeOptions.not_fit') }
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
  lead_status: statusFilter.value === 'all' ? undefined : statusFilter.value,
  lead_outcome: outcomeFilter.value === 'all' ? undefined : outcomeFilter.value
}));

const leadsQuery = useQuery({
  queryKey: computed(() => ['marketplace-leads', queryParams.value]),
  queryFn: () => fetchMarketplaceLeads(queryParams.value),
  keepPreviousData: true,
  staleTime: 30_000
});

const detailsQuery = useQuery({
  queryKey: computed(() => ['marketplace-lead', selectedLeadId.value]),
  queryFn: () => fetchMarketplaceLead(selectedLeadId.value as number),
  enabled: computed(() => detailsVisible.value && selectedLeadId.value !== null),
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
    if (selectedLeadId.value === variables.leadId) {
      await detailsQuery.refetch();
    }
  },
  onError: () => {
    ElMessage.error(t('feedback.genericError'));
  }
});

const notesMutation = useMutation({
  mutationFn: ({ leadId, notes }: { leadId: number; notes: string | null }) =>
    updateMarketplaceLeadNotes(leadId, notes),
  onSuccess: async (lead) => {
    notesDraft.value = lead.notes ?? '';
    ElMessage.success(t('marketplace.feedback.notesUpdated'));
    await Promise.all([leadsQuery.refetch(), detailsQuery.refetch()]);
  },
  onError: () => {
    ElMessage.error(t('feedback.genericError'));
  }
});

const outcomeMutation = useMutation({
  mutationFn: ({ leadId, outcome }: { leadId: number; outcome: MarketplaceLead['lead_outcome'] }) =>
    updateMarketplaceLeadOutcome(leadId, outcome),
  onSuccess: async (lead) => {
    outcomeDraft.value = lead.lead_outcome;
    ElMessage.success(t('marketplace.feedback.outcomeUpdated'));
    await Promise.all([leadsQuery.refetch(), detailsQuery.refetch()]);
  },
  onError: () => {
    ElMessage.error(t('feedback.genericError'));
  }
});

const leads = computed(() => leadsQuery.data.value?.items ?? []);
const selectedLead = computed(() => detailsQuery.data.value ?? null);
const total = computed(() => leadsQuery.data.value?.total ?? 0);
const sourceBreakdown = computed(() => leadsQuery.data.value?.source_breakdown ?? []);
const sourceRecommendations = computed(() => leadsQuery.data.value?.source_recommendations ?? []);
const todoQueue = computed(() => leadsQuery.data.value?.todo_queue ?? []);
const highPurityCount = computed(() => leadsQuery.data.value?.tier_breakdown?.high_purity ?? 0);
const expandedCount = computed(() => leadsQuery.data.value?.tier_breakdown?.expanded ?? 0);
const projectCount = computed(() => leadsQuery.data.value?.kind_breakdown?.project ?? 0);
const contractRoleCount = computed(() => leadsQuery.data.value?.kind_breakdown?.contract_role ?? 0);
const reviewableCount = computed(() => projectCount.value + contractRoleCount.value);
const fullTimeJobCount = computed(() => leadsQuery.data.value?.kind_breakdown?.full_time_job ?? 0);
const watchingCount = computed(() => leadsQuery.data.value?.status_breakdown?.watching ?? 0);
const contactedCount = computed(() => leadsQuery.data.value?.status_breakdown?.contacted ?? 0);
const wonCount = computed(() => leadsQuery.data.value?.outcome_breakdown?.won ?? 0);
const noResponseCount = computed(() => leadsQuery.data.value?.outcome_breakdown?.no_response ?? 0);
const resolvedCount = computed(() =>
  (leadsQuery.data.value?.outcome_breakdown?.won ?? 0) +
  (leadsQuery.data.value?.outcome_breakdown?.lost ?? 0) +
  (leadsQuery.data.value?.outcome_breakdown?.no_response ?? 0) +
  (leadsQuery.data.value?.outcome_breakdown?.not_fit ?? 0)
);
const overallWinRate = computed(() => {
  if (resolvedCount.value === 0) return 0;
  return wonCount.value / resolvedCount.value;
});
const sourceConversionBreakdown = computed(
  () => leadsQuery.data.value?.source_conversion_breakdown ?? []
);
const segmentConversionBreakdown = computed(
  () => leadsQuery.data.value?.segment_conversion_breakdown ?? []
);
const highSeverityTodoCount = computed(() => leadsQuery.data.value?.todo_breakdown?.high ?? 0);
const mediumSeverityTodoCount = computed(() => leadsQuery.data.value?.todo_breakdown?.medium ?? 0);

watch([search, sourceId, statusFilter, outcomeFilter, queueView, leadKindView], () => {
  page.value = 1;
});

watch(
  () => detailsQuery.data.value,
  (value) => {
    notesDraft.value = value?.notes ?? '';
    outcomeDraft.value = value?.lead_outcome ?? null;
  },
  { immediate: true }
);

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

const leadOutcomeLabel = (outcome: NonNullable<MarketplaceLead['lead_outcome']>) =>
  t(`marketplace.filters.outcomeOptions.${outcome}`);

const leadOutcomeTagType = (outcome: NonNullable<MarketplaceLead['lead_outcome']>) => {
  if (outcome === 'won') return 'success';
  if (outcome === 'lost') return 'danger';
  if (outcome === 'no_response') return 'warning';
  return 'info';
};

const formatLeadEvent = (event: MarketplaceLeadEvent) => {
  if (event.event_type === 'captured') {
    return t('marketplace.activity.captured');
  }
  if (event.event_type === 'status_changed') {
    return t('marketplace.activity.statusChanged', {
      from: event.status_from ? leadStatusLabel(event.status_from) : '—',
      to: event.status_to ? leadStatusLabel(event.status_to) : '—'
    });
  }
  if (event.event_type === 'notes_updated') {
    return t('marketplace.activity.notesUpdated');
  }
  if (event.event_type === 'outcome_updated') {
    return t('marketplace.activity.outcomeUpdated', {
      from: event.outcome_from ? leadOutcomeLabel(event.outcome_from) : '—',
      to: event.outcome_to ? leadOutcomeLabel(event.outcome_to) : '—'
    });
  }
  return event.event_type;
};

const reminderTypeLabel = (value: MarketplaceLeadReminder['reminder_type']) =>
  t(`marketplace.todo.types.${value}`);

const reminderSeverityTagType = (value: MarketplaceLeadReminder['severity']) => {
  if (value === 'high') return 'danger';
  if (value === 'medium') return 'warning';
  return 'info';
};

const recommendationSeverityTagType = (value: MarketplaceSourceRecommendation['severity']) => {
  if (value === 'high') return 'danger';
  if (value === 'medium') return 'warning';
  return 'info';
};

const conversionSegmentLabel = (key: string, fallback: string) => {
  if (key.startsWith('tier:')) {
    const tier = key.slice(5) as MarketplaceLead['lead_tier'];
    return t(`marketplace.filters.queueOptions.${tier}`);
  }
  if (key.startsWith('kind:')) {
    const kind = key.slice(5) as MarketplaceLead['lead_kind'];
    return t(`marketplace.filters.leadKindOptions.${kind}`);
  }
  if (fallback.startsWith('queue:')) {
    const tier = fallback.slice(6) as MarketplaceLead['lead_tier'];
    return t(`marketplace.filters.queueOptions.${tier}`);
  }
  if (fallback.startsWith('kind:')) {
    const kind = fallback.slice(5) as MarketplaceLead['lead_kind'];
    return t(`marketplace.filters.leadKindOptions.${kind}`);
  }
  return fallback;
};

const handleStatusChange = (leadId: number, value: string) => {
  void statusMutation.mutate({
    leadId,
    status: value as MarketplaceLead['lead_status']
  });
};

const openLeadDetails = (leadId: number) => {
  selectedLeadId.value = leadId;
  detailsVisible.value = true;
};

const saveLeadNotes = () => {
  if (selectedLeadId.value === null) return;
  void notesMutation.mutate({
    leadId: selectedLeadId.value,
    notes: notesDraft.value.trim() || null
  });
};

const saveLeadOutcome = () => {
  if (selectedLeadId.value === null) return;
  void outcomeMutation.mutate({
    leadId: selectedLeadId.value,
    outcome: outcomeDraft.value
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

const formatPercent = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: 'percent',
    maximumFractionDigits: 0
  }).format(value);
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

.retrospective-summary {
  margin-top: 0;
  margin-bottom: 1rem;
}

.source-health-title {
  font-weight: 600;
  color: #0f172a;
}

.todo-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.todo-subtitle {
  margin-top: 0.3rem;
  font-size: 0.875rem;
  color: #64748b;
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.todo-item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.85rem;
  background: #f8fafc;
}

.todo-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.35rem;
}

.todo-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
}

.todo-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: #2563eb;
  font-size: 0.98rem;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.todo-link:hover {
  text-decoration: underline;
}

.todo-side {
  display: flex;
  min-width: 72px;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
}

.todo-empty {
  color: #64748b;
  font-size: 0.95rem;
}

.recommendation-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.recommendation-item {
  padding: 0.9rem 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.85rem;
  background: #f8fafc;
}

.recommendation-main {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.recommendation-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
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

.details-drawer {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.details-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.details-header h3 {
  margin: 0;
  color: #0f172a;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem 1.25rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.detail-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #64748b;
}

.details-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.detail-paragraph {
  margin: 0;
  line-height: 1.6;
  color: #0f172a;
  white-space: pre-wrap;
}

.priority-cell {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.priority-score {
  font-weight: 700;
  color: #0f172a;
}

.details-actions {
  display: flex;
  justify-content: flex-end;
}

.outcome-select {
  width: 240px;
}

.activity-timeline {
  margin-top: 0.75rem;
}

.timeline-title {
  color: #0f172a;
  font-weight: 600;
}

.timeline-note {
  margin-top: 0.35rem;
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

  .details-grid {
    grid-template-columns: 1fr;
  }

  .todo-header,
  .todo-item,
  .todo-title-row,
  .recommendation-title-row {
    flex-direction: column;
    align-items: stretch;
  }

  .todo-side {
    align-items: flex-start;
  }
}
</style>
