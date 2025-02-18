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
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        fieldOptions:
          this.$options.propsData.storePrefix + 'view/grid/getAllFieldOptions',
        publicGrid: 'page/view/public/getIsPublic',
        activeGroupBys:
          this.$options.propsData.storePrefix + 'view/grid/getActiveGroupBys',
      }),
    }
  },
  computed: {
    activeGroupByWidth() {
      return this.activeGroupBys.reduce(
        (width, groupBy) => width + groupBy.width,
        0
      )
    },
    GRID_VIEW_MIN_FIELD_WIDTH() {
      return GRID_VIEW_MIN_FIELD_WIDTH
    },
  },
  methods: {
    getFieldWidth(field) {
      const fieldId = field?.id
      const hasFieldOptions =
        fieldId &&
        Object.prototype.hasOwnProperty.call(this.fieldOptions, fieldId)

      if (
        hasFieldOptions &&
        this.fieldOptions[fieldId].hidden &&
        !field.primary
      ) {
        return 0
      }

      return hasFieldOptions ? this.fieldOptions[fieldId].width : 200
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
    async moveGroupWidth(groupBy, view, width) {
      await this.$store.dispatch('view/forceUpdateGroupBy', {
        groupBy,
        values: { width },
      })
    },
    async updateGroupWidth(groupBy, view, database, readOnly, { width }) {
      // The provided group by can be an object of the `activeGroupBys`, which not
      // actually the same. Because active group by width has already been set using
      // the `moveGroupWidth`, we would not want to update the real one so that the
      // width change is applied there as well.
      const sourceGroupBy = view.group_bys.find((gb) => gb.id === groupBy.id)

      try {
        await this.$store.dispatch(`view/updateGroupBy`, {
          groupBy: sourceGroupBy,
          values: { width },
          readOnly:
            readOnly ||
            !this.$hasPermission(
              'database.table.view.group_by.update',
              view,
              database.workspace.id
            ),
        })
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
  },
}
