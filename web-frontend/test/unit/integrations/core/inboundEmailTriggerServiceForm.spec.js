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

const EMAIL_ADDRESS = `${'a'.repeat(32)}@inbound.baserow.io`

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
      },
      mocks: {
        $t: (key) => key,
      },
    },
  })
}

describe('Core email trigger service form', () => {
  test('renders the generated email address', async () => {
    const wrapper = await mountComponent({
      defaultValues: { email_address: EMAIL_ADDRESS },
    })

    expect(wrapper.text()).toContain(EMAIL_ADDRESS)
    expect(wrapper.find('.alert-stub').exists()).toBe(false)
  })

  test('shows the not configured alert when there is no email address', async () => {
    const wrapper = await mountComponent({
      defaultValues: { email_address: null },
    })

    expect(wrapper.find('.alert-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain(
      'inboundEmailTriggerServiceForm.notConfigured'
    )
    expect(wrapper.find('.button-stub').exists()).toBe(false)
  })

  test('regenerate button emits values-changed with the regenerate flag', async () => {
    const wrapper = await mountComponent({
      defaultValues: { email_address: EMAIL_ADDRESS },
    })

    await wrapper.find('.button-stub').trigger('click')

    const emitted = wrapper.emitted('values-changed')
    expect(emitted).toHaveLength(1)
    expect(emitted[0]).toStrictEqual([{ regenerate_token: true }])
  })
})
