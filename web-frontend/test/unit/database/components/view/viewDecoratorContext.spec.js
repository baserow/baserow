import ViewDecoratorContext from '@baserow/modules/database/components/view/ViewDecoratorContext'
import { DecoratorValueProviderType } from '@baserow/modules/database/decoratorValueProviders'
import { ViewDecoratorType } from '@baserow/modules/database/viewDecorators'

import { MockServer } from '@baserow/test/fixtures/mockServer'
import MockAdapter from 'axios-mock-adapter'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { h } from 'vue'

export class FakeDecoratorType extends ViewDecoratorType {
  static getType() {
    return 'fake_decorator'
  }

  getName() {
    return 'Fake decorator'
  }

  getDescription() {
    return 'Fake decorator description'
  }

  getImage() {
    return 'fake/url.png'
  }

  isCompatible(view) {
    return true
  }

  isDeactivated(workspaceId) {
    return false
  }

  getDeactivatedText() {
    return 'unavailability reason'
  }

  getComponent() {
    return (props) => h('div', `fake_decoration: ${props.value}`)
  }

  canAdd({ view }) {
    return [true]
  }
}

export class FakeValueProviderType extends DecoratorValueProviderType {
  static getType() {
    return 'fake_value_provider_type'
  }

  getName() {
    return 'Fake value provider'
  }

  getDescription() {
    return 'Fake value provider description.'
  }

  getIconClass() {
    return 'iconoir-filter'
  }

  isCompatible() {
    return true
  }

  getFormComponent() {
    return (props) => h('div', `fake_value_provider_form`)
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
    name: 'Status',
    type: 'single_select',
    text_default: '',
    primary: false,
  },
]

const rows = [
  { id: 2, order: '2.00000000000000000000', field_2: 'Bram' },
  { id: 4, order: '2.50000000000000000000', field_2: 'foo', field_3: 'bar' },
]

describe('GridViewRows component with decoration', () => {
  let testApp = null
  let mockServer = null
  let store = null
  let wrapperToDestroy = null
  let mock = null

  beforeEach(() => {
    testApp = useNuxtApp()
    const { $store, $client, $registry } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
    mockServer = new MockServer(mock, $store)
  })

  afterEach((done) => {
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
    if (wrapperToDestroy) {
      wrapperToDestroy.unmount()
      wrapperToDestroy = null
    }
    mock.restore()
    //testApp.afterEach().then(done)
  })

  const populateStore = async ({ viewId = 1, decorations } = {}) => {
    const table = mockServer.createTable()
    const { application } = await mockServer.createAppAndWorkspace(table)
    const view = mockServer.createGridView(application, table, {
      decorations,
      viewId,
    })

    mockServer.createFields(application, table, fieldData)
    await store.dispatch('field/fetchAll', table)
    const primary = store.getters['field/getPrimary']
    const fields = store.getters['field/getAll']

    mockServer.createGridRows(view, fields, rows)
    await store.dispatch('page/view/grid/fetchInitial', {
      gridId: view.id,
      fields,
      primary,
    })
    await store.dispatch('view/fetchAll', { id: table.id })
    return { application, table, fields, view }
  }

  const mountComponent = async (props) => {
    const wrapper = await mountSuspended(ViewDecoratorContext, { props })

    await wrapper.vm.show(document.body)
    await wrapper.vm.$nextTick()

    // Allow to clean the DOM after the test
    wrapperToDestroy = wrapper

    return wrapper
  }

  test('Default component', async () => {
    const { application, table, fields, view } = await populateStore()

    const fakeDecorator = new FakeDecoratorType({ app: testApp })
    const fakeValueProvider = new FakeValueProviderType({ app: testApp })

    store.$registry.register('viewDecorator', fakeDecorator)
    store.$registry.register('decoratorValueProvider', fakeValueProvider)

    const wrapper = await mountComponent({
      database: application,
      view,
      table,
      fields,
      readOnly: false,
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('View with decoration configured', async () => {
    const { application, table, fields, view } = await populateStore({
      decorations: [
        {
          type: 'fake_decorator',
          value_provider_type: 'fake_value_provider_type',
          value_provider_conf: {},
          _: { loading: false },
        },
        {
          type: 'fake_decorator',
          value_provider_type: '',
          value_provider_conf: {},
          _: { loading: false },
        },
      ],
    })

    const fakeDecorator = new FakeDecoratorType({ app: testApp })
    const fakeValueProvider = new FakeValueProviderType({ app: testApp })

    store.$registry.register('viewDecorator', fakeDecorator)
    store.$registry.register('decoratorValueProvider', fakeValueProvider)

    const wrapper = await mountComponent({
      database: application,
      view,
      table,
      fields,
      readOnly: false,
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('Should show unavailable decorator tooltip', async () => {
    const { application, table, fields, view } = await populateStore()

    const fakeDecorator = new FakeDecoratorType({ app: testApp })
    const fakeValueProvider = new FakeValueProviderType({ app: testApp })

    fakeDecorator.isDeactivated = () => true

    store.$registry.register('viewDecorator', fakeDecorator)
    store.$registry.register('decoratorValueProvider', fakeValueProvider)

    const wrapper = await mountComponent({
      database: application,
      view,
      table,
      fields,
      readOnly: false,
    })

    await wrapper
      .find('.decorator-list > div:first-child')
      .trigger('mouseenter')

    expect(document.body).toMatchSnapshot()
  })

  test('Should show cant add decorator tooltip', async () => {
    const { application, table, fields, view } = await populateStore()

    const fakeDecorator = new FakeDecoratorType({ app: testApp })
    const fakeValueProvider = new FakeValueProviderType({ app: testApp })

    fakeDecorator.canAdd = () => [false, "can't be added reason"]

    store.$registry.register('viewDecorator', fakeDecorator)
    store.$registry.register('decoratorValueProvider', fakeValueProvider)

    const wrapper = await mountComponent({
      database: application,
      view,
      table,
      fields,
      readOnly: false,
    })

    await wrapper
      .find('.decorator-list > div:first-child')
      .trigger('mouseenter')

    expect(document.body).toMatchSnapshot()
  })
})
