import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { GRID_VIEW_MIN_FIELD_WIDTH } from '@baserow/modules/database/constants'

export default {
  props: {
    storePrefix: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      gridViewRowDetailsWidth: 72,
    }
  },
  computed: {
    GRID_VIEW_MIN_FIELD_WIDTH() {
      return GRID_VIEW_MIN_FIELD_WIDTH
    },
    fieldOptions() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getAllFieldOptions'
      ]
    },
    publicGrid() {
      return this.$store.getters['page/view/public/getIsPublic']
    },
    activeGroupBys() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getActiveGroupBys'
      ]
    },
  },
  methods: {
    getFieldWidth(field) {
      const fieldId = field?.id
      const options = fieldId ? this.fieldOptions[fieldId] : undefined

      if (options?.hidden && !field.primary) {
        return 0
      }

      return options?.width ?? 200
    },
    async moveFieldWidth(field, width) {
      await this.$store.dispatch(
        this.storePrefix + 'view/grid/setFieldOptionsOfField',
        {
          field,
          values: { width },
        }
      )
    },
    async updateFieldWidth(
      field,
      view,
      database,
      readOnly,
      { width, oldWidth }
    ) {
      try {
        await this.$store.dispatch(
          `${this.storePrefix}view/grid/updateFieldOptionsOfField`,
          {
            field,
            values: { width },
            oldValues: { width: oldWidth },
            readOnly:
              readOnly ||
              !this.$hasPermission(
                'database.table.view.update_field_options',
                view,
                database.workspace.id
              ),
          }
        )
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
  },
}
