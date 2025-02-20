<template>
  <div
    :style="getStyleOverride(element.variant)"
    :class="[
      'menu-element menu-element__menu-items-container',
      element.orientation === 'horizontal' ? 'horizontal' : 'vertical',
    ]"
  >
    <div
      v-for="item in visibleMenuItems"
      :key="item.id"
      class="menu-element__menu-item"
    >
      <template v-if="item.type === 'separator'">
        <div class="menu-element__menu-separator"></div>
      </template>
      <template
        v-else-if="item.menu_item_variant === 'link' && !item.parent_menu_item"
      >
        <div class="menu-element__menu-link-container">
          <div v-if="!item.children?.length">
            <ABLink
              :variant="item.menu_item_variant"
              :url="getItemUrl(item)"
              :target="getElement(item).target"
              class="menu-element__menu-item-link"
            >
              {{
                item.name
                  ? getResolvedValue(item.name) ||
                    (mode === 'editing'
                      ? $t('menuElement.emptyLinkValue')
                      : '&nbsp;')
                  : $t('menuElement.missingLinkValue')
              }}
            </ABLink>
          </div>
          <div
            v-else
            ref="menuSubLinkContainer"
            class="menu-element__sub-link-menu-container"
            @click="toggleExpanded(item.id)"
          >
            <div class="menu-element__sub-link-menu-container-item">
              <div class="menu-element__menu-item-link">
                <a>{{ getResolvedValue(item.name) }}</a>
              </div>
              <div
                v-if="element.orientation === 'vertical'"
                class="menu-element__spacer"
              ></div>
              <div>
                <i
                  class="menu-element__menu-link-expanded-icon"
                  :class="
                    isExpanded(item.id)
                      ? 'iconoir-nav-arrow-up'
                      : 'iconoir-nav-arrow-down'
                  "
                />
              </div>
            </div>
            <div v-if="isExpanded(item.id)">
              <div class="menu-element__sub-link-menu">
                <ABLink
                  v-for="child in item.children"
                  :key="child.id"
                  :variant="child?.menu_item_variant || 'link'"
                  :url="getItemUrl(child)"
                  :target="getElement(child).target"
                  class="menu-element__menu-item-link"
                >
                  {{
                    child.name
                      ? getResolvedValue(child.name) ||
                        (mode === 'editing'
                          ? $t('menuElement.emptyLinkValue')
                          : '&nbsp;')
                      : $t('menuElement.missingLinkValue')
                  }}
                </ABLink>
              </div>
            </div>
          </div>
        </div>
      </template>
      <template v-else-if="item.menu_item_variant === 'button'">
        <ABButton @click="onButtonClick(item)">
          {{
            item.name
              ? getResolvedValue(item.name) ||
                (mode === 'editing'
                  ? $t('menuElement.emptyButtonValue')
                  : '&nbsp;')
              : $t('menuElement.missingButtonValue')
          }}
        </ABButton>
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
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'

/**
 * @typedef MenuElement
 */

export default {
  name: 'MenuElement',
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
    },
    pages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
    menuElementType() {
      return this.$registry.get('element', 'menu')
    },
  },
  mounted() {
    document.addEventListener('click', this.handleClickOutsideSubLinkMenu)
  },
  beforeDestroy() {
    document.removeEventListener('click', this.handleClickOutsideSubLinkMenu)
  },
  methods: {
    getItemUrl(item) {
      try {
        return resolveElementUrl(
          this.getElement(item),
          this.builder,
          this.pages,
          this.resolveFormula,
          this.mode
        )
      } catch (e) {
        return '#error'
      }
    },
    getElement(item) {
      return {
        // TODO: this is probably not needed
        id: this.element.id,
        // Needed for the MenuItemElementType.getEvents()
        element_id: this.element.id,
        menu_item_id: item?.id,
        uid: item?.uid,
        target: item.target || 'self',
        variant: item?.menu_item_variant || 'link',
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
    handleClickOutsideSubLinkMenu(event) {
      const subMenuContainers = this.$refs.menuSubLinkContainer
      if (!subMenuContainers) return

      // subMenuContainers could be a single element (if there is only
      // one sub menu), or an array or a DOM element (if there are multiple
      // sub menus)
      const isClickOutside = Array.isArray(subMenuContainers)
        ? // If it is an array, check if at least one sub menu received the click
          !subMenuContainers.some((container) =>
            container.contains(event.target)
          )
        : // If it is a DOM element, check if it received the click
          !subMenuContainers.contains(event.target)

      // If a click is received anywhere outside of a sub menu, close all
      // sub menus.
      if (isClickOutside) {
        this.expandedItems = {}
      }
    },
    onButtonClick(item) {
      const eventName = `${item.uid}_click`
      this.fireEvent(
        this.menuElementType.getEventByName(this.element, eventName)
      )
    },
  },
}
</script>
