<template>
  <form class="table-element-form" @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="table"
      :config-block-types="['table', 'typography']"
      :theme="builder.theme"
      :extra-args="{ onlyBody: true, noAlignment: true }"
    />
    <FormGroup
      v-show="dataSourceDropdownAvailable"
      :label="$t('dataSourceDropdown.label')"
      small-label
      required
      class="margin-bottom-2"
    >
      <DataSourceDropdown
        v-model="computedDataSourceId"
        small
        :shared-data-sources="sharedDataSources"
        :local-data-sources="localDataSources"
      >
        <template #chooseValueState>
          {{ $t('collectionElementForm.noDataSourceMessage') }}
        </template>
      </DataSourceDropdown>
    </FormGroup>
    <FormGroup
      v-show="propertySelectorAvailable"
      small-label
      required
      class="margin-bottom-2"
      :label="$t('serviceSchemaPropertySelector.label')"
    >
      <ServiceSchemaPropertySelector
        v-model="values.schema_property"
        small
        :schema="propertySelectorSchema"
      >
        <template #emptyState
          >{{ $t('tableElementForm.propertySelectorMissingArrays') }}
        </template>
        <template #chooseValueState>
          {{ $t('collectionElementForm.noSchemaPropertyMessage') }}
        </template>
      </ServiceSchemaPropertySelector>
    </FormGroup>
    <FormGroup
      v-show="pagingOptionsAvailable"
      class="margin-bottom-2"
      small-label
      :label="$t('tableElementForm.itemsPerPage')"
      required
      :error-message="getFirstErrorMessage('items_per_page')"
    >
      <FormInput
        v-model="v$.values.items_per_page.$model"
        :placeholder="$t('tableElementForm.itemsPerPagePlaceholder')"
        :to-value="(value) => parseInt(value)"
        type="number"
        @blur="v$.values.items_per_page.$touch"
      />
    </FormGroup>

    <CustomStyleButton
      v-show="pagingOptionsAvailable"
      v-model="values.styles"
      style-key="button"
      :config-block-types="['button']"
      :theme="builder.theme"
    />
    <FormGroup
      v-show="pagingOptionsAvailable"
      small-label
      :label="$t('tableElementForm.buttonLoadMoreLabel')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.button_load_more_label"
        :placeholder="$t('elementForms.textInputPlaceholder')"
      />
    </FormGroup>
    <FormSection
      :key="element.data_source_id"
      class="margin-bottom-2"
      :title="$t('tableElementForm.fields')"
    >
      <template v-if="values.fields?.length">
        <ButtonText
          v-show="selectedDataSourceReturnsList"
          type="primary"
          icon="iconoir-refresh-double"
          size="small"
          class="table-element-form__refresh-fields-button"
          @click="refreshFieldsFromDataSource"
        >
          {{ $t('tableElementForm.refreshFieldsFromDataSource') }}
        </ButtonText>
        <div>
          <SidebarExpandable
            v-for="(field, index) in values.fields"
            :key="field.id"
            v-sortable="{
              id: field.id,
              update: orderFields,
              enabled: $hasPermission(
                'builder.page.element.update',
                element,
                workspace.id
              ),
              handle: '[data-sortable-handle]',
            }"
            toggle-on-click
          >
            <template #title>
              <span v-if="field.name">{{ field.name }}</span>
              <span v-else class="color-neutral">
                ({{ $t('tableElementForm.noName') }})
              </span>
              <Icon
                v-if="getFieldErrorMessage(field)"
                :key="getFieldErrorMessage(field)"
                v-tooltip="getFieldErrorMessage(field)"
                icon="iconoir-warning-circle"
                size="medium"
                type="error"
              />
            </template>
            <template #default>
              <FormGroup
                small-label
                horizontal
                required
                class="margin-bottom-2"
                :label="$t('tableElementForm.name')"
                :error-message="v$.values.fields.$each.$message[index]?.[0]"
              >
                <FormInput
                  v-model="v$.values.fields.$model[index].name"
                  class="table-element-form__field-label"
                >
                </FormInput>
              </FormGroup>

              <FormGroup
                small-label
                horizontal
                required
                :label="$t('tableElementForm.fieldType')"
                class="margin-bottom-2"
              >
                <Dropdown
                  :value="field.type"
                  :show-search="false"
                  @input="changeFieldType(field, $event)"
                >
                  <DropdownItem
                    v-for="collectionType in orderedCollectionTypes"
                    :key="collectionType.getType()"
                    :name="collectionType.name"
                    :value="collectionType.getType()"
                  />
                </Dropdown>
              </FormGroup>
              <component
                :is="collectionTypes[field.type].formComponent"
                :element="element"
                :default-values="field"
                :base-theme="collectionFieldBaseTheme"
                :application-context-additions="{
                  allowSameElement: true,
                }"
                @values-changed="updateField(field, $event)"
              />
            </template>
            <template #footer>
              <template v-if="v$.values.fields.$model.length > 1">
                <ButtonText icon="iconoir-bin" @click="removeField(field)">
                  {{ $t('action.delete') }}
                </ButtonText>
              </template>
            </template>
          </SidebarExpandable>
        </div>
        <ButtonText
          type="primary"
          icon="iconoir-plus"
          size="small"
          @click="addField"
        >
          {{ $t('tableElementForm.addField') }}
        </ButtonText>
      </template>
      <p v-else>{{ $t('tableElementForm.selectSourceFirst') }}</p>
    </FormSection>
    <FormGroup
      :label="$t('orientations.label')"
      small-label
      required
      class="margin-bottom-2"
    >
      <DeviceSelector
        :device-type-selected="deviceTypeSelected"
        direction="row"
        @selected="actionSetDeviceTypeSelected"
      >
        <template #deviceTypeControl="{ deviceType }">
          <RadioButton
            v-model="values.orientation[deviceType.getType()]"
            icon="iconoir-view-columns-3"
            :value="ORIENTATIONS.HORIZONTAL"
          >
            {{ $t('orientations.horizontal') }}
          </RadioButton>
          <RadioButton
            v-model="values.orientation[deviceType.getType()]"
            icon="iconoir-table-rows"
            :value="ORIENTATIONS.VERTICAL"
          >
            {{ $t('orientations.vertical') }}
          </RadioButton>
        </template>
      </DeviceSelector>
    </FormGroup>
    <CustomStyleButton
      v-if="propertyOptionsAvailable"
      v-model="values.styles"
      style-key="header_button"
      :config-block-types="['button']"
      :theme="builder.theme"
      :extra-args="{ noAlignment: true, noWidth: true }"
    />
    <FormGroup
      v-if="propertyOptionsAvailable"
      small-label
      class="margin-bottom-2"
      :label="$t('collectionElementForm.propertyOptionLabel')"
      required
    >
      <PropertyOptionForm
        :default-values="element"
        :is-filterable="element.is_publicly_filterable"
        :is-sortable="element.is_publicly_sortable"
        :is-searchable="element.is_publicly_searchable"
        :data-source="selectedDataSource"
        @values-changed="$emit('values-changed', $event)"
      ></PropertyOptionForm>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import {
  getNextAvailableNameInSequence,
  uuid,
} from '@baserow/modules/core/utils/string'
import {
  required,
  maxLength,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'
import collectionElementForm from '@baserow/modules/builder/mixins/collectionElementForm'
import { ORIENTATIONS } from '@baserow/modules/builder/enums'
import DeviceSelector from '@baserow/modules/builder/components/page/header/DeviceSelector.vue'
import { mapActions, mapGetters } from 'vuex'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import ServiceSchemaPropertySelector from '@baserow/modules/core/components/services/ServiceSchemaPropertySelector'
import DataSourceDropdown from '@baserow/modules/builder/components/dataSource/DataSourceDropdown'
import PropertyOptionForm from '@baserow/modules/builder/components/elements/components/forms/general/settings/PropertyOptionForm'
import SidebarExpandable from '@baserow/modules/builder/components/SidebarExpandable.vue'

export default {
  name: 'TableElementForm',
  components: {
    PropertyOptionForm,
    DataSourceDropdown,
    ServiceSchemaPropertySelector,
    InjectedFormulaInput,
    DeviceSelector,
    CustomStyleButton,
    SidebarExpandable,
  },
  mixins: [collectionElementForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'data_source_id',
        'schema_property',
        'fields',
        'items_per_page',
        'orientation',
        'styles',
        'button_load_more_label',
      ],
      values: {
        fields: [],
        data_source_id: null,
        schema_property: null,
        items_per_page: 1,
        styles: {},
        orientation: {},
        button_load_more_label: {},
      },
    }
  },
  computed: {
    ...mapGetters({ deviceTypeSelected: 'page/getDeviceTypeSelected' }),
    ORIENTATIONS() {
      return ORIENTATIONS
    },
    orderedCollectionTypes() {
      return this.$registry.getOrderedList('collectionField')
    },
    collectionTypes() {
      return this.$registry.getAll('collectionField')
    },
    collectionFieldBaseTheme() {
      return { ...this.builder.theme, ...this.values.styles?.table }
    },
    computedDataSourceId: {
      get() {
        return this.element.data_source_id
      },
      set(newValue) {
        const oldValue = this.values.data_source_id
        this.values.data_source_id = newValue
        if (newValue !== oldValue && newValue) {
          this.refreshFieldsFromDataSource()
        }
      },
    },
  },
  methods: {
    ...mapActions({
      actionSetDeviceTypeSelected: 'page/setDeviceTypeSelected',
    }),
    addField() {
      this.v$.values.fields.$model.push({
        name: getNextAvailableNameInSequence(
          this.$t('tableElementForm.fieldDefaultName'),
          this.v$.values.fields.$model.map(({ name }) => name)
        ),
        value: {},
        type: 'text',
        id: uuid(), // Temporary id
        uid: uuid(),
      })
    },
    changeFieldType(fieldToUpdate, newType) {
      this.v$.values.fields.$model = this.v$.values.fields.$model.map(
        (field) => {
          if (field.id === fieldToUpdate.id) {
            // When the type of the workflow action changes we assign a new UID to
            // trigger the backend workflow action removal
            return {
              id: field.id,
              uid: uuid(),
              name: field.name,
              type: newType,
            }
          }
          return field
        }
      )
    },
    updateField(fieldToUpdate, values) {
      this.v$.values.fields.$model = this.v$.values.fields.$model.map(
        (field, index) => {
          if (field.id === fieldToUpdate.id) {
            return { ...field, ...values }
          }
          return field
        }
      )
    },
    removeField(field) {
      this.v$.values.fields.$model = this.v$.values.fields.$model.filter(
        (item) => item !== field
      )
    },
    orderFields(newOrder) {
      const fieldById = Object.fromEntries(
        this.v$.values.fields.$model.map((field) => [field.id, field])
      )
      this.v$.values.fields.$model = newOrder.map(
        (fieldId) => fieldById[fieldId]
      )
    },
    getFieldErrorMessage(field) {
      return this.collectionTypes[field.type].getErrorMessage({
        field,
        element: this.element,
        builder: this.builder,
      })
    },
    refreshFieldsFromDataSource() {
      // If the data source returns multiple records, generate
      // the collection field values.

      if (
        this.selectedDataSourceReturnsList &&
        !this.selectedDataSourceType.isInError({
          service: this.selectedDataSource,
        })
      ) {
        this.values.fields =
          this.selectedDataSourceType.getDefaultCollectionFields(
            this.selectedDataSource
          )
      }
    },
  },
  validations() {
    const itemsPerPageRules = {
      integer: helpers.withMessage(this.$t('error.integerField'), integer),
    }
    if (this.pagingOptionsAvailable) {
      itemsPerPageRules.required = helpers.withMessage(
        this.$t('error.requiredField'),
        required
      )
      itemsPerPageRules.minValue = helpers.withMessage(
        this.$t('error.minValueField', { min: 1 }),
        minValue(1)
      )
      itemsPerPageRules.maxValue = helpers.withMessage(
        this.$t('error.maxValueField', { max: this.maxItemPerPage }),
        maxValue(this.maxItemPerPage)
      )
    }
    return {
      values: {
        fields: {
          $each: helpers.forEach({
            name: {
              maxLength: helpers.withMessage(
                this.$t('error.maxLength', { max: 255 }),
                maxLength(225)
              ),
            },
          }),
        },
        items_per_page: itemsPerPageRules,
      },
    }
  },
}
</script>
