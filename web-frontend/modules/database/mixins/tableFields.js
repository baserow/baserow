import FieldService from '@baserow/modules/database/services/field'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * This mixin request the fields of the given table Id.
 */
export default {
  props: {},
  data() {
    return { tableFields: [], fieldsLoading: false }
  },
  computed: {
    tableId() {
      return this.getTableId()
    },
  },
  watch: {
    tableId: {
      async handler(newValue, oldValue) {
        if (newValue !== oldValue) {
          this.tableFields = []
          if (newValue) {
            this.fieldsLoading = true
            try {
              const { data } = await FieldService(this.$client).fetchAll(
                newValue
              )
              this.tableFields = data
            } catch (e) {
              notifyIf(e, 'application')
            } finally {
              this.fieldsLoading = false
            }
          }
        }
      },
      immediate: true,
    },
  },
  methods: {
    getTableId() {
      throw new Error(
        'Not implemented error. This method should return the table id we want the field for.'
      )
    },
  },
}
