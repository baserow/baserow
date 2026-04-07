<template>
  <div>
    <FormGroup
      small-label
      required
      :label="$t('fieldFormViewEditRowSubForm.selectFormViewLabel')"
      :error="fieldHasErrors('form_view_id')"
      class="margin-bottom-2"
    >
      <div v-if="viewsLoading" class="loading"></div>
      <Dropdown
        v-else
        v-model="v$.values.form_view_id.$model"
        :error="fieldHasErrors('form_view_id')"
        :fixed-items="true"
        small
        @hide="v$.values.form_view_id.$touch"
      >
        <DropdownItem
          v-for="view in formViews"
          :key="view.id"
          :name="getViewLabel(view)"
          :value="view.id"
          :icon="view._.type.iconClass"
        ></DropdownItem>
      </Dropdown>
      <div class="control__messages padding-top-0 margin-top-1">
        <p class="control__helper-text field-context__inner-element-width">
          {{ $t('fieldFormViewEditRowSubForm.description') }}
        </p>
      </div>
      <template #error>
        {{ v$.values.form_view_id.$errors[0]?.$message }}
      </template>
    </FormGroup>
    <p
      v-if="values.form_view_id && !selectedFormExists"
      class="error field-context__inner-element-width"
    >
      <i class="iconoir-warning-triangle"></i>
      {{ $t('fieldFormViewEditRowSubForm.formDoesNotExist') }}
    </p>
    <p
      v-else-if="values.form_view_id && !selectedViewIsPublic"
      class="error field-context__inner-element-width"
    >
      <i class="iconoir-warning-triangle"></i>
      {{ $t('fieldFormViewEditRowSubForm.notPublicWarning') }}
    </p>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import ViewService from '@baserow/modules/database/services/view'
import { notifyIf } from '~/modules/core/utils/error.js'

export default {
  name: 'FieldFormViewEditRowSubForm',
  mixins: [form, fieldSubForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['form_view_id'],
      values: {
        form_view_id: null,
      },
      formViews: [],
      viewsLoading: true,
    }
  },
  computed: {
    selectedFormExists() {
      if (!this.values.form_view_id) return false
      return !!this.formViews.find((v) => v.id === this.values.form_view_id)
    },
    selectedViewIsPublic() {
      if (!this.values.form_view_id) return false
      const view = this.formViews.find((v) => v.id === this.values.form_view_id)
      return view ? view.public : false
    },
  },
  async created() {
    const selectedTableId = this.$store.getters['table/getSelected']?.id
    const isSelectedTable = selectedTableId && selectedTableId === this.table.id
    let views
    try {
      if (isSelectedTable) {
        views = this.$store.getters['view/getAll']
      } else {
        const { data } = await ViewService(this.$client).fetchAll(
          this.table.id,
          false,
          false,
          false,
          false,
          false
        )
        views = data
      }
      this.formViews = views
        .filter((view) => view.type === 'form')
        .map((view) => {
          const viewType = this.$registry.get('view', view.type)
          view._ = { type: viewType.serialize() }
          return view
        })
        .sort((a, b) => a.order - b.order)
    } catch (error) {
      notifyIf(error)
    } finally {
      this.viewsLoading = false
    }
  },
  methods: {
    getViewLabel(view) {
      if (view.public) {
        return view.name
      }
      return `${view.name} ${this.$t('fieldFormViewEditRowSubForm.notPublic')}`
    },
  },
  validations() {
    return {
      values: {
        form_view_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
