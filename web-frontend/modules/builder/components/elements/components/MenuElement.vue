<template>
  <div
    :class="[
      'menu-element__wrapper',
      `menu-element__align-${menuElementAlignment}`,
    ]"
  >
    <template v-if="useCompactMenu">
      <div
        :class="burgerTriggerClasses"
        :style="{ '--alignment': menuAlignment, ...getStyleOverride('menu') }"
      >
        <button
          type="button"
          :class="[
            'menu-element__burger-menu',
            `menu-element__burger-menu-${menuElementAlignment}`,
          ]"
          @click.stop="compactMenuOpen = !compactMenuOpen"
        >
          <i class="iconoir-menu"></i>
        </button>
      </div>

      <div
        v-if="compactMenuOpen"
        v-click-outside="closeCompactMenu"
        :class="compactPanelClasses"
        :style="{
          ...getStyleOverride('menu'),
          '--alignment': defaultMenuAlignment,
        }"
      >
        <button
          type="button"
          class="menu-element__burger-menu-close"
          @click="closeCompactMenu"
        >
          <i class="iconoir-cancel"></i>
        </button>

        <div
          v-for="item in element.menu_items"
          :key="item.id"
          :class="getMenuItemClasses(item)"
        >
          <MenuItem
            :menu-item="item"
            :element="element"
            :is-compact-menu="useCompactMenu"
          />
        </div>

        <div v-if="!element.menu_items.length" class="element--no-value">
          {{ $t('menuElement.missingValue') }}
        </div>
      </div>
    </template>

    <div
      v-else
      :class="menuContainerClasses"
      :style="{ '--alignment': menuAlignment, ...getStyleOverride('menu') }"
    >
      <div
        v-for="item in element.menu_items"
        :key="item.id"
        :class="getMenuItemClasses(item)"
      >
        <MenuItem :menu-item="item" :element="element" />
      </div>

      <div v-if="!element.menu_items.length" class="element--no-value">
        {{ $t('menuElement.missingValue') }}
      </div>
    </div>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { HORIZONTAL_ALIGNMENTS } from '@baserow/modules/builder/enums'
import MenuItem from '@baserow/modules/builder/components/elements/components/MenuItem.vue'

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
      compactMenuOpen: false,
    }
  },
  computed: {
    burgerTriggerClasses() {
      return [
        'menu-element__container',
        'menu-element__container--burger',
        'menu-element__container--burger-trigger',
      ]
    },
    compactPanelClasses() {
      return [
        'menu-element__container',
        'menu-element__container--burger',
        'menu-element__burger-active',
      ]
    },
    menuContainerClasses() {
      return [
        'menu-element__container',
        `menu-element__container--${this.element.orientation}`,
      ]
    },
    menuAlignment() {
      const alignmentsCSS = {
        [HORIZONTAL_ALIGNMENTS.LEFT]: 'flex-start',
        [HORIZONTAL_ALIGNMENTS.CENTER]: 'center',
        [HORIZONTAL_ALIGNMENTS.RIGHT]: 'flex-end',
      }
      return alignmentsCSS[this.menuElementAlignment]
    },
    defaultMenuAlignment() {
      return 'flex-start'
    },
    menuElementAlignment() {
      return this.element.alignment || HORIZONTAL_ALIGNMENTS.LEFT
    },
    useCompactMenu() {
      const deviceType =
        this.$store.getters['page/getDeviceTypeSelected'] || 'desktop'
      return this.element.variant?.[deviceType] === 'compact'
    },
  },
  methods: {
    closeCompactMenu() {
      this.compactMenuOpen = false
    },
    getMenuItemClasses(item) {
      return [
        `menu-element__menu-item-${item.type}`,
        {
          'menu-element__menu-item--compact-spacer':
            this.useCompactMenu && item.type === 'spacer',
        },
      ]
    },
  },
}
</script>
