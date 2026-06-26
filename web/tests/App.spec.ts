import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import { createI18n } from 'vue-i18n';
import { createRouter, createMemoryHistory } from 'vue-router';
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query';
import App from '../src/App.vue';

describe('App', () => {
  it('renders navigation menu', async () => {
    const navRoutes = [
      '/',
      '/sources',
      '/marketplace',
      '/customer-radar',
      '/email-followups',
      '/entries',
      '/filter',
      '/candidates',
      '/alerts'
    ];
    const router = createRouter({
      history: createMemoryHistory(),
      routes: navRoutes.map((path) => ({
        path,
        component: { template: '<div>page</div>' }
      }))
    });

    await router.push('/');
    await router.isReady();

    const wrapper = mount(App, {
      global: {
        plugins: [
          router,
          createTestingPinia({ createSpy: vi.fn }),
          createI18n({
            legacy: false,
            locale: 'zh-CN',
            messages: {
              'zh-CN': {
                nav: {
                  dashboard: '仪表盘',
                  sources: '数据源',
                  marketplace: '外包项目线索',
                  customerRadar: '客户雷达',
                  emailFollowups: '邮件跟进',
                  entries: '原始内容',
                  filter: '筛选监控',
                  candidates: '候选需求',
                  alerts: '系统告警'
                }
              }
            }
          }),
          [
            VueQueryPlugin,
            {
              queryClient: new QueryClient({
                defaultOptions: {
                  queries: { retry: false }
                }
              })
            }
          ]
        ]
      }
    });

    expect(wrapper.html()).toContain('仪表盘');
  });
});
