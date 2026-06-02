<template>
  <form @submit.prevent @keydown.enter.stop>
    <FormGroup
      small-label
      :label="$t('coreCodeServiceForm.injectionsLabel')"
      :helper-text="$t('coreCodeServiceForm.injectionsHelperText')"
      required
      class="margin-bottom-2"
    >
      <template v-if="v$.values.injections.$model.length">
        <div class="row" style="--gap: 6px">
          <label class="col col-7 control__label control__label--small">
            {{ $t('coreCodeServiceForm.nameLabel') }}
          </label>
          <label class="col col-5 control__label control__label--small">
            {{ $t('coreCodeServiceForm.valueLabel') }}
          </label>
        </div>
        <div
          v-for="(injection, index) in v$.values.injections.$model"
          :key="injection.id"
          style="--gap: 6px"
          class="row margin-bottom-1"
        >
          <div class="col col-5">
            <FormInput
              v-model="injection.name"
              :error="!!v$.values.injections.$each.$message[index]?.[0]"
              :placeholder="$t('coreCodeServiceForm.namePlaceholder')"
              @blur="v$.values.injections.$touch()"
            />
          </div>
          <div class="col col-5">
            <InjectedFormulaInput
              v-model="injection.formula"
              :placeholder="$t('coreCodeServiceForm.valuePlaceholder')"
            />
          </div>
          <div class="col col-2">
            <ButtonIcon
              icon="iconoir-bin"
              @click="deleteInjection(injection)"
            />
          </div>
          <div
            v-show="v$.values.injections.$each.$message[index]?.[0]"
            class="error margin-left-1"
          >
            {{ v$.values.injections.$each.$message[index]?.[0] }}
          </div>
        </div>
      </template>
      <ButtonText
        type="secondary"
        size="small"
        icon="iconoir-plus"
        @click="createInjection"
      >
        {{ $t('coreCodeServiceForm.addInjection') }}
      </ButtonText>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('coreCodeServiceForm.codeLabel')"
      :helper-text="$t('coreCodeServiceForm.codeHelperText')"
      :error-message="getFirstErrorMessage('code')"
      required
      class="margin-bottom-2"
    >
      <CodeEditor
        v-model="values.code"
        language="javascript"
        :placeholder="$t('coreCodeServiceForm.codePlaceholder')"
        :modal-title="$t('coreCodeServiceForm.codeLabel')"
      />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import CodeEditor from '@baserow/modules/core/components/CodeEditor.vue'
import { useVuelidate } from '@vuelidate/core'
import { helpers, maxLength, required } from '@vuelidate/validators'
import { uuid } from '@baserow/modules/core/utils/string'

const CORE_CODE_SERVICE_CODE_MAX_LENGTH = 4096

export default {
  name: 'CoreCodeServiceForm',
  components: {
    CodeEditor,
    InjectedFormulaInput,
  },
  mixins: [form],
  props: {
    service: {
      type: Object,
      required: false,
      default: null,
    },
    serviceType: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['code', 'injections'],
      values: {
        code: '',
        injections: [],
      },
    }
  },
  methods: {
    getDefaultValues() {
      const defaultValues = form.methods.getDefaultValues.call(this)
      return this.serviceType.getDefaultValues(this.service, defaultValues)
    },
    createInjection() {
      this.v$.values.injections.$model.push({
        name: `value${this.v$.values.injections.$model.length + 1}`,
        formula: { formula: '', mode: 'simple' },
        id: uuid(),
      })
    },
    deleteInjection({ id }) {
      this.v$.values.injections.$model =
        this.v$.values.injections.$model.filter(
          (injection) => injection.id !== id
        )
    },
  },
  validations() {
    const isValidVariableName = (name) => {
      const validNameRegex = /^[a-zA-Z_][a-zA-Z0-9_]*$/
      return validNameRegex.test(name)
    }

    return {
      values: {
        code: {
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', {
              max: CORE_CODE_SERVICE_CODE_MAX_LENGTH,
            }),
            maxLength(CORE_CODE_SERVICE_CODE_MAX_LENGTH)
          ),
        },
        injections: {
          $each: helpers.forEach({
            name: {
              required: helpers.withMessage(
                this.$t('coreCodeServiceForm.nameFieldRequired'),
                required
              ),
              maxLength: helpers.withMessage(
                this.$t('error.maxLength', { max: 255 }),
                maxLength(255)
              ),
              invalid: helpers.withMessage(
                this.$t('coreCodeServiceForm.nameFieldInvalid'),
                isValidVariableName
              ),
            },
            formula: {},
          }),
        },
      },
    }
  },
}
</script>
