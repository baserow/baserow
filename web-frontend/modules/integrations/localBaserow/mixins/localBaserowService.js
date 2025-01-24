export default {
  props: {
    builder: {
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
    dataSource: {
      type: Object,
      required: true,
    },
  },
  computed: {
    /**
     * Used by `LocalBaserowTableServiceConditionalForm` so that when read,
     * we only provide filters which are from untrashed fields. When writing,
     * we update the service's filters.
     */
    dataSourceFilters: {
      get() {
        return this.excludeTrashedFields(this.values.filters)
      },
      set(newValue) {
        this.values.filters = newValue
      },
    },
    /**
     * Used by `LocalBaserowTableServiceSortForm` so that when read, we
     * only provide sortings which are from untrashed fields. When writing,
     * we update the service's sortings.
     */
    dataSourceSortings: {
      get() {
        return this.excludeTrashedFields(this.values.sortings)
      },
      set(newValue) {
        this.values.sortings = newValue
      },
    },
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
    tableFields() {
      return this.tableSelected?.fields || []
    },
  },
  watch: {
    'values.table_id'(newValue, oldValue) {
      if (oldValue && newValue !== oldValue) {
        this.tableLoading = true
      }
    },
  },
  methods: {
    /**
     * Given an array of objects containing a `field` property (e.g. the data
     * source filters or sortings arrays), this method will return a new array
     * containing only the objects where the field is part of the schema, so,
     * untrashed.
     *
     * @param {Array} value - The array of objects to filter.
     * @returns {Array} - The filtered array.
     */
    excludeTrashedFields(value) {
      const localBaserowFieldIds = this.tableFields.map(({ id }) => id)
      return value.filter(({ field }) => localBaserowFieldIds.includes(field))
    },
  },
}
