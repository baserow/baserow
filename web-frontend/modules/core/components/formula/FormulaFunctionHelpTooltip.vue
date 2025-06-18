<template>
  <Context ref="context">
    <div v-if="functionData" class="formula-function-help-tooltip">
      <div class="formula-function-help-tooltip__header">
        <div class="formula-function-help-tooltip__icon">
          <i
            :class="functionData.icon || 'iconoir-function'"
            class="formula-function-help-tooltip__icon-symbol"
          ></i>
        </div>
        <h3 class="formula-function-help-tooltip__title">
          {{ functionData.name }}
        </h3>
      </div>

      <div class="formula-function-help-tooltip__content">
        <p class="formula-function-help-tooltip__description">
          {{ functionData.description }}
        </p>

        <div
          v-if="functionData.example"
          class="formula-function-help-tooltip__example"
        >
          <div class="formula-function-help-tooltip__example-code">
            <FormulaInputField
              :value="functionData.example"
              :read-only="true"
              :context-tabs="contextTabs"
            />
          </div>
        </div>
      </div>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import Context from '@baserow/modules/core/components/Context'

export default {
  name: 'FormulaFunctionHelpTooltip',
  components: {
    Context,
    FormulaInputField: () =>
      import('@baserow/modules/core/components/formula/FormulaInputField'), // Lazy load the component to avoid circular dependency issue
  },
  mixins: [context],
  props: {
    functionData: {
      type: Object,
      default: null,
    },
    contextTabs: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  methods: {
    show(
      targetElement,
      verticalPosition = 'bottom',
      horizontalPosition = 'right',
      verticalOffset = 0,
      horizontalOffset = 10
    ) {
      if (!this.functionData) {
        return
      }

      return this.$refs.context.show(
        targetElement,
        verticalPosition,
        horizontalPosition,
        verticalOffset,
        horizontalOffset
      )
    },
    hide() {
      this.$refs.context.hide()
    },
  },
}
</script>
