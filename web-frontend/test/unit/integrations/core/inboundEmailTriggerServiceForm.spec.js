import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import CoreInboundEmailTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CoreInboundEmailTriggerServiceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  inheritAttrs: false,
  template: '<div v-bind="$attrs"><slot /></div>',
})

const AlertStub = defineComponent({
  name: 'Alert',
  inheritAttrs: false,
  template: '<div class="alert-stub" v-bind="$attrs"><slot /></div>',
})

const ButtonStub = defineComponent({
  name: 'Button',
  inheritAttrs: false,
  template: '<button class="button-stub" v-bind="$attrs"><slot /></button>',
})

const CopiedStub = defineComponent({
  name: 'Copied',
  methods: {
    show() {},
  },
  template: '<div class="copied-stub" />',
})

const RadioGroupStub = defineComponent({
  name: 'RadioGroup',
  props: ['modelValue', 'options'],
  emits: ['update:modelValue'],
  template: `
    <div class="radio-group-stub">
      <button
        v-for="option in options"
        :key="String(option.value)"
        class="radio-option-stub"
        @click="$emit('update:modelValue', option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  `,
})

const EMAIL_ADDRESS = `${'a'.repeat(32)}@inbound.baserow.io`
const TEST_EMAIL_ADDRESS = `test-${EMAIL_ADDRESS}`

async function mountComponent({ defaultValues = {} } = {}) {
  return await mountSuspended(CoreInboundEmailTriggerServiceForm, {
    props: {
      defaultValues,
    },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        Alert: AlertStub,
        Button: ButtonStub,
        Copied: CopiedStub,
        RadioGroup: RadioGroupStub,
      },
      mocks: {
        // Render the key plus any interpolation params so tests can assert
        // on the values passed to translations.
        $t: (key, params) =>
          params ? `${key}(${Object.values(params).join(',')})` : key,
      },
    },
  })
}

describe('Core email trigger service form', () => {
  test('renders the test address by default, like the HTTP trigger', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        email_address: EMAIL_ADDRESS,
        test_email_address: TEST_EMAIL_ADDRESS,
      },
    })

    expect(wrapper.find('code').text()).toBe(TEST_EMAIL_ADDRESS)
    // The delivery-delay note is always shown: the trigger can only be added
    // on an instance configured for inbound email, so there is no
    // "not configured" state for the form to handle.
    expect(wrapper.find('.alert-stub').text()).toBe(
      'inboundEmailTriggerServiceForm.infoDescription'
    )
  })

  test('switches to the published address', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        email_address: EMAIL_ADDRESS,
        test_email_address: TEST_EMAIL_ADDRESS,
      },
    })

    const [testOption, publishedOption] = wrapper.findAll('.radio-option-stub')
    expect(testOption.text()).toBe(
      'inboundEmailTriggerServiceForm.addressVersionTest'
    )
    expect(publishedOption.text()).toBe(
      'inboundEmailTriggerServiceForm.addressVersionPublished'
    )

    await publishedOption.trigger('click')
    expect(wrapper.find('code').text()).toBe(EMAIL_ADDRESS)

    await testOption.trigger('click')
    expect(wrapper.find('code').text()).toBe(TEST_EMAIL_ADDRESS)
  })

  test('shows the size limit and attachment note when the limit is known', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        email_address: EMAIL_ADDRESS,
        test_email_address: TEST_EMAIL_ADDRESS,
        max_message_size_mb: 25,
      },
    })

    expect(wrapper.text()).toContain(
      'inboundEmailTriggerServiceForm.limits(25)'
    )
  })

  test('hides the size limit note when the limit is unknown', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        email_address: EMAIL_ADDRESS,
        test_email_address: TEST_EMAIL_ADDRESS,
      },
    })

    expect(wrapper.text()).not.toContain(
      'inboundEmailTriggerServiceForm.limits'
    )
  })

  test('regenerate button emits values-changed flagged as immediate', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        email_address: EMAIL_ADDRESS,
        test_email_address: TEST_EMAIL_ADDRESS,
      },
    })

    await wrapper.find('.button-stub').trigger('click')

    const emitted = wrapper.emitted('values-changed')
    expect(emitted).toHaveLength(1)
    // The second argument asks the side panel to skip the debounce so the
    // request and spinner are not held back for half a second, and to say
    // when the request has settled.
    expect(emitted[0]).toStrictEqual([
      { regenerate_token: true },
      { immediate: true, onSettled: expect.any(Function) },
    ])
  })

  test('regenerate button spins from the click until the request has settled', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        email_address: EMAIL_ADDRESS,
        test_email_address: TEST_EMAIL_ADDRESS,
      },
    })
    const button = wrapper.find('.button-stub')
    expect(button.attributes('loading')).toBe('false')

    await button.trigger('click')
    expect(button.attributes('loading')).toBe('true')

    // The state is the form's own: it ends when the side panel reports the
    // request as settled, not when the node's loading flag changes.
    const [, { onSettled }] = wrapper.emitted('values-changed')[0]
    onSettled()
    await wrapper.vm.$nextTick()
    expect(button.attributes('loading')).toBe('false')
  })
})
