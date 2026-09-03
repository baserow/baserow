<template>
  <Context ref="context" class="node-help-tooltip-context">
    <div
      v-if="node"
      class="node-help-tooltip"
      @mouseenter="$emit('mouseenter')"
      @mouseleave="$emit('mouseleave')"
    >
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
        <p v-if="node.description" class="node-help-tooltip__description">
          {{ node.description }}
        </p>

        <template v-if="node.examples && node.examples.length > 0">
          <label class="control__label control__label--small">
            {{
              $t('nodeHelpTooltip.exampleLabel', {
                count: node.examples.length,
              })
            }}
          </label>
          <div
            class="node-help-tooltip__examples"
            :class="{
              'node-help-tooltip__examples--clickable': clickableExamples,
            }"
          >
            <div
              v-for="(example, index) in node.examples"
              :key="index"
              class="node-help-tooltip__example"
              :class="{
                'node-help-tooltip__example--clickable': clickableExamples,
              }"
              @mousedown="onExampleMouseDown"
              @click="onExampleClick(example, $event)"
            >
              <FormGroup
                :helper-text="
                  example.result
                    ? $t('nodeHelpTooltip.result', { result: example.result })
                    : null
                "
                required
              >
                <FormulaInputField
                  class="node-help-tooltip__example-code"
                  :value="example.formula"
                  :read-only="true"
                  :nodes-hierarchy="nodesHierarchy"
                  mode="advanced"
                />
              </FormGroup>
            </div>
          </div>
          <p v-if="clickableExamples" class="node-help-tooltip__examples-hint">
            {{ $t('nodeHelpTooltip.clickToInsert') }}
          </p>
        </template>
      </div>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import Context from '@baserow/modules/core/components/Context'

import { defineAsyncComponent } from 'vue'

export default {
  name: 'NodeHelpTooltip',
  components: {
    Context,
    FormulaInputField: defineAsyncComponent(
      () => import('@baserow/modules/core/components/formula/FormulaInputField')
    ), // Lazy load the component to avoid circular dependency issue
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
    clickableExamples: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['example-click', 'mouseenter', 'mouseleave'],
  methods: {
    onExampleMouseDown(event) {
      if (this.clickableExamples) {
        // The tooltip is teleported to <body>, so a mousedown here would blur
        // the formula editor and unmount the explorer (tooltip included)
        // before the click can land. Preventing the default keeps focus in
        // the editor, which also preserves the cursor position the example
        // will be inserted at.
        event.preventDefault()
      }
    },
    onExampleClick(example, event) {
      if (this.clickableExamples) {
        // Keep the click from reaching the document-level click-outside
        // handlers, which would treat it as outside the formula context and
        // hide the explorer.
        event.stopPropagation()
        this.$emit('example-click', example)
      }
    },
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
