<template>
  <div
    class="text-element"
    :class="{
      'element--no-value': !resolvedValue,
    }"
    :style="getStyleOverride('typography')"
  >
    <ABFormattedText
      v-if="hasValue"
      :value="resolvedValue"
      :format="element.value?.format"
      profile="block"
    />
    <ABParagraph v-else-if="element.value">
      {{ mode === 'editing' ? $t('textElement.emptyValue') : '&nbsp;' }}
    </ABParagraph>
    <ABParagraph v-else>
      {{ $t('textElement.missingValue') }}
    </ABParagraph>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'TextElement',
  mixins: [element],
  props: {
    /**
     * @type {Object}
     * @property {Object} value - The formula of the text, whose `format` says
     *   whether the resolved text renders as plain text or as markdown
     * @property {string} alignment - The alignment of the element on the page
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    resolvedValue() {
      try {
        return ensureString(this.resolveFormula(this.element.value))
      } catch (e) {
        return ''
      }
    },
    hasValue() {
      return this.resolvedValue.trim() !== ''
    },
  },
}
</script>
