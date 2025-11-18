import type { Meta, StoryObj } from '@storybook/vue3';
import DataTable, { type DataTableColumn } from './DataTable.vue';

type AlertRow = {
  code: string;
  message: string;
  severity: 'info' | 'warning' | 'critical';
};

const rows: AlertRow[] = [
  { code: 'RSS_STALE', message: 'RSS 源 12 小时未更新', severity: 'warning' },
  { code: 'LLM_FAILURE', message: 'LLM 分析连续 3 次失败', severity: 'critical' },
  { code: 'EXPORT_QUEUE', message: '导出队列堆积 50 条待处理', severity: 'info' }
];

const columns: DataTableColumn<AlertRow>[] = [
  { label: '告警编码', prop: 'code', width: 140 },
  { label: '描述', prop: 'message', minWidth: 200 },
  { label: '等级', prop: 'severity', width: 120, slot: 'severity' }
];

const meta: Meta<typeof DataTable> = {
  title: 'Components/DataTable',
  component: DataTable,
  tags: ['autodocs'],
  argTypes: {
    refresh: { action: 'refresh' },
    'page-change': { action: 'page-change' },
    'page-size-change': { action: 'page-size-change' }
  },
  args: {
    title: '系统告警',
    rows,
    columns,
    refreshable: true,
    pagination: {
      currentPage: 1,
      pageSize: 10,
      total: 3
    }
  }
};

export default meta;

type Story = StoryObj<typeof DataTable>;

export const Default: Story = {};

export const WithCustomSeverity: Story = {
  render: (args) => ({
    components: { DataTable },
    setup() {
      return { args };
    },
    template: `
      <DataTable v-bind="args">
        <template #severity="{ row }">
          <el-tag :type="row.severity === 'critical' ? 'danger' : row.severity === 'warning' ? 'warning' : 'info'">
            {{ row.severity }}
          </el-tag>
        </template>
      </DataTable>
    `
  })
};
