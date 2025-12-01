<template>
  <ABFormGroup
    :label="resolvedLabel"
    :required="element.required"
    :error-message="getErrorMessage()"
    :style="getStyleOverride('input')"
  >
    <ABDropdown
      ref="recordSelectorDropdown"
      v-model="inputValue"
      :show-search="adhocSearchEnabled"
      :emit-search="adhocSearchEnabled"
      class="choice-element"
      :placeholder="resolvedPlaceholder"
      :multiple="element.multiple"
      :before-show="beforeShow"
      @hide="onFormElementTouch"
      @query-change="adhocSearch = $event"
      @scroll="$refs.infiniteScroll.handleScroll($event)"
    >
      <template #value>
        <template v-if="loading">
          <div class="loading" />
        </template>
        <span class="ab-dropdown__selected-text">
          {{ selectedValueDisplay }}
        </span>
      </template>
      <template #emptyState>
        {{
          adhocSearchEnabled
            ? $t('recordSelectorElement.emptyAdhocState', {
                query: adhocSearch,
              })
            : $t('recordSelectorElement.emptyState')
        }}
      </template>
      <template #defaultValue>
        <template v-if="loading">
          <div class="loading" />
        </template>
        <span class="ab-dropdown__selected-placeholder">{{
          resolvedPlaceholder ? resolvedPlaceholder : $t('action.makeChoice')
        }}</span>
      </template>
      <InfiniteScroll
        ref="infiniteScroll"
        :current-count="currentOffset"
        :has-more-page="hasMorePage"
        :loading="loading"
        :reverse="false"
        :render-end="false"
        @load-next-page="nextPage"
      >
        <template #default>
          <ABDropdownItem
            v-for="{ value, name, nameSuffix } in resolvedOptions"
            :key="value"
            :name="`${name}${nameSuffix ? ` - ${nameSuffix}` : ''}`"
            :value="value"
          />
        </template>
      </InfiniteScroll>
    </ABDropdown>
  </ABFormGroup>
</template>

<script>
import _ from 'lodash'
import { ensureString } from '@baserow/modules/core/utils/validator'
import formElement from '@baserow/modules/builder/mixins/formElement'
import collectionElement from '@baserow/modules/builder/mixins/collectionElement'
import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll.vue'
import DataSourceService from '@baserow/modules/builder/services/dataSource'
import { handleDispatchError } from '@baserow/modules/builder/utils/error'

