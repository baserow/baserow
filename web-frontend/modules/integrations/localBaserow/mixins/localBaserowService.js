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
