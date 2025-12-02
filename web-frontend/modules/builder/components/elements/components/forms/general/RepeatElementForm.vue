<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      v-show="dataSourceDropdownAvailable"
      :label="$t('dataSourceDropdown.label')"
      small-label
      required
      class="margin-bottom-2"
    >
      <DataSourceDropdown
        v-model="values.data_source_id"
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
        <template #emptyState>
          {{ $t('repeatElementForm.propertySelectorMissingArrays') }}
        </template>
        <template #chooseValueState>
          {{ $t('collectionElementForm.noSchemaPropertyMessage') }}
        </template>
      </ServiceSchemaPropertySelector>
    </FormGroup>
    <FormGroup
      v-show="pagingOptionsAvailable"
      :label="$t('repeatElementForm.itemsPerPage')"
      small-label
      required
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('items_per_page')"
    >
      <FormInput
        v-model="v$.values.items_per_page.$model"
        :placeholder="$t('repeatElementForm.itemsPerPagePlaceholder')"
        :to-value="(value) => parseInt(value)"
        type="number"
        @blur="v$.values.items_per_page.$touch()"
      />
    </FormGroup>

    <CustomStyleButton
      v-show="values.data_source_id"
      v-model="values.styles"
      style-key="button"
      :config-block-types="['button']"
      :theme="builder.theme"
    />
    <FormGroup
      v-show="pagingOptionsAvailable"
      small-label
      :label="$t('repeatElementForm.buttonLoadMoreLabel')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.button_load_more_label"
        :placeholder="$t('elementForms.textInputPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('orientations.label')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="values.orientation"
        :options="orientationOptions"
        type="button"
      >
      </RadioGroup>
    </FormGroup>
    <FormGroup
      v-show="values.orientation === 'horizontal'"
      :error-message="itemsPerRowError"
      :label="$t('repeatElementForm.itemsPerRowLabel')"
      small-label
      required
      :helper-text="$t('repeatElementForm.itemsPerRowDescription')"
      class="margin-bottom-2"
    >
      <DeviceSelector
        :device-type-selected="deviceTypeSelected"
        class="repeat-element__device-selector margin-bottom-2"
        @selected="actionSetDeviceTypeSelected"
      >
        <template #deviceTypeControl="{ deviceType }">
          <FormInput
            :ref="`itemsPerRow-${deviceType.getType()}`"
            v-model="values.items_per_row[deviceType.getType()]"
            remove-number-input-controls
            type="number"
            @input="handlePerRowInput($event, deviceType.getType())"
          />
        </template>
      </DeviceSelector>
    </FormGroup>
    <FormGroup
      small-label
      required
      :label="$t('repeatElementForm.gapLabel')"
      :error-message="gapError"
      class="margin-bottom-2"
    >
      <PaddingSelector
        v-model="padding"
        :default-values-when-empty="paddingDefaults"
      />
    </FormGroup>
    <FormGroup
      small-label
      class="margin-bottom-2"
      :label="$t('repeatElementForm.toggleEditorRepetitionsLabel')"
    >
      <Checkbox :checked="isCollapsed" @input="emitToggleRepetitions($event)">
      </Checkbox>
    </FormGroup>
    <CustomStyleButton
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
import _ from 'lodash'
import { useVuelidate } from '@vuelidate/core'
import {
  required,
  integer,
  minValue,
  maxValue,
  between,
  helpers,
} from '@vuelidate/validators'
import collectionElementForm from '@baserow/modules/builder/mixins/collectionElementForm'
import DeviceSelector from '@baserow/modules/builder/components/page/header/DeviceSelector.vue'
import { mapActions, mapGetters } from 'vuex'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import ServiceSchemaPropertySelector from '@baserow/modules/core/components/services/ServiceSchemaPropertySelector.vue'
import DataSourceDropdown from '@baserow/modules/builder/components/dataSource/DataSourceDropdown.vue'
import PropertyOptionForm from '@baserow/modules/builder/components/elements/components/forms/general/settings/PropertyOptionForm'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import { ORIENTATIONS } from '@baserow/modules/builder/enums'

const MAX_GAP_PX = 2000

