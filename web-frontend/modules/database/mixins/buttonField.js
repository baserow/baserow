import { resolveButtonUrl } from '@baserow/modules/database/utils/buttonField'

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
      if (this.field.error) {
        return { url: '', label: this.field.label }
      }
      const fields =
        this.allFieldsInTable?.length > 0
          ? this.allFieldsInTable
          : this.$store.getters['field/getAll']
      return {
        url: resolveButtonUrl(this.$registry, this.field, this.row, fields),
        label: this.field.label,
      }
    },
  },
}
