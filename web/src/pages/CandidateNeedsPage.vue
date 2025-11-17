<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>候选需求工作台</h1>
        <p>统一管理评审状态、指派与导出</p>
      </div>
      <el-select v-model="status" placeholder="状态过滤" style="width: 200px">
        <el-option label="全部" value="all" />
        <el-option label="待评审" value="pending" />
        <el-option label="已通过" value="approved" />
      </el-select>
    </header>
    <el-table :data="filtered" empty-text="暂无候选需求">
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="score" label="规则得分" />
      <el-table-column prop="owner" label="负责人" />
      <el-table-column prop="status" label="状态" />
      <el-table-column label="操作">
        <template #default="{ row }">
          <el-button size="small" type="primary">通过</el-button>
          <el-button size="small" type="danger">拒绝</el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

const status = ref('all');
const needs = [
  { title: 'AI 笔记跨端同步', score: 0.85, owner: 'Lydia', status: 'pending' },
  { title: 'DevRel 数据报表', score: 0.65, owner: 'Aaron', status: 'approved' }
];

const filtered = computed(() =>
  status.value === 'all' ? needs : needs.filter((item) => item.status === status.value)
);
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
</style>
