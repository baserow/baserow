<template>
  <div
    class="heading-element"
    :class="{
      'element--no-value': !resolvedValue,
    }"
  >
    <ABHeading :level="element.level" :style="getStyleOverride('typography')">
      <!-- The button sits inside the heading so the heading keeps its role. -->
      <span
        v-bind="clickableElementAttributes"
        :class="isClickable ? 'element--clickable' : undefined"
        @click="onElementClick"
        @keydown="onElementKeydown"
        @keyup="onElementKeyup"
        >{{ headingText }}</span
      >
    </ABHeading>
  </div>
</template>

<script>
import clickableElement from '@baserow/modules/builder/mixins/clickableElement'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'HeadingElement',
  mixins: [clickableElement],
  props: {
    /**
     * @type {Object}
     * @property {number} level - The size of the heading
     * @property {string} value - The text displayed
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    resolvedValue() {
      return ensureString(this.resolveFormula(this.element.value))
    },
    headingText() {
      if (!this.element.value) {
        return this.$t('headingElement.missingValue')
      }
      return (
        this.resolvedValue ||
        (this.mode === 'editing' ? this.$t('headingElement.emptyValue') : ' ')
      )
    },
    canContainInteractiveContent() {
      // The click target only holds the heading text.
      return false
    },
  },
}
</script>
