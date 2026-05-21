<template>
  <div
    :class="[
      'menu-element__wrapper',
      `menu-element__wrapper--${menuElementAlignment}`,
    ]"
    :style="{ '--alignment': menuAlignment }"
  >
    <template v-if="useCompactMenu">
      <div
        class="menu-element__burger-menu"
        :style="{
          ...getStyleOverride('burger'),
        }"
      >
        <ABIcon
          icon="iconoir-menu"
          :class="'menu-element__burger-menu-icon'"
          is-button
          @click.stop="compactMenuOpen = !compactMenuOpen"
        />
      </div>

      <div
        v-if="compactMenuOpen"
        v-click-outside="closeCompactMenu"
        :class="compactPanelClasses"
        :style="{
          ...getStyleOverride('menu'),
          '--alignment': 'flex-start',
        }"
      >
        <ABIcon
          icon="iconoir-cancel"
          class="menu-element__burger-menu-close"
          is-button
          @click="closeCompactMenu"
        />

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

    <div
      v-else
      :class="menuContainerClasses"
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
    compactPanelClasses() {
      return [
        'menu-element__container',
        'menu-element__container--vertical',
        'menu-element__container--burger',
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
  },
}
</script>
