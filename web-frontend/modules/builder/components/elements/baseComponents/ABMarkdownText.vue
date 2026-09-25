<template>
  <MarkdownIt
    :content="value"
    :rules="rules"
    :inline="isInline"
    :disabled-rules="disabledRules"
    @click="onClick"
  />
</template>

<script>
import formattedTextRenderer from '@baserow/modules/builder/mixins/formattedTextRenderer'
import { createApplicationBuilderMarkdownRules } from '@baserow/modules/builder/utils/markdown'

/**
 * The markdown renderer of `ABFormattedText`. The inline profile only uses the
 * inline syntax: it never breaks the line and never shows an image. Links
 * follow the Application Builder rules (internal `/` links go through the
 * router, nothing navigates in editing mode) and can be switched off with
 * `allowLinks`. Outside editing mode a click on a link stops here, so that an
 * ancestor with a click handler of its own (a drop zone, a row) doesn't react
 * to it as well.
 */
export default {
  name: 'ABMarkdownText',
  mixins: [formattedTextRenderer],
  // Both are provided by the page and the editor preview; the defaults let the
  // component render outside of them, e.g. in the toasts container.
  inject: {
    builder: { from: 'builder', default: null },
    mode: { from: 'mode', default: null },
  },
  computed: {
    // Custom rules to pass down to `MarkdownIt`, so that the rendered markdown
    // uses the Application Builder CSS classes.
    rules() {
      return createApplicationBuilderMarkdownRules({
        builder: this.builder,
        mode: this.mode,
      })
    },
    disabledRules() {
      const rules = this.isInline ? ['newline', 'image'] : []
      if (!this.allowLinks) {
        rules.push('link', 'autolink')
      }
      return rules
    },
  },
  methods: {
    onClick(event) {
      if (this.mode === 'editing') {
        // The click still bubbles: the editor selects the element with it.
        event.preventDefault()
        return
      }
      // Markdown can nest inline elements inside a link (`[**bold**](url)`),
      // so the click target isn't always the anchor itself. The lookup stays
      // within this component's own markup.
      const link = event.target.closest('a.ab-link')
      if (link && this.$el.contains(link)) {
        // The click belongs to the link: nothing above must act on it too.
        event.stopPropagation()

        const url = link.getAttribute('href')
        if (url?.startsWith('/')) {
          event.preventDefault()
          this.$router.push(url)
        }
      }
    },
  },
}
</script>