export default {
  name: 'RepeatElementForm',
  components: {
    PropertyOptionForm,
    DataSourceDropdown,
    DeviceSelector,
    CustomStyleButton,
    InjectedFormulaInput,
    ServiceSchemaPropertySelector,
    PaddingSelector,
  },
  mixins: [collectionElementForm],
  inject: ['applicationContext'],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'data_source_id',
        'schema_property',
        'items_per_page',
        'items_per_row',
        'vertical_gap',
        'horizontal_gap',
        'orientation',
        'button_load_more_label',
        'styles',
      ],
      values: {
        data_source_id: null,
        schema_property: null,
        items_per_page: 1,
        items_per_row: {},
        orientation: 'vertical',
        vertical_gap: 0,
        horizontal_gap: 0,
        button_load_more_label: {},
        styles: {},
      },
    }
  },
  computed: {
    ...mapGetters({ deviceTypeSelected: 'page/getDeviceTypeSelected' }),
    isCollapsed() {
      const { element } = this.applicationContext
      return this.$store.getters['element/getRepeatElementCollapsed'](element)
    },
    deviceTypes() {
      return Object.values(this.$registry.getOrderedList('device'))
    },
    itemsPerRowError() {
      for (const device of this.deviceTypes) {
        const message =
          this.v$.values.items_per_row[device.getType()].$errors[0]?.$message
        if (message) {
          return message
        }
      }
      return ''
    },
    gapError() {
      if (this.v$.values.vertical_gap.$invalid) {
        return this.$t('error.minMaxValueField', {
          min: 0,
          max: MAX_GAP_PX,
        })
      }

      if (this.v$.values.horizontal_gap.$invalid) {
        return this.$t('error.minMaxValueField', {
          min: 0,
          max: MAX_GAP_PX,
        })
      }

      return ''
    },
    orientationOptions() {
      return [
        {
          label: this.$t('orientations.vertical'),
          value: ORIENTATIONS.VERTICAL,
          icon: 'iconoir-table-rows',
        },
        {
          label: this.$t('orientations.horizontal'),
          value: ORIENTATIONS.HORIZONTAL,
          icon: 'iconoir-view-columns-3',
        },
      ]
    },
    padding: {
      get() {
        return {
          vertical: this.values.vertical_gap,
          horizontal: this.values.horizontal_gap,
        }
      },
      set(newValue) {
        this.values.vertical_gap = newValue.vertical
        this.values.horizontal_gap = newValue.horizontal
      },
    },
    paddingDefaults() {
      return {
        vertical: 0,
        horizontal: 0,
      }
    },
  },
  mounted() {
    if (_.isEmpty(this.values.items_per_row)) {
      this.v$.values.items_per_row.$model = this.deviceTypes.reduce(
        (acc, deviceType) => {
          acc[deviceType.getType()] = 2
          return acc
        },
        {}
      )
    }
  },
  methods: {
    ...mapActions({
      actionSetDeviceTypeSelected: 'page/setDeviceTypeSelected',
    }),
    emitToggleRepetitions(value) {
      const { element } = this.applicationContext
      this.$store.dispatch('element/setRepeatElementCollapsed', {
        element,
        collapsed: value,
      })
    },
    handlePerRowInput(event, deviceTypeType) {
      this.v$.values.items_per_row[deviceTypeType].$touch()
      this.v$.values.items_per_row[deviceTypeType].$model = parseInt(event)
      this.$emit('input', this.values)
    },
  },
  validations() {
    const itemsPerPageRules = { integer }
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
        items_per_page: itemsPerPageRules,
        items_per_row: this.deviceTypes.reduce((acc, deviceType) => {
          acc[deviceType.getType()] = {
            integer: helpers.withMessage(
              this.$t('error.integerField'),
              integer
            ),
            minValue: helpers.withMessage(
              this.$t('error.minValueField', { min: 1 }),
              minValue(1)
            ),
            maxValue: helpers.withMessage(
              this.$t('error.maxValueField', { max: 10 }),
              maxValue(10)
            ),
          }
          return acc
        }, {}),
        vertical_gap: {
          required,
          integer,
          between: between(0, MAX_GAP_PX),
        },
        horizontal_gap: {
          required,
          integer,
          between: between(0, MAX_GAP_PX),
        },
      },
    }
  },
}
</script>
