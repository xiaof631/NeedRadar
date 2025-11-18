import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import SyncChannelBreakdownCard from '../../src/components/analytics/SyncChannelBreakdownCard.vue';
import { createI18n } from 'vue-i18n';
import zh from '../../src/locales/zh-CN.json';

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: { 'zh-CN': zh }
});

describe('SyncChannelBreakdownCard', () => {
  const stats = [
    {
      channel: 'webhook',
      total_attempts: 3,
      success: 2,
      failed: 1,
      pending: 0,
      success_rate: 0.66,
      last_attempt_at: new Date().toISOString(),
      last_error: 'timeout'
    },
    {
      channel: 'file_drop',
      total_attempts: 0,
      success: 0,
      failed: 0,
      pending: 0,
      success_rate: 0,
      last_attempt_at: null,
      last_error: null
    }
  ];

  it('renders stats table with channel labels', () => {
    const wrapper = mount(SyncChannelBreakdownCard, {
      props: { stats },
      global: { plugins: [i18n] }
    });

    expect(wrapper.text()).toContain('Webhook');
    expect(wrapper.text()).toContain('文件同步');
    expect(wrapper.text()).toContain('66%');
    expect(wrapper.text()).toContain('timeout');
  });

  it('emits select event when row is clicked', async () => {
    const wrapper = mount(SyncChannelBreakdownCard, {
      props: { stats },
      global: { plugins: [i18n] }
    });

    await wrapper.findComponent({ name: 'ElTable' }).vm.$emit('row-click', stats[0]);
    expect(wrapper.emitted('select')?.[0]).toEqual(['webhook']);
  });
});
