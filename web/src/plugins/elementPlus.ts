import type { App } from 'vue';
import { ElButton } from 'element-plus/es/components/button/index';
import { ElCard } from 'element-plus/es/components/card/index';
import { ElCol } from 'element-plus/es/components/col/index';
import { ElDialog } from 'element-plus/es/components/dialog/index';
import { ElForm, ElFormItem } from 'element-plus/es/components/form/index';
import { ElInput } from 'element-plus/es/components/input/index';
import { ElInputNumber } from 'element-plus/es/components/input-number/index';
import { ElLink } from 'element-plus/es/components/link/index';
import { ElLoadingDirective } from 'element-plus/es/components/loading/index';
import { ElMenu, ElMenuItem } from 'element-plus/es/components/menu/index';
import { ElOption, ElSelect } from 'element-plus/es/components/select/index';
import { ElPagination } from 'element-plus/es/components/pagination/index';
import { ElProgress } from 'element-plus/es/components/progress/index';
import { ElRadioButton, ElRadioGroup } from 'element-plus/es/components/radio/index';
import { ElRow } from 'element-plus/es/components/row/index';
import { ElTable, ElTableColumn } from 'element-plus/es/components/table/index';
import { ElTag } from 'element-plus/es/components/tag/index';
import { ElTimeline, ElTimelineItem } from 'element-plus/es/components/timeline/index';
import { ElTooltip } from 'element-plus/es/components/tooltip/index';

import 'element-plus/es/components/button/style/css';
import 'element-plus/es/components/card/style/css';
import 'element-plus/es/components/col/style/css';
import 'element-plus/es/components/dialog/style/css';
import 'element-plus/es/components/form/style/css';
import 'element-plus/es/components/form-item/style/css';
import 'element-plus/es/components/input/style/css';
import 'element-plus/es/components/input-number/style/css';
import 'element-plus/es/components/link/style/css';
import 'element-plus/es/components/loading/style/css';
import 'element-plus/es/components/menu/style/css';
import 'element-plus/es/components/menu-item/style/css';
import 'element-plus/es/components/message/style/css';
import 'element-plus/es/components/option/style/css';
import 'element-plus/es/components/pagination/style/css';
import 'element-plus/es/components/progress/style/css';
import 'element-plus/es/components/radio-button/style/css';
import 'element-plus/es/components/radio-group/style/css';
import 'element-plus/es/components/row/style/css';
import 'element-plus/es/components/select/style/css';
import 'element-plus/es/components/table/style/css';
import 'element-plus/es/components/table-column/style/css';
import 'element-plus/es/components/tag/style/css';
import 'element-plus/es/components/timeline/style/css';
import 'element-plus/es/components/timeline-item/style/css';
import 'element-plus/es/components/tooltip/style/css';

const components = [
  ElButton,
  ElCard,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElLink,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElPagination,
  ElProgress,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTimeline,
  ElTimelineItem,
  ElTooltip,
];

export default {
  install(app: App) {
    components.forEach((component) => {
      app.component(component.name, component);
    });
    app.directive('loading', ElLoadingDirective);
  },
};
