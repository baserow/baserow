import { TestApp } from '@baserow/test/helpers/testApp'
import LocalBaserowUpsertRowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowUpsertRowServiceForm'

const WORKSPACE = { id: 1 }
const DATABASES = [
  { id: 100, name: 'Customers', tables: [{ id: 1, name: 'Contacts' }] },
]
const serviceType = { supportedTables: (tables) => tables }

describe('LocalBaserowUpsertRowServiceForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountForm = async (props = {}) =>
    testApp.mount(LocalBaserowUpsertRowServiceForm, {
      props: {
        application: { id: 1, integrations: [] },
        serviceType,
        service: {},
        defaultValues: {},
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

  describe('the table loading spinner', () => {
    test('a table change raises it by default, as the builder expects', async () => {
      // The builder, automation and dashboard callers save the service on a
      // table change and toggle `loading` around that round trip, which is
      // what lowers the spinner again. Nothing here may change for them.
      const wrapper = await mountForm({ databases: DATABASES })

      await chooseTable(wrapper, 1)

      expect(wrapper.vm.tableLoading).toBe(true)
      expect(wrapper.find('.loading-spinner').exists()).toBe(true)
      expect(
        wrapper.findComponent({ name: 'FieldMappingsForm' }).exists()
      ).toBe(false)
    })

    test('a caller that does not save on a table change opts out', async () => {
      // The button field's action editor buffers its changes until the field
      // form is submitted, so no round trip happens and `loading` is never
      // passed. Raising the spinner there would leave it spinning forever and
      // keep the field mappings form permanently unmounted.
      const wrapper = await mountForm({
        databases: DATABASES,
        savesOnTableChange: false,
      })

      await chooseTable(wrapper, 1)

      expect(wrapper.vm.tableLoading).toBe(false)
      expect(wrapper.find('.loading-spinner').exists()).toBe(false)
      expect(
        wrapper.findComponent({ name: 'FieldMappingsForm' }).exists()
      ).toBe(true)
    })
  })

  describe('the "choose a table" message', () => {
    test('it is shown while no table is chosen', async () => {
      const wrapper = await mountForm({ databases: DATABASES, service: {} })

      expect(wrapper.text()).toContain('noTableSelectedMessage')
    })

    test('it is hidden once the service has a table', async () => {
      // The message used to test `values.table_id`, which this form never
      // populates: `allowedValues` is `['field_mappings']`, so the form mixin
      // copies nothing else out of `defaultValues`. The condition has to test
      // the service, which is the object that actually carries the table.
      const wrapper = await mountForm({
        databases: DATABASES,
        service: { table_id: 1 },
        defaultValues: { table_id: 1 },
      })

      expect(wrapper.vm.values.table_id).toBeUndefined()
      expect(wrapper.text()).not.toContain('noTableSelectedMessage')
    })

    test('it stays hidden for a caller with no databases and no integration', async () => {
      // The regression guard for the builder, automation and dashboard: with
      // no `databases` prop the message must remain unreachable, exactly as
      // it was before the prop existed.
      const wrapper = await mountForm({ service: { table_id: 1 } })

      expect(wrapper.text()).not.toContain('noTableSelectedMessage')
    })
  })
})
