import tableFields from '@baserow/modules/database/mixins/tableFields'

export default {
  mixins: [tableFields],
  props: {
    application: {
      type: Object,
      required: true,
    },
    contextData: {
      type: Object,
      required: false,
      default: () => ({
        databases: [],
      }),
    },
    /**
     * Determines whether the refinements (filters, sortings, search)
     * are enabled in this service form, by default they are.
     */
    enableRefinements: {
      type: Boolean,
      required: false,
      default: true,
    },
    /**
     * Determines whether the integration picker is enabled in this service form.
     * If enabled, the user can select an integration to use for this service.
     * By default, it is disabled.
     */
    enableIntegrationPicker: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    /**
     * Used by `LocalBaserowTableSelector` so that when read, we return the
     * table ID. When writing, if the table ID has changed, it gives us an
     * opportunity to reset the `filters`, `sortings` and `view_id`.
     */
    fakeTableId: {
      get() {
        return this.values.table_id
      },
      set(newValue) {
        // If we currently have a `table_id` selected, and the `newValue`
        // is different to the current `table_id`, then reset the `filters`
        // and `sortings` to a blank array, and `view_id` to `null`.
        if (this.values.table_id && this.values.table_id !== newValue) {
          this.values.filters = []
          this.values.sortings = []
          this.values.view_id = null
        }
        this.values.table_id = newValue
      },
    },
    databases() {
      return this.contextData?.databases || []
    },
    tables() {
      return this.databases.map((database) => database.tables).flat()
    },
    tableSelected() {
      return this.tables.find(({ id }) => id === this.values.table_id)
    },
  },
  methods: {
    /**
     * Overrides the method in the tableFields mixin
     */
    getTableId() {
      return this.values.table_id
    },
  },
}
