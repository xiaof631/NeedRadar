<template>
  <el-card class="filter-panel" shadow="never">
    <template #header>
      <div class="filter-panel__header">
        <div>
          <h3>{{ title }}</h3>
          <p v-if="description">{{ description }}</p>
        </div>
        <div class="filter-panel__actions">
          <el-tag v-if="activeFilters > 0 && activeText" type="info" effect="plain">
            {{ activeText }}
          </el-tag>
          <el-button v-if="clearable" text size="small" @click="$emit('clear')">
            {{ clearText }}
          </el-button>
          <el-button v-if="collapsible" text size="small" @click="collapsed = !collapsed">
            {{ collapsed ? expandText : collapseText }}
          </el-button>
        </div>
      </div>
    </template>
    <div v-show="!collapsed" class="filter-panel__content">
      <slot />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue';

withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    activeFilters?: number;
    activeText?: string;
    clearable?: boolean;
    clearText?: string;
    collapsible?: boolean;
    collapseText?: string;
    expandText?: string;
  }>(),
  {
    title: '',
    description: '',
    activeFilters: 0,
    activeText: '',
    clearable: false,
    clearText: '',
    collapsible: false,
    collapseText: '',
    expandText: ''
  }
);

defineEmits<{
  (event: 'clear'): void;
}>();

const collapsed = ref(false);
</script>

<style scoped>
.filter-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.filter-panel__header h3 {
  margin: 0;
  font-size: 1rem;
}

.filter-panel__header p {
  margin: 0.25rem 0 0;
  color: var(--nr-muted);
}

.filter-panel__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.filter-panel__content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
