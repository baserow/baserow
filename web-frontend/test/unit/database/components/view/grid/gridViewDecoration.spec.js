import { TestApp } from '@baserow/test/helpers/testApp'
import GridView from '@baserow/modules/database/components/view/grid/GridView'
import { DecoratorValueProviderType } from '@baserow/modules/database/decoratorValueProviders'
import { ViewDecoratorType } from '@baserow/modules/database/viewDecorators'
import { h } from 'vue'

export class FakeDecoratorType extends ViewDecoratorType {
  static getType() {
    return 'fake_decorator'
  }

  getPlace() {
    return 'first_cell'
  }

  isDeactivated(workspaceId) {
    return false
  }

  getComponent() {
    return (props) => h('div', `fake_decoration: ${props.value}`)
  }
}

export class FakeValueProviderType extends DecoratorValueProviderType {
  static getType() {
    return 'fake_value_provider_type'
  }

  getValue({ options, fields, row }) {
    return 'fake_value'
  }

  getComponent() {
    return () => h('div', `fake_value_provider_form`)
  }
}

const fieldData = [
  {
    id: 1,
    name: 'Name',
    order: 0,
    type: 'text',
    primary: true,
    text_default: '',
  },
  {
    id: 2,
    name: 'Surname',
    type: 'text',
    text_default: '',
    primary: false,
  },
  {
    id: 3,
    name: 'Address',
    type: 'text',
    text_default: '',
    primary: false,
  },
]

const rows = [
  {
    id: 2,
    order: '2.00000000000000000000',
    field_1: 'first',
    field_2: 'Bram',
  },
  {
    id: 4,
    order: '2.50000000000000000000',
    field_1: 'second',
    field_2: 'foo',
    field_3: 'bar',
  },
]

describe('GridView component with decoration', () => {
  let testApp = null
  let mockServer = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach(async () => {
    await testApp.afterEach()
    // Clean up potentially registered stuff
    try {
      store.$registry.unregister('viewDecorator', 'fake_decorator')
    } catch {
      /* empty */
    }
    try {
      store.$registry.unregister(
        'decoratorValueProvider',
        'fake_value_provider_type'
      )
    } catch {
      /* empty */
    }
  })

  const mountComponent = async (props, slots = {}) => {
    const attachTo = document.body
    const result = await testApp.mount(GridView, {
      attachTo,
      props,
      slots,
    })
    await nextTick()
    return result
  }

  const populateStore = async (decorations) => {
    const table = mockServer.createTable()
    const { application } = await mockServer.createAppAndWorkspace(table)
    const view = mockServer.createGridView(application, table, {
      decorations,
    })
    mockServer.createFields(application, table, fieldData)
    await store.dispatch('field/fetchAll', table)
    const primary = store.getters['field/getPrimary']
    const fields = store.getters['field/getAll']

    mockServer.createGridRows(view, fields, rows)
    await store.dispatch('page/view/grid/fetchInitial', {
      gridId: 1,
      fields,
      primary,
    })
    await store.dispatch('view/fetchAll', { id: 1 })
    return { application, table, fields, view }
  }

  test('Default component with first_cell decoration', async () => {
    const { application, table, fields, view } = await populateStore([
      {
        type: 'fake_decorator',
        value_provider_type: 'fake_value_provider_type',
        value_provider_conf: {},
      },
      {
        type: 'fake_decorator',
        value_provider_type: 'fake_value_provider_type',
        value_provider_conf: {},
      },
    ])

    const fakeDecorator = new FakeDecoratorType({ app: testApp })
    const fakeValueProvider = new FakeValueProviderType({ app: testApp })

    store.$registry.register('viewDecorator', fakeDecorator)
    store.$registry.register('decoratorValueProvider', fakeValueProvider)

    const wrapper1 = await mountComponent({
      database: application,
      table,
      view,
      fields,
      readOnly: false,
      storePrefix: 'page/',
      row: null,
    })

    expect(wrapper1.element).toMatchSnapshot()
  })

  test('Default component with row wrapper decoration', async () => {
    const { application, table, fields, view } = await populateStore([
      {
        type: 'fake_decorator',
        value_provider_type: 'fake_value_provider_type',
        value_provider_conf: {},
      },
      {
        type: 'fake_decorator',
        value_provider_type: 'fake_value_provider_type',
        value_provider_conf: {},
      },
    ])

    const fakeDecorator = new FakeDecoratorType({ app: testApp })
    const fakeValueProvider = new FakeValueProviderType({ app: testApp })

    fakeDecorator.getPlace = () => 'wrapper'
    fakeDecorator.getComponent = () => {
      return {
        name: 'FakeDecorator',
        setup(_, { slots }) {
          return () =>
            h(
              'div',
              { class: 'test-wrapper' },
              slots.default ? slots.default() : []
            )
        },
      }
    }

    store.$registry.register('viewDecorator', fakeDecorator)
    store.$registry.register('decoratorValueProvider', fakeValueProvider)

    const wrapper1 = await mountComponent({
      database: application,
      table,
      view,
      fields,
      readOnly: false,
      storePrefix: 'page/',
      row: null,
    })

    expect(wrapper1.element).toMatchSnapshot()
  })

  test('Default component with unavailable decoration', async () => {
    const { application, table, fields, view } = await populateStore([
      {
        type: 'fake_decorator',
        value_provider_type: 'fake_value_provider_type',
        value_provider_conf: {},
      },
    ])

    const fakeDecorator = new FakeDecoratorType({ app: testApp })
    const fakeValueProvider = new FakeValueProviderType({ app: testApp })

    fakeDecorator.isDeactivated = () => true

    store.$registry.register('viewDecorator', fakeDecorator)
    store.$registry.register('decoratorValueProvider', fakeValueProvider)

    const wrapper1 = await mountComponent({
      database: application,
      table,
      view,
      fields,
      readOnly: false,
      storePrefix: 'page/',
      row: null,
    })

    expect(wrapper1.element).toMatchSnapshot()
  })
})
