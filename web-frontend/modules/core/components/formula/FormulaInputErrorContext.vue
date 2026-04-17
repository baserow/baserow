<template>
  <Context
    ref="context"
    class="formula-input-error-context"
    :hide-on-click-outside="false"
    data-formula-input-context
    force-position
  >
    <Alert type="error">
      <template #title>{{ formulaErrorContext.title }}</template>
      <p>{{ formulaErrorContext.message }}</p>
    </Alert>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'FormulaInputErrorContext',
  mixins: [context],
  props: {
    formulaErrorContext: {
      type: Object,
      required: true,
    },
    visible: {
      type: Boolean,
      required: true,
    },
    target: {
      type: Object,
      default: null,
      validator: (value) => value == null || value instanceof HTMLElement,
    },
  },
  watch: {
    display: {
      handler(visible) {
        if (visible) {
          this.show(this.target)
        } else {
          this.hide()
        }
      },
    },
  },
  methods: {
    show(
      targetElement = null,
      verticalPosition = 'top',
      horizontalPosition = 'left',
      verticalOffset = 10,
      horizontalOffset = 0
    ) {
      const el = targetElement ?? this.target
      if (!el || !this.$refs.context) {
        return
      }
      const { width } = el.getBoundingClientRect()
      this.$refs.context.$el.style.width = `${width}px`
      return this.$refs.context.show(
        el,
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
