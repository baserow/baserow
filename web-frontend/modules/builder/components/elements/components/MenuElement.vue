<template>
  <div
    :class="[
      'menu-element__container',
      element.orientation === 'horizontal'
        ? 'menu-element__container--horizontal'
        : 'menu-element__container--vertical',
    ]"
    :style="{ '--alignment': menuAlignment, ...getStyleOverride('menu') }"
  >
    <div
      v-for="item in element.menu_items"
      :key="item.id"
      :class="`menu-element__menu-item-${item.type}`"
    >
      <MenuItem :menu-item="item" :element="element" />
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
import { HORIZONTAL_ALIGNMENTS } from '@baserow/modules/builder/enums'
import MenuItem from '@baserow/modules/builder/components/elements/components/MenuItem.vue'

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
    /*const found = resolveApplicationRoute(
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
    }*/
  },
}
</script>
