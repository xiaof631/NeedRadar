<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1>系统告警与操作日志</h1>
        <p>追踪任务失败、队列堆积等异常事件</p>
      </div>
      <el-button type="primary">告警规则</el-button>
    </header>
    <el-timeline>
      <el-timeline-item
        v-for="alert in alerts"
        :key="alert.id"
        :timestamp="alert.timestamp"
        :type="alert.type"
      >
        {{ alert.message }}
      </el-timeline-item>
    </el-timeline>
  </section>
</template>

<script setup lang="ts">
const alerts = [
  { id: 1, message: 'Product Hunt 抓取失败 3 次', timestamp: '09:00', type: 'warning' },
  { id: 2, message: '候选需求 Webhook 返回 500', timestamp: '09:15', type: 'danger' }
];
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
</style>
