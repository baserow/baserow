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
  <div v-else-if="showHTML" v-html-content:[scriptMode]="resolvedHTML"></div>
</template>

<script>
import ElementPreviewHint from '@baserow/modules/builder/components/elements/ElementPreviewHint'
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'
import HTMLElementPreview from '@baserow_enterprise/builder/components/elements/HTMLElementPreview'
import {
  parseWithoutScripts,
  runInsertedScripts,
} from '@baserow_enterprise/builder/htmlElementScripts'
import { previewSharesEditorHostname } from '@baserow/modules/builder/utils/preview'

const RUN = Symbol('htmlElementScriptRun')

function insertHTML(host, { value, oldValue, arg }) {
  if (value === oldValue) {
    return
  }
  if (arg === 'run') {
    host.innerHTML = value
  } else {
    host.replaceChildren(parseWithoutScripts(value))
  }
  const run = Symbol('run')
  host[RUN] = run
  if (arg === 'run') {
    runInsertedScripts(host, () => host[RUN] === run)
  }
}

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
    /**
     * Preview on the editor's hostname shares the editor's cookies, so the
     * snippet's scripts and event handlers don't run there, like head HTML and
     * custom JavaScript aren't added there.
     */
    scriptMode() {
      return this.applicationContext.mode === 'preview' &&
        previewSharesEditorHostname(this.$config.public)
        ? 'inert'
        : 'run'
    },
  },
  directives: {
    // Insert client-side and, with the `run` argument, run the snippet's
    // scripts, which `innerHTML` alone leaves inert. Otherwise anything that
    // would run JavaScript is removed first. A newer render cancels a run
    // still loading scripts.
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
