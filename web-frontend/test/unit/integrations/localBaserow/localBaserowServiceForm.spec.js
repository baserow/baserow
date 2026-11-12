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

  test('it picks a table and leaves the integration to its wrapper', async () => {
    const wrapper = await mountForm()

    // Choosing the integration belongs to the wrapper of the application type
    // this form is rendered in, so the form itself never offers one.
    expect(
      wrapper.findComponent({ name: 'IntegrationDropdown' }).exists()
    ).toBe(false)
    expect(
      wrapper.findComponent({ name: 'LocalBaserowTableSelector' }).exists()
    ).toBe(true)
  })

  test('with no databases the table selector has nothing to offer', async () => {
    const wrapper = await mountForm()

    expect(
      wrapper
        .findComponent({ name: 'LocalBaserowTableSelector' })
        .props('databases')
    ).toEqual([])
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

  test('choosing another table clears the view of the previous table', async () => {
    const wrapper = await mountForm({
      databases: [
        {
          id: 100,
          name: 'Customers',
          tables: [
            { id: 1, name: 'Contacts' },
            { id: 2, name: 'Companies' },
          ],
          views: [{ id: 10, table_id: 1, name: 'Active contacts' }],
        },
      ],
      defaultValues: { table_id: 1, view_id: 10 },
    })

    await wrapper
      .findComponent({ name: 'LocalBaserowTableSelector' })
      .vm.$emit('update:modelValue', 2)
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('values-changed')
    expect(emitted[emitted.length - 1][0]).toMatchObject({
      table_id: 2,
      view_id: null,
    })
  })

  test('resetting to restored values keeps their view', async () => {
    const databases = [
      {
        id: 100,
        name: 'Customers',
        tables: [
          { id: 1, name: 'Contacts' },
          { id: 2, name: 'Companies' },
        ],
        views: [
          { id: 10, table_id: 1, name: 'Active contacts' },
          { id: 20, table_id: 2, name: 'Big companies' },
        ],
      },
    ]
    const wrapper = await mountForm({
      databases,
      defaultValues: { table_id: 1, view_id: 10 },
    })

    // Like after an undo, which restores another table and its view.
    await wrapper.setProps({ defaultValues: { table_id: 2, view_id: 20 } })
    await wrapper.vm.reset()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.values).toMatchObject({ table_id: 2, view_id: 20 })
  })
})
