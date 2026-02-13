<template>
  <ul v-if="!tableLoading" class="header__filter header__filter--full-width">
    <li class="header__filter-item">
      <a
        ref="stackedContextLink"
        class="header__filter-link"
        @click="
          $refs.stackedContext.toggle(
            $refs.stackedContextLink,
            'bottom',
            'left',
            4
          )
        "
      >
        <i class="header__filter-icon iconoir-nav-arrow-down"></i>
        <span class="header__filter-name">
          <template v-if="view.single_select_field === null">{{
            $t('kanbanViewHeader.stackBy')
          }}</template
          ><template v-else>{{
            $t('kanbanViewHeader.stackedBy', {
              fieldName: stackedByFieldName,
            })
          }}</template></span
        >
      </a>
      <Context
        ref="stackedContext"
        overflow-scroll
        max-height-if-outside-viewport
      >
        <KanbanViewStackedBy
          :table="table"
          :view="view"
          :database="database"
          :fields="fields"
          :read-only="
            readOnly ||
            !$hasPermission(
              'database.table.view.update',
              view,
              database.workspace.id
            )
          "
          :store-prefix="storePrefix"
          @refresh="$emit('refresh', $event)"
        ></KanbanViewStackedBy>
      </Context>
    </li>
    <li v-if="singleSelectFieldId !== -1" class="header__filter-item">
      <a
        ref="customizeContextLink"
        class="header__filter-link"
        @click="
          $refs.customizeContext.toggle(
            $refs.customizeContextLink,
            'bottom',
            'left',
            4
          )
        "
      >
        <i class="header__filter-icon iconoir-settings"></i>
        <span class="header__filter-name">{{
          $t('kanbanViewHeader.customizeCards')
        }}</span>
      </a>
      <ViewFieldsContext
        ref="customizeContext"
        :database="database"
        :view="view"
        :fields="fields"
        :field-options="fieldOptions"
        :cover-image-field="view.card_cover_image_field"
        :allow-cover-image-field="true"
        @update-all-field-options="updateAllFieldOptions"
        @update-field-options-of-field="updateFieldOptionsOfField"
        @update-order="orderFieldOptions"
        @update-cover-image-field="updateCoverImageField"
      ></ViewFieldsContext>
    </li>
  </ul>
</template>

<script>
import { mapState, mapGetters } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import ViewFieldsContext from '@baserow/modules/database/components/view/ViewFieldsContext'
import KanbanViewStackedBy from '@baserow_premium/components/views/kanban/KanbanViewStackedBy'
import kanbanViewHelper from '@baserow_premium/mixins/kanbanViewHelper'

export default {
  name: 'KanbanViewHeader',
  emits: ['refresh'],
  components: { KanbanViewStackedBy, ViewFieldsContext },
  mixins: [kanbanViewHelper],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    stackedByFieldName() {
      for (let i = 0; i < this.fields.length; i++) {
        if (this.fields[i].id === this.view.single_select_field) {
          return this.fields[i].name
        }
      }
      return ''
    },
    ...mapState({
      tableLoading: (state) => state.table.loading,
    }),
  },
  methods: {
    async updateAllFieldOptions({ newFieldOptions, oldFieldOptions }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/kanban/updateAllFieldOptions',
          {
            newFieldOptions,
            oldFieldOptions,
            readOnly:
              this.readOnly ||
              !this.$hasPermission(
                'database.table.view.update_field_options',
                this.view,
                this.database.workspace.id
              ),
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async updateFieldOptionsOfField({ field, values, oldValues }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/kanban/updateFieldOptionsOfField',
          {
            field,
            values,
            oldValues,
            readOnly:
              this.readOnly ||
              !this.$hasPermission(
                'database.table.view.update_field_options',
                this.view,
                this.database.workspace.id
              ),
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async orderFieldOptions({ order }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/kanban/updateFieldOptionsOrder',
          {
            order,
            readOnly: this.readOnly,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async updateCoverImageField(value) {
      try {
        await this.$store.dispatch('view/update', {
          view: this.view,
          values: { card_cover_image_field: value },
          readOnly: this.readOnly,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>
