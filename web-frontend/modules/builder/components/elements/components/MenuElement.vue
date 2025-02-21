<template>
  <div
    :style="getStyleOverride(element.variant)"
    :class="[
      'menu-element__container',
      element.orientation === 'horizontal' ? 'horizontal' : 'vertical',
    ]"
  >
    <div v-for="item in visibleMenuItems" :key="item.id">
      <template v-if="item.type === 'separator'">
        <div class="menu-element__menu-item-separator"></div>
      </template>
      <template v-else-if="item.type === 'link' && !item.parent_menu_item">
        <div v-if="!item.children?.length">
          <ABLink
            :variant="item.variant"
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
          @click="showSubMenu($event, item.id)"
        >
          <div class="menu-element__sub-link-menu--container">
            <a>{{ getResolvedValue(item.name) }}</a>

            <div class="menu-element__sub-link-menu--spacer"></div>

            <div>
              <i
                class="menu-element__sub-link--expanded-icon"
                :class="
                  isExpanded(item.id)
                    ? 'iconoir-nav-arrow-up'
                    : 'iconoir-nav-arrow-down'
                "
              ></i>
            </div>
          </div>

          <Context
            :ref="`subLinkContext_${item.id}`"
            :hide-on-click-outside="true"
            @shown="toggleExpanded(item.id)"
            @hidden="toggleExpanded(item.id)"
          >
            <div class="menu-element__sub-link-children-container">
              <ABLink
                v-for="child in item.children"
                :key="child.id"
                :variant="child.variant"
                :url="getItemUrl(child)"
                :target="getElement(child).target"
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
          </Context>
        </div>
      </template>
      <template v-else-if="item.type === 'button'">
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
  methods: {
    showSubMenu(event, itemId) {
      const contextRef = this.$refs[`subLinkContext_${itemId}`][0]
      if (contextRef?.isOpen()) {
        contextRef.hide()
      } else {
        const containerRef = event.currentTarget
        contextRef.show(containerRef, 'bottom', 'left', 0)
      }
    },
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
    toggleExpanded(itemId) {
      this.$set(this.expandedItems, itemId, !this.expandedItems[itemId])
    },
    getElement(item) {
      return {
        // TODO: this is probably not needed
        id: this.element.id,
        // was needed for the MenuItemElementType.getEvents()
        // element_id: this.element.id,
        menu_item_id: item?.id,
        uid: item?.uid,
        target: item.target || 'self',
        variant: item?.variant || 'link',
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
    isExpanded(itemId) {
      return !!this.expandedItems[itemId]
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
