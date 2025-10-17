<template>
  <div
    class="filters__condition-item"
    :class="{
      'filters__condition-item--loading': filter._?.loading,
      'filters__condition-item--misconfigured': filterMisconfigured,
    }"
  >
    <div v-if="filterMisconfigured" class="flex-grow-1">
      <p class="filters__misconfigured-text">
        {{ $t('viewFieldConditionItem.filterMisconfigured') }}
      </p>
    </div>
    <template v-else>
      <div class="filters__field">
        <Dropdown
          :value="filter.field"
          :disabled="disableFilter"
          :fixed-items="true"
          @input="$emit('updateFilter', { field: $event })"
        >
          <DropdownItem
            v-for="field in fields"
            :key="'field-' + field.id"
            :name="field.name"
            :value="field.id"
            :disabled="!hasCompatibleFilterTypes(field, filterTypes)"
          ></DropdownItem>
        </Dropdown>
      </div>
      <div class="filters__type">
        <Dropdown
          :disabled="disableFilter"
          :value="filter.type"
          :fixed-items="true"
          @input="$emit('updateFilter', { type: $event })"
        >
          <DropdownItem
            v-for="fType in allowedFilters(filterTypes, fields, filter.field)"
            :key="fType.type"
            :name="fType.getName()"
            :value="fType.type"
            :visible="
              fType.isDeprecated() === false || fType.type === filter.type
            "
          ></DropdownItem>
        </Dropdown>
      </div>
      <div
        class="filters__value"
        :class="{
          'filters__value--with-input-field': hasAfterValueInputContent,
        }"
      >
        <slot
          name="filterInputComponent"
          :slot-props="{
            filter: filter,
            field: getField(filter.field),
            filterType: getFilterType(filter.type),
          }"
        >
          <component
            :is="getInputComponent(filter.type, filter.field)"
            v-if="fieldCanBeFiltered(fields, filter)"
            ref="filter-value"
            :filter="filter"
            :view="view"
            :is-public-view="isPublicView"
            :fields="fields"
            :disabled="disableFilter"
            :read-only="readOnly"
            :placeholder="placeholder"
            @input="$emit('updateFilter', { value: $event })"
            @migrate="$emit('updateFilter', $event)"
          />
        </slot>
        <slot
          name="afterValueInput"
          :slot-props="{
            filter: filter,
            filterType: getFilterType(filter.type),
            emitUpdate: emitUpdate,
          }"
        ></slot>
        <i
          v-if="!fieldIdExists(fields, filter.field)"
          v-tooltip="$t('viewFilterContext.relatedFieldNotFound')"
          class="fas fa-exclamation-triangle color-error"
        ></i>
        <i
          v-if="!fieldIsCompatible(filter.type, filter.field)"
          v-tooltip="$t('viewFilterContext.filterTypeNotFound')"
          class="fas fa-exclamation-triangle color-error"
        ></i>
      </div>
    </template>
    <a
      class="filters__remove"
      :class="{ 'filters__remove--disabled': disableFilter }"
      @click.stop="!disableFilter && $emit('deleteFilter', $event)"
    >
      <i class="iconoir-bin"></i>
    </a>
  </div>
</template>

<script>
import { hasCompatibleFilterTypes } from '@baserow/modules/database/utils/field'
import viewFilterTypes from '@baserow/modules/database/mixins/viewFilterTypes'

export default {
  name: 'ViewFieldConditionItem',
  mixins: [viewFilterTypes],
  props: {
    filter: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: false,
      default: () => undefined,
    },
    isPublicView: {
      type: Boolean,
      required: false,
      default: false,
    },
    disableFilter: {
      type: Boolean,
      default: false,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
  },
  computed: {
    hasAfterValueInputContent() {
      return !!this.$scopedSlots.afterValueInput
    },
    /**
     * If a filter points to a `field` which is not present in `this.fields`,
     * or the field object is found, and the field is trashed, flag this filter
     * as being misconfigured. This is very unlikely to happen in the database,
     * but when this component is used in the builder, it is possible. In that
     * implementation, the builder needs the ability to display a misconfigured
     * filter so that the page designer can delete it.
     * @returns {Boolean} True if the filter is misconfigured, false otherwise.
     */
    filterMisconfigured() {
      const field = this.getField(this.filter.field)
      return field === undefined || field.trashed
    },
  },
  methods: {
    hasCompatibleFilterTypes,
    focusValue() {
      if (this.$refs['filter-value']?.focus !== undefined) {
        this.$refs['filter-value'].focus()
      }
    },
    getField(fieldId) {
      return this.fields.find(({ id }) => id === fieldId)
    },
    getFilterType(type) {
      return this.$registry.get('viewFilter', type)
    },
    allowedFilters(filterTypes, fields, fieldId) {
      const field = this.getField(fieldId)
      return Object.values(filterTypes).filter((filterType) => {
        return field !== undefined && filterType.fieldIsCompatible(field)
      })
    },
    getInputComponent(type, fieldId) {
      const field = this.getField(fieldId)
      return this.getFilterType(type).getInputComponent(field)
    },
    fieldCanBeFiltered(fields, filter) {
      return (
        this.fieldIdExists(fields, filter.field) &&
        this.fieldIsCompatible(filter.type, filter.field)
      )
    },
    fieldIdExists(fields, fieldId) {
      return fields.findIndex((field) => field.id === fieldId) !== -1
    },
    fieldIsCompatible(filterType, fieldId) {
      const field = this.getField(fieldId)
      if (!(filterType in this.filterTypes)) {
        return false
      }
      return this.filterTypes[filterType].fieldIsCompatible(field)
    },
    emitUpdate(changes) {
      this.$emit('updateFilter', changes)
    },
  },
}
</script>
