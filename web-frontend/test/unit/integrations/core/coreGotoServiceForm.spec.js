import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import CoreGotoServiceForm from '@baserow/modules/integrations/core/components/services/CoreGotoServiceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  template: '<div><slot /></div>',
})

const DropdownStub = defineComponent({
  name: 'Dropdown',
  props: {
    modelValue: {
      type: Number,
      required: false,
      default: null,
    },
  },
  emits: ['update:modelValue'],
  template: '<div><slot /></div>',
})

const DropdownItemStub = defineComponent({
  name: 'DropdownItem',
  props: {
    name: {
      type: String,
      required: true,
    },
    value: {
      type: Number,
      required: true,
    },
  },
  template: '<div />',
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: {
      required: false,
      default: null,
    },
  },
  emits: ['update:modelValue'],
  template: '<div />',
})

async function mountComponent({ destinations = [], defaultValues = {} } = {}) {
  return await mountSuspended(CoreGotoServiceForm, {
    props: {
      destinations,
      defaultValues,
    },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        Dropdown: DropdownStub,
        DropdownItem: DropdownItemStub,
        InjectedFormulaInput: InjectedFormulaInputStub,
      },
      mocks: {
        $t: (key) => key,
      },
    },
  })
}

describe('CoreGotoServiceForm destinations rendering', () => {
  test('renders a dropdown item per provided destination', async () => {
    const destinations = [
      { value: 12, name: 'Before node' },
      { value: 14, name: 'After node' },
    ]
    const wrapper = await mountComponent({ destinations })
    await flushPromises()

    const items = wrapper.findAllComponents({ name: 'DropdownItem' })
    expect(items.map((item) => item.props('value'))).toEqual([12, 14])
    expect(items.map((item) => item.props('name'))).toEqual([
      'Before node',
      'After node',
    ])
  })

  test('renders no dropdown items when there are no destinations', async () => {
    const wrapper = await mountComponent({ destinations: [] })
    await flushPromises()

    expect(wrapper.findAllComponents({ name: 'DropdownItem' })).toHaveLength(0)
  })

  test('seeds the selected destination from the saved service value', async () => {
    const wrapper = await mountComponent({
      destinations: [{ value: 14, name: 'After node' }],
      defaultValues: { condition: {}, destination_service_id: 14 },
    })
    await flushPromises()

    expect(wrapper.vm.values.destination_service_id).toBe(14)
  })
})

describe('CoreGotoServiceForm service watcher', () => {
  const watcher = CoreGotoServiceForm.watch.service

  test('adopts an externally cleared destination into the form values', () => {
    // The store cleared the link (a move took the destination off the goto's path).
    const ctx = { values: { destination_service_id: 2 } }
    watcher.call(ctx, { destination_service_id: null })
    expect(ctx.values.destination_service_id).toBeNull()
  })

  test('leaves the form values untouched when nothing changed', () => {
    const values = { destination_service_id: 2 }
    const ctx = { values }
    watcher.call(ctx, { destination_service_id: 2 })
    // Same reference, unchanged — no redundant write that could loop.
    expect(ctx.values).toBe(values)
    expect(ctx.values.destination_service_id).toBe(2)
  })

  test('treats a missing service as no destination', () => {
    const ctx = { values: { destination_service_id: 2 } }
    watcher.call(ctx, null)
    expect(ctx.values.destination_service_id).toBeNull()
  })
})
