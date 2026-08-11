import { defineComponent, nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import AIDatabaseOnboardingForm from '@baserow_enterprise/components/onboarding/AIDatabaseOnboardingForm'
import { AIDatabaseOnboardingStepType } from '@baserow_enterprise/databaseOnboardingStepTypes'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  props: { label: { type: String, default: '' } },
  template: '<div class="form-group-stub" :data-label="label"><slot /></div>',
})

let focused = null

const FormInputStub = defineComponent({
  name: 'FormInput',
  props: {
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'input'],
  methods: {
    focus() {
      focused = this.placeholder
    },
  },
  template:
    '<input class="form-input-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value); $emit(\'input\', $event)" />',
})

async function mountComponent(stubs = {}) {
  focused = null
  return await mountSuspended(AIDatabaseOnboardingForm, {
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        FormInput: FormInputStub,
        ...stubs,
      },
      mocks: { $t: (key) => key },
    },
  })
}

// The questions fade in and out, so the next one is only in the DOM after the
// transition has run.
const flushTransition = async () => {
  await new Promise((resolve) => setTimeout(resolve, 50))
  await nextTick()
}

const label = (wrapper) =>
  wrapper.find('.form-group-stub').attributes('data-label')

const answer = async (wrapper, value) => {
  await wrapper.find('.form-input-stub').setValue(value)
  await nextTick()
}

const stepType = new AIDatabaseOnboardingStepType({})

describe('AI database onboarding form', () => {
  test('asks the two questions one by one before moving on', async () => {
    const wrapper = await mountComponent()

    expect(label(wrapper)).toBe('aiDatabaseOnboardingForm.industryLabel')
    await answer(wrapper, 'Marketing')
    expect(wrapper.vm.beforeNext()).toBe(true)
    await nextTick()

    expect(label(wrapper)).toBe('aiDatabaseOnboardingForm.teamLabel')
    await answer(wrapper, 'Client services')

    // The last question hands control back so the onboarding branches to the
    // prompt step.
    expect(wrapper.vm.beforeNext()).toBe(false)
    const emitted = wrapper.emitted('input').at(-1)[0]
    expect(emitted).toMatchObject({
      industry: 'Marketing',
      team: 'Client services',
    })
  })

  test('the continue button stays disabled until the question is answered', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.vm.isValid()).toBe(false)
    await answer(wrapper, '  ')
    expect(wrapper.vm.isValid()).toBe(false)
    await answer(wrapper, 'Acme')
    expect(wrapper.vm.isValid()).toBe(true)
  })

  test('the onboarding back button moves between the questions', async () => {
    const wrapper = await mountComponent()

    // The first question is the start, so the onboarding itself decides whether
    // there is anything to go back to.
    expect(wrapper.vm.canGoBack()).toBe(false)

    await answer(wrapper, 'Marketing')
    wrapper.vm.beforeNext()
    await nextTick()

    expect(wrapper.vm.canGoBack()).toBe(true)
    wrapper.vm.goBack()
    await nextTick()

    expect(label(wrapper)).toBe('aiDatabaseOnboardingForm.industryLabel')
    expect(wrapper.find('.form-input-stub').element.value).toBe('Marketing')
  })

  test('the next question is faded in and gets the focus', async () => {
    const wrapper = await mountComponent({ transition: false })
    await flushTransition()
    expect(focused).toBe('aiDatabaseOnboardingForm.industryPlaceholder')

    await answer(wrapper, 'Marketing')
    wrapper.vm.beforeNext()
    await flushTransition()

    expect(label(wrapper)).toBe('aiDatabaseOnboardingForm.teamLabel')
    expect(focused).toBe('aiDatabaseOnboardingForm.teamPlaceholder')
  })

  test('reports invalid while the ref still points at another tab', () => {
    // Switching tabs renders us once while `stepComponent` is still the form of
    // the previously selected type, which has no `isValid`.
    const otherTabsForm = { $props: {} }

    expect(stepType.isValid({}, null, { stepComponent: otherTabsForm })).toBe(
      false
    )
    expect(stepType.isValid({}, null, {})).toBe(false)
  })
})
