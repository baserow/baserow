<template>
  <div>
    <Table
      :database="database"
      :table="table"
      :fields="fields"
      :views="views"
      :view="view"
      :table-loading="false"
      store-prefix="page/"
    ></Table>
  </div>
</template>

<script>
import Table from '@baserow/modules/database/components/table/Table'
import { populateView } from '@baserow/modules/database/store/view'
import { GridViewType } from '@baserow/modules/database/viewTypes'
import { CollaborativeViewOwnershipType } from '@baserow/modules/database/viewOwnershipTypes'
import { populateField } from '@baserow/modules/database/store/field'
import { TextFieldType } from '@baserow/modules/database/fieldTypes'
import { populateRow } from '@baserow/modules/database/store/view/grid'

export default {
  name: 'DatabaseTablePreview',
  components: { Table },
  props: {
    data: {
      type: Object,
      required: true,
    },
    selectedWorkspace: {
      type: Object,
      required: true,
    },
    applications: {
      type: Array,
      required: true,
    },
  },
  emits: ['focusOnTable'],
  data() {
    return {
      fieldsDefs: [],
      nameRows: [],
    }
  },
  computed: {
    scratchTrack() {
      return {
        track: this.data.database_scratch_track,
        fields: this.data.database_scratch_track_fields,
      }
    },
    database() {
      return this.applications[0]
    },
    table() {
      return this.database.tables[0]
    },
    fields() {
      const { $registry } = useNuxtApp()
      const primaryTextField = populateField(
        {
          id: 0,
          table_id: this.table.id,
          name: 'Name',
          order: 0,
          type: TextFieldType.getType(),
          primary: true,
          read_only: false,
          text_default: '',
        },
        $registry
      )

      const instances = [primaryTextField]
      this.fieldsDefs.forEach((field, index) => {
        instances.push(
          populateField(
            {
              id: index + 1,
              table_id: this.table.id,
              order: index + 1,
              read_only: false,
              primary: false,
              hidden: false,
              ...field,
            },
            $registry
          )
        )
      })
      return instances
    },
    views() {
      const gridView1 = populateView(
        {
          id: 0,
          table_id: this.table.id,
          name: 'Grid',
          order: 1,
          type: GridViewType.getType(),
          table: this.table,
          filter_type: 'AND',
          filters: [],
          filter_groups: [],
          sortings: [],
          group_bys: [],
          decorations: [],
          filters_disabled: false,
          public_view_has_password: false,
          show_logo: true,
          ownership_type: CollaborativeViewOwnershipType.getType(),
          owned_by_id: null,
          row_identifier_type: 'id',
          public: false,
          slug: '',
        },
        this.$registry
      )
      return [gridView1]
    },
    view() {
      return this.views[0]
    },
  },
  watch: {
    scratchTrack: {
      handler({ track, fields }) {
        const commit = (name, value) => {
          return this.$store.commit(`page/view/grid/${name}`, value)
        }

        if (!track || !track.rows) {
          return
        }

        const rows = track.rows.map((name, index) => {
          return populateRow({
            id: index + 1,
            field_0: name,
            order: `${index + 1}.00000000000000000000`,
          })
        })

        this.nameRows = rows

        const fieldsDefs = []
        if (fields && fields.fields) {
          Object.values(fields.fields).forEach((field, fieldIndex) => {
            fieldsDefs.push({
              primary: false,
              ...field.props,
            })

            field.rows.forEach((rowValue, index) => {
              if (rows[index]) {
                rows[index][`field_${fieldIndex + 1}`] = rowValue
              }
            })
          })
        }

        commit('CLEAR_ROWS')
        commit('ADD_ROWS', {
          rows,
          prependToRows: 0,
          appendToRows: rows.length,
          count: rows.length,
          bufferStartIndex: 0,
          bufferLimit: rows.length,
        })
        commit('SET_ROWS_INDEX', {
          startIndex: 0,
          endIndex: rows.length,
          top: 0,
        })

        this.fieldsDefs = fieldsDefs
        for (let idx = 0; idx <= this.fieldsDefs.length; idx++) {
          commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
            fieldId: idx + 1,
            values: {
              width: 150,
              order: 32767,
              aggregation_type: '',
              aggregation_raw_type: '',
              hidden: false,
            },
          })
        }

        if (fields && fields.fields) {
          this.$emit('focusOnTable', fieldsDefs.length > 0)
        }
      },
      immediate: true,
      deep: true,
      flush: 'post',
    },
  },
}
</script>
