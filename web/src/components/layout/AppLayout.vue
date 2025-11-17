<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">NeedRadar</div>
      <el-menu class="menu" :default-active="route.path" router>
        <el-menu-item index="/">{{ t('nav.dashboard') }}</el-menu-item>
        <el-menu-item index="/sources">{{ t('nav.sources') }}</el-menu-item>
        <el-menu-item index="/entries">{{ t('nav.entries') }}</el-menu-item>
        <el-menu-item index="/filter">{{ t('nav.filter') }}</el-menu-item>
        <el-menu-item index="/candidates">{{ t('nav.candidates') }}</el-menu-item>
        <el-menu-item index="/alerts">{{ t('nav.alerts') }}</el-menu-item>
      </el-menu>
    </aside>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';

const route = useRoute();
const { t } = useI18n();
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}

.sidebar {
  background: #0f172a;
  color: #fff;
  padding: 1.5rem 1rem;
}

.logo {
  font-weight: 700;
  font-size: 1.25rem;
  margin-bottom: 1.5rem;
}

.menu {
  background: transparent;
}

.content {
  padding: 1.5rem;
  background: #f5f6fb;
}
</style>
