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
      <template v-if="v$.values.query_params.$model.length">
        <div class="row" style="--gap: 6px">
          <label class="col col-5 control__label control__label--small">
            {{ $t('coreHTTPRequestServiceForm.name') }}
          </label>
          <label class="col col-7 control__label control__label--small">
            {{ $t('coreHTTPRequestServiceForm.value') }}
          </label>
        </div>
        <div
          v-for="(query_param, index) in v$.values.query_params.$model"
          :key="query_param.id"
          style="--gap: 6px"
          class="row margin-bottom-1"
        >
          <div class="col col-5">
            <FormInput
              v-model="query_param.key"
              :error="!!v$.values.query_params.$each.$message[index]?.[0]"
              :placeholder="$t('coreHTTPRequestServiceForm.namePlaceholder')"
              @blur="v$.values.query_params.$touch()"
            />
          </div>
          <div class="col col-5">
            <InjectedFormulaInput
              v-model="query_param.value"
              :placeholder="$t('coreHTTPRequestServiceForm.valuePlaceholder')"
            />
          </div>
          <div class="col col-2">
            <ButtonIcon
              icon="iconoir-bin"
              @click="deleteQueryParam(query_param)"
            />
          </div>
          <div
            v-show="v$.values.query_params.$each.$message[index]?.[0]"
            class="error margin-left-1"
          >
            {{ v$.values.query_params.$each.$message[index]?.[0] }}
          </div>
        </div>
      </template>
      <ButtonText
        type="secondary"
        size="small"
        icon="iconoir-plus"
        @click="createQueryParam"
      >
        {{ $t('coreHTTPRequestServiceForm.addQueryParam') }}
      </ButtonText>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('coreHTTPRequestServiceForm.headers')"
      required
      class="margin-bottom-2"
    >
      <template v-if="v$.values.headers.$model.length">
        <div class="row" style="--gap: 6px">
          <label class="col col-5 control__label control__label--small">
            {{ $t('coreHTTPRequestServiceForm.name') }}
          </label>
          <label class="col col-7 control__label control__label--small">
            {{ $t('coreHTTPRequestServiceForm.value') }}
          </label>
        </div>
        <div
          v-for="(header, index) in v$.values.headers.$model"
          :key="header.id"
          style="--gap: 6px"
          class="row margin-bottom-1"
        >
          <div class="col col-5">
            <FormInput
              v-model="header.key"
              :error="!!v$.values.headers.$each.$message[index]?.[0]"
              :placeholder="$t('coreHTTPRequestServiceForm.namePlaceholder')"
              @blur="v$.values.headers.$touch()"
            />
          </div>
          <div class="col col-5">
            <InjectedFormulaInput
              v-model="header.value"
              :placeholder="$t('coreHTTPRequestServiceForm.valuePlaceholder')"
            />
          </div>
          <div class="col col-2">
            <ButtonIcon icon="iconoir-bin" @click="deleteHeader(header)" />
          </div>
          <div
            v-show="v$.values.headers.$each.$message[index]?.[0]"
            class="error margin-left-1"
          >
            {{ v$.values.headers.$each.$message[index]?.[0] }}
          </div>
        </div>
      </template>
      <ButtonText
        type="secondary"
        size="small"
        icon="iconoir-plus"
        @click="createHeader"
      >
        {{ $t('coreHTTPRequestServiceForm.addHeader') }}
      </ButtonText>
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
        :enabled-modes="
          values.body_type === 'plain'
            ? BASEROW_FORMULA_MODES
            : ['raw', 'simple']
        "
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
      <template v-if="v$.values.form_data.$model.length">
        <div class="row" style="--gap: 6px">
          <label class="col col-5 control__label control__label--small">
            {{ $t('coreHTTPRequestServiceForm.name') }}
          </label>
          <label class="col col-7 control__label control__label--small">
            {{ $t('coreHTTPRequestServiceForm.value') }}
          </label>
        </div>
        <div
          v-for="(fdata, index) in v$.values.form_data.$model"
          :key="fdata.id"
          style="--gap: 6px"
          class="row margin-bottom-1"
        >
          <div class="col col-5">
            <FormInput
              v-model="fdata.key"
              :error="!!v$.values.form_data.$each.$message[index]?.[0]"
              :placeholder="$t('coreHTTPRequestServiceForm.namePlaceholder')"
              @blur="v$.values.form_data.$touch()"
            />
          </div>
          <div class="col col-5">
            <InjectedFormulaInput
              v-model="fdata.value"
              :placeholder="$t('coreHTTPRequestServiceForm.valuePlaceholder')"
            />
          </div>
          <div class="col col-2">
            <ButtonIcon icon="iconoir-bin" @click="deleteFormData(fdata)" />
          </div>
          <div
            v-show="v$.values.form_data.$each.$message[index]?.[0]"
            class="error margin-left-1"
          >
            {{ v$.values.form_data.$each.$message[index]?.[0] }}
          </div>
        </div>
      </template>
      <ButtonText
        type="secondary"
        size="small"
        icon="iconoir-plus"
        @click="createFormData"
      >
        {{ $t('coreHTTPRequestServiceForm.addFormData') }}
      </ButtonText>
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
import { useVuelidate } from '@vuelidate/core'
import {
  required,
  integer,
  minValue,
  maxValue,
  maxLength,
  helpers,
} from '@vuelidate/validators'
import { uuid } from '@baserow/modules/core/utils/string'
import { BASEROW_FORMULA_MODES } from '@baserow/modules/core/formula/constants'

