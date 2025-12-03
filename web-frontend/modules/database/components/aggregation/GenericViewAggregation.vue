<template>
  <div class="grid-view-aggregation__generic">
    <span class="grid-view-aggregation__generic-name">
      {{ aggregationType.getShortName() }}
    </span>
    <span
      class="grid-view-aggregation__generic-value"
      :class="{
        'grid-view-aggregation__generic-value--loading': loading,
      }"
    >
      {{ value }}
    </span>
  </div>
</template>

<script>
export default {
  props: {
    aggregationType: {
      type: Object,
      required: true,
    },
    value: {
      type: null,
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
