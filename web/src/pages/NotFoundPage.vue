<template>
  <section class="page">
    <h1>页面未找到</h1>
    <p>请检查链接或返回仪表盘</p>
    <router-link to="/">
      <el-button type="primary">返回</el-button>
    </router-link>
  </section>
</template>

<script setup lang="ts"></script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
