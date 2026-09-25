<template>
  <component
    :is="isInline ? 'span' : 'div'"
    class="ab-formatted-text"
    :class="{
      'ab-formatted-text--inline': isInline,
      'ab-formatted-text--block': !isInline,
    }"
    @click="onClick"
  >
    <MarkdownIt
      v-if="isMarkdown"
      :content="value"
      :rules="rules"
      :inline="isInline"
      :disabled-rules="disabledRules"
    />
    <template v-else-if="isInline">{{ value }}</template>
    <template v-else>
      <ABParagraph v-for="paragraph in paragraphs" :key="paragraph.id">
        {{ paragraph.content }}
      </ABParagraph>
    </template>
  </component>
</template>

<script>
import { generateHash } from '@baserow/modules/core/utils/hashing'
import { createApplicationBuilderMarkdownRules } from '@baserow/modules/builder/utils/markdown'
import {
  BASEROW_FORMULA_FORMAT_MARKDOWN,
  BASEROW_FORMULA_FORMAT_PLAIN,
  BASEROW_FORMULA_FORMATS,
} from '@baserow/modules/core/formula/constants'

/**
 * @typedef Paragraph
 * @property {string} content - The text of the paragraph
 * @property {string} id - A hash identifying the paragraph
 */

/**
 * Renders the resolved value of a formula in its `format`, plain text or
 * markdown, with one of two profiles:
 *
 * - `inline`: for text that sits inside something else, like a table header
 *   cell, a form label or a dropdown option. Markdown is rendered inline, so
 *   it inherits the surrounding typography, never breaks the line and never
 *   shows an image.
 * - `block`: for text that stands on its own, like the Text element. Plain
 *   text is split into paragraphs, markdown follows the Text element rules.
 *
 * Links follow the Application Builder rules (internal `/` links go through
 * the router, nothing navigates in editing mode) and can be switched off with
 * `allowLinks`. Outside editing mode a click on a link stops here, so that an
 * ancestor with a click handler of its own (a drop zone, a row) doesn't react
 * to it as well.
 */
export default {
  name: 'ABFormattedText',
  // Both are provided by the page and the editor preview; the defaults let the
  // component render outside of them, e.g. in the toasts container.
  inject: {
    builder: { from: 'builder', default: null },
    mode: { from: 'mode', default: null },
  },
  props: {
    /**
     * The resolved value to render, as a string.
     */
    value: {
      type: String,
      required: false,
      default: '',
    },
    /**
     * The `format` of the formula object the value came from.
     */
    format: {
      type: String,
      required: false,
      default: BASEROW_FORMULA_FORMAT_PLAIN,
      validator: (value) => BASEROW_FORMULA_FORMATS.includes(value),
    },
    profile: {
      type: String,
      required: false,
      default: 'inline',
      validator: (value) => ['inline', 'block'].includes(value),
    },
    allowLinks: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  computed: {
    isInline() {
      return this.profile === 'inline'
    },
    isMarkdown() {
      return this.format === BASEROW_FORMULA_FORMAT_MARKDOWN
    },
    /**
     * The plain text split into paragraphs, for the block profile.
     * @returns {Array.<Paragraph>}
     */
    paragraphs() {
      return this.value
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line)
        .map((line, index) => ({
          content: line,
          id: generateHash(line + index),
        }))
    },
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
