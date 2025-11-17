<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>RSS 源管理</h1>
        <p>查看源状态、抓取频率与最近一次运行情况</p>
      </div>
      <div class="actions">
        <el-button>{{ t('actions.create') }}</el-button>
        <el-button type="primary">{{ t('actions.refresh') }}</el-button>
      </div>
    </header>
    <DataTable title="已配置数据源" :rows="sources">
      <template #actions>
        <el-input v-model="keyword" :placeholder="t('actions.search')" clearable />
      </template>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="category" label="分类" />
      <el-table-column prop="frequency" label="频率" />
      <el-table-column prop="status" label="状态" />
    </DataTable>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import DataTable from '../components/common/DataTable.vue';

const { t } = useI18n();
const keyword = ref('');

const mockSources = [
  { name: 'Product Hunt', category: '产品', frequency: '10m', status: 'active' },
  { name: '少数派', category: '社区', frequency: '30m', status: 'active' },
  { name: '脉脉热帖', category: '社区', frequency: '1h', status: 'paused' }
];

const sources = computed(() =>
  mockSources.filter((item) => item.name.toLowerCase().includes(keyword.value.toLowerCase()))
);
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

.actions {
  display: flex;
  gap: 0.5rem;
}
</style>
