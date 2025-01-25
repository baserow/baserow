<template>
  <div
    class="link-element"
    :class="classes"
    :style="getStyleOverride(element.variant)"
  >
    <ABLink :target="element.target" :url="url" :variant="element.variant">
      {{
        element.value
          ? resolvedValue ||
            (mode === 'editing' ? $t('linkElement.emptyValue') : '&nbsp;')
          : $t('linkElement.missingValue')
      }}
    </ABLink>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'
import { ensureString } from '@baserow/modules/core/utils/validator'

/**
 * @typedef LinkElement
 * @property {string} value The text inside the button
 * @property {string} variant link|button
 * @property {string} navigation_type page|custom
 * @property {string} navigate_to_page_id The page id for `page` navigation type.
 * @property {object} page_parameters the page parameters
 * @property {string} navigate_to_url The URL for `custom` navigation type.
 * @property {string} target self|blank
 */

export default {
  name: 'LinkElement',
  mixins: [element],
  props: {
    /**
     * @type {LinkElement}
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    resolvedValue() {
      return ensureString(this.resolveFormula(this.element.value))
    },
    pages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
    classes() {
      return {
        'element--no-value': !this.resolvedValue,
      }
    },
    url() {
      try {
        return resolveElementUrl(
          this.element,
          this.builder,
          this.pages,
          this.resolveFormula,
          this.mode
        )
      } catch (e) {
        return '#error'
      }
    },
  },
}
</script>
