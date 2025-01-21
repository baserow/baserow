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
      :error-message="
        $v.values.items_per_page.$dirty && !$v.values.items_per_page.required
          ? $t('error.requiredField')
          : !$v.values.items_per_page.integer
          ? $t('error.integerField')
          : !$v.values.items_per_page.minValue
          ? $t('error.minValueField', { min: 1 })
          : !$v.values.items_per_page.maxValue
          ? $t('error.maxValueField', { max: maxItemPerPage })
          : ''
      "
    >
      <FormInput
        v-model="values.items_per_page"
        :placeholder="$t('repeatElementForm.itemsPerPagePlaceholder')"
        :to-value="(value) => parseInt(value)"
        type="number"
        @blur="$v.values.items_per_page.$touch()"
      />
    </FormGroup>

    <CustomStyle
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
      :label="$t('repeatElementForm.orientationLabel')"
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
    <FormGroup
      v-if="propertyOptionsAvailable"
      small-label
      class="margin-bottom-2"
      :label="$t('collectionElementForm.propertyOptionLabel')"
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
import {
  between,
  required,
  integer,
  minValue,
  maxValue,
} from 'vuelidate/lib/validators'
import collectionElementForm from '@baserow/modules/builder/mixins/collectionElementForm'
import DeviceSelector from '@baserow/modules/builder/components/page/header/DeviceSelector.vue'
import { mapActions, mapGetters } from 'vuex'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import ServiceSchemaPropertySelector from '@baserow/modules/core/components/services/ServiceSchemaPropertySelector.vue'
import DataSourceDropdown from '@baserow/modules/builder/components/dataSource/DataSourceDropdown.vue'
import PropertyOptionForm from '@baserow/modules/builder/components/elements/components/forms/general/settings/PropertyOptionForm'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'

const MAX_GAP_PX = 2000

export default {
  name: 'RepeatElementForm',
  components: {
    PropertyOptionForm,
    DataSourceDropdown,
    DeviceSelector,
    CustomStyle,
    InjectedFormulaInput,
    ServiceSchemaPropertySelector,
    PaddingSelector,
  },
  mixins: [collectionElementForm],
  inject: ['applicationContext'],
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
        button_load_more_label: '',
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
        const validation = this.$v.values.items_per_row[device.getType()]
        if (validation.$dirty) {
          if (!validation.integer) {
            return this.$t('error.integerField')
          }
          if (!validation.minValue) {
            return this.$t('error.minValueField', { min: 1 })
          }
          if (!validation.maxValue) {
            return this.$t('error.maxValueField', { max: 10 })
          }
        }
      }
      return ''
    },
    gapError() {
      if (this.$v.values.vertical_gap.$invalid) {
        return this.$t('error.minMaxValueField', {
          min: 0,
          max: MAX_GAP_PX,
        })
      }

      if (this.$v.values.horizontal_gap.$invalid) {
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
          label: this.$t('repeatElementForm.orientationVertical'),
          value: 'vertical',
          icon: 'iconoir-table-rows',
        },
        {
          label: this.$t('repeatElementForm.orientationHorizontal'),
          value: 'horizontal',
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
      this.values.items_per_row = this.deviceTypes.reduce((acc, deviceType) => {
        acc[deviceType.getType()] = 2
        return acc
      }, {})
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
      this.$v.values.items_per_row[deviceTypeType].$touch()
      this.values.items_per_row[deviceTypeType] = parseInt(event)
      this.$emit('input', this.values)
    },
  },
  validations() {
    const itemsPerPageRules = { integer }
    if (this.pagingOptionsAvailable) {
      itemsPerPageRules.required = required
      itemsPerPageRules.minValue = minValue(1)
      itemsPerPageRules.maxValue = maxValue(this.maxItemPerPage)
    }
    return {
      values: {
        items_per_page: itemsPerPageRules,
        items_per_row: this.deviceTypes.reduce((acc, deviceType) => {
          acc[deviceType.getType()] = {
            integer,
            minValue: minValue(1),
            maxValue: maxValue(10),
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
