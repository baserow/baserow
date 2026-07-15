import { defineComponent, nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import DataSourceForm from '@baserow/modules/builder/components/dataSource/DataSourceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  template: '<div><slot /></div>',
})

const FormInputStub = defineComponent({
  name: 'FormInput',
  props: {
    modelValue: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['update:modelValue', 'blur'],
  template: '<input :value="modelValue" />',
})

const MultiStageDropdownStub = defineComponent({
  name: 'MultiStageDropdown',
  props: {
    modelValue: {
      type: String,
      required: false,
      default: null,
    },
    items: {
      type: Array,
      required: true,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
    searchPlaceholder: {
      type: String,
      required: false,
      default: '',
    },
    emptyText: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  template: '<div class="multi-stage-dropdown-stub" />',
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
      required: false,
      default: null,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  template: '<div class="integration-dropdown-stub" />',
})

const localBaserowIntegrationType = {
  name: 'Local Baserow',
  image: '/local-baserow.svg',
  iconClass: 'iconoir-database',
  getType: () => 'local_baserow',
}

const otherIntegrationType = {
  name: 'Other',
  image: '/other.svg',
  getType: () => 'other',
}

const serviceType = {
  name: 'Get row',
  icon: 'iconoir-pin',
  description: 'Reads a row from a Baserow table.',
  integrationType: localBaserowIntegrationType,
  isDataSource: true,
  formComponent: null,
  getType: () => 'local_baserow_get_row',
  isDeactivatedReason: () => null,
}

async function mountComponent() {
  const integrations = [
    { id: 1, type: 'local_baserow' },
    { id: 2, type: 'other' },
  ]
  const registry = {
    getOrderedList(namespace) {
      return namespace === 'service'
        ? [serviceType]
        : [localBaserowIntegrationType, otherIntegrationType]
    },
    get(namespace, type) {
      if (namespace === 'service' && type === serviceType.getType()) {
        return serviceType
      }
      return null
    },
  }

  return await mountSuspended(DataSourceForm, {
    props: {
      builder: { id: 1, workspace: { id: 1 } },
      page: { id: 1 },
      integrations,
      create: true,
    },
    global: {
      provide: {
        applicationContext: {},
      },
      stubs: {
        FormGroup: FormGroupStub,
        FormInput: FormInputStub,
        IntegrationDropdown: IntegrationDropdownStub,
        MultiStageDropdown: MultiStageDropdownStub,
      },
      mocks: {
        $registry: registry,
        $store: {
          getters: {
            'dataSource/getPageDataSources': () => [],
          },
        },
        $t: (key) => key,
      },
    },
  })
}

describe('DataSourceForm', () => {
  test('groups service types under their integration type', async () => {
    const wrapper = await mountComponent()
    const actionDropdown = wrapper.findComponent(MultiStageDropdownStub)

    expect(actionDropdown.props('items')).toEqual([
      {
        id: 'integration-local_baserow',
        label: 'Local Baserow',
        image: '/local-baserow.svg',
        icon: 'iconoir-database',
        children: [
          {
            id: 'service-local_baserow_get_row',
            label: 'Get row',
            value: 'local_baserow_get_row',
            icon: 'iconoir-pin',
            description: 'Reads a row from a Baserow table.',
            disabled: false,
            disabledReason: null,
          },
        ],
      },
    ])
  })

  test('filters and auto-selects connections for the selected action', async () => {
    const wrapper = await mountComponent()

    wrapper
      .findComponent(MultiStageDropdownStub)
      .vm.$emit('update:modelValue', serviceType.getType())
    await nextTick()

    const connectionDropdown = wrapper.findComponent(IntegrationDropdownStub)
    expect(connectionDropdown.props('integrations')).toEqual([
      { id: 1, type: 'local_baserow' },
    ])
    expect(connectionDropdown.props('modelValue')).toBe(1)
  })
})
