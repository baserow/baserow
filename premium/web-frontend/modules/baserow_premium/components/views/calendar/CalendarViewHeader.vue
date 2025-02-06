<template>
  <ul v-if="!tableLoading" class="header__filter header__filter--full-width">
    <li class="header__filter-item">
      <a
        class="header__filter-link"
        :class="!canChooseDateField ? 'header__filter-link--disabled' : ''"
        @click="showChooseDateFieldModal"
      >
        <i class="header__filter-icon iconoir-calendar"></i>
        <span class="header__filter-name">
          {{ selectDateFieldLinkText }}
        </span>
      </a>
      <SelectDateFieldModal
        ref="selectDateFieldModal"
        :view="view"
        :table="table"
        :fields="fields"
        :database="database"
        :date-field-id="dateFieldId(fields)"
        @refresh="$emit('refresh', $event)"
      >
      </SelectDateFieldModal>
    </li>
    <li v-if="dateFieldId(fields) != null" class="header__filter-item">
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
        <i class="header__filter-icon iconoir-list"></i>
        <span class="header__filter-name">{{
          $t('calendarViewHeader.labels')
        }}</span>
      </a>
      <ViewFieldsContext
        ref="customizeContext"
        :database="database"
        :view="view"
        :fields="fields"
        :field-options="fieldOptions"
        :allow-cover-image-field="false"
        @update-all-field-options="updateAllFieldOptions"
        @update-field-options-of-field="updateFieldOptionsOfField"
        @update-order="orderFieldOptions"
      ></ViewFieldsContext>
    </li>
    <li class="header__filter-item header__filter-item--full-width">
      <ViewSearch
        :view="view"
        :fields="fields"
        :store-prefix="storePrefix"
        :always-hide-rows-not-matching-search="true"
        @refresh="$emit('refresh', $event)"
      ></ViewSearch>
    </li>
  </ul>
</template>

<script>
import { mapState, mapGetters } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import SelectDateFieldModal from '@baserow_premium/components/views/calendar/SelectDateFieldModal'
import ViewFieldsContext from '@baserow/modules/database/components/view/ViewFieldsContext'
import ViewSearch from '@baserow/modules/database/components/view/ViewSearch'

export default {
  name: 'CalendarViewHeader',
  components: {
    ViewFieldsContext,
    SelectDateFieldModal,
    ViewSearch,
  },
  props: {
    storePrefix: {
      type: String,
      required: true,
      default: '',
    },
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
    selectDateFieldLinkText() {
      const df = this.getDateField(this.fields)
      if (
        !df ||
        this.$registry.get('field', df.type).canRepresentDate(df) === false
      ) {
        return this.$t('calendarViewHeader.displayBy')
      } else {
        return this.$t('calendarViewHeader.displayedBy', {
          fieldName: this.displayedByFieldName,
        })
      }
    },
    displayedByFieldName() {
      for (let i = 0; i < this.fields.length; i++) {
        if (this.fields[i].id === this.view.date_field) {
          return this.fields[i].name
        }
      }
      return ''
    },
    isDev() {
      return process.env.NODE_ENV === 'development'
    },
    ...mapState({
      tableLoading: (state) => state.table.loading,
    }),
    canChooseDateField() {
      return (
        !this.readOnly &&
        this.$hasPermission(
          'database.table.view.update',
          this.view,
          this.database.workspace.id
        )
      )
    },
  },
  watch: {
    fields() {
      const df = this.getDateField(this.fields)
      if (
        !df ||
        this.$registry.get('field', df.type).canRepresentDate(df) === false
      ) {
        this.showChooseDateFieldModal()
      }
    },
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        timezone:
          this.$options.propsData.storePrefix + 'view/calendar/getTimeZone',
        fieldOptions:
          this.$options.propsData.storePrefix +
          'view/calendar/getAllFieldOptions',
        dateFieldId:
          this.$options.propsData.storePrefix +
          'view/calendar/getDateFieldIdIfNotTrashed',
        getDateField:
          this.$options.propsData.storePrefix + 'view/calendar/getDateField',
      }),
    }
  },
  mounted() {
    if (this.dateFieldId(this.fields) == null) {
      this.showChooseDateFieldModal()
    }
  },
  methods: {
    showChooseDateFieldModal() {
      if (this.canChooseDateField) {
        this.$refs.selectDateFieldModal.show()
      }
    },
    async updateAllFieldOptions({ newFieldOptions, oldFieldOptions }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/calendar/updateAllFieldOptions',
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
          this.storePrefix + 'view/calendar/updateFieldOptionsOfField',
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
          this.storePrefix + 'view/calendar/updateFieldOptionsOrder',
          {
            order,
            readOnly: this.readOnly,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>
