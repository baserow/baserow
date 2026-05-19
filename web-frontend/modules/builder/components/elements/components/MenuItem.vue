<template>
  <div>
    <template v-if="menuItem.type === 'link' && !menuItem.parent_menu_item">
      <div v-if="!menuItem.children?.length">
        <ABLink
          :variant="menuItem.variant"
          :url="getItemUrl(menuItem)"
          :target="getMenuItem(menuItem).target"
          :force-active="menuItemIsActive(menuItem)"
        >
          {{
            menuItem.name
              ? menuItem.name ||
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
        class="menu-element__menu-item-with-children"
        @click="toggleSubMenu()"
      >
        <div>
          <ABLink :variant="menuItem.variant" :force-active="sublinkIsActive">
            <div class="menu-element__sub-link-menu--container">
              {{ menuItem.name }}
              <div class="menu-element__sub-link-menu-spacer"></div>
              <div>
                <i
                  class="menu-element__sub-link--expanded-icon"
                  :class="
                    isExpanded
                      ? 'iconoir-nav-arrow-up'
                      : 'iconoir-nav-arrow-down'
                  "
                ></i>
              </div>
            </div>
          </ABLink>
        </div>

        <div v-if="isExpanded" class="menu-element__sub-link--container">
          <div
            v-for="child in menuItem.children"
            :key="child.id"
            class="menu-element__sub-links"
            :style="getStyleOverride('menu')"
          >
            <ABLink
              :variant="child.variant"
              :url="getItemUrl(child)"
              :target="getMenuItem(child).target"
              class="menu-element__sub-link"
              :force-active="menuItemIsActive(child)"
              @click.stop
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
        </div>

        <Context
          v-if="!useInlineSubLinks"
          :ref="`subLinkContext`"
          :hide-on-click-outside="true"
        >
          <ThemeProvider class="menu-element__sub-links">
            <div
              v-for="child in menuItem.children"
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
    <template v-else-if="menuItem.type === 'button'">
      <ABButton
        :style="getStyleOverride('menu')"
        @click="onButtonClick(menuItem)"
      >
        {{
          menuItem.name
            ? menuItem.name ||
              (mode === 'editing'
                ? $t('menuElement.emptyButtonValue')
                : '&nbsp;')
            : $t('menuElement.missingButtonValue')
        }}
      </ABButton>
    </template>
  </div>
</template>

<script>
import { resolveApplicationRoute } from '@baserow/modules/builder/utils/routing'
import element from '@baserow/modules/builder/mixins/element'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'
import ThemeProvider from '@baserow/modules/builder/components/theme/ThemeProvider.vue'
import { ORIENTATIONS } from '@baserow/modules/builder/enums'
/**
 * @typedef MenuItem
 */

export default {
  name: 'MenuItem',
  components: { ThemeProvider },
  mixins: [element],
  props: {
    menuItem: {
      type: Object,
      required: true,
    },
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      activeItem: {},
      isExpanded: false,
    }
  },
  computed: {
    menuElementType() {
      return this.$registry.get('element', 'menu')
    },
    pages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
    sublinkIsActive() {
      return this.menuItem.children?.some(
        (child) => child.uid === this.activeItem?.uid
      )
    },
    useInlineSubLinks() {
      const deviceType =
        this.$store.getters['page/getDeviceTypeSelected'] || 'desktop'
      return (
        this.element.orientation === ORIENTATIONS.VERTICAL ||
        this.element.variant?.[deviceType] === 'compact'
      )
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
    toggleSubMenu() {
      if (this.useInlineSubLinks) {
        this.isExpanded = !this.isExpanded
      } else {
        this.$refs.subLinkContext.toggle(
          this.$refs.menuSubLinkContainer,
          'bottom',
          'left',
          5
        )
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
    onButtonClick(item) {
      const eventName = `${item.uid}_click`
      this.fireEvent(
        this.menuElementType.getEventByName(this.element, eventName)
      )
    },
    menuItemIsActive(item) {
      return this.activeItem?.uid === item.uid
    },
  },
}
</script>
