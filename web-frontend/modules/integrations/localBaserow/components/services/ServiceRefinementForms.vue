<template>
  <div>
    <!-- Small screen: Buttons + Contexts -->
    <div v-if="small" class="service-form__filter-buttons">
      <span class="service-form__filter-title">{{
        $t('serviceRefinementForms.refinements')
      }}</span>
      <!-- Group Button -->
      <a
        v-if="showGroup"
        ref="groupContextLink"
        class="header__filter-link"
        :class="{
          'active active--success': hasActiveGroups,
        }"
        @click="openContextWithContent('group', $refs.groupContextLink)"
      >
        <i class="header__filter-icon iconoir-group"></i>
        <span class="header__filter-name">{{
          $t(
            'serviceRefinementForms.groupTabTitle',
            {
              count: groupCount,
            },
            groupCount
          )
        }}</span>
      </a>

      <!-- Filter Button -->
      <a
        v-if="showFilter"
        ref="filterContextLink"
        class="header__filter-link"
        :class="{
          'active active--success': hasActiveFilters,
        }"
        @click="openContextWithContent('filter', $refs.filterContextLink)"
      >
        <i class="header__filter-icon iconoir-filter"></i>
        <span class="header__filter-name">{{
          $t(
            'serviceRefinementForms.filterTabTitle',
            {
              count: filterCount,
            },
            filterCount
          )
        }}</span>
      </a>

      <!-- Sort Button -->
      <a
        v-if="showSort"
        ref="sortContextLink"
        class="header__filter-link"
        :class="{
          'active active--success': hasActiveSorts,
        }"
        @click="openContextWithContent('sort', $refs.sortContextLink)"
      >
        <i class="header__filter-icon iconoir-sort"></i>
        <span class="header__filter-name">{{
          $t(
            'serviceRefinementForms.sortTabTitle',
            {
              count: sortCount,
            },
            sortCount
          )
        }}</span>
      </a>

      <!-- Search Button -->
      <a
        v-if="showSearch"
        ref="searchContextLink"
        class="header__filter-link"
        :class="{
          'active active--success': hasActiveSearch,
        }"
        @click="openContextWithContent('search', $refs.searchContextLink)"
      >
        <i class="header__filter-icon iconoir-search"></i>
        <span class="header__filter-name">{{
          $t('serviceRefinementForms.searchTabTitle', {
            count: hasActiveSearch ? 1 : 0,
          })
        }}</span>
      </a>

      <!-- Additional Content Slot -->
      <slot name="additional-buttons"></slot>

      <!-- Filter Context -->
      <Context
        v-if="showFilter"
        ref="filterContext"
        class="service-form__context service-form__context--filter"
        overflow-scroll
        max-height-if-outside-viewport
      >
        <div class="service-form__context-content">
          <span class="service-form__context-title">
            {{ $t('serviceRefinementForms.filterTabTitle', { count: 0 }) }}
          </span>
          <LocalBaserowTableServiceConditionalForm
            v-if="values.table_id"
            v-model="values.filters"
            v-model:filter-groups="values.filter_groups"
            v-model:filter-type="values.filter_type"
            :fields="tableFields"
          />
          <p v-if="!values.table_id">
            {{ $t('serviceRefinementForms.noTableChosenForFiltering') }}
          </p>
        </div>
      </Context>

      <!-- Group Context -->
      <Context
        v-if="showGroup"
        ref="groupContext"
        class="service-form__context service-form__context--group"
        overflow-scroll
        max-height-if-outside-viewport
      >
        <div class="service-form__context-content">
          <span class="service-form__context-title">
            {{ $t('serviceRefinementForms.groupTabTitle', { count: 0 }) }}
          </span>
          <slot name="group-form"></slot>
          <p v-if="!values.table_id">
            {{ $t('serviceRefinementForms.noTableChosenForGrouping') }}
          </p>
        </div>
      </Context>

      <!-- Sort Context -->
      <Context
        v-if="showSort"
        ref="sortContext"
        class="service-form__context service-form__context--sort"
        overflow-scroll
        max-height-if-outside-viewport
      >
        <div class="service-form__context-content">
          <span class="service-form__context-title">
            {{ $t('serviceRefinementForms.sortTabTitle', { count: 0 }) }}
          </span>
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
        </div>
      </Context>

      <!-- Search Context -->
      <Context
        v-if="showSearch"
        ref="searchContext"
        class="service-form__context service-form__context--search"
        overflow-scroll
        max-height-if-outside-viewport
      >
        <div class="service-form__context-content">
          <span class="service-form__context-title">
            {{ $t('serviceRefinementForms.searchTabTitle', { count: 0 }) }}
          </span>
          <InjectedFormulaInput
            v-model="values.search_query"
            small
            :placeholder="$t('serviceRefinementForms.searchFieldPlaceHolder')"
          />
        </div>
      </Context>
    </div>

    <!-- Large screen: Tabs -->
    <div v-if="!small" class="row">
      <div class="col col-12">
        <Tabs>
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
import Context from '@baserow/modules/core/components/Context'
import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import LocalBaserowTableServiceSortForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceSortForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import Tabs from '@baserow/modules/core/components/Tabs'
import Tab from '@baserow/modules/core/components/Tab'
import FormGroup from '@baserow/modules/core/components/FormGroup'

export default {
  name: 'ServiceRefinementForms',
  components: {
    Context,
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
  },
  computed: {
    filterCount() {
      return this.values.filters ? this.values.filters.length : 0
    },
    sortCount() {
      if (this.sortCountOverride !== null) {
        return this.sortCountOverride
      }
      return this.values.sortings ? this.values.sortings.length : 0
    },
    groupCount() {
      if (this.groupCountOverride !== null) {
        return this.groupCountOverride
      }
      return this.values.group_bys ? this.values.group_bys.length : 0
    },
    hasActiveFilters() {
      return this.values.filters && this.values.filters.length > 0
    },
    hasActiveSorts() {
      return this.sortCount > 0
    },
    hasActiveGroups() {
      return this.groupCount > 0
    },
    hasActiveSearch() {
      return (
        this.values.search_query &&
        this.values.search_query.formula.trim().length > 0
      )
    },
  },
  methods: {
    getContextHorizontalOffset(contentType) {
      // Calculate horizontal offset based on context width
      switch (contentType) {
        case 'search':
          return -400
        case 'filter':
          return -660
        case 'sort':
          return -660
        case 'group':
          return -660
        default:
          return 0
      }
    },
    openContextWithContent(contentType, targetElement) {
      const contextRef = `${contentType}Context`
      const horizontalOffset = this.getContextHorizontalOffset(contentType)
      this.$refs[contextRef].toggle(
        targetElement,
        'bottom',
        'left',
        -32,
        horizontalOffset - 30
      )
    },
  },
}
</script>
