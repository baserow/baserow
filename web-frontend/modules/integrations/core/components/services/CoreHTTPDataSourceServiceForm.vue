<template>
  <form class="http-data-source-form" @submit.prevent>
    <FormGroup
      :label="$t('coreHTTPRequestServiceForm.url')"
      required
      small-label
    >
      <div class="http-data-source-form__request">
        <span class="http-data-source-form__method">GET</span>
        <InjectedFormulaInput
          v-model="values.url"
          class="http-data-source-form__url"
          :placeholder="$t('coreHTTPRequestServiceForm.urlPlaceholder')"
        />
        <Button
          v-if="dataSourceTest"
          icon="iconoir-play"
          class="http-data-source-form__test"
          :loading="dataSourceTest.isLoading"
          :disabled="dataSourceTest.isLoading"
          @click="dataSourceTest.test()"
        >
          {{ $t('coreHTTPDataSourceServiceForm.test') }}
        </Button>
      </div>
    </FormGroup>

    <Tabs
      v-model:selected-index="selectedTab"
      header-no-padding
      content-no-x-padding
    >
      <Tab
        :title="$t('coreHTTPRequestServiceForm.queryParams')"
        :badge="`${values.query_params.length}`"
        :append-icon="tabErrorIcon(TABS.QUERY_PARAMS)"
      >
        <HTTPKeyValueList
          v-model="values.query_params"
          key-prefix="param"
          :add-label="$t('coreHTTPRequestServiceForm.addQueryParam')"
        />
        <p class="http-data-source-form__help">
          {{ $t('coreHTTPDataSourceServiceForm.queryParamsHelp') }}
        </p>
      </Tab>
      <Tab
        :title="$t('coreHTTPRequestServiceForm.headers')"
        :badge="`${values.headers.length}`"
        :append-icon="tabErrorIcon(TABS.HEADERS)"
      >
        <HTTPKeyValueList
          v-model="values.headers"
          key-prefix="header"
          :add-label="$t('coreHTTPRequestServiceForm.addHeader')"
        />
        <p class="http-data-source-form__help">
          {{ $t('coreHTTPDataSourceServiceForm.headersHelp') }}
        </p>
      </Tab>
      <Tab
        :title="$t('coreHTTPDataSourceServiceForm.response')"
        :badge="
          returnsList
            ? $t('coreHTTPDataSourceServiceForm.aList')
            : $t('coreHTTPDataSourceServiceForm.oneRecord')
        "
      >
        <template v-if="response !== undefined">
          <p
            class="http-data-source-form__help http-data-source-form__help--above"
          >
            {{ $t('coreHTTPDataSourceServiceForm.responseHelp') }}
          </p>
          <HTTPResponsePicker
            :response="response"
            :returns-list="returnsList"
            :list-path="values.list_path"
            @select="selectRecords"
          />
        </template>
        <template v-else>
          <p
            class="http-data-source-form__help http-data-source-form__help--above"
          >
            {{ $t('coreHTTPDataSourceServiceForm.testToChoose') }}
          </p>
          <div class="http-data-source-form__shapes">
            <RadioCard
              v-for="shape in shapes"
              :key="shape.value"
              :value="shape.value"
              :model-value="returnsList"
              :label="shape.label"
              @update:model-value="returnsList = $event"
            >
              {{ shape.description }}
            </RadioCard>
          </div>
          <FormGroup
            v-if="returnsList"
            class="margin-top-2"
            small-label
            :label="$t('coreHTTPDataSourceServiceForm.listPath')"
            :helper-text="$t('coreHTTPDataSourceServiceForm.listPathHelper')"
          >
            <FormInput
              v-model="values.list_path"
              :placeholder="
                $t('coreHTTPDataSourceServiceForm.listPathPlaceholder')
              "
            />
          </FormGroup>
        </template>
      </Tab>
      <Tab
        :title="$t('coreHTTPDataSourceServiceForm.settings')"
        :badge="`${values.timeout} s`"
        :append-icon="tabErrorIcon(TABS.SETTINGS)"
      >
        <FormGroup
          small-label
          :label="$t('coreHTTPRequestServiceForm.timeout')"
          :helper-text="
            $t('coreHTTPDataSourceServiceForm.timeoutHelper', {
              max: maxTimeout,
            })
          "
          :error-message="getFirstErrorMessage('timeout')"
        >
          <FormInput
            v-model="v$.values.timeout.$model"
            class="http-data-source-form__timeout"
            :placeholder="$t('coreHTTPRequestServiceForm.timeoutPlaceholder')"
            :to-value="(value) => parseInt(value)"
            type="number"
          >
            <template #suffix>{{
              $t('coreHTTPRequestServiceForm.seconds')
            }}</template>
          </FormInput>
        </FormGroup>
      </Tab>
    </Tabs>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import HTTPKeyValueList from '@baserow/modules/integrations/core/components/services/HTTPKeyValueList'
