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
    visible: {
      handler(isVisible) {
        if (isVisible) {
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
      // Ensure that the context's width is dynamically set
      // to the targetElement's width, as it can be variable.
      const contextEl = this.$refs.context?.getTeleportedElement()
      if (contextEl) {
        const { width } = el.getBoundingClientRect()
        contextEl.style.width = `${width}px`
      }
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
