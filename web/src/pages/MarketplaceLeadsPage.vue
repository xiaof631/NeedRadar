<template>
  <section class="page">
    <div class="page-banner">
      <h1 class="page-title">{{ t('marketplace.title') }}</h1>
      <p class="page-description">{{ t('marketplace.subtitle') }}</p>
    </div>
    <header class="page-header">
      <div class="actions">
        <el-radio-group v-model="queueView" size="small">
          <el-radio-button value="high_purity">
            {{ t('marketplace.filters.queueOptions.high_purity') }}
          </el-radio-button>
          <el-radio-button value="expanded">
            {{ t('marketplace.filters.queueOptions.expanded') }}
          </el-radio-button>
          <el-radio-button value="all">
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
        <el-select v-model="followUpFilter" class="status-select" :placeholder="t('marketplace.filters.followUp')">
          <el-option :label="t('marketplace.filters.followUpOptions.all')" value="all" />
          <el-option :label="t('marketplace.filters.followUpOptions.overdue')" value="overdue" />
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
        <el-select v-model="budgetBandFilter" class="profile-select" :placeholder="t('marketplace.filters.budgetBand')">
          <el-option :label="t('marketplace.filters.budgetBandOptions.all')" value="all" />
          <el-option
            v-for="option in budgetBandOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select
          v-model="deliveryScopeFilter"
          class="profile-select"
          :placeholder="t('marketplace.filters.deliveryScope')"
        >
          <el-option :label="t('marketplace.filters.deliveryScopeOptions.all')" value="all" />
          <el-option
            v-for="option in deliveryScopeOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="techStackFilter" class="profile-select" :placeholder="t('marketplace.filters.techStack')">
          <el-option :label="t('marketplace.filters.techStackOptions.all')" value="all" />
          <el-option
            v-for="option in techStackOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="regionFilter" class="profile-select" :placeholder="t('marketplace.filters.region')">
          <el-option :label="t('marketplace.filters.regionOptions.all')" value="all" />
          <el-option
            v-for="option in regionOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select
          v-model="timezoneFitFilter"
          class="profile-select"
          :placeholder="t('marketplace.filters.timezoneFit')"
        >
          <el-option :label="t('marketplace.filters.timezoneFitOptions.all')" value="all" />
          <el-option :label="t('marketplace.filters.timezoneFitOptions.fit')" value="fit" />
          <el-option :label="t('marketplace.filters.timezoneFitOptions.unfit')" value="unfit" />
        </el-select>
        <el-select
          v-model="bulkOutcomeDraft"
          class="status-select"
          :placeholder="t('marketplace.bulk.outcomePlaceholder')"
        >
          <el-option
            v-for="option in leadOutcomeOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select
          v-model="bulkReasonTagsDraft"
          class="reason-select"
          multiple
          filterable
          allow-create
          default-first-option
          collapse-tags
          collapse-tags-tooltip
          :placeholder="t('marketplace.bulk.reasonPlaceholder')"
        />
        <el-button
          type="success"
          :disabled="!selectedLeadIds.length || !bulkOutcomeDraft"
          :loading="bulkOutcomeMutation.isPending.value"
          @click="applyBulkOutcome"
        >
          {{ t('marketplace.bulk.apply', { count: selectedLeadIds.length }) }}
        </el-button>
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
          <div class="todo-header-actions">
            <div class="todo-sort-group">
              <button
                v-for="opt in sortOptions"
                :key="opt.value"
                class="todo-sort-btn"
                :class="{ active: todoSort === opt.value }"
                @click="todoSort = opt.value"
              >{{ opt.label }}</button>
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
      <template #header>
        <div class="source-health-title">{{ t('marketplace.reasonBreakdown.title') }}</div>
      </template>
      <div v-if="topOutcomeReasons.length" class="tag-list">
        <el-tag
          v-for="item in topOutcomeReasons"
          :key="item.reason"
          size="small"
          effect="plain"
          type="warning"
        >
          {{ item.reason }} × {{ item.count }}
        </el-tag>
      </div>
      <div v-else class="todo-empty">{{ t('marketplace.reasonBreakdown.empty') }}</div>
    </el-card>

    <el-card shadow="never">
      <el-table
        ref="leadsTableRef"
        :data="leads"
        row-key="id"
        v-loading="leadsQuery.isFetching.value"
        :empty-text="t('marketplace.table.empty')"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" reserve-selection />
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
        <el-table-column :label="t('marketplace.table.profile')" min-width="240">
          <template #default="{ row }">
            <div class="tag-list">
              <el-tag v-if="row.budget_band" size="small" effect="plain">
                {{ budgetBandLabel(row.budget_band) }}
              </el-tag>
              <el-tag v-if="row.delivery_scope" size="small" effect="plain" type="success">
                {{ deliveryScopeLabel(row.delivery_scope) }}
              </el-tag>
              <el-tag v-if="row.region" size="small" effect="plain" type="warning">
                {{ regionLabel(row.region) }}
              </el-tag>
              <el-tag
                v-if="row.timezone_fit !== null"
                size="small"
                effect="plain"
                :type="row.timezone_fit ? 'success' : 'danger'"
              >
                {{ timezoneFitLabel(row.timezone_fit) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.skills')" min-width="220">
          <template #default="{ row }">
            <div class="tag-list">
              <el-tag
                v-for="stack in row.tech_stack_normalized.slice(0, 3)"
                :key="`stack-${stack}`"
                size="small"
                effect="plain"
                type="success"
              >
                {{ stack }}
              </el-tag>
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
        <el-table-column :label="t('marketplace.table.lastActionAt')" width="190">
          <template #default="{ row }">{{ formatDate(row.last_action_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.nextFollowUp')" width="220">
          <template #default="{ row }">
            <div>{{ formatDate(row.next_follow_up_at) }}</div>
            <div v-if="row.follow_up_reason" class="summary-text">
              {{ followUpReasonLabel(row.follow_up_reason) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.followUpState')" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.is_follow_up_overdue" type="danger" effect="plain">
              {{ t('marketplace.table.followUpOverdue') }}
            </el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('marketplace.table.latestSeenAt')" width="190">
          <template #default="{ row }">{{ formatDate(row.latest_seen_at) }}</template>
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
              <span class="detail-label">{{ t('marketplace.details.budgetBand') }}</span>
              <span>{{ selectedLead.budget_band ? budgetBandLabel(selectedLead.budget_band) : '—' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.timeline') }}</span>
              <span>{{ selectedLead.normalized_timeline || selectedLead.timeline || '—' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.deliveryScope') }}</span>
              <span>
                {{ selectedLead.delivery_scope ? deliveryScopeLabel(selectedLead.delivery_scope) : '—' }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.region') }}</span>
              <span>{{ selectedLead.region ? regionLabel(selectedLead.region) : '—' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.timezoneFit') }}</span>
              <span>
                {{
                  selectedLead.timezone_fit === null
                    ? '—'
                    : timezoneFitLabel(selectedLead.timezone_fit)
                }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.published') }}</span>
              <span>{{ formatDate(selectedLead.published_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.latestSeenAt') }}</span>
              <span>{{ formatDate(selectedLead.latest_seen_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.firstSeenAt') }}</span>
              <span>{{ formatDate(selectedLead.first_seen_at) }}</span>
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
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.nextFollowUp') }}</span>
              <span>{{ formatDate(selectedLead.next_follow_up_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ t('marketplace.details.followUpState') }}</span>
              <span>
                {{
                  selectedLead.is_follow_up_overdue
                    ? t('marketplace.table.followUpOverdue')
                    : selectedLead.follow_up_reason
                      ? followUpReasonLabel(selectedLead.follow_up_reason)
                      : '—'
                }}
              </span>
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
            <el-select
              v-model="outcomeReasonDraft"
              class="outcome-select"
              multiple
              filterable
              allow-create
              default-first-option
              collapse-tags
              collapse-tags-tooltip
              :placeholder="t('marketplace.details.outcomeReasonPlaceholder')"
            />
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

          <div class="details-section">
            <div class="detail-label">{{ t('marketplace.details.followUpSchedule') }}</div>
            <input
              v-model="followUpDraft"
              class="native-datetime-input"
              type="datetime-local"
            />
            <el-input
              v-model="followUpReasonDraft"
              :placeholder="t('marketplace.details.followUpReasonPlaceholder')"
            />
            <div class="details-actions">
              <el-button
                type="primary"
                size="small"
                :loading="followUpMutation.isPending.value"
                @click="saveLeadFollowUp"
              >
                {{ t('marketplace.details.saveFollowUp') }}
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

          <div v-if="selectedLead.tech_stack_normalized.length" class="details-section">
            <div class="detail-label">{{ t('marketplace.details.techStack') }}</div>
            <div class="tag-list">
              <el-tag
                v-for="stack in selectedLead.tech_stack_normalized"
                :key="stack"
                size="small"
                effect="plain"
                type="success"
              >
                {{ stack }}
              </el-tag>
            </div>
          </div>

          <div v-if="selectedLead.outcome_reason_tags.length" class="details-section">
            <div class="detail-label">{{ t('marketplace.details.outcomeReasons') }}</div>
            <div class="tag-list">
              <el-tag
                v-for="reason in selectedLead.outcome_reason_tags"
                :key="reason"
                size="small"
                effect="plain"
                type="warning"
              >
                {{ reason }}
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

          <div class="details-section history-grid">
            <div>
              <div class="detail-label">{{ t('marketplace.activity.notesHistory') }}</div>
              <div v-if="notesHistory.length" class="history-list">
                <div v-for="event in notesHistory" :key="`${event.created_at}-${event.note || ''}`" class="history-item">
                  <div class="summary-text">{{ formatDate(event.created_at) }}</div>
                  <p class="detail-paragraph">{{ event.note || '—' }}</p>
                </div>
              </div>
              <p v-else class="detail-paragraph">{{ t('marketplace.activity.emptyNotesHistory') }}</p>
            </div>
            <div>
              <div class="detail-label">{{ t('marketplace.activity.outcomeHistory') }}</div>
              <div v-if="outcomeHistory.length" class="history-list">
                <div
                  v-for="event in outcomeHistory"
                  :key="`${event.created_at}-${event.outcome_to || ''}-${event.note || ''}`"
                  class="history-item"
                >
                  <div class="summary-text">{{ formatDate(event.created_at) }}</div>
                  <p class="detail-paragraph">{{ formatLeadEvent(event) }}</p>
                  <p v-if="event.note" class="detail-paragraph timeline-note">{{ event.note }}</p>
                </div>
              </div>
              <p v-else class="detail-paragraph">{{ t('marketplace.activity.emptyOutcomeHistory') }}</p>
            </div>
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
  bulkUpdateMarketplaceLeadOutcome,
  fetchMarketplaceLead,
  fetchMarketplaceLeads,
  fetchRssSources,
  updateMarketplaceLeadFollowUp,
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
const followUpFilter = ref<'all' | 'overdue'>('all');
const budgetBandFilter = ref<'all' | NonNullable<MarketplaceLead['budget_band']>>('all');
const deliveryScopeFilter = ref<'all' | NonNullable<MarketplaceLead['delivery_scope']>>('all');
const techStackFilter = ref<'all' | string>('all');
const regionFilter = ref<'all' | NonNullable<MarketplaceLead['region']>>('all');
const timezoneFitFilter = ref<'all' | 'fit' | 'unfit'>('all');
const queueView = ref<'high_purity' | 'expanded' | 'all'>('high_purity');
const leadKindView = ref<'reviewable' | 'project' | 'contract_role' | 'full_time_job' | 'all'>('reviewable');
const todoSort = ref<'default' | 'newest_first' | 'oldest_first' | 'priority'>('default');

const sortOptions = computed<{ value: typeof todoSort['value']; label: string }[]>(() => [
  { value: 'default', label: t('marketplace.sort.default') },
  { value: 'newest_first', label: t('marketplace.sort.newestFirst') },
  { value: 'oldest_first', label: t('marketplace.sort.oldestFirst') },
  { value: 'priority', label: t('marketplace.sort.priority') },
]);
const detailsVisible = ref(false);
const selectedLeadId = ref<number | null>(null);
const leadsTableRef = ref<{ clearSelection?: () => void } | null>(null);
const selectedLeadIds = ref<number[]>([]);
const notesDraft = ref('');
const outcomeDraft = ref<MarketplaceLead['lead_outcome']>(null);
const outcomeReasonDraft = ref<string[]>([]);
const followUpDraft = ref('');
const followUpReasonDraft = ref('');
const bulkOutcomeDraft = ref<NonNullable<MarketplaceLead['lead_outcome']> | null>(null);
const bulkReasonTagsDraft = ref<string[]>([]);

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

const budgetBandOptions = computed(() => [
  { value: 'lt_1k' as const, label: t('marketplace.filters.budgetBandOptions.band_lt_1k') },
  { value: '1k_5k' as const, label: t('marketplace.filters.budgetBandOptions.band_1k_5k') },
  { value: '5k_20k' as const, label: t('marketplace.filters.budgetBandOptions.band_5k_20k') },
  { value: 'gt_20k' as const, label: t('marketplace.filters.budgetBandOptions.band_gt_20k') },
  { value: 'negotiable' as const, label: t('marketplace.filters.budgetBandOptions.band_negotiable') }
]);

const deliveryScopeOptions = computed(() => [
  { value: 'website' as const, label: t('marketplace.filters.deliveryScopeOptions.website') },
  { value: 'app' as const, label: t('marketplace.filters.deliveryScopeOptions.app') },
  { value: 'backend' as const, label: t('marketplace.filters.deliveryScopeOptions.backend') },
  { value: 'plugin' as const, label: t('marketplace.filters.deliveryScopeOptions.plugin') },
  { value: 'automation' as const, label: t('marketplace.filters.deliveryScopeOptions.automation') },
  { value: 'data_tool' as const, label: t('marketplace.filters.deliveryScopeOptions.data_tool') },
  { value: 'embedded' as const, label: t('marketplace.filters.deliveryScopeOptions.embedded') }
]);

const regionOptions = computed(() => [
  { value: 'china' as const, label: t('marketplace.filters.regionOptions.china') },
  { value: 'apac' as const, label: t('marketplace.filters.regionOptions.apac') },
  {
    value: 'europe_americas' as const,
    label: t('marketplace.filters.regionOptions.europe_americas')
  },
  { value: 'global' as const, label: t('marketplace.filters.regionOptions.global') }
]);

const techStackOptions = computed(() =>
  [
    'react',
    'nextjs',
    'vue',
    'angular',
    'typescript',
    'javascript',
    'nodejs',
    'python',
    'django',
    'fastapi',
    'flask',
    'php',
    'laravel',
    'wordpress',
    'java',
    'spring',
    'go',
    'dotnet',
    'postgres',
    'mysql',
    'mongodb',
    'docker',
    'kubernetes',
    'graphql',
    'android',
    'ios',
    'flutter',
    'react_native',
    'shopify',
    'webflow',
    'llm'
  ].map((value) => ({ value, label: value }))
);

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
  budget_band: budgetBandFilter.value === 'all' ? undefined : budgetBandFilter.value,
  delivery_scope: deliveryScopeFilter.value === 'all' ? undefined : deliveryScopeFilter.value,
  tech_stack: techStackFilter.value === 'all' ? undefined : techStackFilter.value,
  region: regionFilter.value === 'all' ? undefined : regionFilter.value,
  timezone_fit:
    timezoneFitFilter.value === 'fit' ? true : timezoneFitFilter.value === 'unfit' ? false : undefined,
  reviewable_only: leadKindView.value === 'reviewable' ? true : undefined,
  overdue_only: followUpFilter.value === 'overdue' ? true : undefined,
  lead_status: statusFilter.value === 'all' ? undefined : statusFilter.value,
  lead_outcome: outcomeFilter.value === 'all' ? undefined : outcomeFilter.value,
  todo_sort: todoSort.value
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

const followUpMutation = useMutation({
  mutationFn: ({
    leadId,
    nextFollowUpAt,
    followUpReason
  }: {
    leadId: number;
    nextFollowUpAt: string | null;
    followUpReason: string | null;
  }) => updateMarketplaceLeadFollowUp(leadId, nextFollowUpAt, followUpReason),
  onSuccess: async (lead) => {
    followUpDraft.value = toDatetimeLocal(lead.next_follow_up_at);
    followUpReasonDraft.value = lead.follow_up_reason ?? '';
    ElMessage.success(t('marketplace.feedback.followUpUpdated'));
    await Promise.all([leadsQuery.refetch(), detailsQuery.refetch()]);
  },
  onError: () => {
    ElMessage.error(t('feedback.genericError'));
  }
});

const outcomeMutation = useMutation({
  mutationFn: ({
    leadId,
    outcome,
    reasonTags
  }: {
    leadId: number;
    outcome: MarketplaceLead['lead_outcome'];
    reasonTags: string[];
  }) => updateMarketplaceLeadOutcome(leadId, outcome, reasonTags),
  onSuccess: async (lead) => {
    outcomeDraft.value = lead.lead_outcome;
    outcomeReasonDraft.value = lead.outcome_reason_tags;
    ElMessage.success(t('marketplace.feedback.outcomeUpdated'));
    await Promise.all([leadsQuery.refetch(), detailsQuery.refetch()]);
  },
  onError: () => {
    ElMessage.error(t('feedback.genericError'));
  }
});

const bulkOutcomeMutation = useMutation({
  mutationFn: ({
    leadIds,
    outcome,
    reasonTags
  }: {
    leadIds: number[];
    outcome: NonNullable<MarketplaceLead['lead_outcome']>;
    reasonTags: string[];
  }) => bulkUpdateMarketplaceLeadOutcome(leadIds, outcome, reasonTags),
  onSuccess: async (_, variables) => {
    ElMessage.success(
      t('marketplace.feedback.bulkOutcomeUpdated', {
        count: variables.leadIds.length
      })
    );
    selectedLeadIds.value = [];
    bulkOutcomeDraft.value = null;
    bulkReasonTagsDraft.value = [];
    leadsTableRef.value?.clearSelection?.();
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
const notesHistory = computed(() =>
  (selectedLead.value?.lead_events ?? []).filter((event) => event.event_type === 'notes_updated')
);
const outcomeHistory = computed(() =>
  (selectedLead.value?.lead_events ?? []).filter((event) =>
    ['outcome_updated', 'follow_up_scheduled'].includes(event.event_type)
  )
);
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
const topOutcomeReasons = computed(() =>
  Object.entries(leadsQuery.data.value?.outcome_reason_breakdown ?? {})
    .slice(0, 8)
    .map(([reason, count]) => ({ reason, count }))
);
const highSeverityTodoCount = computed(() => leadsQuery.data.value?.todo_breakdown?.high ?? 0);
const mediumSeverityTodoCount = computed(() => leadsQuery.data.value?.todo_breakdown?.medium ?? 0);

watch(
  [
    search,
    sourceId,
    statusFilter,
    outcomeFilter,
    followUpFilter,
    budgetBandFilter,
    deliveryScopeFilter,
    techStackFilter,
    regionFilter,
    timezoneFitFilter,
    queueView,
    leadKindView
  ],
  () => {
    page.value = 1;
  }
);

watch(
  () => detailsQuery.data.value,
  (value) => {
    notesDraft.value = value?.notes ?? '';
    outcomeDraft.value = value?.lead_outcome ?? null;
    outcomeReasonDraft.value = value?.outcome_reason_tags ?? [];
    followUpDraft.value = toDatetimeLocal(value?.next_follow_up_at ?? null);
    followUpReasonDraft.value = value?.follow_up_reason ?? '';
  },
  { immediate: true }
);

const handlePageChange = (value: number) => {
  page.value = value;
};

const handleSelectionChange = (rows: MarketplaceLead[]) => {
  selectedLeadIds.value = rows.map((row) => row.id);
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
  return 'info';
};

const leadStatusLabel = (status: MarketplaceLead['lead_status']) =>
  t(`marketplace.filters.statusOptions.${status}`);

const leadOutcomeLabel = (outcome: NonNullable<MarketplaceLead['lead_outcome']>) =>
  t(`marketplace.filters.outcomeOptions.${outcome}`);

const budgetBandLabel = (value: NonNullable<MarketplaceLead['budget_band']>) =>
  t(`marketplace.filters.budgetBandOptions.band_${value}`);

const deliveryScopeLabel = (value: NonNullable<MarketplaceLead['delivery_scope']>) =>
  t(`marketplace.filters.deliveryScopeOptions.${value}`);

const regionLabel = (value: NonNullable<MarketplaceLead['region']>) =>
  t(`marketplace.filters.regionOptions.${value}`);

const timezoneFitLabel = (value: boolean) =>
  value ? t('marketplace.filters.timezoneFitOptions.fit') : t('marketplace.filters.timezoneFitOptions.unfit');

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
  if (event.event_type === 'follow_up_scheduled') {
    return t('marketplace.activity.followUpScheduled');
  }
  return event.event_type;
};

const followUpReasonLabel = (reason: string) => {
  const normalized = reason.trim().toLowerCase();
  if (normalized === 'watching_checkin' || normalized === 'contacted_follow_up') {
    return t(`marketplace.followUpReasons.${normalized}`);
  }
  return reason;
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

const applyBulkOutcome = () => {
  if (!selectedLeadIds.value.length || !bulkOutcomeDraft.value) return;
  void bulkOutcomeMutation.mutate({
    leadIds: selectedLeadIds.value,
    outcome: bulkOutcomeDraft.value,
    reasonTags: bulkReasonTagsDraft.value
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
    outcome: outcomeDraft.value,
    reasonTags: outcomeReasonDraft.value
  });
};

const saveLeadFollowUp = () => {
  if (selectedLeadId.value === null) return;
  void followUpMutation.mutate({
    leadId: selectedLeadId.value,
    nextFollowUpAt: fromDatetimeLocal(followUpDraft.value),
    followUpReason: followUpReasonDraft.value.trim() || null
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

function toDatetimeLocal(value: string | null) {
  if (!value) return '';
  const date = new Date(value);
  const pad = (input: number) => String(input).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromDatetimeLocal(value: string) {
  if (!value) return null;
  return new Date(value).toISOString();
}

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

.page-banner {
  padding-bottom: 0.25rem;
}

.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.page-description {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  color: #64748b;
  line-height: 1.5;
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
.kind-select,
.profile-select,
.reason-select {
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
  align-items: center;
  gap: 1rem;
}

.todo-header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.todo-sort-group {
  display: flex;
  gap: 0;
  background: #f1f5f9;
  border-radius: 0.5rem;
  padding: 3px;
}

.todo-sort-btn {
  padding: 0.35rem 0.85rem;
  font-size: 0.825rem;
  color: #64748b;
  background: transparent;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}

.todo-sort-btn:hover {
  color: #334155;
  background: #e2e8f0;
}

.todo-sort-btn.active {
  background: #fff;
  color: #1d4ed8;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
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
  padding: 0.85rem 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.todo-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 2rem;
  padding: 0.1rem 0.5rem;
  font-size: 0.8125rem;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 999px;
  line-height: 1.5;
}

.todo-side .priority-score {
  font-size: 0.85rem;
  min-width: 2.25rem;
  padding: 0.15rem 0.6rem;
}

.details-actions {
  display: flex;
  justify-content: flex-end;
}

.outcome-select {
  width: 240px;
}

.native-datetime-input {
  width: 240px;
  padding: 0.625rem 0.75rem;
  border: 1px solid #d0d7de;
  border-radius: 0.5rem;
  font: inherit;
  color: #0f172a;
}

.native-datetime-input:focus {
  outline: 2px solid rgba(37, 99, 235, 0.2);
  border-color: #2563eb;
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

.history-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.history-item {
  padding: 0.75rem 0.85rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  background: #f8fafc;
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
  .kind-select,
.profile-select,
  .reason-select {
    width: 100%;
  }

  .details-grid {
    grid-template-columns: 1fr;
  }

  .history-grid {
    grid-template-columns: 1fr;
  }

  .todo-header,
  .todo-header-actions,
  .todo-item,
  .todo-title-row,
  .recommendation-title-row {
    flex-direction: column;
    align-items: stretch;
  }

  .todo-sort-group {
    width: 100%;
  }

  .todo-sort-btn {
    flex: 1;
  }

  .todo-side {
    align-items: flex-start;
  }
}
</style>
