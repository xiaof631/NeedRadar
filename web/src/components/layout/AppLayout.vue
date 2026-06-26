<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">NeedRadar</div>
      <nav class="mobile-nav" aria-label="Primary">
        <router-link
          v-for="item in navItems"
          :key="item.index"
          :to="item.index"
          class="mobile-nav__item"
          :class="{ 'mobile-nav__item--active': isActive(item.index) }"
        >
          {{ t(item.labelKey) }}
        </router-link>
      </nav>
      <el-menu
        class="menu desktop-menu"
        :default-active="route.path"
        background-color="#0f172a"
        text-color="#cbd5e1"
        active-text-color="#f8fafc"
        router
      >
        <el-menu-item v-for="item in navItems" :key="item.index" :index="item.index">
          {{ t(item.labelKey) }}
        </el-menu-item>
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

const navItems = [
  { index: '/', labelKey: 'nav.dashboard' },
  { index: '/sources', labelKey: 'nav.sources' },
  { index: '/marketplace', labelKey: 'nav.marketplace' },
  { index: '/customer-radar', labelKey: 'nav.customerRadar' },
  { index: '/document-ops', labelKey: 'nav.documentOps' },
  { index: '/email-followups', labelKey: 'nav.emailFollowups' },
  { index: '/entries', labelKey: 'nav.entries' },
  { index: '/filter', labelKey: 'nav.filter' },
  { index: '/candidates', labelKey: 'nav.candidates' },
  { index: '/alerts', labelKey: 'nav.alerts' }
];

const isActive = (index: string) => {
  if (index === '/') {
    return route.path === '/';
  }
  return route.path === index || route.path.startsWith(`${index}/`);
};
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.sidebar {
  display: flex;
  flex-direction: column;
  background: #0f172a;
  color: #fff;
  padding: 1.5rem 1rem;
  min-height: 0;
  overflow-y: auto;
}

.logo {
  font-weight: 700;
  font-size: 1.25rem;
  margin-bottom: 1.5rem;
}

.mobile-nav {
  display: none;
}

.menu {
  background: transparent;
  border-right: none;
}

.menu :deep(.el-menu-item) {
  margin-bottom: 0.35rem;
  border-radius: 0.8rem;
  color: #cbd5e1;
  font-weight: 500;
}

.menu :deep(.el-menu-item:hover) {
  background: rgba(148, 163, 184, 0.16);
  color: #f8fafc;
}

.menu :deep(.el-menu-item.is-active) {
  background: rgba(59, 130, 246, 0.22);
  color: #f8fafc;
}

.content {
  padding: 1.5rem;
  background: #f5f6fb;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }

  .sidebar {
    gap: 0.9rem;
    padding: 1rem 1rem 0.8rem;
    overflow: hidden;
    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  }

  .logo {
    margin-bottom: 0;
    font-size: 1.1rem;
  }

  .desktop-menu {
    display: none;
  }

  .mobile-nav {
    display: flex;
    gap: 0.7rem;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 0.15rem;
    scrollbar-width: none;
    -ms-overflow-style: none;
    overscroll-behavior-x: contain;
  }

  .mobile-nav::-webkit-scrollbar {
    display: none;
  }

  .mobile-nav__item {
    flex: 0 0 auto;
    padding: 0.7rem 0.95rem;
    border-radius: 999px;
    background: rgba(148, 163, 184, 0.12);
    color: #cbd5e1;
    font-size: 0.92rem;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
    transition:
      background-color 0.2s ease,
      color 0.2s ease,
      transform 0.2s ease;
  }

  .mobile-nav__item:hover {
    background: rgba(148, 163, 184, 0.2);
    color: #f8fafc;
  }

  .mobile-nav__item--active {
    background: rgba(59, 130, 246, 0.24);
    color: #f8fafc;
  }

  .content {
    padding: 1rem;
  }
}
</style>
