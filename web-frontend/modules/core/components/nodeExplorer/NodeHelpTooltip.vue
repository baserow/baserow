<template>
  <Context ref="context">
    <div v-if="node" class="node-help-tooltip">
      <div class="node-help-tooltip__header">
        <div class="node-help-tooltip__icon">
          <i
            :class="node.icon || 'iconoir-function'"
            class="node-help-tooltip__icon-symbol"
          ></i>
        </div>
        <h3 class="node-help-tooltip__title">
          {{ node.name }}
        </h3>
      </div>

      <div class="node-help-tooltip__content">
        <p class="node-help-tooltip__description">
          {{ node.description }}
        </p>

        <FormGroup
          v-if="node.example"
          class="node-help-tooltip__example"
          :label="$t('nodeHelpTooltip.exampleLabel')"
          small-label
          required
          :helper-text="
            $t('nodeHelpTooltip.result', { result: node.example.result })
          "
        >
          <FormulaInputField
            class="node-help-tooltip__example-code"
            :value="node.example.formula"
            :read-only="true"
            :nodes-hierarchy="nodesHierarchy"
            mode="advanced"
          />
        </FormGroup>
      </div>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import Context from '@baserow/modules/core/components/Context'

export default {
  name: 'NodeHelpTooltip',
  components: {
    Context,
    FormulaInputField: () =>
      import('@baserow/modules/core/components/formula/FormulaInputField'), // Lazy load the component to avoid circular dependency issue
  },
  mixins: [context],
  inject: ['nodesHierarchy'],
  props: {
    node: {
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
