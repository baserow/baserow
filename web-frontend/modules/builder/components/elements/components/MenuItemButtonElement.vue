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
      @click="fireEvent(menuItemElementType.getEventByName(element, eventName))"
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
 * @typedef MenuItemButtonElement
 * @property {string} value The text inside the button
 * @property {Object} styles contains style overides
 */

export default {
  name: 'MenuItemButtonElement',
  mixins: [element],
  props: {
    /**
     * @type {MenuItemButtonElement}
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
    eventName() {
      return `${this.element.uid}_click`
    },
    menuItemElementType() {
      return this.$registry.get('element', 'menu_item')
    },
  },
}
</script>
