<template>
  <div
    v-if="isEditor || (!builder.untrusted_content && resolvedHTML)"
    :class="{ 'html-element__editor': isEditor }"
  >
    <p
      v-if="builder.untrusted_content || !resolvedHTML"
      class="html-element__placeholder"
    >
      {{
        builder.untrusted_content
          ? $t('iframeElementForm.untrustedContent')
          : $t('htmlElement.placeholder')
      }}
    </p>
    <template v-else>
      <ClientOnly v-if="isAuthorCodeRestricted">
        <HTMLElementPreview :html="resolvedHTML" :interactive="!isEditor" />
      </ClientOnly>
      <div v-else v-html-content="resolvedHTML"></div>
      <ElementPreviewHint
        v-if="isEditor && isAuthorCodeRestricted"
        class="html-element__hint"
        :message="authorCodeEditorHint"
      />
    </template>
  </div>
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
    isEditor() {
      return this.applicationContext.mode === 'editing'
    },
    resolvedHTML() {
      return ensureString(this.resolveFormula(this.element.html)).trim()
    },
  },
  directives: {
    // Insert client-side and run the snippet's scripts, which `innerHTML`
    // alone leaves inert. Only used where author code isn't restricted. A
    // newer render cancels a run still loading scripts.
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
