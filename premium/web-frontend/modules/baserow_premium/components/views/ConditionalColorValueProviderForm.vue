<template>
  <div>
    <div>
      <div class="conditional-color-value-provider-form__colors-header">
        <div class="conditional-color-value-provider-form__colors-header-title">
          {{ $t('conditionalColorValueProviderForm.title') }}
        </div>
        <ButtonText
          icon="iconoir-plus"
          class="conditional-color-value-provider-form__color-add"
          @click.prevent="addColor()"
        >
          {{ $t('conditionalColorValueProviderForm.addColor') }}
        </ButtonText>
      </div>
      <div>
        <div
          v-for="color in options.colors || []"
          :key="color.id"
          v-sortable="{
            id: color.id,
            update: orderColor,
            handle: '[data-sortable-handle]',
            marginTop: -5,
          }"
          class="conditional-color-value-provider-form__color"
        >
          <div class="conditional-color-value-provider-form__color-header">
            <div
              class="conditional-color-value-provider-form__color-handle"
              data-sortable-handle
            ></div>
            <a
              :ref="`colorSelect-${color.id}`"
              class="conditional-color-value-provider-form__color-color"
              :class="`background-color--${color.color}`"
              @click="openColor(color)"
            >
              <i class="iconoir-nav-arrow-down"></i>
            </a>
            <div
              v-if="color.filters.length === 0"
              class="conditional-color-value-provider-form__color-filter--empty"
            >
              <div>
                {{
                  $t('conditionalColorValueProviderForm.colorAlwaysApplyTitle')
                }}
              </div>
              <div>
                {{ $t('conditionalColorValueProviderForm.colorAlwaysApply') }}
              </div>
            </div>
          </div>
          <ViewFieldConditionsForm
            v-show="color.filters.length !== 0"
            class="conditional-color-value-provider-form__color-filters"
            :filters="color.filters"
            :filter-groups="color.filter_groups"
            :disable-filter="false"
            :filter-type="color.operator"
            :fields="fields"
            :view="view"
            :read-only="readOnly"
            :variant="'dark'"
            :sorted="true"
            @add-filter="addFilter(color, $event)"
            @add-filter-group="addFilterGroup(color, $event)"
            @delete-filter="deleteFilter(color, $event)"
            @update-filter="updateFilter(color, $event)"
            @update-filter-type="updateFilterType(color, $event)"
            @delete-filter-group="deleteFilterGroup(color, $event)"
          />
          <div
            class="conditional-color-value-provider-form__color-filter-actions"
          >
            <ButtonText
              class="conditional-color-value-provider-form__color-filter-add"
              icon="iconoir-plus"
              @click.prevent="addFilter(color)"
            >
              {{ $t('conditionalColorValueProviderForm.addCondition') }}
            </ButtonText>
            <ButtonText
              class="conditional-color-value-provider-form__color-filter-group-add"
              icon="iconoir-plus"
              @click.prevent="addFilterGroup(color)"
            >
              {{ $t('conditionalColorValueProviderForm.addConditionGroup') }}
            </ButtonText>
            <div :style="{ flex: '1 1 auto' }"></div>
            <a
              v-if="options.colors.length > 1"
              class="conditional-color-value-provider-form__color-trash-link"
              @click="deleteColor(color)"
            >
              <i
                class="iconoir-bin conditional-color-value-provider-form__color-trash-link-icon"
              ></i>
              {{ $t('conditionalColorValueProviderForm.deleteColor') }}
            </a>
          </div>
          <ColorSelectContext
            :ref="`colorContext-${color.id}`"
            @selected="updateColor(color, { color: $event })"
          ></ColorSelectContext>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import ViewFieldConditionsForm from '@baserow/modules/database/components/view/ViewFieldConditionsForm'
import ColorSelectContext from '@baserow/modules/core/components/ColorSelectContext'
import { ConditionalColorValueProviderType } from '@baserow_premium/decoratorValueProviders'
import { createFiltersTree } from '@baserow/modules/database/utils/view'

