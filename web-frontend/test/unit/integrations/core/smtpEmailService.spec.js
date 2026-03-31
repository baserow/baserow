import { defineComponent, nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { vi } from 'vitest'

import CoreSMTPEmailServiceForm from '@baserow/modules/integrations/core/components/services/CoreSMTPEmailServiceForm'
import { flushPromises } from '@vue/test-utils'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  inheritAttrs: false,
  template: '<div v-bind="$attrs"><slot /></div>',
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: {
      type: [Object, String],
      required: false,
      default: undefined,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
    enabledModes: {
      type: Array,
      required: false,
      default: () => [],
    },
    textarea: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  template: `
    <div
      :modelvalue="modelValue"
      :placeholder="placeholder"
      :enabled-modes="enabledModes.length ? enabledModes.join(',') : undefined"
      :textarea="textarea ? '' : undefined"
    />
  `,
})

const IntegrationDropdownStub = defineComponent({
  name: 'IntegrationDropdown',
  props: {
    modelValue: {
      type: Number,
      required: false,
      default: null,
    },
    application: {
      type: Object,
      required: true,
    },
    integrations: {
      type: Array,
      required: true,
    },
    integrationType: {
      type: Object,
      required: true,
    },
  },
  template: `
    <div
      :modelvalue="modelValue"
      :application="application"
      :integrations="integrations"
      :integration-type="integrationType"
    />
  `,
})

const DropdownStub = defineComponent({
  name: 'Dropdown',
  props: {
    modelValue: {
      type: String,
      required: false,
      default: '',
    },
  },
  template: '<div :modelvalue="modelValue"><slot /></div>',
})

const DropdownItemStub = defineComponent({
  name: 'DropdownItem',
  props: {
    name: {
      type: String,
      required: true,
    },
    value: {
      type: String,
      required: true,
    },
  },
  template: '<div :name="name" :value="value" />',
})

const defaultService = {
  instance_smtp_settings_enabled: true,
}

async function mountComponent({
  service = defaultService,
  defaultValues = service,
  integrations = [],
  application = { id: 1 },
} = {}) {
  return await mountSuspended(CoreSMTPEmailServiceForm, {
    props: {
      application,
      service,
      defaultValues,
    },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        InjectedFormulaInput: InjectedFormulaInputStub,
        IntegrationDropdown: IntegrationDropdownStub,
        Dropdown: DropdownStub,
        DropdownItem: DropdownItemStub,
      },
      mocks: {
        $t: (key) => key,
        $store: {
          getters: {
            'integration/getIntegrations': () => integrations,
          },
        },
        $registry: {
          get: vi.fn(() => ({ type: 'smtp' })),
        },
      },
    },
  })
}

describe('Core SMTP email service form', () => {
  test('defaults to instance SMTP settings when available without an existing custom SMTP configuration', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.element).toMatchSnapshot()
  })

  test('defaults to instance SMTP settings when available even if custom SMTP fields already exist', async () => {
    const wrapper = await mountComponent({
      service: {
        ...defaultService,
        from_email: {
          formula: "'from@example.com'",
        },
      },
      defaultValues: {
        ...defaultService,
        from_email: {
          formula: "'from@example.com'",
        },
      },
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('defaults to instance SMTP settings when available even if an SMTP integration is already selected', async () => {
    const wrapper = await mountComponent({
      service: {
        ...defaultService,
        integration_id: 123,
      },
      defaultValues: {
        ...defaultService,
        integration_id: 123,
      },
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('does not default to instance SMTP settings when custom SMTP mode was explicitly selected', async () => {
    const wrapper = await mountComponent({
      service: {
        ...defaultService,
        use_instance_smtp_settings: false,
        integration_id: 123,
        from_email: {
          formula: "'from@example.com'",
        },
      },
      defaultValues: {
        ...defaultService,
        use_instance_smtp_settings: false,
        integration_id: 123,
        from_email: {
          formula: "'from@example.com'",
        },
      },
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('shows custom SMTP fields when instance SMTP is unchecked', async () => {
    const wrapper = await mountComponent()

    await wrapper.find('input[type="checkbox"]').trigger('click')
    await nextTick()

    expect(wrapper.element).toMatchSnapshot()
  })

  test('only passes SMTP integrations to the integration dropdown', async () => {
    const smtpIntegration = { id: 1, type: 'smtp' }
    const wrapper = await mountComponent({
      service: {
        instance_smtp_settings_enabled: false,
      },
      defaultValues: {
        instance_smtp_settings_enabled: false,
      },
      integrations: [smtpIntegration, { id: 2, type: 'slack' }],
    })

    expect(
      wrapper.findComponent(IntegrationDropdownStub).props('integrations')
    ).toEqual([smtpIntegration])
  })
})
