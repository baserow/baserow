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

const GroupedDropdownStub = defineComponent({
  name: 'GroupedDropdown',
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
    panelHeight: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['update:modelValue'],
  template: '<div class="grouped-dropdown-stub" />',
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
  iconColor: 'darker-blue',
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
  iconColor: 'darker-blue',
  description: 'Reads a row from a Baserow table.',
  integrationType: localBaserowIntegrationType,
  isDataSource: true,
  formComponent: null,
  getType: () => 'local_baserow_get_row',
  isDeactivatedReason: () => null,
}

const httpGroup = {
  id: 'http',
  label: 'HTTP',
  icon: 'iconoir-globe',
  iconColor: 'muted-cyan',
}

const ServiceFormStub = defineComponent({
  name: 'ServiceForm',
  template: '<div class="service-form-stub" />',
})

const httpServiceType = {
  name: 'HTTP request',
  icon: 'iconoir-globe',
  iconColor: 'muted-cyan',
  description: 'Fetches data from a URL.',
  integrationType: null,
  group: httpGroup,
  isDataSource: true,
  canBeTested: true,
  formComponent: ServiceFormStub,
  getType: () => 'http_get',
  isDeactivatedReason: () => null,
}

const hiddenServiceType = {
  name: 'Read a CSV file',
  icon: 'iconoir-page',
  iconColor: 'muted-yellow',
  description: 'Reads rows from a CSV file.',
  integrationType: null,
  group: { id: 'files', label: 'Files' },
  isDataSource: true,
  hiddenInDataSourcePicker: true,
  formComponent: null,
  getType: () => 'csv_file_reader',
  isDeactivatedReason: () => null,
}

async function mountComponent({
  serviceTypes = [serviceType],
  create = true,
  dataSource = {},
  defaultValues = {},
} = {}) {
  const integrations = [
    { id: 1, type: 'local_baserow' },
    { id: 2, type: 'other' },
  ]
  const registry = {
    getOrderedList(namespace) {
      return namespace === 'service'
        ? serviceTypes
        : [localBaserowIntegrationType, otherIntegrationType]
    },
    get(namespace, type) {
      if (namespace === 'service') {
        return serviceTypes.find((s) => s.getType() === type) || null
      }
      return null
    },
  }

  return await mountSuspended(DataSourceForm, {
    props: {
      builder: { id: 1, workspace: { id: 1 } },
      page: { id: 1 },
      integrations,
      create,
      dataSource,
      defaultValues,
    },
    global: {
      provide: {
        applicationContext: {},
      },
      stubs: {
        FormGroup: FormGroupStub,
        FormInput: FormInputStub,
        IntegrationDropdown: IntegrationDropdownStub,
        GroupedDropdown: GroupedDropdownStub,
        DataSourceTestForm: {
          name: 'DataSourceTestForm',
          template: '<div class="data-source-test-form-stub" />',
        },
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
    const actionDropdown = wrapper.findComponent(GroupedDropdownStub)

    expect(actionDropdown.props('panelHeight')).toBe('240px')
    expect(actionDropdown.props('items')).toEqual([
      {
        id: 'integration-local_baserow',
        label: 'Local Baserow',
        image: '/local-baserow.svg',
        icon: 'iconoir-database',
        iconColor: 'darker-blue',
        children: [
          {
            id: 'service-local_baserow_get_row',
            label: 'Get row',
            value: 'local_baserow_get_row',
            icon: 'iconoir-pin',
            iconColor: 'darker-blue',
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
      .findComponent(GroupedDropdownStub)
      .vm.$emit('update:modelValue', serviceType.getType())
    await nextTick()

    const connectionDropdown = wrapper.findComponent(IntegrationDropdownStub)
    expect(connectionDropdown.props('integrations')).toEqual([
      { id: 1, type: 'local_baserow' },
    ])
    expect(connectionDropdown.props('modelValue')).toBe(1)
  })

  test('groups service types without an integration under their own group', async () => {
    const wrapper = await mountComponent({
      serviceTypes: [serviceType, httpServiceType, hiddenServiceType],
    })
    const items = wrapper.findComponent(GroupedDropdownStub).props('items')

    expect(items.map(({ id }) => id)).toEqual([
      'integration-local_baserow',
      'http',
    ])
    expect(items[1]).toEqual({
      id: 'http',
      label: 'HTTP',
      image: undefined,
      icon: 'iconoir-globe',
      iconColor: 'muted-cyan',
      children: [
        {
          id: 'service-http_get',
          label: 'HTTP request',
          value: 'http_get',
          icon: 'iconoir-globe',
          iconColor: 'muted-cyan',
          description: 'Fetches data from a URL.',
          disabled: false,
          disabledReason: null,
        },
      ],
    })
  })

  test('hides the connection dropdown for a service without an integration', async () => {
    const wrapper = await mountComponent({
      serviceTypes: [serviceType, httpServiceType],
    })
    expect(wrapper.findComponent(IntegrationDropdownStub).exists()).toBe(true)

    wrapper
      .findComponent(GroupedDropdownStub)
      .vm.$emit('update:modelValue', httpServiceType.getType())
    await nextTick()

    expect(wrapper.findComponent(IntegrationDropdownStub).exists()).toBe(false)
  })

  test('shows the service and test forms of a data source without an integration', async () => {
    const dataSource = {
      id: 3,
      name: 'Products',
      type: 'http_get',
      integration_id: null,
    }
    const wrapper = await mountComponent({
      serviceTypes: [serviceType, httpServiceType],
      create: false,
      dataSource,
      defaultValues: dataSource,
    })
    await nextTick()

    expect(wrapper.find('.service-form-stub').exists()).toBe(true)
    expect(wrapper.find('.data-source-test-form-stub').exists()).toBe(true)
  })
})
