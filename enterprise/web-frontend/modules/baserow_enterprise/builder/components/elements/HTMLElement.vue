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
        :message="$t('iframeElementForm.editorEmbedHint')"
      />
    </template>
  </div>
  <div
    v-else-if="
      ['preview', 'public'].includes(applicationContext.mode) &&
      !builder.untrusted_content &&
      resolvedHTML
    "
    v-html-content="resolvedHTML"
  ></div>
</template>

<script>
import ElementPreviewHint from '@baserow/modules/builder/components/elements/ElementPreviewHint'
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'
import HTMLElementPreview from '@baserow_enterprise/builder/components/elements/HTMLElementPreview'
import { runInsertedScripts } from '@baserow_enterprise/builder/htmlElementScripts'

const RUN = Symbol('htmlElementScriptRun')

function insertHTML(host, { value, oldValue }) {
  if (value === oldValue) {
    return
  }
  host.innerHTML = value
  const run = Symbol('run')
  host[RUN] = run
  runInsertedScripts(host, () => host[RUN] === run)
}

export default {
  name: 'BuilderHTMLElement',
  components: { ElementPreviewHint, HTMLElementPreview },
  mixins: [element],
  computed: {
    resolvedHTML() {
      return ensureString(this.resolveFormula(this.element.html))
    },
  },
  directives: {
    // Insert client-side and run the snippet's scripts, which `innerHTML`
    // alone leaves inert. A newer render cancels a run still loading scripts.
    htmlContent: {
      mounted: insertHTML,
      updated: insertHTML,
      beforeUnmount(host) {
        host[RUN] = null
      },
    },
  },
}
</script>