export default {
  name: 'RecordSelectorElement',
  components: { InfiniteScroll },
  mixins: [formElement, collectionElement],
  props: {
    /**
     * @type {Object}
     * @property {boolean} required - If the element is required for form submission
     * @property {string} data_source_id - The data source for the record selector element
     * @propeRty {number} items_per_page - Number of items to show per page
     * @property {string} label - The label displayed above the record selector element
     * @property {string} default_value - The formula to generate the displayed name
     * @property {string} placeholder - The placeholder text which should be applied to the element
     * @property {boolean} multiple - Whether this element can hold multiple values
     * @property {string} option_name_suffix - The formula to generate the displayed suffix name
     */
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      openedOnce: false,
      defaultValueOptions: [],
      shouldDebounce: false,
      debounceTimeout: null,
    }
  },
  computed: {
    adhocSearchEnabled() {
      return (
        this.elementType.adhocSearchableProperties(
          this.element,
          this.dataSource
        ).length > 0
      )
    },
    resolvedLabel() {
      return ensureString(this.resolveFormula(this.element.label))
    },
    resolvedPlaceholder() {
      return ensureString(this.resolveFormula(this.element.placeholder))
    },
    /**
     * These fallback options are here to maintain reactivity of the dropdown component
     * that can detect DOM changes. As we have always at least fallback for missing
     * rows we can see the default value.
     */
    fallbackOptions() {
      let recordIds = this.resolvedDefaultValue

      if (!this.element.multiple) {
        if (this.resolvedDefaultValue !== null) {
          recordIds = [this.resolvedDefaultValue]
        } else {
          recordIds = []
        }
      }

      return recordIds.map((id) => ({
        value: id,
        name: this.$t('recordSelectorElementForm.record', { id }),
        nameSuffix: '',
      }))
    },
    resolvedOptions() {
      // Fill the dropdown options with an array containing
      // the record id and name from the resolved formula
      const options = this.elementContent.map((record, recordIndex) => ({
        value: record?.id,
        nameSuffix: ensureString(
          this.resolveFormula(
            this.element.option_name_suffix,
            // Formula context to resolve `current record` to the current index
            new Proxy(
              new RuntimeFormulaContext(
                this.$registry.getAll('builderDataProvider'),
                {
                  ...this.applicationContext,
                  // We don't want the full recordIndex path here as we always want a
                  // data source as source for this component and we don't want nested
                  // data selection.
                  recordIndexPath: [recordIndex],
                  allowSameElement: true,
                }
              ),
              {
                get(target, prop) {
                  return target.get(prop)
                },
              }
            )
          )
        ),
        name:
          this.dataSourceType.getRecordName(this.dataSource, record || {}) ||
          this.$t('recordSelectorElementForm.record', { id: recordIndex }),
      }))

      // Append the default value options so that they are displayed in the
      // dropdown even if we haven't reached its page yet.
      // When we retrieve the records that are present in the default values,
      // we remove the duplicate ones.
      return _.uniqBy(
        [...options, ...this.defaultValueOptions, ...this.fallbackOptions],
        'value'
      )
    },
    selectedOption() {
      if (this.element.multiple) {
        return this.resolvedOptions.filter((option) =>
          this.inputValue.includes(option.value)
        )
      } else {
        return this.resolvedOptions.find(
          (option) => option.value === this.inputValue
        )
      }
    },
    selectedValueDisplay() {
      if (this.element.multiple) {
        return this.selectedOption.map(({ name }) => name).join(', ')
      } else {
        return this.selectedOption?.name
      }
    },
    elementContent() {
      // elementContent mixin uses applicationContext.recordIndexPath to determine
      // if we are inside a collection element.
      // In this scenario we set recordIndexPath to be empty so that the whole
      // element._.content is returned
      // Also the element content can be shared among all the record selectors in all
      // repetitions, it's even better and it saves queries.
      return this.getElementContent(this.element, {
        ...this.applicationContext,
        recordIndexPath: [],
      })
    },
  },
  watch: {
    resolvedDefaultValue: {
      async handler(newDefaultValue, oldValue) {
        if (!_.isEqual(newDefaultValue, oldValue)) {
          this.inputValue = newDefaultValue
          if (!this.shouldDebounce) {
            await this.updateDefaultRecordNames(newDefaultValue)
            this.shouldDebounce = true
          } else {
            // Debounced update to avoid too many queries
            this.debouncedUpdateDefaultRecordNames(newDefaultValue)
          }
        }
      },
      immediate: true,
    },
    async 'element.data_source_id'() {
      await this.updateDefaultRecordNames(this.resolvedDefaultValue)
    },
    'element.multiple'() {
      this.setFormData(this.resolvedDefaultValue)
    },
  },
  methods: {
    async beforeShow() {
      if (!this.openedOnce) {
        this.openedOnce = true
        this.loading = true
        // Fetch first content on first opening instead of onMount.
        await this.fetchContent([0, this.element.items_per_page])
        this.loading = false
      }
    },
    async nextPage() {
      try {
        this.loading = true
        await this.loadMore()
      } finally {
        this.loading = false
      }
    },
    async updateDefaultRecordNames(recordIdsToFetch) {
      // There is no need to resolve the default value when there is no data source
      if (!this.element.data_source_id) {
        this.defaultValueOptions = []
        return
      }

      let recordIds = recordIdsToFetch
      if (!this.element.multiple) {
        if (recordIdsToFetch !== null) {
          recordIds = [recordIdsToFetch]
        } else {
          recordIds = []
        }
      }

      if (recordIds.length === 0) {
        return
      }

      this.loading = true
      try {
        const data = await DataSourceService(this.$client).getRecordNames(
          this.element.data_source_id,
          recordIds
        )
        this.defaultValueOptions = Object.entries(data).map(
          ([value, name]) => ({
            value: parseInt(value),
            name,
            actualName: name,
          })
        )
      } catch (error) {
        handleDispatchError(
          error,
          this,
          this.$t('builderToast.errorDataSourceDispatch', {
            name: this.dataSource.name,
          })
        )
      } finally {
        this.loading = false
      }
    },
    debouncedUpdateDefaultRecordNames(val) {
      clearTimeout(this.debounceTimeout)
      this.debounceTimeout = setTimeout(() => {
        this.updateDefaultRecordNames(val)
      }, 500)
    },
    canFetch() {
      // We want to fetch data only if the dropdown have been opened at least once.
      // It's not necessary otherwise
      return this.openedOnce && collectionElement.methods.canFetch.call(this)
    },
    getErrorMessage() {
      return this.displayFormDataError ? this.$t('error.requiredField') : ''
    },
  },
}
</script>
