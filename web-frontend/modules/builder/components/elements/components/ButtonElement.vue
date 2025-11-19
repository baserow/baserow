<template>
  <div
    class="button-element"
    :class="{
      'element--no-value': !resolvedValue,
    }"
    :style="getStyleOverride('button')"
  >
    <ABButton
      :loading="workflowActionsInProgress"
      @click="fireEvent(elementType.getEventByName(element, 'click'))"
    >
      <span
        v-html="
          element.value
            ? resolvedValue ||
              (mode === 'editing' ? $t('buttonElement.emptyValue') : '&nbsp;')
            : $t('buttonElement.missingValue')
        "
      >
      </span>
    </ABButton>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'
import { decodeHTMLEntities } from '@baserow/modules/core/utils/string'

/**
 * @typedef ButtonElement
 * @property {string} value The text inside the button
 * @property {Object} styles contains style overides
 */

export default {
  name: 'ButtonElement',
  mixins: [element],
  props: {
    /**
     * @type {ButtonElement}
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    resolvedValue() {
      const raw = ensureString(this.resolveFormula(this.element.value))
      return decodeHTMLEntities(raw);
    },
  },
}
</script>
