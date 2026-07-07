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
        v-if="isEditMode && isCompactMenuOpen"
        class="menu-element__compact-menu-editor-overlay"
        @click.stop
        @mousedown.stop
      />

      <div
        class="menu-element__compact-menu-trigger"
        :style="{
          ...getStyleOverride('burger'),
        }"
      >
        <ABIcon
          icon="iconoir-menu"
          :class="'menu-element__compact-menu-trigger-icon'"
          is-button
          @click.stop="toggleCompactMenu"
        />
      </div>

      <div
        v-if="isCompactMenuOpen"
        v-click-outside="closeCompactMenu"
        :class="compactPanelClasses"
        :style="{
          ...getStyleOverride('menu'),
          '--alignment': 'flex-start',
        }"
        @mousedown.stop
        @dragstart.prevent.stop
      >
        <ABIcon
          icon="iconoir-cancel"
          class="menu-element__compact-menu-close"
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
  inject: {
    setPagePreviewLocked: {
      default: null,
    },
  },
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
        'menu-element__container--compact',
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
    isCompactMenuOpen() {
      if (this.isEditMode) {
        return this.element._.compactMenuOpen
      }
      return this.compactMenuOpen
    },
  },
  watch: {
    isCompactMenuOpen(isOpen) {
      this.setCompactMenuPreviewLock(this.isEditMode && isOpen)
    },
  },
  mounted() {
    this.setCompactMenuPreviewLock(this.isEditMode && this.isCompactMenuOpen)
  },
  beforeUnmount() {
    this.setCompactMenuPreviewLock(false)
    this.resetEditorCompactMenu()
  },
  methods: {
    toggleCompactMenu() {
      if (this.isEditMode) {
        return
      }
      this.compactMenuOpen = !this.compactMenuOpen
    },
    closeCompactMenu() {
      if (this.isEditMode) {
        return
      }
      this.compactMenuOpen = false
    },
    setCompactMenuPreviewLock(locked) {
      // the setPagePreviewLocked is not provided in public mode
      this.setPagePreviewLocked?.(locked)
    },
    resetEditorCompactMenu() {
      if (!this.isEditMode) {
        return
      }

      this.$store.dispatch('element/forceUpdate', {
        builder: this.builder,
        page: this.elementPage,
        element: this.element,
        values: {
          _: {
            ...this.element._,
            compactMenuOpen: false,
          },
        },
      })
    },
  },
}
</script>
