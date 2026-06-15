import ViewService from '@baserow/modules/database/services/view'

/**
 * Shared logic for the single (`FormViewFieldLinkRow`) and multiple
 * (`FormViewFieldMultipleLinkRow`) form-view link-row components: how a related
 * row is labelled in the dropdown and how a page of related rows is fetched.
 */
export default {
  props: {
    slug: {
      type: String,
      required: true,
    },
    /**
     * In some cases, for example in the form view preview, we only want to fetch the
     * first related rows after the user has opened the dropdown. This will prevent a
     * race condition where the enabled state of the field might not yet been updated
     * before we fetch the related rows. If the state has not yet been changed in the
     * backend, it will result in an error.
     */
    lazyLoad: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  methods: {
    /**
     * The display label for a related row. Rows whose primary field is empty
     * fall back to the same "unnamed row" label used in the grid, while
     * placeholder slots (without a real row id) keep their empty value.
     */
    rowDisplayName(row) {
      if (row.value) {
        return row.value
      }
      if (!Number.isInteger(row.id)) {
        return row.value
      }
      return this.$t('functionnalGridViewFieldLinkRow.unnamed', {
        value: row.id,
      })
    },
    /**
     * Fetches a page of related rows for the dropdown. This is a pure
     * pass-through: the dropdown derives the display label through `valueName`
     * and hands the original row back on selection, so no copy of the data has
     * to be kept here.
     */
    fetchPage(page, search) {
      const publicAuthToken =
        this.$store.getters['page/view/public/getAuthToken']
      return ViewService(this.$client).linkRowFieldLookup(
        this.slug,
        this.field.id,
        page,
        search,
        100,
        publicAuthToken
      )
    },
  },
}
