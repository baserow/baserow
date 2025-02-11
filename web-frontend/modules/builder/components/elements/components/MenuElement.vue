<template>
  <div
    class="menu-element"
    :style="getStyleOverride(element.variant)"
    :class="['menu-items-container', element.orientation === 'horizontal' ? 'horizontal' : 'vertical']"
    >
    <div v-for="item in element.menu_items" :key="item.id">
      <template v-if="item.menu_item_variant === 'link'">
        <LinkElement :element="getElement(item)" />
      </template>
    </div>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'
import ABLink from '@baserow/modules/builder/components/elements/components/collectionField/LinkField.vue'
import LinkElement from '@baserow/modules/builder/components/elements/components/LinkElement.vue'
/**
 * @typedef MenuElement
 */

export default {
  name: 'MenuElement',
  components: {
    ABLink,
    LinkElement,
  },
  mixins: [element],
  props: {
    /**
     * @type {MenuElement}
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {},
  methods: {
    getElement(item) {
      console.log('item is: ', item)
      return {
        id: item.id,
        target: item.target || 'self',
        variant: item.menu_item_variant,
        value: item.name,
        navigation_type: item.navigation_type,
        navigate_to_page_id: item.navigate_to_page_id || null,
        page_parameters: item.page_parameters || {},
        navigate_to_url: item.navigate_to_url || '#',
      }
    },
    getResolvedValue(name) {
      return ensureString(this.resolveFormula(name))
    },
  },
}
</script>
