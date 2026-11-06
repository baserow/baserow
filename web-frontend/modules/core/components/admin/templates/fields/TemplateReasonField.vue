<template>
  <div
    v-tooltip:[TOOLTIP_OPTIONS]="row.reason || null"
    class="templates-admin-reason"
  >
    {{ row.reason }}
  </div>
</template>

<script setup>
// Reasons are sentences and can hold a long link, so they wrap anywhere.
const TOOLTIP_OPTIONS = {
  contentClasses: [
    'tooltip__content--expandable',
    'templates-admin-reason__tooltip',
  ],
}

defineProps({
  row: {
    type: Object,
    required: true,
  },
})
</script>
