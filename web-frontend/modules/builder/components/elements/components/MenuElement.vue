<template>
  <div
    :style="getStyleOverride(element.variant)"
    :class="[
      'menu-element__menu-items-container',
      element.orientation === 'horizontal' ? 'horizontal' : 'vertical',
    ]"
  >
    <div class="menu-element__menu-item" v-for="item in visibleMenuItems" :key="item.id">
      <template v-if="item.type === 'separator'">
        <div class="menu-element__menu-separator"></div>
      </template>
      <template v-else-if="item.menu_item_variant === 'link' && !item.parent_menu_item">
        <div class="menu-element__menu-link-container">
          <div v-if="!item.children?.length">
            <LinkElement
              :element="getElement(item)"
              class="menu-element__menu-item-link"
            />
          </div>
          <div class="menu-element__sub-link-menu-container" v-else @click="toggleExpanded(item.id)">
            <div class="menu-element__sub-link-menu-container-item">
              <div class="menu-element__menu-item-link">
                <a>{{ getResolvedValue(item.name) }}</a>
              </div>
              <div v-if="element.orientation === 'vertical'" class="menu-element__spacer"></div>
              <div>
                <i
                  class="menu-element__menu-link-expanded-icon"
                  :class="
                    isExpanded(item.id) ? 'iconoir-nav-arrow-up' : 'iconoir-nav-arrow-down'
                  "
                />
              </div>
            </div>
            <div v-if="isExpanded(item.id)">
              <div class="menu-element__sub-link-menu">
                <LinkElement
                  v-for="child in item.children" :key="child.id"
                  :element="getElement(child)"
                  class="menu-element__menu-item-link"
                />
              </div>
            </div>
          </div>
        </div>        
      </template>
      <template v-else-if="item.menu_item_variant === 'button'">
        <MenuItemButtonElement :element="getElement(item)" />
      </template>
    </div>

    <div v-if="!element.menu_items.length" class="element--no-value">
      {{ $t('menuElement.missingValue') }}
    </div>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'
import ABLink from '@baserow/modules/builder/components/elements/components/collectionField/LinkField.vue'
import LinkElement from '@baserow/modules/builder/components/elements/components/LinkElement.vue'
import ButtonElement from '@baserow/modules/builder/components/elements/components/ButtonElement.vue'
import MenuItemButtonElement from '@baserow/modules/builder/components/elements/components/MenuItemButtonElement.vue'
/**
 * @typedef MenuElement
 */

export default {
  name: 'MenuElement',
  components: {
    ABLink,
    ButtonElement,
    LinkElement,
    MenuItemButtonElement,
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
  data() {
    return {
      expandedItems: {},
    }
  },
  computed: {
    visibleMenuItems() {
      return this.element.menu_items.filter((item) => {
        return !item.parent_menu_item
      })
    }
  },
  methods: {
    getElement(item) {
      return {
        // TODO: this is probably not needed
        id: this.element.id,
        // Needed for the MenuItemElementType.getEvents()
        element_id: this.element.id,
        menu_item_id: item.id,
        uid: item.uid,
        target: item.target || 'self',
        variant: item.menu_item_variant,
        value: item.name,
        navigation_type: item.navigation_type,
        navigate_to_page_id: item.navigate_to_page_id || null,
        page_parameters: item.page_parameters || {},
        navigate_to_url: item.navigate_to_url || '#',
        page_id: this.element.page_id,
        type: 'menu_item',
      }
    },
    getResolvedValue(name) {
      return ensureString(this.resolveFormula(name))
    },
    toggleExpanded(itemId) {
      this.$set(this.expandedItems, itemId, !this.expandedItems[itemId])
    },
    isExpanded(itemId) {
      return !!this.expandedItems[itemId]
    },
  },
}
</script>
