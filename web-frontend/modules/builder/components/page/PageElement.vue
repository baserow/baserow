<template>
  <div
    v-if="elementMode === 'editing' || isVisible"
    class="element__wrapper"
    :class="wrapperClasses"
    :style="elementStyles"
  >
    <div class="element__inner-wrapper">
      <span v-if="showElementId" class="element--element-id">{{
        element.id
      }}</span>
      <!-- See element store to understand why we are using the element uid as key here -->
      <component
        :is="component"
        :key="element._.uid"
        :element="element"
        class="element"
        :application-context-additions="{ element }"
        :class="elementClasses"
        @move="$emit('move', $event)"
      />
    </div>
  </div>
</template>

<script>
import { resolveColor, colorContrast } from '@baserow/modules/core/utils/colors'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'

import {
  BACKGROUND_TYPES,
  CHILD_WIDTH_TYPES,
  WIDTH_TYPES,
  BACKGROUND_MODES,
} from '@baserow/modules/builder/enums'
import applicationContextMixin from '@baserow/modules/builder/mixins/applicationContext'

import { mapGetters } from 'vuex'

export default {
  name: 'PageElement',
  mixins: [applicationContextMixin],
  inject: ['workspace', 'builder', 'mode', 'currentPage'],
  provide() {
    return { mode: this.elementMode, elementPage: this.elementPage }
  },
  props: {
    element: {
      type: Object,
      required: true,
    },
    forceMode: {
      type: String,
      required: false,
      default: null,
    },
    showElementId: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    BACKGROUND_TYPES: () => BACKGROUND_TYPES,
    CHILD_WIDTH_TYPES: () => CHILD_WIDTH_TYPES,
    WIDTH_TYPES: () => WIDTH_TYPES,
    applicationContext() {
      return {
        ...this.injectedApplicationContext,
        ...this.applicationContextAdditions,
        element: this.element,
      }
    },
    themeConfigBlocks() {
      return this.$registry.getOrderedList('themeConfigBlock')
    },
    colorVariables() {
      return ThemeConfigBlockType.getAllColorVariables(
        this.themeConfigBlocks,
        this.builder.theme
      )
    },
    elementMode() {
      return this.forceMode !== null ? this.forceMode : this.mode
    },
    component() {
      const elementType = this.$registry.get('element', this.element.type)
      const componentName =
        this.elementMode === 'editing' ? 'editComponent' : 'component'
      return elementType[componentName]
    },
    ...mapGetters({
      loggedUser: 'userSourceUser/getUser',
    }),
    elementPage() {
      // We use the page from the element itself
      return this.$store.getters['page/getById'](
        this.builder,
        this.element.page_id
      )
    },
    elementType() {
      return this.$registry.get('element', this.element.type)
    },
    elementClasses() {
      return this.element.css_classes.replaceAll('"', '')
    },
    isVisible() {
      const isInError = this.elementType.isInError(
        this.element,
        this.applicationContext
      )

      if (this.mode !== 'editing' && isInError) {
        return false
      }

      return this.elementType.isVisible({
        element: this.element,
        applicationContext: this.applicationContext,
      })
    },
    wrapperClasses() {
      if (this.element?.parent_element_id) {
        return {
          'element__wrapper--full-width':
            this.element.style_width_child === CHILD_WIDTH_TYPES.NORMAL.value,
          'element__wrapper--medium-width':
            this.element.style_width_child === CHILD_WIDTH_TYPES.MEDIUM.value,
          'element__wrapper--small-width':
            this.element.style_width_child === CHILD_WIDTH_TYPES.SMALL.value,
        }
      } else {
        return {
          'element__wrapper--full-bleed':
            this.element.style_width === WIDTH_TYPES.FULL.value,
          'element__wrapper--full-width':
            this.element.style_width === WIDTH_TYPES.FULL_WIDTH.value,
          'element__wrapper--medium-width':
            this.element.style_width === WIDTH_TYPES.MEDIUM.value,
          'element__wrapper--small-width':
            this.element.style_width === WIDTH_TYPES.SMALL.value,
        }
      }
    },
    elementStyles() {
      const styles = {
        '--element-background-color':
          this.element.style_background === BACKGROUND_TYPES.COLOR
            ? this.resolveColor(
                this.element.style_background_color,
                this.colorVariables
              )
            : 'none',
        '--element-background-image':
          this.element.style_background_file !== null
            ? `url(${this.element.style_background_file.url})`
            : 'none',

        '--element-border-top': this.border(
          this.element.style_border_top_size,
          this.element.style_border_top_color
        ),
        '--element-margin-top': `${this.element.style_margin_top || 0}px`,
        '--element-padding-top': `${this.element.style_padding_top || 0}px`,
        '--element-border-bottom': this.border(
          this.element.style_border_bottom_size,
          this.element.style_border_bottom_color
        ),
        '--element-margin-bottom': `${this.element.style_margin_bottom || 0}px`,
        '--element-padding-bottom': `${
          this.element.style_padding_bottom || 0
        }px`,
        '--element-border-left': this.border(
          this.element.style_border_left_size,
          this.element.style_border_left_color
        ),
        '--element-margin-left': `${this.element.style_margin_left || 0}px`,
        '--element-padding-left': `${this.element.style_padding_left || 0}px`,
        '--element-border-right': this.border(
          this.element.style_border_right_size,
          this.element.style_border_right_color
        ),
        '--element-margin-right': `${this.element.style_margin_right || 0}px`,

        '--element-padding-right': `${this.element.style_padding_right || 0}px`,

        '--element-background-radius': `${
          this.element.style_background_radius || 0
        }px`,
        '--element-border-radius': `${this.element.style_border_radius || 0}px`,
      }

      if (this.element.style_background === BACKGROUND_TYPES.COLOR) {
        styles['--element-background-color-contrast'] = colorContrast(
          this.resolveColor(
            this.element.style_background_color,
            this.colorVariables
          )
        )
      }

      if (this.element.style_background_file !== null) {
        if (this.element.style_background_mode === BACKGROUND_MODES.FILL) {
          styles['--element-background-size'] = 'cover'
          styles['--element-background-repeat'] = 'no-repeat'
        }
        if (this.element.style_background_mode === BACKGROUND_MODES.TILE) {
          styles['--element-background-size'] = 'auto'
          styles['--element-background-repeat'] = 'repeat'
        }
        if (this.element.style_background_mode === BACKGROUND_MODES.FIT) {
          styles['--element-background-size'] = 'contain'
          styles['--element-background-repeat'] = 'no-repeat'
        }
      }

      return styles
    },
  },
  methods: {
    resolveColor,
    border(size, color) {
      if (!size) {
        return 'none'
      }
      return `solid ${size}px ${this.resolveColor(color, this.colorVariables)}`
    },
  },
}
</script>
