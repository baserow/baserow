<template>
  <div
    v-bind="clickableElementAttributes"
    class="heading-element"
    :class="{
      'element--no-value': !resolvedValue,
      'element--clickable': isClickable,
    }"
    @click="onElementClick"
    @keydown="onElementKeydown"
    @keyup="onElementKeyup"
  >
    <ABHeading :level="element.level" :style="getStyleOverride('typography')">
      {{
        element.value
          ? resolvedValue ||
            (mode === 'editing' ? $t('headingElement.emptyValue') : '&nbsp;')
          : $t('headingElement.missingValue')
      }}
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
  },
}
</script>
