<template>
  <div>
    <div
      v-for="rule in fieldRules"
      :key="rule.id"
      class="timeline-grid__field-rules"
    >
      <svg :width="canvasWidth" :height="canvasHeight">
        style="background-color: chocolate">
      </svg>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    table: { type: Object, required: true },
    rows: { type: Array, required: true },
  },
  computed: {
    fieldRules() {
      return this.$store.getters['fieldRules/getRules'](this.table.id).filter(
        (rule) => rule.is_valid
      )
    },
    canvasWidth() {
      return this.$parent.gridWidth
    },
    canvasHeight() {
      return this.$parent.gridHeight
    },
  },
}
</script>
