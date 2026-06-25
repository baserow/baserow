<template>
  <form @submit.prevent>
    <FormGroup
      class="margin-bottom-2"
      small-label
      required
      :label="$t('coreResponseServiceForm.statusCode')"
      :error-message="getFirstErrorMessage('status_code')"
    >
      <FormInput
        v-model="v$.values.status_code.$model"
        :to-value="(value) => parseInt(value)"
        type="number"
      />
    </FormGroup>

    <FormGroup
      class="margin-bottom-2"
      small-label
      required
      :label="$t('coreResponseServiceForm.bodyType')"
    >
      <Dropdown v-model="values.body_type">
        <DropdownItem
          v-for="bodyType in bodyTypes"
          :key="bodyType.value"
          :name="bodyType.name"
          :value="bodyType.value"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup
      v-if="values.body_type !== 'empty'"
      class="margin-bottom-2"
      small-label
      :label="$t('coreResponseServiceForm.body')"
    >
      <InjectedFormulaInput
        v-model="values.body"
        :placeholder="$t('coreResponseServiceForm.bodyPlaceholder')"
        textarea
      />
    </FormGroup>

    <FormGroup
      class="margin-bottom-2"
      small-label
      :label="$t('coreResponseServiceForm.headers')"
    >
      <template v-if="v$.values.headers.$model.length">
        <div class="row" style="--gap: 6px">
          <label class="col col-5 control__label control__label--small">
            {{ $t('coreResponseServiceForm.name') }}
          </label>
          <label class="col col-7 control__label control__label--small">
            {{ $t('coreResponseServiceForm.value') }}
          </label>
        </div>
        <div
          v-for="(header, index) in v$.values.headers.$model"
          :key="header.id"
          class="row margin-bottom-1"
          style="--gap: 6px"
        >
          <div class="col col-5">
            <FormInput
              v-model="header.key"
              :error="!!v$.values.headers.$each.$message[index]?.[0]"
              :placeholder="$t('coreResponseServiceForm.namePlaceholder')"
              @blur="v$.values.headers.$touch()"
            />
          </div>
          <div class="col col-5">
            <InjectedFormulaInput
              v-model="header.value"
              :placeholder="$t('coreResponseServiceForm.valuePlaceholder')"
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
        {{ $t('coreResponseServiceForm.addHeader') }}
      </ButtonText>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import { uuid } from '@baserow/modules/core/utils/string'
import { useVuelidate } from '@vuelidate/core'
import {
  helpers,
  integer,
  maxLength,
  maxValue,
  minValue,
  required,
} from '@vuelidate/validators'

export default {
  name: 'CoreResponseServiceForm',
  components: { InjectedFormulaInput },
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['status_code', 'body_type', 'body', 'headers'],
      values: {
        status_code: 204,
        body_type: 'empty',
        body: {},
        headers: [],
      },
    }
  },
  computed: {
    bodyTypes() {
      return [
        {
          name: this.$t('coreResponseServiceForm.bodyTypeEmpty'),
          value: 'empty',
        },
        {
          name: this.$t('coreResponseServiceForm.bodyTypeJson'),
          value: 'json',
        },
        {
          name: this.$t('coreResponseServiceForm.bodyTypeText'),
          value: 'text',
        },
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
  },
  validations() {
    const isValidHeaderName = (name) => {
      const validNameRegex = /^[a-zA-Z0-9-_]+$/
      if (!name || name[0] === '-' || name[0] === '_') {
        return false
      }
      return validNameRegex.test(name)
    }

    return {
      values: {
        status_code: {
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 100 }),
            minValue(100)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 599 }),
            maxValue(599)
          ),
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
        },
        headers: {
          $each: helpers.forEach({
            key: {
              required: helpers.withMessage(
                this.$t('coreResponseServiceForm.nameFieldRequired'),
                required
              ),
              maxLength: helpers.withMessage(
                this.$t('error.maxLength', { max: 255 }),
                maxLength(255)
              ),
              invalid: helpers.withMessage(
                this.$t('coreResponseServiceForm.nameFieldInvalid'),
                isValidHeaderName
              ),
            },
            value: {},
          }),
        },
      },
    }
  },
}
</script>
