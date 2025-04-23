<template>
  <div
    :class="[
      'menu-element__wrapper',
      `menu-element__align-${element.alignment.toLowerCase()}`,
    ]"
  >
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
          <ABMenuItem
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
            <ABMenuItem
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
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { HORIZONTAL_ALIGNMENTS } from '@baserow/modules/builder/enums'

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
}
</script>
