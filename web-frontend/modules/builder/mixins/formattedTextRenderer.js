/**
 * The contract between `ABFormattedText` and the renderer of a format (see its
 * `FORMAT_RENDERERS` map): every renderer takes the same props, whatever the
 * format does with them, and renders its own single root element, so that the
 * attributes set on `ABFormattedText` fall through to it. That root must be
 * valid where the profile puts it: phrasing content (`span`, `code`) in the
 * inline profile, which sits inside labels and table cells, and flow content
 * (`div`, `pre`) in the block profile, whose renderers emit paragraphs.
 */

export const FORMATTED_TEXT_PROFILES = ['inline', 'block']

export default {
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
     * `inline` for text that sits inside something else (a header cell, a
     * label, a dropdown option), `block` for text that stands on its own.
     */
    profile: {
      type: String,
      required: false,
      default: 'inline',
      validator: (value) => FORMATTED_TEXT_PROFILES.includes(value),
    },
    /**
     * Whether links may be rendered. A format without links ignores it.
     */
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
  },
}
