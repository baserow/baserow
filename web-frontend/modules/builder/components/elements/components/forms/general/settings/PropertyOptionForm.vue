<template>
  <div>
    <p class="margin-bottom-2">
      {{ $t('propertyOptionForm.formDescription') }}
    </p>
    <BaserowTable
      class="property-option-form__table"
      :fields="fields"
      :rows="rows"
    >
      <template #field-name="{ field }">
        <th
          :key="field.__id__"
          class="baserow-table__header-cell"
          :class="{
            'property-option-form__table-field': !field.isOption,
          }"
        >
          <slot name="field-name" :field="field">{{ field.name }}</slot>
        </th>
      </template>
      <template #cell-content="{ rowIndex, value, field }">
        <td
          v-if="field.isOption"
          :key="field.name"
          class="baserow-table__cell property-option-form__table-option"
        >
          <Checkbox
            v-tooltip="
              optionIsDisabled(rows[rowIndex], field.__id__)
                ? $t('propertyOptionForm.optionUnavailable')
                : null
            "
            tooltip-position="top"
            :checked="value"
            :disabled="optionIsDisabled(rows[rowIndex], field.__id__)"
            @input="onOptionChange(rows[rowIndex], field.property, $event)"
          ></Checkbox>
        </td>
        <td
          v-else
          :key="field.name"
          class="baserow-table__cell property-option-form__table-property"
        >
          <span :title="value">{{ value }}</span>
        </td>
      </template>
      <template #empty-state>
        {{ $t('propertyOptionForm.noPropertiesAvailable') }}
      </template>
    </BaserowTable>
  </div>
</template>

<script>
import BaserowTable from '@baserow/modules/builder/components/elements/components/BaserowTable'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'PropertyOptionForm',
  components: { BaserowTable },
  mixins: [form],
  props: {
    dataSource: {
      type: Object,
      required: true,
    },
    isFilterable: {
      type: Boolean,
      required: false,
      default: false,
    },
    isSearchable: {
      type: Boolean,
      required: false,
      default: false,
    },
    isSortable: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      allowedValues: ['property_options'],
      values: {
        property_options: [],
      },
    }
  },
  computed: {
    schema() {
      return this.$registry
        .get('service', this.dataSource.type)
        .getDataSchema(this.dataSource)
    },
    elementType() {
      return this.$registry.get('element', this.element.type)
    },
    /**
     * Returns an object with schema properties as keys and their corresponding
     * property options as values. It's a convenience computed method to easily
     * access property options by schema property.
     * @returns {object} - The grouped property options.
     */
    propertyGroupedOptions() {
      return Object.fromEntries(
        this.values.property_options.map((po) => [po.schema_property, po])
      )
    },
    /**
     * Returns an array of objects that represent the table fields.
     * Each field is flagged as `isOption` if it represents a user
     * configurable property option.
     * @returns {Array} - The table fields.
     */
    fields() {
      const fields = [
        {
          name: this.$t('propertyOptionForm.fieldHeading'),
          property: null,
          isOption: false,
          __id__: 'field',
        },
      ]
      if (this.isFilterable) {
        fields.push({
          name: this.$t('propertyOptionForm.filterHeading'),
          property: 'filterable',
          isOption: true,
          __id__: 'filter',
        })
      }
      if (this.isSortable) {
        fields.push({
          name: this.$t('propertyOptionForm.sortHeading'),
          property: 'sortable',
          isOption: true,
          __id__: 'sort',
        })
      }
      if (this.isSearchable) {
        fields.push({
          name: this.$t('propertyOptionForm.searchHeading'),
          property: 'searchable',
          isOption: true,
          __id__: 'search',
        })
      }
      return fields
    },
    rows() {
      if (this.schema === null) {
        return []
      }
      const schemaProperties =
        this.schema.type === 'array'
          ? this.schema.items.properties
          : this.schema.properties
      return Object.entries(schemaProperties)
        .filter(
          ([_, propertyValues]) =>
            propertyValues.sortable ||
            propertyValues.filterable ||
            propertyValues.searchable
        )
        .map(([schemaProperty, propertyValues]) => ({
          schemaProperty,
          propertyValues,
          field: propertyValues.title,
          filter: this.getOptionValue(
            schemaProperty,
            propertyValues,
            'filterable'
          ),
          sort: this.getOptionValue(schemaProperty, propertyValues, 'sortable'),
          search: this.getOptionValue(
            schemaProperty,
            propertyValues,
            'searchable'
          ),
        }))
    },
  },
  methods: {
    /**
     * A convenience method which returns whether a particular option name
     * (e.g. Filter, Sort, Search) is disabled for a given row. This would
     * happen if the schema property specifies that the option is not ever
     * available for this property.
     *
     * @param row - The row object.
     * @param optionName - The option name to check.
     * @returns {boolean} - Whether the option is disabled.
     */
    optionIsDisabled(row, optionName) {
      return row[optionName] === null
    },
    getOptionValue(schemaProperty, propertyValues, optionName) {
      if (!propertyValues[optionName]) {
        // The schema has specified that this property is not
        // filterable/sortable/searchable. We return null to inform
        // the template that the checkbox should be disabled.
        return null
      }
      // If we have an existing property option for this property,
      // return whether it's filterable/sortable/searchable. If it hasn't
      // been configured, we default to false for this `optionName`.
      return this.propertyGroupedOptions[schemaProperty]
        ? this.propertyGroupedOptions[schemaProperty][optionName]
        : false
    },
    /**
     * Updates the property option of a schema property.
     *
     * @param row - The row object.
     * @param optionProperty - The property option to update.
     * @param value - The new value for the property option.
     */
    onOptionChange(row, optionProperty, value) {
      let newOptions
      const existingOption = this.values.property_options.find((po) => {
        return po.schema_property === row.schemaProperty
      })
      if (existingOption) {
        newOptions = this.values.property_options.map((propOption) => {
          if (propOption.schema_property === row.schemaProperty) {
            return { ...propOption, ...{ [optionProperty]: value } }
          }
          return propOption
        })
      } else {
        newOptions = [
          ...this.values.property_options,
          { schema_property: row.schemaProperty, [optionProperty]: value },
        ]
      }
      this.values.property_options = newOptions
    },
  },
}
</script>
