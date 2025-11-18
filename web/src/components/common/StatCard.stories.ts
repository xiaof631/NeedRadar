import type { Meta, StoryObj } from '@storybook/vue3';
import StatCard from './StatCard.vue';

const meta: Meta<typeof StatCard> = {
  title: 'Components/StatCard',
  component: StatCard,
  tags: ['autodocs'],
  args: {
    label: '待处理需求',
    value: 128
  }
};

export default meta;

export type Story = StoryObj<typeof StatCard>;

export const Default: Story = {};

export const WithStringValue: Story = {
  args: {
    value: '42/100'
  }
};
