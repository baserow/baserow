import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewGroupByBanner from '@baserow/modules/database/components/view/grid/GridViewGroupByBanner'

describe('GridViewGroupByBanner component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountBanner = (field, { path, display }) =>
    testApp.mount(GridViewGroupByBanner, {
      props: {
        groupByFields: [field],
        item: {
          depth: 0,
          path,
          display,
          rowCount: 1,
          collapsed: false,
          y: 0,
          height: 48,
        },
        includeRowDetails: true,
        primaryFieldWidth: 200,
        width: 300,
        workspaceId: null,
      },
    })

  test('renders the collaborator name from the backend display value', async () => {
    const field = { id: 1, type: 'multiple_collaborators', name: 'People' }
    const wrapper = await mountBanner(field, {
      path: { field_1: [10] },
      display: { field_1: [{ id: 10, name: 'Davide' }] },
    })

    expect(wrapper.text()).toContain('Davide')
    // The raw collaborator id must no longer leak into the header.
    expect(wrapper.text()).not.toContain('10')
  })

  test('renders the linked row primary value from the backend display value', async () => {
    const field = { id: 2, type: 'link_row', name: 'Links' }
    const wrapper = await mountBanner(field, {
      path: { field_2: [5] },
      display: { field_2: [{ id: 5, value: 'Row A' }] },
    })

    expect(wrapper.text()).toContain('Row A')
  })

  test('renders the single select value from the backend display value', async () => {
    const field = {
      id: 3,
      type: 'single_select',
      name: 'Status',
      select_options: [],
    }
    const wrapper = await mountBanner(field, {
      path: { field_3: 7 },
      display: { field_3: { id: 7, value: 'Open', color: 'blue' } },
    })

    expect(wrapper.text()).toContain('Open')
  })

  test('renders the multiple select values from the backend display value', async () => {
    const field = {
      id: 5,
      type: 'multiple_select',
      name: 'Tags',
      select_options: [],
    }
    const wrapper = await mountBanner(field, {
      path: { field_5: [7, 8] },
      display: {
        field_5: [
          { id: 7, value: 'Red', color: 'red' },
          { id: 8, value: 'Blue', color: 'blue' },
        ],
      },
    })

    expect(wrapper.text()).toContain('Red')
    expect(wrapper.text()).toContain('Blue')
  })

  test('renders a scalar field from the path value when no display is present', async () => {
    const field = { id: 4, type: 'text', name: 'Title' }
    const wrapper = await mountBanner(field, {
      path: { field_4: 'hello world' },
      display: undefined,
    })

    expect(wrapper.text()).toContain('hello world')
  })
})
