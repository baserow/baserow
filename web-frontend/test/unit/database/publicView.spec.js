import { TestApp } from '@baserow/test/helpers/testApp'
import PublicGrid from '@baserow/modules/database/pages/publicView'

// Mock out debounce so we dont have to wait or simulate waiting for the various
// debounces in the search functionality.
vi.mock('lodash/debounce', () => ({ default: vi.fn((fn) => fn) }))

describe('Public View Page Tests', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(() => testApp.afterEach())

  test('Can see a publicly shared grid view', async () => {
    const slug = 'testSlug'
    const gridViewName = 'my public grid view name'
    givenAPubliclySharedGridViewWithSlug(gridViewName, slug)

    const publicGridViewPage = await testApp.mount(PublicGrid, {
      route: `/public/grid/${slug}`,
    })

    expect(publicGridViewPage.html()).toContain(gridViewName)
    expect(publicGridViewPage.element).toMatchSnapshot()
  })

  test('Publicly shared view is not saved as a last visited view', async () => {
    const slug = 'testSlug'
    const gridViewName = 'my public grid view name'
    givenAPubliclySharedGridViewWithSlug(gridViewName, slug)

    await testApp.mount(PublicGrid, {
      route: `/public/grid/${slug}`,
    })

    const cookie = useCookie('defaultViewId', {
      path: '/',
    })
    expect(cookie.value.length).toBe(0)
  })

  function givenAPubliclySharedGridViewWithSlug(name, slug) {
    mockServer.fakeSettings()

    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
      },
      {
        id: 2,
        name: 'Last name',
        type: 'text',
      },
      {
        id: 3,
        name: 'Notes',
        type: 'long_text',
      },
      {
        id: 4,
        name: 'Active',
        type: 'boolean',
      },
    ]
    const gridView = mockServer.createPublicGridView(slug, {
      name,
      fields,
    })
    mockServer.createPublicGridViewRows(slug, fields, [
      {
        id: 1,
        order: 0,
        field_1: 'name',
        field_2: 'last_name',
        field_3: 'notes',
        field_4: false,
      },
    ])

    return { gridView }
  }
})
