<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>筛选流程监控</h1>
        <p>规则命中率、LLM 成功率与整体耗时</p>
      </div>
      <el-date-picker v-model="range" type="daterange" unlink-panels />
    </header>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <h3>规则命中率</h3>
          <el-progress :percentage="72" :stroke-width="18" status="success" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <h3>LLM 成功率</h3>
          <el-progress :percentage="88" :stroke-width="18" />
        </el-card>
      </el-col>
    </el-row>
    <el-card>
      <template #header>
        <div class="title">数据源命中统计</div>
      </template>
      <el-table :data="stats">
        <el-table-column prop="source" label="数据源" />
        <el-table-column prop="rules" label="规则命中" />
        <el-table-column prop="llm" label="LLM 通过" />
        <el-table-column prop="conversion" label="转化率" />
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const range = ref<[Date, Date] | null>(null);

const stats = [
  { source: 'Product Hunt', rules: 42, llm: 18, conversion: '42.8%' },
  { source: 'V2EX', rules: 30, llm: 9, conversion: '30.0%' }
];
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

.title {
  font-weight: 600;
}
</style>
