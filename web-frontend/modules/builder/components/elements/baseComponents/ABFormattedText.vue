<template>
  <component
    :is="renderer"
    :value="value"
    :profile="profile"
    :allow-links="allowLinks"
  />
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
 * `formattedTextRenderer` mixin and renders its own root element. A new format
 * only needs its constant and an entry here.
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
 * This component only picks the renderer of the format, see
 * `FORMAT_RENDERERS`. The renderer is the root: it owns the element the text
 * is rendered in, so the attributes set on this component land on that
 * element. What a profile means for a format is up to its renderer.
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
