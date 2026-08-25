import { createApplicationBuilderMarkdownRules } from '@baserow/modules/builder/utils/markdown'

/**
 * Shared behaviour for elements and collection fields that render Markdown
 * through the global `MarkdownIt` component: the Application Builder renderer
 * rules and the click handler that keeps internal links inside the SPA router.
 *
 * Requires `builder` and `mode` on the component, which are both provided by
 * the `element` / `collectionField` mixins via inject.
 */
export default {
  computed: {
    // Custom rules to pass down to the `MarkdownIt` component. The goal is to
    // make the styling of the rendered markdown content consistent with the
    // rest of the application builder CSS classes.
    markdownRules() {
      return createApplicationBuilderMarkdownRules({
        builder: this.builder,
        mode: this.mode,
      })
    },
  },
  methods: {
    onMarkdownClick(event) {
      if (this.mode === 'editing') {
        event.preventDefault()
        return
      }
      if (event.target.classList.contains('ab-link')) {
        const url = event.target.getAttribute('href')

        if (url.startsWith('/')) {
          event.preventDefault()
          this.$router.push(url)
        }
      }
    },
  },
}
