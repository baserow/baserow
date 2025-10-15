<template>
  <div
    v-auto-overflow-scroll="scrollable"
    class="filters__items"
    :class="{
      'filters__container--dark': variant === 'dark',
      'filters__items--full-width': fullWidth,
      'filters__items--scrollable': scrollable,
    }"
  >
    <div
      v-for="(filter, index) in filtersTree.filtersOrdered()"
      :key="index"
      class="filters__item-wrapper"
    >
      <div class="filters__item filters__item--level-1">
        <ViewFilterFormOperator
          :index="index"
          :filter-type="filterType"
          :disable-filter="disableFilter"
          @updateFilterType="$emit('updateFilterType', { value: $event })"
        />

        <ViewFieldConditionItem
          :ref="`condition-${filter.id}`"
          :filter="filter"
          :view="view"
          :is-public-view="isPublicView"
          :fields="fields"
          :disable-filter="disableFilter"
          :read-only="readOnly"
          :placeholder="placeholder"
          @updateFilter="updateFilter({ filter, values: $event })"
          @deleteFilter="deleteFilter({ filter, event: $event })"
        >
          <template #filterInputComponent="{ slotProps }">
            <slot name="filterInputComponent" :slot-props="slotProps"></slot>
          </template>
          <template #afterValueInput="{ slotProps }">
            <slot name="afterValueInput" :slot-props="slotProps"></slot>
          </template>
        </ViewFieldConditionItem>
      </div>
    </div>
    <div
      v-for="(groupNode, groupIndex) in filtersTree.groupsOrdered()"
      :key="filtersTree.filters.length + groupIndex"
      class="filters__group-item-wrapper"
    >
      <ViewFilterFormOperator
        :index="filtersTree.filters.length + groupIndex"
        :filter-type="filterType"
        :disable-filter="disableFilter"
        @updateFilterType="$emit('updateFilterType', { value: $event })"
      />
      <ViewFieldConditionGroup
        :group-node="groupNode"
        :disable-filter="disableFilter"
        :is-public-view="isPublicView"
        :read-only="readOnly"
        :fields="fields"
        :view="view"
        :can-add-filter-groups="canAddFilterGroups"
        :add-condition-string="addConditionString"
        :add-condition-group-string="addConditionGroupString"
        @addFilter="$emit('addFilter', $event)"
        @addFilterGroup="$emit('addFilterGroup', $event)"
        @updateFilter="updateFilter($event)"
        @deleteFilter="deleteFilter($event)"
        @updateFilterType="$emit('updateFilterType', $event)"
      >
      </ViewFieldConditionGroup>
    </div>
  </div>
</template>

<script>
import ViewFilterFormOperator from '@baserow/modules/database/components/view/ViewFilterFormOperator'
import ViewFieldConditionItem from '@baserow/modules/database/components/view/ViewFieldConditionItem'
import ViewFieldConditionGroup from '@baserow/modules/database/components/view/ViewFieldConditionGroup'
import { sortNumbersAndUuid1Asc } from '@baserow/modules/core/utils/sort'

const GroupNode = class {
  constructor(group, parent = null, sorted = false) {
    this.group = group
    this.parent = parent
    this.children = []
    this.filters = []
    this.sorted = sorted
    if (parent) {
      parent.children.push(this)
    }
  }

  groupsOrdered() {
    if (this.sorted) {
      return this.children
    }

    return this.children.sort((a, b) => {
      return sortNumbersAndUuid1Asc(a.group, b.group)
    })
  }

  filtersOrdered() {
    if (this.sorted) {
      return this.filters
    }

    return this.filters.sort(sortNumbersAndUuid1Asc)
  }

  findGroup(id) {
    if (this.group && this.group.id === id) {
      return this
    }
    for (const groupNode of this.children) {
      const found = groupNode.findGroup(id)
      if (found) {
        return found
      }
    }
    return null
  }

  addFilter(filter) {
    this.filters.push(filter)
  }

  remove() {
    if (this.parent) {
      this.parent.children = this.parent.children.filter((g) => g !== this)
    }
  }
}