import HTTPResponsePicker from '@baserow/modules/integrations/core/components/services/HTTPResponsePicker'
import { httpKeyValueRowsRules } from '@baserow/modules/integrations/core/validators'
import { useVuelidate } from '@vuelidate/core'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'
import {
  HTTP_DATA_SOURCE_DEFAULT_TIMEOUT,
  HTTP_DATA_SOURCE_MAX_TIMEOUT,
  HTTP_DATA_SOURCE_TYPE,
} from '@baserow/modules/integrations/core/enums'

// The position of each tab of the form.
const TABS = { QUERY_PARAMS: 0, HEADERS: 1, RESPONSE: 2, SETTINGS: 3 }

/**
 * The form of the HTTP request data source. Choosing whether it returns one
 * record or a list sets `returns_list`.
 */
export default {
  name: 'CoreHTTPDataSourceServiceForm',
  components: { InjectedFormulaInput, HTTPKeyValueList, HTTPResponsePicker },
  mixins: [form],
  inject: {
    // Provided by the data source form, to test from the request bar.
    dataSourceTest: { default: null },
  },
  props: {
    service: {
      type: Object,
      required: false,
      default: null,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'returns_list',
        'url',
        'query_params',
        'headers',
        'timeout',
        'list_path',
      ],
      values: {
        returns_list: false,
        url: {},
        query_params: [],
        headers: [],
        timeout: HTTP_DATA_SOURCE_DEFAULT_TIMEOUT,
        list_path: '',
      },
      maxTimeout: HTTP_DATA_SOURCE_MAX_TIMEOUT,
      TABS,
      selectedTab: TABS.QUERY_PARAMS,
      // The response of the last test. Kept when the sample data is emptied,
      // like when the list isn't at the new list path, until it's tested again.
      response: undefined,
    }
  },
  computed: {
    /**
     * The tabs holding a value which isn't valid. A tab only shows what it holds
     * while it's open, so the rules are the form's own rather than its fields'.
     */
    invalidTabs() {
      const fields = {
        [TABS.QUERY_PARAMS]: 'query_params',
        [TABS.HEADERS]: 'headers',
        [TABS.SETTINGS]: 'timeout',
      }
      return Object.entries(fields)
        .filter(([, field]) => this.v$.values[field].$invalid)
        .map(([tab]) => parseInt(tab))
    },
    sampleResponse() {
      // The service is the saved one, which isn't an HTTP request yet while
      // another type of data source is being switched to it.
      if (this.service?.type !== HTTP_DATA_SOURCE_TYPE) {
        return undefined
      }
      return this.$registry
        .get('service', this.service.type)
        .getSampleResponse(this.service)
    },
    returnsList: {
      get() {
        return this.values.returns_list
      },
      set(value) {
        this.values.returns_list = value
      },
    },
    shapes() {
      return [
        {
          value: false,
          label: this.$t('coreHTTPDataSourceServiceForm.oneRecord'),
          description: this.$t(
            'coreHTTPDataSourceServiceForm.oneRecordDescription'
          ),
        },
        {
          value: true,
          label: this.$t('coreHTTPDataSourceServiceForm.listOfRecords'),
          description: this.$t(
            'coreHTTPDataSourceServiceForm.listOfRecordsDescription'
          ),
        },
      ]
    },
  },
  watch: {
    sampleResponse: {
      handler(value) {
        if (value !== undefined) {
          this.response = value
        }
      },
      immediate: true,
    },
  },
  methods: {
    tabErrorIcon(tab) {
      return this.invalidTabs.includes(tab)
        ? 'iconoir-warning-circle color-error'
        : null
    },
    /**
     * Touching the form shows its errors, so a value which isn't valid in
     * another tab than the open one is shown by opening its tab.
     */
    touch(deep = false) {
      form.methods.touch.call(this, deep)
      if (
        this.invalidTabs.length &&
        !this.invalidTabs.includes(this.selectedTab)
      ) {
        this.selectedTab = this.invalidTabs[0]
      }
    },
    selectRecords({ returnsList, listPath }) {
      this.returnsList = returnsList
      if (returnsList) {
        this.values.list_path = listPath
      }
    },
    /**
     * A single record data source has no list path, so it isn't sent: it would
     * otherwise count as a change to the data source.
     */
    withoutUnusedValues(values) {
      if (this.returnsList) {
        return values
      }
      const { list_path: listPath, ...usedValues } = values
      return usedValues
    },
    getFormValues(deep = false) {
      return this.withoutUnusedValues(
        form.methods.getFormValues.call(this, deep)
      )
    },
    emitChange(newValues) {
      form.methods.emitChange.call(this, this.withoutUnusedValues(newValues))
    },
  },
  validations() {
    const t = (...args) => this.$t(...args)
    return {
      values: {
        query_params: httpKeyValueRowsRules(t),
        headers: httpKeyValueRowsRules(t),
        timeout: {
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', {
              max: HTTP_DATA_SOURCE_MAX_TIMEOUT,
            }),
            maxValue(HTTP_DATA_SOURCE_MAX_TIMEOUT)
          ),
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
        },
      },
    }
  },
}
</script>
