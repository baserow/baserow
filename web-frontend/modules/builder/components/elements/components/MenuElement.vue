<template>
  <div
    :style="{
      '--alignment': menuAlignment,
    }"
    :class="menuContainerClass"
  >
    <template v-if="!isMobileDevice">
      <div
        v-for="item in element.menu_items"
        :key="item.id"
        :class="`menu-element__menu-item-${item.type}`"
      >
        <ABMenuItem :key="item.uid" :menu-item="item" :element="element" />
      </div>
    </template>

    <template v-else>
      <div
        :class="[
          element.alignment === alignments.LEFT
            ? 'menu-element__burger-menu-left'
            : 'menu-element__burger-menu-right',
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
          <ABMenuItem :key="item.uid" :menu-item="item" :element="element" />
        </div>
      </template>
    </template>

    <div v-if="!element.menu_items.length" class="element--no-value">
      {{ $t('menuElement.missingValue') }}
    </div>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { HORIZONTAL_ALIGNMENTS } from '@baserow/modules/builder/enums'

/**
 * @typedef MenuElement
 * @property {Array}  menu_items Array of Menu items
 */

export default {
  name: 'MenuElement',
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
    alignments() {
      return HORIZONTAL_ALIGNMENTS
    },
    menuContainerClass() {
      const classes = ['menu-element__container']
      if (this.isMobileDevice) {
        classes.push('menu-element__container--mobile')
        if (this.burgerMenuActive) {
          classes.push('menu-element__burger-full-screen')
        }
      } else {
        classes.push(`menu-element__container--${this.element.orientation}`)
      }
      return classes
    },
    menuAlignment() {
      const alignmentsCSS = {
        [HORIZONTAL_ALIGNMENTS.LEFT]: 'flex-start',
        [HORIZONTAL_ALIGNMENTS.CENTER]: 'center',
        [HORIZONTAL_ALIGNMENTS.RIGHT]: 'flex-end',
      }
      return alignmentsCSS[this.element.alignment]
    },
    isMobileDevice() {
      return this.$store.getters['page/getDeviceTypeSelected'] === 'smartphone'
    },
  },
}
</script>
