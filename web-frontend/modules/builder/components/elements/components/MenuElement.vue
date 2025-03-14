<template>
  <div
    :class="[
      'menu-element__wrapper',
      `menu-element__align-${element.alignment.toLowerCase()}`,
    ]"
  >
    <client-only>
      <div
        :style="{
          '--alignment': menuAlignment,
        }"
        :class="menuContainerClass"
      >
        <template v-if="!useBurgerMenu">
          <div
            v-for="item in element.menu_items"
            :key="item.id"
            :class="`menu-element__menu-item-${item.type}`"
          >
            <MenuItem
              :key="item.uid"
              :menu-item="item"
              :element="element"
              :is-mobile-device="useBurgerMenu"
            />
          </div>
        </template>

        <template v-else>
          <div
            :class="[
              'menu-element__burger-menu',
              `menu-element__burger-menu-${element.alignment.toLowerCase()}`,
            ]"
          >
            <i
              :class="burgerMenuActive ? 'iconoir-cancel' : 'iconoir-menu'"
              @click="burgerMenuActive = !burgerMenuActive"
            ></i>
          </div>

          <template v-if="burgerMenuActive">
            <div
              v-for="item in element.menu_items"
              :key="item.id"
              :class="`menu-element__menu-item-${item.type}`"
            >
              <MenuItem
                :key="item.uid"
                :menu-item="item"
                :element="element"
                :is-mobile-device="useBurgerMenu"
              />
            </div>
          </template>
        </template>

        <div v-if="!element.menu_items.length" class="element--no-value">
          {{ $t('menuElement.missingValue') }}
        </div>
      </div>
    </client-only>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { HORIZONTAL_ALIGNMENTS } from '@baserow/modules/builder/enums'
import MenuItem from '@baserow/modules/builder/components/elements/components/MenuItem'

/**
 * @typedef MenuElement
 * @property {Array}  menu_items Array of Menu items
 *
 *  The `MenuElement` supports two menu layouts for three device types:
 *
 * Expanded (normal) menu: Best for wider screens.
 * Mobile (burger) menu: Ideal for smaller devices like smartphones and tablets.
 *
 * The menu type can be customized per device. Users can opt for the mobile burger
 * menu even on `desktop`, or use the expanded menu across
 * all three device types: `tablet`, `desktop`, and `smartphone`.
 *
 */

export default {
  name: 'MenuElement',
  components: { MenuItem },
  mixins: [element],
  props: {
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      burgerMenuActive: false,
    }
  },
  computed: {
    menuContainerClass() {
      const classes = ['menu-element__container']
      if (this.useBurgerMenu) {
        classes.push('menu-element__container--burger')
        if (this.burgerMenuActive) {
          classes.push('menu-element__burger-active')
        }
      } else {
        classes.push(`menu-element__container--${this.element.orientation}`)
      }
      return classes
    },
    menuAlignment() {
      const alignmentsCSS = {
        [HORIZONTAL_ALIGNMENTS.LEFT]: 'flex-start',
        [HORIZONTAL_ALIGNMENTS.CENTER]: this.useBurgerMenu
          ? 'flex-start'
          : 'center',
        [HORIZONTAL_ALIGNMENTS.RIGHT]: 'flex-end',
      }
      return alignmentsCSS[this.element.alignment]
    },
    useBurgerMenu() {
      const deviceType = this.$store.getters['page/getDeviceTypeSelected']
      // If menu_type is defined for the current device, use it,
      // otherwise fall back to the default behavior
      if (this.element.menu_type && this.element.menu_type[deviceType]) {
        return this.element.menu_type[deviceType] === 'mobile'
      }
      return deviceType === 'smartphone'
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
      Array.isArray(this.$route.params.pathMatch)
        ? this.$route.params.pathMatch.join('/')
        : this.$route.params.pathMatch
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
      } catch {
        return '#error'
      }
    },
    toggleExpanded(itemId) {
      this.expandedItems[itemId] = !this.expandedItems[itemId]
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
