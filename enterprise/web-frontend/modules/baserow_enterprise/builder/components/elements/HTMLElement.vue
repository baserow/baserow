<template>
  <div
    v-if="isEditMode || applicationContext.mode === 'editing'"
    class="html-element__placeholder"
  >
    {{ $t('htmlElement.placeholder') }}
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
import element from '@baserow/modules/builder/mixins/element'
import { parseStaticHTML } from '@baserow_enterprise/builder/staticHtml'

export default {
  name: 'BuilderHTMLElement',
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
