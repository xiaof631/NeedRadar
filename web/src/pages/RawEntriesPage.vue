<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>原始内容列表</h1>
        <p>核对抓取结果、手动标记与批量导出</p>
      </div>
      <div class="actions">
        <el-input v-model="keyword" :placeholder="t('actions.search')" clearable />
        <el-button>{{ t('actions.export') }}</el-button>
      </div>
    </header>
    <el-table :data="entries" empty-text="暂无内容">
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="source" label="来源" />
      <el-table-column prop="status" label="状态" />
      <el-table-column prop="published_at" label="发布时间" />
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const keyword = ref('');

const mockEntries = [
  { title: 'OpenAI 发布新功能', source: 'Product Hunt', status: 'new', published_at: '10:00' },
  { title: '飞书推出 AI 套件', source: '少数派', status: 'processing', published_at: '09:15' }
];

const entries = computed(() =>
  mockEntries.filter((item) => item.title.toLowerCase().includes(keyword.value.toLowerCase()))
);
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.actions {
  display: flex;
  gap: 0.75rem;
}
</style>
