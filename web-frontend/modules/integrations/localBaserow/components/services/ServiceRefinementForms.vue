<template>
  <div>
    <!-- Small screen: Buttons + Contexts -->
    <div v-if="small" class="service-form__filter-buttons">
      <span class="service-form__filter-title">{{
        $t('serviceRefinementForms.refinements')
      }}</span>
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
          $tc('serviceRefinementForms.filterTabTitle', filterCount, {
            count: filterCount,
          })
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
          $tc('serviceRefinementForms.sortTabTitle', sortCount, {
            count: sortCount,
          })
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
          $tc(
            'serviceRefinementForms.searchTabTitle',
            hasActiveSearch ? 1 : 0,
            { count: 1 }
          )
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
            {{ $tc('serviceRefinementForms.filterTabTitle', 0, { count: 0 }) }}
          </span>
          <LocalBaserowTableServiceConditionalForm
            v-if="values.table_id"
            v-model="values.filters"
            :fields="tableFields"
            :filter-type.sync="values.filter_type"
          />
          <p v-if="!values.table_id">
            {{ $t('serviceRefinementForms.noTableChosenForFiltering') }}
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
            {{ $tc('serviceRefinementForms.sortTabTitle', 0, { count: 0 }) }}
          </span>
          <LocalBaserowTableServiceSortForm
            v-if="values.table_id"
            v-model="values.sortings"
            :fields="tableFields"
          />
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
            {{ $tc('serviceRefinementForms.searchTabTitle', 0, { count: 0 }) }}
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
            v-if="showFilter"
            :title="
              $tc('serviceRefinementForms.filterTabTitle', 0, { count: 0 })
            "
            class="service-form__condition-form-tab"
          >
            <LocalBaserowTableServiceConditionalForm
              v-if="values.table_id"
              v-model="values.filters"
              :fields="tableFields"
              :filter-type.sync="values.filter_type"
            />
            <p v-if="!values.table_id">
              {{ $t('serviceRefinementForms.noTableChosenForFiltering') }}
            </p>
          </Tab>
          <Tab
            v-if="showSort"
            :title="$tc('serviceRefinementForms.sortTabTitle', 0, { count: 0 })"
            class="service-form__sort-form-tab"
          >
            <LocalBaserowTableServiceSortForm
              v-if="values.table_id"
              v-model="values.sortings"
              :fields="tableFields"
            />
            <p v-if="!values.table_id">
              {{ $t('serviceRefinementForms.noTableChosenForSorting') }}
            </p>
          </Tab>
          <Tab
            v-if="showSearch"
            :title="
              $tc('serviceRefinementForms.searchTabTitle', 0, { count: 0 })
            "
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
    showSearch: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    filterCount() {
      return this.values.filters ? this.values.filters.length : 0
    },
    sortCount() {
      return this.values.sortings ? this.values.sortings.length : 0
    },
    hasActiveFilters() {
      return this.values.filters && this.values.filters.length > 0
    },
    hasActiveSorts() {
      return this.values.sortings && this.values.sortings.length > 0
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
