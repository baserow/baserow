<template>
  <form @submit.prevent>
    <FormGroup
      small-label
      :label="$t('coreHTTPRequestServiceForm.httpMethod')"
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.http_method">
        <DropdownItem
          v-for="method in methods"
          :key="method.value"
          :name="method.name"
          :value="method.value"
        >
        </DropdownItem>
      </Dropdown>
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('coreHTTPRequestServiceForm.url')"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.url"
        :placeholder="$t('coreHTTPRequestServiceForm.urlPlaceholder')"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('coreHTTPRequestServiceForm.queryParams')"
      required
      class="margin-bottom-2"
    >
      <HTTPKeyValueList
        v-model="values.query_params"
        key-prefix="param"
        :add-label="$t('coreHTTPRequestServiceForm.addQueryParam')"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('coreHTTPRequestServiceForm.headers')"
      required
      class="margin-bottom-2"
    >
      <HTTPKeyValueList
        v-model="values.headers"
        key-prefix="header"
        :add-label="$t('coreHTTPRequestServiceForm.addHeader')"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('coreHTTPRequestServiceForm.bodyType')"
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.body_type">
        <DropdownItem
          v-for="body_type in body_types"
          :key="body_type.value"
          :name="body_type.name"
          :value="body_type.value"
        >
        </DropdownItem>
      </Dropdown>
    </FormGroup>
    <FormGroup
      v-if="['json', 'raw'].includes(values.body_type)"
      class="margin-bottom-2"
      :label="$t('coreHTTPRequestServiceForm.bodyContent')"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.body_content"
        :placeholder="$t('coreHTTPRequestServiceForm.bodyPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      v-if="['form'].includes(values.body_type)"
      class="margin-bottom-2"
      :label="$t('coreHTTPRequestServiceForm.formData')"
      required
      small-label
    >
      <HTTPKeyValueList
        v-model="values.form_data"
        key-prefix="form"
        :add-label="$t('coreHTTPRequestServiceForm.addFormData')"
      />
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      small-label
      :label="$t('coreHTTPRequestServiceForm.timeout')"
      required
      :error-message="getFirstErrorMessage('timeout')"
    >
      <FormInput
        v-model="v$.values.timeout.$model"
        :placeholder="$t('coreHTTPRequestServiceForm.timeoutPlaceholder')"
        :to-value="(value) => parseInt(value)"
        type="number"
      >
        <template #suffix>{{
          $t('coreHTTPRequestServiceForm.seconds')
        }}</template>
      </FormInput>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import HTTPKeyValueList from '@baserow/modules/integrations/core/components/services/HTTPKeyValueList'
import { useVuelidate } from '@vuelidate/core'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'

export default {
  name: 'CoreHTTPRequestService',
  components: { InjectedFormulaInput, HTTPKeyValueList },
  mixins: [form],
  props: {},
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'url',
        'http_method',
        'timeout',
        'body_type',
        'body_content',
        'query_params',
        'headers',
        'form_data',
      ],
      values: {
        url: {},
        http_method: 'GET',
        timeout: 60,
        body_type: 'none',
        body_content: {},
        query_params: [],
        headers: [],
        form_data: [],
      },
    }
  },
  computed: {
    methods() {
      return [
        { name: 'GET', value: 'GET' },
        { name: 'POST', value: 'POST' },
        { name: 'PUT', value: 'PUT' },
        { name: 'DELETE', value: 'DELETE' },
        { name: 'PATCH', value: 'PATCH' },
        { name: 'HEAD', value: 'HEAD' },
        { name: 'OPTIONS', value: 'OPTIONS' },
      ]
    },
    body_types() {
      return [
        { name: 'None', value: 'none' },
        { name: 'JSON', value: 'json' },
        { name: 'Form multipart', value: 'form' },
        { name: 'Raw', value: 'raw' },
      ]
    },
  },
  validations() {
    return {
      values: {
        timeout: {
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 120 }),
            maxValue(120)
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
