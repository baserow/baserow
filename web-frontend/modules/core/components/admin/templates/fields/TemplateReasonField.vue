<template>
  <div
    v-tooltip:[TOOLTIP_OPTIONS]="row.reason || null"
    class="templates-admin-reason"
  >
    {{ row.reason }}
  </div>
</template>

<script setup>
// The reasons are sentences, which don't fit in one line, and can hold a long
// word, such as a link, which must wrap too.
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
