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
    <p
      v-else-if="shouldShowEditorURLPlaceholder"
      class="iframe-element__empty iframe-element__editor-placeholder"
      :style="{ height: `${element.height}px` }"
    >
      {{ $t('iframeElementForm.editorPreviewPlaceholder') }}
    </p>
    <template v-else>
      <client-only
        ><iframe
          :key="autoHeight ? resolvedEmbed : null"
          ref="iframe"
          class="iframe-element__iframe"
          :height="
            autoHeight ? (measuredHeight ?? element.height) : element.height
          "
          :src="
            element.source_type === IFRAME_SOURCE_TYPES.URL ? resolvedURL : null
          "
          :srcdoc="
            element.source_type === IFRAME_SOURCE_TYPES.EMBED
              ? embedSrcdoc
              : null
          "
          :sandbox="sandboxPermissions"
          :style="isEditMode ? 'pointer-events: none' : ''"
          @load="onIframeLoad"
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
import {
  createAutoHeightEmbed,
  EMBED_HEIGHT_MESSAGE,
} from '@baserow/modules/builder/utils/iframe'

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
  data() {
    return { measuredHeight: null }
  },
  computed: {
    autoHeight() {
      return (
        this.element.source_type === IFRAME_SOURCE_TYPES.EMBED &&
        this.element.auto_height === true
      )
    },
    embedSrcdoc() {
      return this.autoHeight
        ? createAutoHeightEmbed(this.resolvedEmbed)
        : this.resolvedEmbed
    },
    resolvedURL() {
      return ensureString(this.resolveFormula(this.element.url))
    },
    resolvedEmbed() {
      return ensureString(this.resolveFormula(this.element.embed))
    },
    shouldShowEditorURLPlaceholder() {
      return (
        this.element.source_type === IFRAME_SOURCE_TYPES.URL &&
        Boolean(this.resolvedURL) &&
        (this.isEditMode || this.applicationContext.mode === 'editing')
      )
    },
    sandboxPermissions() {
      if (this.isEditMode) {
        return this.element.source_type === IFRAME_SOURCE_TYPES.EMBED
          ? 'allow-scripts'
          : ''
      }
      if (this.element.source_type !== IFRAME_SOURCE_TYPES.URL) {
        return null
      }

      const permissions = ['allow-scripts', 'allow-forms', 'allow-popups']

      if (
        this.element.allow_same_origin &&
        this.isPreviewOrPublicMode &&
        this.isExternalURL
      ) {
        permissions.push('allow-same-origin')
      }

      return permissions.join(' ')
    },
    isExternalURL() {
      if (typeof window === 'undefined') {
        return false
      }

      try {
        const url = new URL(this.resolvedURL)
        return (
          ['http:', 'https:'].includes(url.protocol) &&
          url.origin !== window.location.origin
        )
      } catch {
        return false
      }
    },
    isPreviewOrPublicMode() {
      return ['preview', 'public'].includes(this.applicationContext.mode)
    },
    IFRAME_SOURCE_TYPES() {
      return IFRAME_SOURCE_TYPES
    },
  },
  watch: {
    embedSrcdoc() {
      this.measuredHeight = null
    },
  },
  mounted() {
    window.addEventListener('message', this.onEmbedHeight)
  },
  beforeUnmount() {
    window.removeEventListener('message', this.onEmbedHeight)
  },
  methods: {
    onIframeLoad() {
      this.measuredHeight = null
      if (this.autoHeight) {
        this.$refs.iframe?.contentWindow?.postMessage(
          { type: `${EMBED_HEIGHT_MESSAGE}:request` },
          '*'
        )
      }
    },
    onEmbedHeight(event) {
      const iframe = this.$refs.iframe
      if (
        !this.autoHeight ||
        !iframe ||
        !event.source ||
        event.source !== iframe.contentWindow ||
        event.data?.type !== EMBED_HEIGHT_MESSAGE ||
        !Number.isSafeInteger(event.data.height) ||
        event.data.height < 0
      ) {
        return
      }
      this.measuredHeight = event.data.height
    },
  },
}
</script>
