<template>
  <div class="filters__content">
    <div
      v-if="view.filters.length === 0"
      v-auto-overflow-scroll
      class="filters__none filters__none--scrollable"
    >
      <div class="filters__none-title">
        {{ $t('viewFilterContext.noFilterTitle') }}
      </div>
      <div class="filters__none-description">
        {{ $t('viewFilterContext.noFilterText') }}
      </div>
    </div>

    <ViewFieldConditionsForm
      v-if="view.filters.length > 0"
      :filters="view.filters"
      :filter-groups="view.filter_groups"
      :disable-filter="disableFilter"
      :filter-type="view.filter_type"
      :fields="fields"
      :view="view"
      :is-public-view="isPublicView"
      :read-only="readOnly"
      :add-condition-string="$t('viewFilterContext.addFilter')"
      :add-condition-group-string="$t('viewFilterContext.addFilterGroup')"
      scrollable
      class="filters__items--with-padding"
      @add-filter="addFilter($event)"
      @add-filter-group="addFilter($event)"
      @delete-filter="deleteFilter($event)"
      @delete-filter-group="deleteFilterGroup($event)"
      @update-filter="updateFilter($event)"
      @update-filter-type="updateFilterType(view, $event)"
    />
    <div v-if="!disableFilter" class="context__footer">
      <ButtonText icon="iconoir-plus" @click.prevent="addFilter()">
        {{ $t('viewFilterContext.addFilter') }}</ButtonText
      >

      <ButtonText
        icon="iconoir-plus"
        @click.prevent="addFilter({ filterGroupId: sortableUid() })"
      >
        {{ $t('viewFilterContext.addFilterGroup') }}</ButtonText
      >

      <div v-if="view.filters.length > 0" class="margin-left-auto">
        <SwitchInput
          small
          :value="view.filters_disabled"
          @input="updateView(view, { filters_disabled: $event })"
          >{{ $t('viewFilterContext.disableAllFilters') }}</SwitchInput
        >
      </div>
    </div>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { ulid } from 'ulid'
import ViewFieldConditionsForm from '@baserow/modules/database/components/view/ViewFieldConditionsForm'
import { hasCompatibleFilterTypes } from '@baserow/modules/database/utils/field'
import viewFilterTypes from '@baserow/modules/database/mixins/viewFilterTypes'

export default {
  name: 'ViewFilterForm',
  components: {
    ViewFieldConditionsForm,
  },
  mixins: [viewFilterTypes],
  props: {
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
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
    disableFilter: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['changed'],
  methods: {
    sortableUid: ulid,
    async addFilter({ filterGroupId = null, parentGroupId = null } = {}) {
      try {
        const field = this.getFirstCompatibleField(this.fields)
        if (field === undefined) {
          await this.$store.dispatch('toast/error', {
            title: this.$t(
              'viewFilterContext.noCompatibleFilterTypesErrorTitle'
            ),
            message: this.$t(
              'viewFilterContext.noCompatibleFilterTypesErrorMessage'
            ),
          })
        } else {
          await this.$store.dispatch('view/createFilter', {
            field,
            view: this.view,
            values: {
              field: field.id,
            },
            emitEvent: false,
            readOnly: this.readOnly,
            filterGroupId,
            parentGroupId,
          })
          this.$emit('changed')
        }
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    getFirstCompatibleField(fields) {
      return fields
        .slice()
        .sort((a, b) => b.primary - a.primary)
        .find((field) => hasCompatibleFilterTypes(field, this.filterTypes))
    },
    async deleteFilter(filter) {
      try {
        await this.$store.dispatch('view/deleteFilter', {
          view: this.view,
          filter,
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async deleteFilterGroup({ group }) {
      try {
        await this.$store.dispatch('view/deleteFilterGroup', {
          view: this.view,
          filterGroup: group,
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    /**
     * Updates a filter with the given values. Some data manipulation will also be done
     * because some filter types are not compatible with certain field types.
     */
    async updateFilter({ filter, values }) {
      try {
        await this.$store.dispatch('view/updateFilter', {
          filter,
          values,
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    /**
     * Updates the view filter type. It will mark the view as loading because that
     * will also trigger the loading state of the second filter.
     */
    async updateView(view, values) {
      this.$store.dispatch('view/setItemLoading', { view, value: true })

      try {
        await this.$store.dispatch('view/update', {
          view,
          values,
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }

      this.$store.dispatch('view/setItemLoading', { view, value: false })
    },
    async updateFilterType(view, { filterGroup, value }) {
      if (filterGroup === undefined) {
        return await this.updateView(view, { filter_type: value })
      }

      this.$store.dispatch('view/setItemLoading', { view, value: true })
      try {
        await this.$store.dispatch('view/updateFilterGroup', {
          filterGroup,
          values: { filter_type: value },
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }
      this.$store.dispatch('view/setItemLoading', { view, value: false })
    },
  },
}
</script>
