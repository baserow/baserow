<template>
  <div class="iframe-element">
    <p
      v-if="
        (element.source_type === IFRAME_SOURCE_TYPES.URL && !resolvedURL) ||
        (element.source_type === IFRAME_SOURCE_TYPES.EMBED && !resolvedEmbed)
      "
      class="iframe-element__empty"
      :style="{ height: `${element.height}px` }"
    >
      {{
        element.url || element.embed
          ? mode === 'editing'
            ? $t('iframeElementForm.emptyValue')
            : ''
          : $t('iframeElementForm.missingValue')
      }}
    </p>
    <template v-else>
      <client-only
        ><iframe
          class="iframe-element__iframe"
          :height="element.height"
          :src="
            element.source_type === IFRAME_SOURCE_TYPES.URL ? resolvedURL : null
          "
          :srcdoc="
            element.source_type === IFRAME_SOURCE_TYPES.EMBED
              ? resolvedEmbed
              : null
          "
          :style="isEditMode ? 'pointer-events: none' : ''"
        >
        </iframe>
        <template #placeholder>
          <div
            :style="{ height: `${element.height}px` }"
            class="loading-spinner iframe-element__placeholder"
          />
        </template>
      </client-only>
    </template>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { IFRAME_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'IFrameElement',
  mixins: [element],
  props: {
    /**
     * @type {Object}
     * @property {string} source_type - If the iframe is an external URL or embed
     * @property {string} url - A link to the page to embed (optional)
     * @property {string} embed - Inline HTML to be embedded (optional)
     * @property {string} height - Height in pixels of the iframe (optional)
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    resolvedURL() {
      return ensureString(this.resolveFormula(this.element.url))
    },
    resolvedEmbed() {
      return ensureString(this.resolveFormula(this.element.embed))
    },
    IFRAME_SOURCE_TYPES() {
      return IFRAME_SOURCE_TYPES
    },
  },
}
</script>
