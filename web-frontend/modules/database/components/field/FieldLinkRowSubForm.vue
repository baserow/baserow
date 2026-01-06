<template>
  <div class="context__form-container">
    <FormGroup
      v-if="tables.length > 0"
      small-label
      :label="$t('fieldLinkRowSubForm.selectTableLabel')"
      required
      :error="fieldHasErrors('link_row_table_id')"
    >
      <Dropdown
        v-model="v$.values.link_row_table_id.$model"
        :error="fieldHasErrors('link_row_table_id')"
        :fixed-items="true"
        :disabled="!isSelectedFieldAccessible"
        @hide="v$.values.link_row_table_id.$touch"
        @input="tableChange"
      >
        <DropdownItem
          v-for="table in tablesWhereFieldsCanBeCreated"
          :key="table.id"
          :name="table.name"
          :value="table.id"
        ></DropdownItem>
      </Dropdown>

      <template #error>
        {{ v$.values.link_row_table_id.$errors[0]?.$message }}
      </template>
    </FormGroup>
    <FormGroup>
      <div
        v-show="v$.values.link_row_table_id.$model !== table.id"
        class="margin-bottom-1"
      >
        <Checkbox v-model="values.has_related_field">{{
          $t('fieldLinkRowSubForm.hasRelatedFieldLabel')
        }}</Checkbox>
      </div>
      <div class="margin-bottom-1">
        <Checkbox v-model="values.link_row_multiple_relationships">{{
          $t('fieldLinkRowSubForm.allowMultipleRelations')
        }}</Checkbox>
      </div>
      <div>
        <Checkbox v-model="limitToViewToggle" @input="limitToViewToggleChange"
          >{{ $t('fieldLinkRowSubForm.limitToView') }}
          <HelpIcon
            :tooltip="$t('fieldLinkRowSubForm.limitToViewDescription')"
            :tooltip-content-classes="['tooltip__content--expandable']"
          ></HelpIcon
        ></Checkbox>
      </div>
      <div v-if="limitToViewToggle">
        <div v-if="viewsLoading" class="loading"></div>
        <Dropdown
          v-else
          v-model="v$.values.link_row_limit_selection_view_id.$model"
          class="margin-top-1"
          :fixed-items="true"
        >
          <DropdownItem
            v-for="view in relatedViews"
            :key="view.id"
            :icon="view._.type.iconClass"
            :name="view.name"
            :value="view.id"
          ></DropdownItem>
        </Dropdown>
      </div>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import ViewService from '@baserow/modules/database/services/view'
import { CollaborativeViewOwnershipType } from '@baserow/modules/database/viewOwnershipTypes'

export default {
  name: 'FieldLinkRowSubForm',
  mixins: [form, fieldSubForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'link_row_table_id',
        'has_related_field',
        'link_row_multiple_relationships',
        'link_row_limit_selection_view_id',
      ],
      values: {
        link_row_table_id: null,
        has_related_field: true,
        link_row_multiple_relationships: true,
        link_row_limit_selection_view_id: null,
      },
      initialLinkRowTableId: null,
      limitToViewToggle: false,
      viewsLoading: false,
      viewsLoadedForTable: 0,
      relatedViews: [],
    }
  },
  computed: {
    tables() {
      const applications = this.$store.getters['application/getAll']
      const databaseType = DatabaseApplicationType.getType()
      const databaseId = this.table.database_id
      // Search for the database of the related table and return all the siblings of
      // that table because those are the only ones the user can choose form.
      for (let i = 0; i < applications.length; i++) {
        const application = applications[i]
        if (
          application.type === databaseType &&
          application.id === databaseId
        ) {
          return application.tables
        }
      }
      return []
    },
    tablesWhereFieldsCanBeCreated() {
      return this.tables.filter((table) =>
        this.$hasPermission(
          'database.table.create_field',
          table,
          this.database.workspace.id
        )
      )
    },
    canDeleteInSelectedFieldTable() {
      return (
        this.selectedFieldTable &&
        this.$hasPermission(
          'database.table.field.delete_related_link_row_field',
          this.selectedFieldTable,
          this.database.workspace.id
        )
      )
    },
    selectedFieldTable() {
      return this.tablesWhereFieldsCanBeCreated.find(
        (table) => table.id === this.values?.link_row_table_id
      )
    },
    isSelectedFieldAccessible() {
      return (
        this.values?.link_row_table_id === null ||
        this.canDeleteInSelectedFieldTable
      )
    },
  },
  watch: {
    'values.link_row_table_id'(newValueType, oldValue) {
      if (newValueType) {
        const table = this.tablesWhereFieldsCanBeCreated.find(
          (table) => table.id === newValueType
        )
        if (newValueType !== oldValue) {
          this.loadViewsIfNeeded()
        }
        this.$emit('suggested-field-name', table.name)
      }
    },
  },
  mounted() {
    this.initialLinkRowTable = this.values.link_row_table_id
    this.values.has_related_field =
      this.initialLinkRowTable == null ||
      this.defaultValues.link_row_related_field != null
    this.limitToViewToggle = !!this.values.link_row_limit_selection_view_id
  },

  methods: {
    reset() {
      this.initialLinkRowTable = this.values.link_row_table_id
      this.defaultValues.has_related_field =
        this.initialLinkRowTable == null ||
        this.defaultValues.link_row_related_field != null
      return form.methods.reset.call(this)
    },
    isValid() {
      return form.methods.isValid().call(this) && this.tables.length > 0
    },
    getFormValues() {
      const data = form.methods.getFormValues.call(this)
      // self-referencing link-row fields cannot have the related field
      if (this.values.link_row_table_id === this.table.id) {
        data.has_related_field = false
      }
      return data
    },
    tableChange() {
      // Only reset the `link_row_limit_selection_view_id` if the user manually changes
      // the table because if it's changed via a real-time event, the new limit
      // selection view will be updated at the same time.
      this.values.link_row_limit_selection_view_id = null
    },
    limitToViewToggleChange() {
      if (!this.limitToViewToggle) {
        this.values.link_row_limit_selection_view_id = null
      }
      this.loadViewsIfNeeded()
    },
    async loadViewsIfNeeded() {
      if (
        !this.limitToViewToggle ||
        this.values.link_row_table_id === this.viewsLoadedForTable ||
        this.values.link_row_table_id === null
      ) {
        return
      }

      this.viewsLoading = true
      const { data } = await ViewService(this.$client).fetchAll(
        this.values.link_row_table_id,
        false,
        false,
        false,
        false
      )
      // Because the field types are accessible for everyone, we only want to list
      // collaborative views, otherwise they might not be visible for everyone. Because
      // it applies the filters of the view is also makes sense to only list views that
      // have filtering capabilities.
      this.relatedViews = data
        .map((view) => {
          const viewType = this.$registry.get('view', view.type)
          view._ = { type: viewType.serialize() }
          return view
        })
        .filter((view) => {
          return (
            view.ownership_type === CollaborativeViewOwnershipType.getType()
          )
        })
        .filter((view) => {
          return view._.type.canFilter
        })
        .sort((a, b) => {
          return a.order - b.order
        })
      this.viewsLoadedForTable = this.values.link_row_table_id
      this.viewsLoading = false
    },
  },
  validations() {
    return {
      values: {
        link_row_table_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        link_row_limit_selection_view_id: {},
      },
    }
  },
}
</script>
