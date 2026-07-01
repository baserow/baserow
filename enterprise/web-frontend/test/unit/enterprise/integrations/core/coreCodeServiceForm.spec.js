import { defineComponent, nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import CoreCodeServiceForm from '@baserow_enterprise/integrations/core/components/services/CoreCodeServiceForm'

const CORE_CODE_SERVICE_CODE_MAX_LENGTH = 4096

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  props: {
    error: {
      type: Boolean,
      default: false,
    },
    errorMessage: {
      type: String,
      default: '',
    },
  },
  template:
    '<div class="form-group-stub" :data-error="error" :data-error-message="errorMessage"><slot /></div>',
})

const CodeEditorStub = defineComponent({
  name: 'CodeEditor',
  props: {
    modelValue: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  template:
    '<textarea class="code-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  template: '<div />',
})

const serviceType = {
  getDefaultValues(service, values) {
    return values
  },
}

async function mountComponent(defaultValues = {}) {
  return await mountSuspended(CoreCodeServiceForm, {
    props: {
      defaultValues,
      service: null,
      serviceType,
    },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        CodeEditor: CodeEditorStub,
        InjectedFormulaInput: InjectedFormulaInputStub,
      },
      mocks: {
        $t: (key, params) => `${key}${params?.max ? `:${params.max}` : ''}`,
      },
    },
  })
}

describe('Core code service form', () => {
  test('shows a validation error when code exceeds the maximum length', async () => {
    const wrapper = await mountComponent()

    await wrapper
      .find('.code-editor-stub')
      .setValue('a'.repeat(CORE_CODE_SERVICE_CODE_MAX_LENGTH + 1))
    await nextTick()

    const codeFormGroup = wrapper.findAllComponents(FormGroupStub).at(1)

    expect(codeFormGroup.props('error')).toBe(true)
    expect(codeFormGroup.props('errorMessage')).toBe(
      `error.maxLength:${CORE_CODE_SERVICE_CODE_MAX_LENGTH}`
    )
  })
})
