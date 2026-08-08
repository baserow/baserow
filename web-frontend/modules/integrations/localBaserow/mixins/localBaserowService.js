import tableFields from '@baserow/modules/database/mixins/tableFields'

export default {
  mixins: [tableFields],
  props: {
    application: {
      type: Object,
      required: true,
    },
    service: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    serviceType: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    contextData: {
      type: Object,
      required: false,
      default: () => ({
        databases: [],
      }),
    },
    /**
     * Whether this form has a reduced amount of space to work with.
     */
    small: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The databases to choose a table from, supplied by the wrapper: an
     * integration for the builder and automation, the workspace for a button
     * field.
     */
    databases: {
      type: Array,
      required: false,
      default: () => [],
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
