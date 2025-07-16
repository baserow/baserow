<template>
  <div>
    <!-- Small screen: Buttons + Contexts -->
    <div v-if="small" class="service-form__filter-buttons">
      <!-- Filter Button -->
      <a
        v-if="showFilter"
        ref="filterContextLink"
        class="header__filter-link"
        :class="{
          active: hasActiveFilters,
        }"
        @click="openContextWithContent('filter', $refs.filterContextLink)"
      >
        <i class="header__filter-icon iconoir-filter"></i>
        <span class="header__filter-name">{{
          $t('serviceFormRefinements.filterTabTitle')
        }}</span>
        <BadgeCounter
          v-if="filterCount > 0"
          class="margin-left-1"
          :count="filterCount"
        />
      </a>

      <!-- Sort Button -->
      <a
        v-if="showSort"
        ref="sortContextLink"
        class="header__filter-link"
        :class="{
          active: hasActiveSorts,
        }"
        @click="openContextWithContent('sort', $refs.sortContextLink)"
      >
        <i class="header__filter-icon iconoir-sort"></i>
        <span class="header__filter-name">{{
          $t('serviceFormRefinements.sortTabTitle')
        }}</span>
        <BadgeCounter
          v-if="sortCount > 0"
          class="margin-left-1"
          :count="sortCount"
        />
      </a>

      <!-- Search Button -->
      <a
        v-if="showSearch"
        ref="searchContextLink"
        class="header__filter-link"
        :class="{
          active: hasActiveSearch,
        }"
        @click="openContextWithContent('search', $refs.searchContextLink)"
      >
        <i class="header__filter-icon iconoir-search"></i>
        <span class="header__filter-name">{{
          $t('serviceFormRefinements.searchTabTitle')
        }}</span>
        <BadgeCounter v-if="hasActiveSearch" class="margin-left-1" :count="1" />
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
            {{ $t('serviceFormRefinements.filterTabTitle') }}
          </span>
          <LocalBaserowTableServiceConditionalForm
            v-if="values.table_id"
            v-model="values.filters"
            :fields="tableFields"
            :filter-type.sync="values.filter_type"
          />
          <p v-if="!values.table_id">
            {{ $t('serviceFormRefinements.noTableChosenForFiltering') }}
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
            {{ $t('serviceFormRefinements.sortTabTitle') }}
          </span>
          <LocalBaserowTableServiceSortForm
            v-if="values.table_id"
            v-model="values.sortings"
            :fields="tableFields"
          />
          <p v-if="!values.table_id">
            {{ $t('serviceFormRefinements.noTableChosenForSorting') }}
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
            {{ $t('serviceFormRefinements.searchTabTitle') }}
          </span>
          <InjectedFormulaInput
            v-model="values.search_query"
            small
            :placeholder="$t('serviceFormRefinements.searchFieldPlaceHolder')"
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
            :title="$t('serviceFormRefinements.filterTabTitle')"
            class="service-form__condition-form-tab"
          >
            <LocalBaserowTableServiceConditionalForm
              v-if="values.table_id"
              v-model="values.filters"
              :fields="tableFields"
              :filter-type.sync="values.filter_type"
            />
            <p v-if="!values.table_id">
              {{ $t('serviceFormRefinements.noTableChosenForFiltering') }}
            </p>
          </Tab>
          <Tab
            v-if="showSort"
            :title="$t('serviceFormRefinements.sortTabTitle')"
            class="service-form__sort-form-tab"
          >
            <LocalBaserowTableServiceSortForm
              v-if="values.table_id"
              v-model="values.sortings"
              :fields="tableFields"
            />
            <p v-if="!values.table_id">
              {{ $t('serviceFormRefinements.noTableChosenForSorting') }}
            </p>
          </Tab>
          <Tab
            v-if="showSearch"
            :title="$t('serviceFormRefinements.searchTabTitle')"
            class="service-form__search-form-tab"
          >
            <FormGroup>
              <InjectedFormulaInput
                v-model="values.search_query"
                :placeholder="
                  $t('serviceFormRefinements.searchFieldPlaceHolder')
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
import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'

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
    BadgeCounter,
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
        this.values.search_query && this.values.search_query.trim().length > 0
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
          return -656
        case 'sort':
          return -436
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
        horizontalOffset - 20
      )
    },
  },
}
</script>
