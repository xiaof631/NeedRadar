<template>
  <el-card shadow="hover" class="stat-card">
    <div class="label">{{ label }}</div>
    <div class="value">{{ value }}</div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{ label: string; value: number | string }>();
</script>

<style scoped>
.stat-card {
  text-align: left;
}

.label {
  font-size: 0.9rem;
  color: #6b7280;
}

.value {
  font-size: 2rem;
  font-weight: 600;
}
</style>
