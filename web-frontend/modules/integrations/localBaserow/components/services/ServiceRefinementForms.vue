<template>
  <div>
    <!-- Small screen: Chips + popovers -->
    <div v-if="small" class="service-form__filter-buttons">
      <span class="service-form__filter-title">{{
        $t('serviceRefinementForms.refinements')
      }}</span>
      <div class="service-form__refinement-chips">
        <RefinementPopover
          v-if="showGroup"
          icon="iconoir-group"
          :label="groupTitle"
          :title="$t('serviceRefinementForms.groupPopoverTitle')"
          :active="hasActiveGroups"
          context-class="service-form__context--group"
          :width="320"
        >
          <slot name="group-form"></slot>
          <p v-if="!values.table_id">
            {{ $t('serviceRefinementForms.noTableChosenForGrouping') }}
          </p>
        </RefinementPopover>

        <RefinementPopover
          v-if="showFilter"
          icon="iconoir-filter"
          :label="$t('serviceRefinementForms.filterTabTitle', { count: 0 })"
          :title="$t('serviceRefinementForms.filterPopoverTitle')"
          :description="$t('serviceRefinementForms.filterPopoverDescription')"
          :count="hasActiveFilters ? filterCount : null"
          :active="hasActiveFilters"
          context-class="service-form__context--filter"
          :width="460"
        >
          <div v-if="!hasAnyFilters" class="service-form__popover-empty">
            <span class="service-form__popover-empty-icon">
              <i class="iconoir-filter"></i>
            </span>
            <div class="service-form__popover-empty-title">
              {{ $t('serviceRefinementForms.noFiltersTitle') }}
            </div>
            <div class="service-form__popover-empty-description">
              {{
                values.table_id
                  ? $t('serviceRefinementForms.noFiltersDescription')
                  : $t('serviceRefinementForms.noTableChosenForFiltering')
              }}
            </div>
          </div>
          <LocalBaserowTableServiceConditionalForm
            v-if="values.table_id"
            v-model="values.filters"
            v-model:filter-groups="values.filter_groups"
            v-model:filter-type="values.filter_type"
            :fields="tableFields"
            :show-empty-state="false"
          >
            <!-- Above the add buttons, so they stay the popover's footer. -->
            <template #before-footer>
              <slot name="after-filter-form" />
            </template>
          </LocalBaserowTableServiceConditionalForm>
        </RefinementPopover>

        <RefinementPopover
          v-if="showSort"
          icon="iconoir-sort"
          :label="$t('serviceRefinementForms.sortTabTitle', { count: 0 })"
          :title="$t('serviceRefinementForms.sortPopoverTitle')"
          :description="$t('serviceRefinementForms.sortPopoverDescription')"
          :count="hasActiveSorts ? sortCount : null"
          :active="hasActiveSorts"
          context-class="service-form__context--sort"
          :width="360"
        >
          <!-- A caller's own sort form, like a chart's, has its own empty choice. -->
          <div
            v-if="!hasActiveSorts && !$slots['sort-form']"
            class="service-form__popover-empty"
          >
            <span class="service-form__popover-empty-icon">
              <i class="iconoir-sort"></i>
            </span>
            <div class="service-form__popover-empty-title">
              {{ $t('serviceRefinementForms.noSortsTitle') }}
            </div>
            <div class="service-form__popover-empty-description">
              {{
                values.table_id
                  ? $t('serviceRefinementForms.noSortsDescription')
                  : $t('serviceRefinementForms.noTableChosenForSorting')
              }}
            </div>
          </div>
          <slot name="sort-form">
            <LocalBaserowTableServiceSortForm
              v-if="values.table_id"
              v-model="values.sortings"
              :fields="tableFields"
              :show-empty-state="false"
            />
          </slot>
        </RefinementPopover>

        <RefinementPopover
          v-if="showSearch"
          icon="iconoir-search"
          :label="$t('serviceRefinementForms.searchTabTitle', { count: 0 })"
          :title="$t('serviceRefinementForms.searchPopoverTitle')"
          :description="$t('serviceRefinementForms.searchPopoverDescription')"
          :count="hasActiveSearch ? 1 : null"
          :active="hasActiveSearch"
          context-class="service-form__context--search"
          :width="360"
        >
          <InjectedFormulaInput
            v-model="values.search_query"
            small
            :placeholder="$t('serviceRefinementForms.searchFieldPlaceHolder')"
          />
        </RefinementPopover>
      </div>

      <!-- Additional Content Slot -->
      <slot name="additional-buttons"></slot>
    </div>

    <!-- Large screen: Tabs -->
    <div v-if="!small" class="row">
      <div class="col col-12">
        <Tabs>
          <slot name="leading-tabs"></slot>
          <Tab
            v-if="showGroup"
            :title="$t('serviceRefinementForms.groupTabTitle', { count: 0 })"
            class="service-form__group-form-tab"
          >
            <slot name="group-form"></slot>
            <p v-if="!values.table_id">
              {{ $t('serviceRefinementForms.noTableChosenForGrouping') }}
            </p>
          </Tab>
          <Tab
            v-if="showFilter"
            :title="$t('serviceRefinementForms.filterTabTitle', { count: 0 })"
            class="service-form__condition-form-tab"
          >
            <LocalBaserowTableServiceConditionalForm
              v-if="values.table_id"
              v-model="values.filters"
              v-model:filter-groups="values.filter_groups"
              v-model:filter-type="values.filter_type"
              :fields="tableFields"
            />
            <slot v-if="values.table_id" name="after-filter-form" />
            <p v-if="!values.table_id">
              {{ $t('serviceRefinementForms.noTableChosenForFiltering') }}
            </p>
          </Tab>
          <Tab
            v-if="showSort"
            :title="$t('serviceRefinementForms.sortTabTitle', { count: 0 })"
            class="service-form__sort-form-tab"
          >
            <slot name="sort-form">
              <LocalBaserowTableServiceSortForm
                v-if="values.table_id"
                v-model="values.sortings"
                :fields="tableFields"
              />
            </slot>
            <p v-if="!values.table_id">
              {{ $t('serviceRefinementForms.noTableChosenForSorting') }}
            </p>
          </Tab>
          <Tab
            v-if="showSearch"
            :title="$t('serviceRefinementForms.searchTabTitle', { count: 0 })"
            class="service-form__search-form-tab"
          >
            <FormGroup>
              <InjectedFormulaInput
                v-model="values.search_query"
                :placeholder="
                  $t('serviceRefinementForms.searchFieldPlaceHolder')
                "
              />
            </FormGroup>
          </Tab>
          <!-- Additional Tab Content Slot -->
          <slot name="additional-tabs"></slot>
        </Tabs>
      </div>
    </div>
  </div>
