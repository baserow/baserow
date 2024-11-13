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
      {{
        element.value
          ? resolvedValue ||
            (mode === 'editing' ? $t('buttonElement.emptyValue') : '&nbsp;')
          : $t('buttonElement.missingValue')
      }}
    </ABButton>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'

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
      return ensureString(this.resolveFormula(this.element.value))
    },
  },
}
</script>
