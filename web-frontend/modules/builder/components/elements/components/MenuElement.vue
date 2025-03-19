<template>
  <div
    :style="{
      '--alignment': menuAlignment,
    }"
    :class="[
      'menu-element__container',
      element.orientation === 'horizontal'
        ? 'menu-element__container--horizontal'
        : 'menu-element__container--vertical',
    ]"
  >
    <div
      v-for="item in element.menu_items"
      :key="item.id"
      :class="`menu-element__menu-item-${item.type}`"
    >
      <template v-if="item.type === 'link' && !item.parent_menu_item">
        <div v-if="!item.children?.length" :style="getStyleOverride('menu')">
          <ABLink
            :variant="item.variant"
            :url="getItemUrl(item)"
            :target="getMenuItem(item).target"
            :force-active="menuItemIsActive(item)"
          >
            {{
              item.name
                ? item.name ||
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
          <div :style="getStyleOverride('menu')">
            <ABLink
              :variant="item.variant"
              url=""
              :force-active="sublinkIsActive(item)"
            >
              <div class="menu-element__sub-link-menu--container">
                {{ item.name }}
                <div class="menu-element__sub-link-menu-spacer"></div>
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
            </ABLink>
          </div>

          <Context
            :ref="`subLinkContext_${item.id}`"
            :hide-on-click-outside="true"
            @shown="toggleExpanded(item.id)"
            @hidden="toggleExpanded(item.id)"
          >
            <ThemeProvider class="menu-element__sub-links">
              <div
                v-for="child in item.children"
                :key="child.id"
                :style="getStyleOverride('menu')"
              >
                <ABLink
                  :variant="child.variant"
                  :url="getItemUrl(child)"
                  :target="getMenuItem(child).target"
                  class="menu-element__sub-link"
                  :force-active="menuItemIsActive(child)"
                >
                  {{
                    child.name
                      ? child.name ||
                        (mode === 'editing'
                          ? $t('menuElement.emptyLinkValue')
                          : '&nbsp;')
                      : $t('menuElement.missingLinkValue')
                  }}
                </ABLink>
              </div>
            </ThemeProvider>
          </Context>
        </div>
      </template>
      <template v-else-if="item.type === 'button'">
        <ABButton
          :style="getStyleOverride('menu')"
          @click="onButtonClick(item)"
        >
          {{
            item.name
              ? item.name ||
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
import { resolveApplicationRoute } from '@baserow/modules/builder/utils/routing'
import element from '@baserow/modules/builder/mixins/element'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'
import ThemeProvider from '@baserow/modules/builder/components/theme/ThemeProvider'
import { HORIZONTAL_ALIGNMENTS } from '@baserow/modules/builder/enums'

/**
 * CSS classes to force a Link variant to appear as active.
 */
const LINK_ACTIVE_CLASSES = {
  link: 'ab-link--force-active',
  button: 'ab-button--force-active',
}

/**
 * @typedef MenuElement
 * @property {Array}  menu_items Array of Menu items
 */

export default {
  name: 'MenuElement',
  components: { ThemeProvider },
  mixins: [element],
  props: {
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      expandedItems: {},
      activeItem: {},
    }
  },
  computed: {
    pages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
    menuElementType() {
      return this.$registry.get('element', 'menu')
    },
    menuAlignment() {
      const alignmentsCSS = {
        [HORIZONTAL_ALIGNMENTS.LEFT]: 'flex-start',
        [HORIZONTAL_ALIGNMENTS.CENTER]: 'center',
        [HORIZONTAL_ALIGNMENTS.RIGHT]: 'flex-end',
      }
      return alignmentsCSS[this.element.alignment]
    },
  },
  mounted() {
    /**
     * If the current page matches a menu item, that menu item is set as the
     * active item. This ensures that the active CSS style is applied to the
     * correct menu item.
     */
    const found = resolveApplicationRoute(
      this.pages,
      this.$route.params.pathMatch
    )

    if (!found?.length) return

    const currentPageId = found[0].id

    for (const item of this.element.menu_items) {
      if (!item.children.length && item.navigate_to_page_id === currentPageId) {
        this.activeItem = item
        break
      }
      for (const child of item.children) {
        if (child.navigate_to_page_id === currentPageId) {
          this.activeItem = child
          break
        }
      }
    }
  },
  methods: {
    showSubMenu(event, itemId) {
      const contextRef = this.$refs[`subLinkContext_${itemId}`][0]
      if (contextRef?.isOpen()) {
        contextRef.hide()
      } else {
        const containerRef = event.currentTarget
        contextRef.show(containerRef, 'bottom', 'left', 10)
      }
    },
    getItemUrl(item) {
      try {
        return resolveElementUrl(
          this.getMenuItem(item),
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
    /**
     * Transforms a Menu Item into a valid object that can be passed as a prop
     * to the ABLink component.
     */
    getMenuItem(item) {
      return {
        id: this.element.id,
        menu_item_id: item?.id,
        uid: item?.uid,
        target: item.target || 'self',
        variant: item?.variant || 'link',
        value: item.name,
        navigation_type: item.navigation_type,
        navigate_to_page_id: item.navigate_to_page_id || null,
        page_parameters: item.page_parameters || {},
        query_parameters: item.query_parameters || {},
        navigate_to_url: item.navigate_to_url || '#',
        page_id: this.element.page_id,
        type: 'menu_item',
      }
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
    menuItemIsActive(item) {
      return this.activeItem?.uid === item.uid
    },
    getActiveParentClass(item) {
      if (item.children?.some((child) => child.uid === this.activeItem?.uid))
        return LINK_ACTIVE_CLASSES[item.variant] || ''

      return ''
    },
    sublinkIsActive(item) {
      if (item.children?.some((child) => child.uid === this.activeItem?.uid))
        return true

      return false
    },
  },
}
</script>
