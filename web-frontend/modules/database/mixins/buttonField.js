import {
  encodeUrlWhitespace,
  resolveButtonUrl,
} from '@baserow/modules/database/utils/buttonField'

/**
 * Computes the {url, label} value of a button field cell. Uses the
 * allFieldsInTable prop where the render context provides it (selected grid
 * cell, row edit modal) and falls back to the field store for contexts that
 * only pass row + field (functional grid cells, cards).
 */
export default {
  computed: {
    resolvedButtonValue() {
      // A broken formula (e.g. referencing a deleted field) must disable
      // the button rather than resolve to a misleading URL.
      const resolved = this.field.error
        ? ''
        : resolveButtonUrl(
            this.$registry,
            this.field,
            this.row,
            this.allFieldsInTable?.length > 0
              ? this.allFieldsInTable
              : this.$store.getters['field/getAll']
          )
      return {
        url: encodeUrlWhitespace(resolved),
        label: this.field.label,
      }
    },
  },
}
