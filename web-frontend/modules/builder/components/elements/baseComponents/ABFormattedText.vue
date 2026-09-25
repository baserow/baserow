<template>
  <component
    :is="isInline ? 'span' : 'div'"
    class="ab-formatted-text"
    :class="{
      'ab-formatted-text--inline': isInline,
      'ab-formatted-text--block': !isInline,
    }"
  >
    <component
      :is="renderer"
      :value="value"
      :profile="profile"
      :allow-links="allowLinks"
    />
  </component>
</template>

<script>
import ABMarkdownText from '@baserow/modules/builder/components/elements/baseComponents/ABMarkdownText.vue'
import ABPlainText from '@baserow/modules/builder/components/elements/baseComponents/ABPlainText.vue'
import formattedTextRenderer from '@baserow/modules/builder/mixins/formattedTextRenderer'
import {
  BASEROW_FORMULA_FORMAT_MARKDOWN,
  BASEROW_FORMULA_FORMAT_PLAIN,
  BASEROW_FORMULA_FORMATS,
} from '@baserow/modules/core/formula/constants'

/**
 * The renderer of each format. Every renderer takes the props of the
 * `formattedTextRenderer` mixin. A new format only needs its constant and an
 * entry here.
 */
const FORMAT_RENDERERS = {
  [BASEROW_FORMULA_FORMAT_PLAIN]: ABPlainText,
  [BASEROW_FORMULA_FORMAT_MARKDOWN]: ABMarkdownText,
}

/**
 * Renders the resolved value of a formula in its `format`, plain text or
 * markdown, with one of two profiles:
 *
 * - `inline`: for text that sits inside something else, like a table header
 *   cell, a form label or a dropdown option. It inherits the surrounding
 *   typography and never breaks the line.
 * - `block`: for text that stands on its own, like the Text element.
 *
 * This component only provides the root element and picks the renderer of the
 * format, see `FORMAT_RENDERERS`; what a profile means for a format is up to
 * its renderer.
 */
export default {
  name: 'ABFormattedText',
  mixins: [formattedTextRenderer],
  props: {
    /**
     * The `format` of the formula object the value came from.
     */
    format: {
      type: String,
      required: false,
      default: BASEROW_FORMULA_FORMAT_PLAIN,
      validator: (value) => BASEROW_FORMULA_FORMATS.includes(value),
    },
  },
  computed: {
    renderer() {
      // An unknown format (the validator warns about it) still shows its text.
      return FORMAT_RENDERERS[this.format] ?? ABPlainText
    },
  },
}
</script>
