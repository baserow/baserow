<template>
  <div
    v-if="isEditMode || applicationContext.mode === 'editing'"
    class="html-element__editor"
  >
    <p
      v-if="builder.untrusted_content || !resolvedHTML.trim()"
      class="html-element__placeholder"
    >
      {{
        builder.untrusted_content
          ? $t('iframeElementForm.untrustedContent')
          : $t('htmlElement.placeholder')
      }}
    </p>
    <template v-else>
      <ClientOnly>
        <HTMLElementPreview :html="resolvedHTML" />
      </ClientOnly>
      <ElementPreviewHint
        class="html-element__hint"
        :message="authorCodeEditorHint"
      />
    </template>
  </div>
  <!-- Without its scripts and event handlers, like in the editor. -->
  <ClientOnly v-else-if="showHTML && isAuthorCodeRestricted">
    <HTMLElementPreview :html="resolvedHTML" :max-height="null" />
  </ClientOnly>
  <div v-else-if="showHTML" v-html-content="resolvedHTML"></div>
</template>

<script>
import ElementPreviewHint from '@baserow/modules/builder/components/elements/ElementPreviewHint'
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'
import HTMLElementPreview from '@baserow_enterprise/builder/components/elements/HTMLElementPreview'

export default {
  name: 'BuilderHTMLElement',
  components: { ElementPreviewHint, HTMLElementPreview },
  mixins: [element],
  computed: {
    resolvedHTML() {
      return ensureString(this.resolveFormula(this.element.html))
    },
    showHTML() {
      return (
        ['preview', 'public'].includes(this.applicationContext.mode) &&
        !this.builder.untrusted_content &&
        Boolean(this.resolvedHTML)
      )
    },
  },
  directives: {
    // Insert client-side; script loading remains in application settings.
    htmlContent(host, { value, oldValue }) {
      if (value !== oldValue) {
        host.innerHTML = value
      }
    },
  },
}
</script>