export default {
  name: 'CoreHTTPRequestService',
  components: { InjectedFormulaInput },
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
    BASEROW_FORMULA_MODES() {
      return BASEROW_FORMULA_MODES
    },
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
  methods: {
    createHeader() {
      this.v$.values.headers.$model.push({
        key: `header${this.v$.values.headers.$model.length + 1}`,
        value: { formula: '', mode: 'simple' },
        id: uuid(),
      })
    },
    deleteHeader({ id }) {
      this.v$.values.headers.$model = this.v$.values.headers.$model.filter(
        (header) => header.id !== id
      )
    },
    createQueryParam() {
      this.v$.values.query_params.$model.push({
        key: `param${this.v$.values.query_params.$model.length + 1}`,
        value: { formula: '', mode: 'simple' },
        id: uuid(),
      })
    },
    deleteQueryParam({ id }) {
      this.v$.values.query_params.$model =
        this.v$.values.query_params.$model.filter((param) => param.id !== id)
    },
    createFormData() {
      this.v$.values.form_data.$model.push({
        key: `form${this.v$.values.form_data.$model.length + 1}`,
        value: { formula: '', mode: 'simple' },
        id: uuid(),
      })
    },
    deleteFormData({ id }) {
      this.v$.values.form_data.$model = this.v$.values.form_data.$model.filter(
        (f) => f.id !== id
      )
    },
  },
  validations() {
    const isValidParamOrHeaderName = (name) => {
      const validNameRegex = /^[a-zA-Z0-9-_.]+$/

      if (name[0] === '-' || name[0] === '_') {
        return false
      }

      return validNameRegex.test(name)
    }
    return {
      values: {
        headers: {
          $each: helpers.forEach({
            key: {
              required: helpers.withMessage(
                this.$t('coreHTTPRequestServiceForm.nameFieldRequired'),
                required
              ),
              maxLength: helpers.withMessage(
                this.$t('error.maxLength', { max: 255 }),
                maxLength(225)
              ),
              invalid: helpers.withMessage(
                this.$t('coreHTTPRequestServiceForm.nameFieldInvalid'),
                isValidParamOrHeaderName
              ),
            },
            value: {},
          }),
        },
        query_params: {
          $each: helpers.forEach({
            key: {
              required: helpers.withMessage(
                this.$t('coreHTTPRequestServiceForm.nameFieldRequired'),
                required
              ),
              invalid: helpers.withMessage(
                this.$t('coreHTTPRequestServiceForm.nameFieldInvalid'),
                isValidParamOrHeaderName
              ),
              maxLength: helpers.withMessage(
                this.$t('error.maxLength', { max: 255 }),
                maxLength(225)
              ),
            },
            value: {},
          }),
        },
        form_data: {
          $each: helpers.forEach({
            key: {
              required: helpers.withMessage(
                this.$t('coreHTTPRequestServiceForm.nameFieldRequired'),
                required
              ),
              invalid: helpers.withMessage(
                this.$t('coreHTTPRequestServiceForm.nameFieldInvalid'),
                isValidParamOrHeaderName
              ),
              maxLength: helpers.withMessage(
                this.$t('error.maxLength', { max: 255 }),
                maxLength(225)
              ),
            },
            value: {},
          }),
        },
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
