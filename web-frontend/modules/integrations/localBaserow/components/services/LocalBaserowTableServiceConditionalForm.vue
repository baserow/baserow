<template>
  <div v-if="modelValue">
    <div v-if="modelValue.length === 0 && filterGroups.length === 0">
      <div class="filters__none">
        <div class="filters__none-title">
          {{ $t('localBaserowTableServiceConditionalForm.noFilterTitle') }}
        </div>
        <div class="filters__none-description">
          {{ $t('localBaserowTableServiceConditionalForm.noFilterText') }}
        </div>
      </div>
    </div>
    <ViewFieldConditionsForm
      :filters="getDataSourceFilters()"
      :filter-groups="filterGroups"
      :disable-filter="false"
      :filter-type="filterType"
      :fields="fields"
      :read-only="false"
      full-width
      sorted
      class="filters__items"
      :prepare-value="prepareValue"
      :add-condition-string="
        $t('localBaserowTableServiceConditionalForm.addFilter')
      "
      :add-condition-group-string="
        $t('localBaserowTableServiceConditionalForm.addFilterGroup')
      "
      :placeholder="
        $t('localBaserowTableServiceConditionalForm.textFilterInputPlaceholder')
      "
      @add-filter="addFilter($event)"
      @add-filter-group="addFilterGroup($event)"
      @delete-filter="deleteFilter($event)"
      @delete-filter-group="deleteFilterGroup($event)"
      @update-filter="updateFilter($event)"
      @update-filter-type="updateFilterType($event)"
    >
      <template
        #filterInputComponent="{
          slotProps: { filter, field, filterType: propFilterType },
        }"
      >
        <InjectedFormulaInput
          v-if="
            propFilterType.hasEditableValue && !propFilterType.isDeprecated()
          "
          :model-value="getFormulaObject(filter)"
          class="filters__value--formula-input"
          allow-raw-values
          :placeholder="
            $t(
              'localBaserowTableServiceConditionalForm.expressionFilterInputPlaceholder'
            )
          "
          @input="
            updateFilter({
              filter,
              values: { value: $event.formula, mode: $event.mode },
            })
          "
        >
          <template #raw-input="{ value, input }">
            <component
              :is="propFilterType.getInputComponent(field)"
              :filter="{ ...filter, value }"
              :fields="fields"
              :disabled="false"
              :read-only="false"
              :placeholder="
                $t(
                  'localBaserowTableServiceConditionalForm.textFilterInputPlaceholder'
                )
              "
              @input="input"
              @migrate="updateFilter({ filter, values: $event })"
            />
          </template>
        </InjectedFormulaInput>
      </template>
    </ViewFieldConditionsForm>
    <div class="filters_footer">
      <ButtonText
        type="secondary"
        size="small"
        icon="iconoir-plus"
        class="filters__add"
        @click.prevent="addFilter()"
      >
        {{ $t('localBaserowTableServiceConditionalForm.addFilter') }}
      </ButtonText>
      <ButtonText
        type="secondary"
        size="small"
        icon="iconoir-plus"
        class="filters__add"
        @click.prevent="addFilterGroup()"
      >
        {{ $t('localBaserowTableServiceConditionalForm.addFilterGroup') }}
      </ButtonText>
    </div>
  </div>
</template>

