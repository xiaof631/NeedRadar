<template>
  <el-card shadow="never" class="data-table">
    <div class="table-header">
      <div class="title">{{ title }}</div>
      <div class="actions" v-if="hasToolbar">
        <slot name="actions">
          <el-button
            v-if="refreshable"
            size="small"
            :loading="loading"
            @click="handleRefresh"
            type="primary"
          >
            {{ refreshText }}
          </el-button>
        </slot>
      </div>
    </div>
    <el-table :data="rows" height="360px" :empty-text="emptyText" :v-loading="loading">
      <template v-if="columns?.length">
        <el-table-column
          v-for="column in columns"
          :key="column.key ?? column.prop ?? column.label"
          :prop="column.prop"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
          :align="column.align"
        >
          <template v-if="column.slot && $slots[column.slot]" #default="scope">
            <slot :name="column.slot" v-bind="scope" />
          </template>
          <template v-else-if="column.formatter" #default="{ row }">
            {{ column.formatter(row) }}
          </template>
        </el-table-column>
      </template>
      <slot v-else />
    </el-table>
    <div v-if="pagination" class="table-footer">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :page-sizes="pagination.pageSizes ?? [10, 20, 50]"
        :total="pagination.total"
        :current-page="pagination.currentPage"
        :page-size="pagination.pageSize"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, useSlots } from 'vue';

export type DataTableColumn<RowType = Record<string, unknown>> = {
  key?: string;
  prop?: keyof RowType | string;
  label: string;
  width?: number | string;
  minWidth?: number | string;
  align?: 'left' | 'center' | 'right';
  formatter?: (row: RowType) => string | number;
  slot?: string;
};

export type DataTablePagination = {
  currentPage: number;
  pageSize: number;
  total: number;
  pageSizes?: number[];
};

const props = withDefaults(
  defineProps<{
    title: string;
    rows: Record<string, unknown>[];
    columns?: DataTableColumn[];
    loading?: boolean;
    pagination?: DataTablePagination;
    emptyText?: string;
    refreshable?: boolean;
    refreshText?: string;
  }>(),
  {
    loading: false,
    emptyText: '暂无数据',
    refreshable: false,
    refreshText: '刷新'
  }
);

const emit = defineEmits<{
  (event: 'refresh'): void;
  (event: 'page-change', page: number): void;
  (event: 'page-size-change', size: number): void;
}>();

const slots = useSlots();
const hasToolbar = computed(() => props.refreshable || Boolean(slots.actions));

const handleRefresh = () => emit('refresh');
const handlePageChange = (page: number) => emit('page-change', page);
const handleSizeChange = (size: number) => emit('page-size-change', size);
</script>

<style scoped>
.data-table {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-weight: 600;
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.table-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
