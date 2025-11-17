<template>
  <el-card shadow="never">
    <div class="table-header">
      <div class="title">{{ title }}</div>
      <slot name="actions"></slot>
    </div>
    <el-table :data="rows" height="360px" empty-text="暂无数据">
      <slot />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{ title: string; rows: Record<string, unknown>[] }>();
</script>

<style scoped>
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.title {
  font-weight: 600;
}
</style>
