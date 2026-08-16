import { TestApp } from '@baserow/test/helpers/testApp'
import LocalBaserowGetRowForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowGetRowForm'

const WORKSPACE = { id: 1 }
// This form keeps the view picker, so the table selector reads `views`.
const DATABASES = [
  {
    id: 100,
    name: 'Customers',
    tables: [{ id: 1, name: 'Contacts' }],
    views: [],
  },
]
const serviceType = { supportedTables: (tables) => tables }

describe('LocalBaserowGetRowForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountForm = async (props = {}) =>
    testApp.mount(LocalBaserowGetRowForm, {
      props: {
        application: { id: 1, integrations: [] },
        serviceType,
        service: {},
        defaultValues: {},
        databases: DATABASES,
        ...props,
      },
      global: { provide: { workspace: WORKSPACE } },
    })

  const chooseTable = async (wrapper, tableId) => {
    const selector = wrapper.findComponent({
      name: 'LocalBaserowTableSelector',
    })
    selector.vm.onTableSelect(tableId)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
  }

  const rowIdInput = (wrapper) =>
    wrapper.findComponent({ name: 'InjectedFormulaInput' })

  test('a chosen table offers the row id to fetch', async () => {
    // The form used to gate this on an integration it no longer carries, so
    // the input never appeared and the data source could not be configured.
    const wrapper = await mountForm()

    await chooseTable(wrapper, 1)

    expect(rowIdInput(wrapper).exists()).toBe(true)
  })

  test('with no table chosen there is no row to ask for', async () => {
    const wrapper = await mountForm()

    expect(rowIdInput(wrapper).exists()).toBe(false)
  })
})
