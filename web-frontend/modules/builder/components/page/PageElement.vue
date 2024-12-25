<template>
  <div
    v-if="elementMode === 'editing' || isVisible"
    class="element__wrapper"
    :class="{
      'element__wrapper--full-bleed':
        element.style_width === WIDTH_TYPES.FULL.value,
      'element__wrapper--full-width':
        element.style_width === WIDTH_TYPES.FULL_WIDTH.value,
      'element__wrapper--medium-width':
        element.style_width === WIDTH_TYPES.MEDIUM.value,
      'element__wrapper--small-width':
        element.style_width === WIDTH_TYPES.SMALL.value,
    }"
    :style="elementStyles"
  >
    <div class="element__inner-wrapper">
      <component
        :is="component"
        :key="element._.uid"
        :element="element"
        :application-context-additions="{
          element,
          page: elementPage,
        }"
        class="element"
        v-on="$listeners"
      />
    </div>
  </div>
</template>

<script>
import { resolveColor } from '@baserow/modules/core/utils/colors'
import { themeToColorVariables } from '@baserow/modules/builder/utils/theme'

import {
  BACKGROUND_TYPES,
  WIDTH_TYPES,
  BACKGROUND_MODES,
} from '@baserow/modules/builder/enums'
import applicationContextMixin from '@baserow/modules/builder/mixins/applicationContext'
import {
  VISIBILITY_NOT_LOGGED,
  VISIBILITY_LOGGED_IN,
  ROLE_TYPE_ALLOW_EXCEPT,
  ROLE_TYPE_DISALLOW_EXCEPT,
} from '@baserow/modules/builder/constants'
import { mapGetters } from 'vuex'

export default {
  name: 'PageElement',
  mixins: [applicationContextMixin],
  inject: ['builder', 'mode', 'currentPage'],
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
  },
  computed: {
    BACKGROUND_TYPES: () => BACKGROUND_TYPES,
    WIDTH_TYPES: () => WIDTH_TYPES,
    colorVariables() {
      return themeToColorVariables(this.builder.theme)
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
    isVisible() {
      const elementType = this.$registry.get('element', this.element.type)
      const isInError = elementType.isInError({
        page: this.elementPage,
        element: this.element,
        builder: this.builder,
      })

      if (this.mode !== 'editing' && isInError) {
        return false
      }

      if (
        !this.elementType.isVisible({
          element: this.element,
          currentPage: this.currentPage,
        })
      ) {
        return false
      }

      const isAuthenticated = this.$store.getters[
        'userSourceUser/isAuthenticated'
      ](this.builder)
      const user = this.loggedUser(this.builder)
      const roles = this.element.roles
      const roleType = this.element.role_type

      const visibility = this.element.visibility
      if (visibility === VISIBILITY_LOGGED_IN) {
        if (!isAuthenticated) {
          return false
        }

        if (roleType === ROLE_TYPE_ALLOW_EXCEPT) {
          return !roles.includes(user.role)
        } else if (roleType === ROLE_TYPE_DISALLOW_EXCEPT) {
          return roles.includes(user.role)
        } else {
          return true
        }
      } else if (visibility === VISIBILITY_NOT_LOGGED) {
        return !isAuthenticated
      } else {
        return true
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
