import { defineComponent, nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import AIPromptStep from '@baserow_enterprise/components/onboarding/AIPromptStep'
import AssistantService from '@baserow_enterprise/services/assistant'

vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: vi.fn(),
}))

vi.mock('@baserow/modules/core/utils/error', () => ({ notifyIf: vi.fn() }))

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  template: '<div class="form-group-stub"><slot /></div>',
})

const FormTextareaStub = defineComponent({
  name: 'FormTextarea',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue', 'input'],
  methods: { focus() {} },
  template:
    '<textarea class="form-textarea-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value); $emit(\'input\', $event)" />',
})

const ButtonTextStub = defineComponent({
  name: 'ButtonText',
  props: { disabled: { type: Boolean, default: false } },
  template:
    '<button class="button-text-stub" :disabled="disabled"><slot /></button>',
})

const DetailsModalStub = defineComponent({
  name: 'AIOnboardingDetailsModal',
  methods: { show() {} },
  template: '<div />',
})

const ErrorStub = defineComponent({
  name: 'Error',
  props: { error: { type: Object, required: true } },
  template:
    '<div v-if="error.visible" class="error-stub">{{ error.title }} {{ error.message }}</div>',
})

// Mimics what the client adds to a failed request, so the component can look up
// the message that belongs to the error code.
const apiError = (code) => {
  const error = new Error(code)
  error.handler = {
    getMessage: (name, specificErrorMap) =>
      specificErrorMap?.[code] || {
        title: 'Something went wrong',
        message: 'Something went wrong',
      },
    handled: () => {},
  }
  return error
}

const suggestions = [
  { name: 'Client projects', prompt: 'Track client projects for Acme.' },
  { name: 'Content calendar', prompt: 'Plan and schedule social posts.' },
]

// The onboarding keeps the steps alive, so leaving and coming back to the step must
// be tested the same way.
const KeepAliveHost = defineComponent({
  components: { AIPromptStep },
  props: {
    data: { type: Object, required: true },
    visible: { type: Boolean, default: true },
  },
  template:
    '<KeepAlive><AIPromptStep v-if="visible" :data="data" /></KeepAlive>',
})

const globalOptions = {
  stubs: {
    FormGroup: FormGroupStub,
    FormTextarea: FormTextareaStub,
    ButtonText: ButtonTextStub,
    AIOnboardingDetailsModal: DetailsModalStub,
    Error: ErrorStub,
  },
  mocks: { $t: (key) => key, $i18n: { locale: 'en' } },
}

function onboardingData(database = {}) {
  return {
    database: {
      type: 'ai',
      industry: 'Marketing',
      team: 'Client services',
      ...database,
    },
  }
}

async function mountComponent(database = {}) {
  return await mountSuspended(AIPromptStep, {
    props: { data: onboardingData(database) },
    global: globalOptions,
  })
}

async function mountKeptAlive() {
  return await mountSuspended(KeepAliveHost, {
    props: { data: onboardingData() },
    global: globalOptions,
  })
}

