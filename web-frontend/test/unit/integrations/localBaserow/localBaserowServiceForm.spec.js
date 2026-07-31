import { TestApp } from '@baserow/test/helpers/testApp'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

const serviceType = { supportedTables: (tables) => tables }

describe('LocalBaserowServiceForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountForm = async (props = {}) =>
    testApp.mount(LocalBaserowServiceForm, {
      props: {
        // An application with no integrations, as the builder and automation
        // see it before one is picked.
        application: { id: 1, integrations: [] },
        serviceType,
        defaultValues: {},
        ...props,
      },
    })

  test('without a databases prop and no integration there is no table selector', async () => {
    const wrapper = await mountForm()

    // The guard for the builder, automation and dashboard callers: nothing
    // about the new `databases` prop may make the table selector appear
    // before an integration has been chosen.
    expect(
      wrapper.findComponent({ name: 'LocalBaserowTableSelector' }).exists()
    ).toBe(false)
  })

  test('an explicit databases prop renders the table selector', async () => {
    const wrapper = await mountForm({
      databases: [
        { id: 100, name: 'Customers', tables: [{ id: 1, name: 'Contacts' }] },
      ],
    })

    const selector = wrapper.findComponent({
      name: 'LocalBaserowTableSelector',
    })
    expect(selector.exists()).toBe(true)
    expect(selector.props('databases')).toHaveLength(1)
  })
})
