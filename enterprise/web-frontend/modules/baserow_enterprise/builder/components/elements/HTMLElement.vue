<template>
  <div
    v-if="isEditMode || applicationContext.mode === 'editing'"
    class="html-element__editor"
  >
    <p
      v-if="builder.untrusted_content || !element.html?.trim()"
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
        <HTMLElementPreview :html="element.html" />
      </ClientOnly>
      <ElementPreviewHint
        class="html-element__hint"
        :message="$t('iframeElementForm.editorEmbedHint')"
      />
    </template>
  </div>
  <div
    v-else-if="
      ['preview', 'public'].includes(applicationContext.mode) &&
      !builder.untrusted_content &&
      element.html
    "
    v-html-content="element.html"
  ></div>
</template>

<script>
import ElementPreviewHint from '@baserow/modules/builder/components/elements/ElementPreviewHint'
import element from '@baserow/modules/builder/mixins/element'
import HTMLElementPreview from '@baserow_enterprise/builder/components/elements/HTMLElementPreview'

export default {
  name: 'BuilderHTMLElement',
  components: { ElementPreviewHint, HTMLElementPreview },
  mixins: [element],
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