describe('AI prompt step', () => {
  beforeEach(() => {
    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: vi.fn().mockResolvedValue(suggestions),
    })
  })

  test('prefills the first suggestion and lists them all', async () => {
    const wrapper = await mountComponent()
    await nextTick()
    await nextTick()

    expect(wrapper.find('.form-textarea-stub').element.value).toBe(
      suggestions[0].prompt
    )

    const cards = wrapper.findAll('.ai-prompt-suggestion')
    expect(cards).toHaveLength(2)
    expect(cards.at(0).classes()).toContain('ai-prompt-suggestion--active')
    expect(cards.at(0).find('.ai-prompt-suggestion__name').text()).toBe(
      'Client projects'
    )
    expect(cards.at(0).find('.ai-prompt-suggestion__preview').text()).toBe(
      suggestions[0].prompt
    )
  })

  test('clicking a suggestion sets it as the prompt', async () => {
    const wrapper = await mountComponent()
    await nextTick()
    await nextTick()

    await wrapper.findAll('.ai-prompt-suggestion').at(1).trigger('click')
    await nextTick()

    expect(wrapper.find('.form-textarea-stub').element.value).toBe(
      suggestions[1].prompt
    )
    expect(wrapper.emitted('update-data').at(-1)[0]).toEqual({
      prompt: suggestions[1].prompt,
      language: 'en',
      industry: 'Marketing',
      team: 'Client services',
    })
  })

  test('the details cannot be changed while the suggestions load', async () => {
    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: vi
        .fn()
        .mockReturnValue(new Promise(() => {})),
    })

    const wrapper = await mountComponent()
    await nextTick()

    expect(
      wrapper.find('.button-text-stub').attributes('disabled')
    ).toBeDefined()
  })

  test('changed details are part of the data of the step', async () => {
    const wrapper = await mountComponent()
    await flushPromises()

    wrapper.findComponent(DetailsModalStub).vm.$emit('updated', {
      industry: 'Retail',
      team: 'Sales',
    })
    await flushPromises()

    expect(wrapper.emitted('update-data').at(-1)[0]).toEqual(
      expect.objectContaining({ industry: 'Retail', team: 'Sales' })
    )
  })

  test('changed details survive leaving and coming back to the step', async () => {
    const host = await mountKeptAlive()
    await flushPromises()

    host.findComponent(DetailsModalStub).vm.$emit('updated', {
      industry: 'Retail',
      team: 'Sales',
    })
    await flushPromises()

    await host.setProps({ visible: false })
    await host.setProps({ visible: true })
    await flushPromises()

    expect(
      host.findComponent(AIPromptStep).emitted('update-data').at(-1)[0]
    ).toEqual(expect.objectContaining({ industry: 'Retail', team: 'Sales' }))
  })

  test('changing the earlier answers replaces the details', async () => {
    const host = await mountKeptAlive()
    await flushPromises()

    host.findComponent(DetailsModalStub).vm.$emit('updated', {
      industry: 'Retail',
      team: 'Sales',
    })
    await flushPromises()

    await host.setProps({ visible: false })
    await host.setProps({
      visible: true,
      data: {
        database: { type: 'ai', industry: 'Hotels', team: 'Front desk' },
      },
    })
    await flushPromises()

    expect(
      host.findComponent(AIPromptStep).emitted('update-data').at(-1)[0]
    ).toEqual(
      expect.objectContaining({ industry: 'Hotels', team: 'Front desk' })
    )
  })

  test('a hand written prompt survives regenerating the suggestions', async () => {
    const wrapper = await mountComponent()
    await nextTick()
    await nextTick()

    await wrapper.find('.form-textarea-stub').setValue('My own prompt')
    await nextTick()

    const fetch = vi
      .fn()
      .mockResolvedValue([
        { name: 'Something else', prompt: 'A brand new suggestion.' },
      ])
    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: fetch,
    })

    wrapper.findComponent(DetailsModalStub).vm.$emit('updated', {
      industry: 'Retail',
      team: 'Sales',
    })
    await flushPromises()

    expect(fetch).toHaveBeenCalledWith(
      expect.objectContaining({ industry: 'Retail', team: 'Sales' })
    )
    expect(wrapper.find('.form-textarea-stub').element.value).toBe(
      'My own prompt'
    )
    expect(wrapper.find('.ai-prompt-suggestion__name').text()).toBe(
      'Something else'
    )
  })

  test('a picked suggestion is replaced when the suggestions regenerate', async () => {
    const wrapper = await mountComponent()
    await flushPromises()

    await wrapper.findAll('.ai-prompt-suggestion').at(1).trigger('click')
    await nextTick()
    expect(wrapper.find('.form-textarea-stub').element.value).toBe(
      suggestions[1].prompt
    )

    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: vi
        .fn()
        .mockResolvedValue([
          { name: 'Something else', prompt: 'A brand new suggestion.' },
        ]),
    })

    wrapper.findComponent(DetailsModalStub).vm.$emit('updated', {
      industry: 'Retail',
      team: 'Sales',
    })
    await flushPromises()

    expect(wrapper.find('.form-textarea-stub').element.value).toBe(
      'A brand new suggestion.'
    )
  })

  test('explains that the model is unavailable and blocks continuing', async () => {
    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: vi
        .fn()
        .mockRejectedValue(apiError('ERROR_ASSISTANT_MODEL_NOT_SUPPORTED')),
    })

    const wrapper = await mountComponent()
    await flushPromises()

    expect(wrapper.find('.error-stub').text()).toContain(
      'aiPromptStep.modelNotSupportedTitle'
    )
    // Kuma can't build the database either, so there is nothing to fill out.
    expect(wrapper.find('.form-textarea-stub').exists()).toBe(false)
    expect(wrapper.findAll('.ai-prompt-suggestion')).toHaveLength(0)
    expect(wrapper.vm.isValid()).toBe(false)
  })

  test('shows the generic error for any other failure', async () => {
    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: vi
        .fn()
        .mockRejectedValue(apiError('ERROR_SOMETHING_ELSE')),
    })

    const wrapper = await mountComponent()
    await flushPromises()

    expect(wrapper.find('.error-stub').text()).toContain('Something went wrong')
    expect(wrapper.find('.form-textarea-stub').exists()).toBe(false)
  })

  test('the error disappears when the suggestions can be fetched again', async () => {
    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: vi
        .fn()
        .mockRejectedValue(apiError('ERROR_ASSISTANT_MODEL_NOT_SUPPORTED')),
    })

    const wrapper = await mountComponent()
    await flushPromises()
    expect(wrapper.find('.error-stub').exists()).toBe(true)

    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: vi.fn().mockResolvedValue(suggestions),
    })
    wrapper.findComponent(DetailsModalStub).vm.$emit('updated', {
      industry: 'Retail',
      team: 'Sales',
    })
    await flushPromises()

    expect(wrapper.find('.error-stub').exists()).toBe(false)
    expect(wrapper.find('.form-textarea-stub').element.value).toBe(
      suggestions[0].prompt
    )
  })
})
