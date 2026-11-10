<template>
  <div
    v-if="isEditMode || applicationContext.mode === 'editing'"
    class="html-element__editor"
  >
    <div
      v-if="builder.untrusted_content || !element.html?.trim()"
      class="html-element__placeholder"
    >
      {{
        builder.untrusted_content
          ? $t('iframeElementForm.untrustedContent')
          : $t('htmlElement.placeholder')
      }}
    </div>
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
    v-static-html="element.html"
  ></div>
</template>

<script>
import ElementPreviewHint from '@baserow/modules/builder/components/elements/ElementPreviewHint'
import element from '@baserow/modules/builder/mixins/element'
import { parseStaticHTML } from '@baserow_enterprise/builder/staticHtml'
import HTMLElementPreview from '@baserow_enterprise/builder/components/elements/HTMLElementPreview'

export default {
  name: 'BuilderHTMLElement',
  components: { ElementPreviewHint, HTMLElementPreview },
  mixins: [element],
  directives: {
    staticHtml(host, { value, oldValue }) {
      if (value !== oldValue) {
        host.replaceChildren(parseStaticHTML(value) ?? '')
      }
    },
  },
}
</script>
