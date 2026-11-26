<template>
  <div class="iframe-element">
    <p
      v-if="builder.untrusted_content"
      class="iframe-element__empty"
      :style="{ height: `${element.height}px` }"
    >
      {{ $t('iframeElementForm.untrustedContent') }}
    </p>
    <p
      v-else-if="
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
          :sandbox="sandboxPermissions"
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
      <ElementPreviewHint
        v-if="shouldShowEditorEmbedHint"
        class="iframe-element__editor-hint"
        :message="authorCodeEditorHint"
      />
    </template>
  </div>
</template>

<script>
import ElementPreviewHint from '@baserow/modules/builder/components/elements/ElementPreviewHint'
import element from '@baserow/modules/builder/mixins/element'
import { IFRAME_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import { ensureString } from '@baserow/modules/core/utils/validator'

const RESTRICTED_SANDBOX = 'allow-scripts allow-forms allow-popups'

export default {
  name: 'IFrameElement',
  components: { ElementPreviewHint },
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
    shouldShowEditorURLPlaceholder() {
      return (
        this.element.source_type === IFRAME_SOURCE_TYPES.URL &&
        Boolean(this.resolvedURL) &&
        (this.isEditMode || this.applicationContext.mode === 'editing')
      )
    },
    shouldShowEditorEmbedHint() {
      return (
        this.element.source_type === IFRAME_SOURCE_TYPES.EMBED &&
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
        // An unsandboxed embed shares the page's origin, so its scripts could
        // act as the logged-in editor.
        return this.isAuthorCodeRestricted ? RESTRICTED_SANDBOX : null
      }

      const permissions = RESTRICTED_SANDBOX.split(' ')

      if (
        this.element.allow_same_origin &&
        this.isPreviewOrPublicMode &&
        this.isExternalURL
      ) {
        permissions.push('allow-same-origin')
      }

      return permissions.join(' ')
    },
    /** Whether the URL uses a hostname outside this page and the web frontend. */
    isExternalURL() {
      if (typeof window === 'undefined') {
        return false
      }

      try {
        const url = new URL(this.resolvedURL)
        const frontendHostname = new URL(
          this.$config.public.publicWebFrontendUrl
        ).hostname
        const extraFrontendHostnames =
          this.$config.public.extraPublicWebFrontendHostnames || []

        // Cookies ignore ports, so a different origin on a frontend hostname
        // must not gain cookie access through allow-same-origin.
        return (
          ['http:', 'https:'].includes(url.protocol) &&
          url.hostname !== window.location.hostname &&
          url.hostname !== frontendHostname &&
          !extraFrontendHostnames.includes(url.hostname)
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
}
</script>
