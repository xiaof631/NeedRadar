import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import { createI18n } from 'vue-i18n';
import { createRouter, createWebHistory } from 'vue-router';
import ElementPlus from 'element-plus';
import App from '../src/App.vue';
import DashboardPage from '../src/pages/DashboardPage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', component: DashboardPage }]
});

describe('App', () => {
  it('renders navigation menu', async () => {
    await router.isReady();
    const wrapper = mount(App, {
      global: {
        plugins: [
          router,
          createTestingPinia({ createSpy: vi.fn }),
          createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': { nav: { dashboard: '仪表盘' } } } }),
          ElementPlus
        ]
      }
    });

    expect(wrapper.html()).toContain('仪表盘');
  });
});
