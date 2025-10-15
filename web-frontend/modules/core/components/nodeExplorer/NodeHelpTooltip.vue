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

        <div v-if="node.example" class="node-help-tooltip__example">
          <div class="node-help-tooltip__example-code">
            <FormulaInputField
              :value="node.example"
              :read-only="true"
              :nodes-hierarchy="nodesHierarchy"
              mode="advanced"
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