export default {
  name: 'ConditionalColorValueProvider',
  emits: ['update'],
  components: { ViewFieldConditionsForm, ColorSelectContext },
  props: {
    database: {
      type: Object,
      required: true,
    },
    options: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
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
  methods: {
    orderColor(colorIds) {
      const newColors = colorIds.map((colorId) =>
        this.options.colors.find(({ id }) => id === colorId)
      )
      this.$emit('update', {
        colors: newColors,
      })
    },
    openColor(color) {
      this.$refs[`colorContext-${color.id}`][0].setActive(color.color)
      this.$refs[`colorContext-${color.id}`][0].toggle(
        this.$refs[`colorSelect-${color.id}`][0],
        'bottom',
        'left',
        4
      )
    },
    addColor() {
      const colorToExclude = this.options.colors.map((color) => color.color)
      this.$emit('update', {
        colors: [
          ...this.options.colors,
          ConditionalColorValueProviderType.getDefaultColorConf(colorToExclude),
        ],
      })
    },
    updateColor(color, values) {
      const newColors = this.options.colors.map((colorConf) => {
        if (colorConf.id === color.id) {
          return { ...colorConf, ...values }
        }
        return colorConf
      })

      this.$emit('update', {
        colors: newColors,
      })
    },
    deleteColor(color) {
      const newColors = this.options.colors.filter(({ id }) => {
        return id !== color.id
      })

      this.$emit('update', {
        colors: newColors,
      })
    },
    addFilterGroup(color, { filterGroupId = null, parentGroupId = null } = {}) {
      const newFilterGroup =
        ConditionalColorValueProviderType.getDefaultFilterGroupConf(
          filterGroupId,
          parentGroupId
        )
      const newFilter = ConditionalColorValueProviderType.getDefaultFilterConf(
        this.$registry,
        {
          fields: this.fields,
          filterGroupId: newFilterGroup.id,
        }
      )
      const newColors = this.options.colors.map((colorConf) => {
        if (colorConf.id === color.id) {
          return {
            ...colorConf,
            filter_groups: [...(colorConf.filter_groups || []), newFilterGroup],
            filters: [...colorConf.filters, newFilter],
          }
        }
        return colorConf
      })

      this.$emit('update', {
        colors: newColors,
      })

      this.$store.dispatch('view/setFocusFilter', {
        view: this.view,
        filterId: newFilter.id,
      })
    },
    updateFilterType(color, { value, filterGroup }) {
      if (filterGroup === undefined) {
        return this.updateColor(color, { operator: value })
      }

      const newColors = this.options.colors.map((colorConf) => {
        if (colorConf.id === color.id) {
          const newFilterGroups = colorConf.filter_groups.map((group) => {
            if (group.id === filterGroup.id) {
              return { ...group, filter_type: value }
            }
            return group
          })
          return {
            ...colorConf,
            filter_groups: newFilterGroups,
          }
        }
        return colorConf
      })

      this.$emit('update', {
        colors: newColors,
      })
    },
    addFilter(color, { filterGroupId = null } = {}) {
      const newFilter = ConditionalColorValueProviderType.getDefaultFilterConf(
        this.$registry,
        {
          fields: this.fields,
          filterGroupId,
        }
      )
      const newColors = this.options.colors.map((colorConf) => {
        if (colorConf.id === color.id) {
          return {
            ...colorConf,
            filters: [...colorConf.filters, newFilter],
          }
        }
        return colorConf
      })

      this.$emit('update', {
        colors: newColors,
      })

      this.$store.dispatch('view/setFocusFilter', {
        view: this.view,
        filterId: newFilter.id,
      })
    },
    updateFilter(color, { filter, values }) {
      const newColors = this.options.colors.map((colorConf) => {
        if (colorConf.id === color.id) {
          const newFilters = colorConf.filters.map((filterConf) => {
            if (filterConf.id === filter.id) {
              return { ...filter, ...values }
            }
            return filterConf
          })
          return {
            ...colorConf,
            filters: newFilters,
          }
        }
        return colorConf
      })

      this.$emit('update', {
        colors: newColors,
      })
    },
    deleteFilter(color, filter) {
      const newColors = this.options.colors.map((colorConf) => {
        if (colorConf.id === color.id) {
          const newFilters = colorConf.filters.filter((filterConf) => {
            return filterConf.id !== filter.id
          })
          return {
            ...colorConf,
            filters: newFilters,
          }
        }
        return colorConf
      })

      this.$emit('update', {
        colors: newColors,
      })
    },
    deleteFilterGroup(color, { group }) {
      const colorConf = this.options.colors.find(({ id }) => id === color.id)
      const filtersTree = createFiltersTree(
        colorConf.filter_type,
        colorConf.filters,
        colorConf.filter_groups
      )
      const groupNode = filtersTree.findNodeByGroupId(group.id)
      if (groupNode === null) {
        return
      }
      // given a group, find all the filters/groups that are children
      const groupsToRemove = [group.id]
      const removeChildGroup = (treeNode) => {
        for (const child of treeNode.children) {
          groupsToRemove.push(child.groupId)
          removeChildGroup(child)
        }
      }
      removeChildGroup(groupNode)

      // remove all filters and groups that are children of the group
      const newColors = this.options.colors.map((colorConf) => {
        if (colorConf.id === color.id) {
          const newFilters = colorConf.filters.filter((filter) => {
            return !groupsToRemove.includes(filter.group)
          })
          const newFilterGroups = colorConf.filter_groups.filter((group) => {
            return !groupsToRemove.includes(group.id)
          })
          return {
            ...colorConf,
            filters: newFilters,
            filter_groups: newFilterGroups,
          }
        } else {
          return colorConf
        }
      })

      this.$emit('update', {
        colors: newColors,
      })
    },
  },
}
</script>