</template>

<script>
import RefinementPopover from '@baserow/modules/integrations/localBaserow/components/services/RefinementPopover'
import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import LocalBaserowTableServiceSortForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceSortForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import Tabs from '@baserow/modules/core/components/Tabs'
import Tab from '@baserow/modules/core/components/Tab'
import FormGroup from '@baserow/modules/core/components/FormGroup'

export default {
  name: 'ServiceRefinementForms',
  components: {
    RefinementPopover,
    LocalBaserowTableServiceConditionalForm,
    LocalBaserowTableServiceSortForm,
    InjectedFormulaInput,
    Tabs,
    Tab,
    FormGroup,
  },
  props: {
    values: {
      type: Object,
      required: true,
    },
    tableFields: {
      type: Array,
      required: true,
    },
    small: {
      type: Boolean,
      required: true,
    },
    showFilter: {
      type: Boolean,
      default: false,
    },
    showSort: {
      type: Boolean,
      default: false,
    },
    showGroup: {
      type: Boolean,
      default: false,
    },
    showSearch: {
      type: Boolean,
      default: false,
    },
    filterCountOverride: {
      type: Number,
      required: false,
      default: null,
    },
    sortCountOverride: {
      type: Number,
      required: false,
      default: null,
    },
    groupCountOverride: {
      type: Number,
      required: false,
      default: null,
    },
    groupTitleOverride: {
      type: String,
      required: false,
      default: null,
    },
  },
  computed: {
    filterCount() {
      if (this.filterCountOverride !== null) {
        return this.filterCountOverride
      }
      return this.values.filters ? this.values.filters.length : 0
    },
    sortCount() {
      if (this.sortCountOverride !== null) {
        return this.sortCountOverride
      }
      return this.values.sortings ? this.values.sortings.length : 0
    },
    groupTitle() {
      if (this.groupTitleOverride !== null) {
        return this.groupTitleOverride
      }
      return this.$t(
        'serviceRefinementForms.groupTabTitle',
        { count: this.groupCount },
        this.groupCount
      )
    },
    groupCount() {
      if (this.groupCountOverride !== null) {
        return this.groupCountOverride
      }
      return this.values.group_bys ? this.values.group_bys.length : 0
    },
    hasActiveFilters() {
      return this.filterCount > 0
    },
    hasActiveSorts() {
      return this.sortCount > 0
    },
    hasActiveGroups() {
      return this.groupCount > 0
    },
    hasAnyFilters() {
      return (
        this.filterCount > 0 || (this.values.filter_groups?.length ?? 0) > 0
      )
    },
    hasActiveSearch() {
      return (
        this.values.search_query &&
        this.values.search_query.formula.trim().length > 0
      )
    },
  },
}
</script>
