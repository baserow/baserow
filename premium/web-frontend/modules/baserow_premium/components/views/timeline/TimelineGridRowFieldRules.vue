<template>
  <div>
    <template v-for="ctx in fieldRules">
      <component
        :is="ctx.component"
        :key="`row-${ctx.rule.id}`"
        :rows="rowsWithDependencies"
        :fields="fields"
        :rule="ctx.rule"
        :view="view"
        :width="canvasWidth"
        :height="canvasHeight"
        :store-prefix="storePrefix"
      />
    </template>
  </div>
</template>

<script>
/**
 * A glue component that allows for field rule-specific additions on a timeline view.
 *
 * Each field rule type can define a dedicated component that will add an overlay to
 * timeline view. A such component should be registered under `timelineFieldRules`
 * namespace with a `TimelineFieldRuleType` subclass.
 *
 *
 */
export default {
  props: {
    rows: { type: Array, required: true },
    storePrefix: { type: String, required: true },
    view: { type: Object, required: true },
    fields: { type: Array, required: true },
  },
  computed: {
    fieldRules() {
      const table = this.$store.getters['table/getSelected']
      const that = this
      const out = []

      this.$store.getters['fieldRules/getRules']({
        tableId: table.id,
      })
        .filter((rule) => rule.is_valid && rule.is_active)
        .forEach((rule) => {
          const component = that.getComponentForRule(rule)
          if (component) {
            out.push({ rule, component })
          }
        })
      return out
    },
    rowsWithDependencies() {
      return this.rows.filter((row) => row.item !== undefined)
    },
    canvasWidth() {
      return this.$parent.gridWidth
    },
    canvasHeight() {
      return this.$parent.gridHeight
    },
  },
  methods: {
    getComponentForRule(rule) {
      let componentHandler
      try {
        componentHandler = this.$registry.get('timelineFieldRules', rule.type)
      } catch (err) {
        return
      }
      if (!componentHandler) {
        return
      }
      const database = this.$store.getters['application/getSelected']
      return componentHandler.getTimelineFieldRuleComponent(
        rule,
        this.view,
        database
      )
    },
  },
}
</script>