<script>
import ViewFieldConditionsForm from '@baserow/modules/database/components/view/ViewFieldConditionsForm.vue'
import { hasCompatibleFilterTypes } from '@baserow/modules/database/utils/field'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { ulid } from 'ulid'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'LocalBaserowTableServiceConditionalForm',
  components: {
    InjectedFormulaInput,
    ViewFieldConditionsForm,
  },
  props: {
    modelValue: {
      type: Array,
      required: true,
    },
    filterGroups: {
      type: Array,
      required: false,
      default: () => [],
    },
    fields: {
      type: Array,
      required: true,
    },
    filterType: {
      type: String,
      required: true,
    },
  },
  emits: ['update:modelValue', 'update:filterGroups', 'update:filterType'],
  computed: {
    filterTypes() {
      return this.$registry.getAll('viewFilter')
    },
    databaseSelected() {
      return this.databases.find(
        (database) => database.id === this.databaseSelectedId
      )
    },
    tables() {
      return this.databaseSelected?.tables || []
    },
  },
  methods: {
    /*
     * Responsible for returning the first compatible field we have in
     * our schema fields. Used by `addFilter` to decide what the newly
     * added filter's field should be.
     */
    getFirstCompatibleField(fields) {
      return fields
        .slice()
        .sort((a, b) => b.primary - a.primary)
        .find((field) => hasCompatibleFilterTypes(field, this.filterTypes))
    },
    /*
     * Responsible for returning all current data source filters in their
     * existing array order. Because we pass `sorted` to
     * `ViewFieldConditionsForm`, it renders filters and groups in insertion
     * order rather than re-sorting them by id. This keeps newly added filters
     * and groups appended (matching the database grid view), which id-based
     * sorting cannot guarantee for our client-side `ulid` ids.
     */
    getDataSourceFilters() {
      // The `value` prop is an array of filters with a formula object value.
      // The `ViewFieldConditionsForm` expects the filter value itself to be a
      // string, so we keep the mode alongside the flattened formula string.
      return this.modelValue.map((filterConf) => {
        const formulaObject = this.normalizeFormulaObject(filterConf)
        return {
          ...filterConf,
          value: formulaObject.formula,
          mode: formulaObject.mode,
        }
      })
    },
    /*
     * Responsible for asynchronously adding a new data source filter.
     * By default it'll be for the first compatible field, of type equal,
     * and value blank. If a `filterGroupId` is provided, the filter is added
     * to that group, otherwise it applies directly to the service.
     */
    async addFilter({ filterGroupId = null } = {}) {
      try {
        const field = this.getFirstCompatibleField(this.fields)
        if (field === undefined) {
          await this.$store.dispatch('toast/error', {
            title: this.$t(
              'localBaserowTableServiceConditionalForm.noCompatibleFilterTypesErrorTitle'
            ),
            message: this.$t(
              'localBaserowTableServiceConditionalForm.noCompatibleFilterTypesErrorMessage'
            ),
          })
        } else {
          const newFilters = [...this.modelValue]
          // Setting an `id` of `ulid` is necessary for two reasons:
          // 1) So that we can distinguish between filters locally
          // 2) It has to match what is sorted against `sortNumbersAndUuid1Asc`.
          newFilters.push({
            id: ulid(),
            field: field.id,
            type: 'equal',
            value: { formula: '', mode: 'raw' },
            group: filterGroupId,
          })
          this.$emit('update:modelValue', newFilters)
        }
      } catch (error) {
        notifyIf(error, 'dataSource')
      }
    },
    /*
     * Responsible for adding a new filter group. A group is created with a
     * default AND operator, and a first filter is seeded inside it (mirroring
     * the database grid view's behaviour). If a `parentGroupId` is provided,
     * the group is nested inside that parent group.
     */
    addFilterGroup({ filterGroupId = null, parentGroupId = null } = {}) {
      const groupId = filterGroupId || ulid()
      const newFilterGroups = [
        ...this.filterGroups,
        {
          id: groupId,
          filter_type: 'AND',
          parent_group: parentGroupId,
        },
      ]
      this.$emit('update:filterGroups', newFilterGroups)
      // Seed the new group with a first filter, just like the grid view does.
      this.addFilter({ filterGroupId: groupId })
    },
    /*
     * Removes a filter group along with all of its descendant groups and any
     * filters belonging to them.
     */
    deleteFilterGroup({ group }) {
      const groupIdsToRemove = new Set([group.id])
      // Collect nested groups iteratively (UI allows a few levels of nesting).
      let changed = true
      while (changed) {
        changed = false
        for (const filterGroup of this.filterGroups) {
          if (
            filterGroup.parent_group != null &&
            groupIdsToRemove.has(filterGroup.parent_group) &&
            !groupIdsToRemove.has(filterGroup.id)
          ) {
            groupIdsToRemove.add(filterGroup.id)
            changed = true
          }
        }
      }
      const newFilterGroups = this.filterGroups.filter(
        ({ id }) => !groupIdsToRemove.has(id)
      )
      const newFilters = this.modelValue.filter(
        ({ group: filterGroupId }) => !groupIdsToRemove.has(filterGroupId)
      )
      this.$emit('update:filterGroups', newFilterGroups)
      this.$emit('update:modelValue', newFilters)
    },
    /*
     * Updates the filter type (AND/OR). When a `filterGroup` is provided, the
     * group's own operator is updated, otherwise the service's top-level
     * operator is updated.
     */
    updateFilterType({ value, filterGroup } = {}) {
      if (filterGroup === undefined) {
        this.$emit('update:filterType', value)
        return
      }
      const newFilterGroups = this.filterGroups.map((group) =>
        group.id === filterGroup.id ? { ...group, filter_type: value } : group
      )
      this.$emit('update:filterGroups', newFilterGroups)
    },
    /*
     * Responsible for removing the chosen filter from the data source's filters.
     */
    deleteFilter(filter) {
      const newFilters = this.modelValue.filter(({ id }) => {
        return id !== filter.id
      })
      this.$emit('update:modelValue', newFilters)
    },
    /*
     * Responsible for updating the chosen filter in the data source's filters.
     */
    updateFilter({ filter, values }) {
      const newFilters = this.modelValue.map((filterConf) => {
        if (filterConf.id === filter.id) {
          const mode = values.mode || filter.mode || 'raw'
          const filterValues = { ...filterConf }
          delete filterValues.value
          delete filterValues.value_is_formula
          delete filterValues.mode

          const updatedValues = { ...values }
          delete updatedValues.value
          delete updatedValues.value_is_formula
          delete updatedValues.mode

          return {
            ...filterValues,
            ...updatedValues,
            value: {
              formula: values.value,
              mode,
            },
          }
        }
        return filterConf
      })
      this.$emit('update:modelValue', newFilters)
    },
    /*
     * Responsible for bypassing the `ViewFieldConditionsForm` component's
     * `updateFilter` method behaviour if the field is a formula. By default,
     * when a filter is updated, `filterType.prepareValue` is called. This is
     * problematic because when formulas are introduced to filters, we don't
     * want any additional processing to happen when the value is reset. For example,
     * when a filter on a date is added, `LocalizedDateViewFilterType.prepareValue`
     * will always add the timezone and `DATE_FILTER_TIMEZONE_VALUE_SEPARATOR`.
     */
    prepareValue(value, filter, field, filterType) {
      // When a filter is not editable (e.g. empty/not empty), ordinarily the
      // value is reset to a blank string by prepareValue. As we want to skip
      // this function, we have to reset manually here.
      return filterType.hasEditableValue ? value : ''
    },
    /**
     * Baserow formula (i.e. non-database formulas) are objects, and within
     * them is the actual formula string. This method is responsible for
     * returning that formula string so that it can be passed to the
     * `InjectedFormulaInput` component.
     * @param {Object} filter - The filter object.
     * @returns {Object} The formula object with the formula string.
     */
    getFormulaObject(filter) {
      return {
        formula: filter.value,
        mode: filter.mode || 'raw',
      }
    },
    normalizeFormulaObject(filter) {
      if (filter.value && typeof filter.value === 'object') {
        const mode =
          filter.value.mode || (filter.value_is_formula ? 'simple' : 'raw')
        return {
          ...filter.value,
          mode: filter.value_is_formula === false ? 'raw' : mode,
        }
      }

      return {
        formula: filter.value || '',
        mode: filter.value_is_formula ? 'simple' : 'raw',
      }
    },
  },
}
</script>