export default {
  name: 'ViewFieldConditionsForm',
  components: {
    ViewFilterFormOperator,
    ViewFieldConditionItem,
    ViewFieldConditionGroup,
  },
  props: {
    filters: {
      type: Array,
      required: true,
    },
    filterGroups: {
      type: Array,
      required: false,
      default: () => [],
    },
    disableFilter: {
      type: Boolean,
      required: true,
    },
    filterType: {
      type: String,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    // A view is optional, but may be required by some specific
    // field components, such as `ViewFilterTypeLinkRow`.
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
    readOnly: {
      type: Boolean,
      required: true,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
    addConditionString: {
      type: String,
      required: false,
      default: null,
    },
    addConditionGroupString: {
      type: String,
      required: false,
      default: null,
    },
    variant: {
      type: String,
      required: false,
      default: 'light',
    },
    fullWidth: {
      type: Boolean,
      required: false,
      default: false,
    },
    sorted: {
      type: Boolean,
      required: false,
      default: false,
    },
    /*
     * Allows the parent component to provide a function that will be called
     * when a filter is updated. This is useful for components that need to
     * do additional processing when a filter is updated.
     */
    prepareValue: {
      type: Function,
      required: false,
      default: (value, filter, field, filterType) => {
        return filterType.prepareValue(value, field, true)
      },
    },
    scrollable: {
      type: Boolean,
      required: false,
      default: false,
    },
    canAddFilterGroups: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  data() {
    return {
      groups: {},
    }
  },
  computed: {
    filterTypes() {
      return this.$registry.getAll('viewFilter')
    },
    filtersTree() {
      const root = new GroupNode(null, null, this.sorted)
      const groups = { '': root }
      for (const filterGroup of this.filterGroups) {
        const parentId = filterGroup.parent_group || ''
        const parent = groups[parentId]
        const node = new GroupNode(filterGroup, parent, this.sorted)
        groups[filterGroup.id] = node
      }
      for (const filter of this.filters) {
        const groupId = filter.group != null ? filter.group : ''
        const group = groups[groupId]
        if (group) {
          group.addFilter(filter)
        }
      }
      return root
    },
  },
  watch: {
    'view._.focusFilter': {
      handler(filterId) {
        const filter =
          filterId !== null && this.filters.find((f) => f.id === filterId)
        if (filter) {
          this.focusFilterValue(filter)
        }
      },
      immediate: true,
    },
  },
  methods: {
    focusFilterValue(filter) {
      this.$nextTick(() => {
        const ref = `condition-${filter.id}`
        if (this.$refs[ref] && this.$refs[ref].length > 0) {
          this.$refs[ref][0]?.focusValue()
        }
        this.$emit('filterFocused', filter)
      })
    },
    /**
     * Returns a list of filter types that are allowed for the given fieldId.
     */
    allowedFilters(filterTypes, fields, fieldId) {
      const field = fields.find((f) => f.id === fieldId)
      return Object.values(filterTypes).filter((filterType) => {
        return field !== undefined && filterType.fieldIsCompatible(field)
      })
    },
    deleteFilter({ filter, event }) {
      event.deletedFilterEvent = true
      let groupNode = this.filtersTree.findGroup(filter.group)
      // Pick the outermost group that is going to be empty after the deletion, if any.
      let emptyGroup = null
      while (
        groupNode?.group?.id &&
        groupNode.filters.length + groupNode.children.length === 1
      ) {
        emptyGroup = groupNode
        groupNode = groupNode.parent
      }
      if (emptyGroup !== null) {
        this.$emit('deleteFilterGroup', emptyGroup)
      } else {
        this.$emit('deleteFilter', filter)
      }
    },
    /**
     * Updates a filter with the given values. Some data manipulation will also be done
     * because some filter types are not compatible with certain field types.
     */
    updateFilter({ filter, values }) {
      const fieldId = Object.prototype.hasOwnProperty.call(values, 'field')
        ? values.field
        : filter.field
      const type = Object.prototype.hasOwnProperty.call(values, 'type')
        ? values.type
        : filter.type
      const value = Object.prototype.hasOwnProperty.call(values, 'value')
        ? values.value
        : filter.value

      // If the field has changed we need to check if the filter type is compatible
      // and if not we are going to choose the first compatible type.
      if (Object.prototype.hasOwnProperty.call(values, 'field')) {
        const allowedFilterTypes = this.allowedFilters(
          this.filterTypes,
          this.fields,
          fieldId
        ).map((filter) => filter.type)
        if (!allowedFilterTypes.includes(type)) {
          values.type = allowedFilterTypes[0]
        }
      }

      // If the type or value has changed it could be that the value needs to be
      // formatted or prepared.
      if (
        Object.prototype.hasOwnProperty.call(values, 'field') ||
        Object.prototype.hasOwnProperty.call(values, 'type') ||
        Object.prototype.hasOwnProperty.call(values, 'value')
      ) {
        const filterType = this.$registry.get('viewFilter', type)
        const field = this.fields.find(({ id }) => id === fieldId)

        values.value = this.prepareValue(value, filter, field, filterType)
      }

      this.$emit('updateFilter', { filter, values })
    },
  },
}
</script>
