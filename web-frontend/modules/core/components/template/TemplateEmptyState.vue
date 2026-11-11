<template>
  <div class="template-empty-state">
    <div class="template-empty-state__icon">
      <i :class="searched ? 'iconoir-search' : icon"></i>
    </div>
    <div class="template-empty-state__title">
      {{ searched ? $t('templateEmptyState.noResultsTitle') : title }}
    </div>
    <div class="template-empty-state__description">
      {{
        searched
          ? $t('templateEmptyState.noResultsDescription', { query })
          : description
      }}
    </div>
    <div v-if="$slots.default" class="template-empty-state__actions">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  // The search that found nothing. When given, the state explains that nothing
  // matches it instead of showing the icon, title and description.
  query: {
    type: String,
    required: false,
    default: '',
  },
  icon: {
    type: String,
    required: false,
    default: 'iconoir-box',
  },
  title: {
    type: String,
    required: false,
    default: '',
  },
  description: {
    type: String,
    required: false,
    default: '',
  },
})

const searched = computed(() => props.query !== '')
</script>
