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
  template: '<a class="button-text-stub"><slot /></a>',
})

const DetailsModalStub = defineComponent({
  name: 'AIOnboardingDetailsModal',
  methods: { show() {} },
  template: '<div />',
})

const suggestions = [
  { name: 'Client projects', prompt: 'Track client projects for Acme.' },
  { name: 'Content calendar', prompt: 'Plan and schedule social posts.' },
]

async function mountComponent(database = {}) {
  return await mountSuspended(AIPromptStep, {
    props: {
      data: {
        database: {
          type: 'ai',
          industry: 'Marketing',
          team: 'Client services',
          ...database,
        },
      },
    },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        FormTextarea: FormTextareaStub,
        ButtonText: ButtonTextStub,
        AIOnboardingDetailsModal: DetailsModalStub,
      },
      mocks: { $t: (key) => key, $i18n: { locale: 'en' } },
    },
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
    })
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

  test('falls back to the static examples when the request fails', async () => {
    AssistantService.mockReturnValue({
      fetchOnboardingPromptSuggestions: vi
        .fn()
        .mockRejectedValue(new Error('nope')),
    })

    const wrapper = await mountComponent()
    await flushPromises()

    // The step is never left empty, and the user can still write their own.
    expect(wrapper.findAll('.ai-prompt-suggestion--skeleton')).toHaveLength(0)
    expect(wrapper.findAll('.ai-prompt-suggestion')).toHaveLength(4)
    expect(wrapper.find('.form-textarea-stub').element.value).toBe('')
  })
})
