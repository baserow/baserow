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
  methods: {
    /**
     * Overrides the method in the tableFields mixin
     */
    getTableId() {
      return this.values.table_id
    },
  },
}
