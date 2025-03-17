import { TestApp } from '@baserow/test/helpers/testApp'
import PublicGrid from '@baserow/modules/database/pages/publicView'
import { getCookiesInstance } from '@baserow/modules/core/utils/cookies'

// Mock out debounce so we dont have to wait or simulate waiting for the various
// debounces in the search functionality.
jest.mock('lodash/debounce', () => jest.fn((fn) => fn))

describe('Public View Page Tests', () => {
  let testApp = null
  let mockServer = null
  let cookiesInstance = null
  beforeAll(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
    cookiesInstance = getCookiesInstance()
    // Setting HAS_DOCUMENT_COOKIE to false to indicate that we're in a test environment
    // where document.cookie is not available (Node.js). This makes the cookie implementation
    // use a mock/alternative storage mechanism instead of the browser's document.cookie API.
    cookiesInstance.HAS_DOCUMENT_COOKIE = false
  })

  afterEach(() => testApp.afterEach())

  test('Can see a publicly shared grid view', async () => {
    const slug = 'testSlug'
    const gridViewName = 'my public grid view name'
    givenAPubliclySharedGridViewWithSlug(gridViewName, slug)

    const publicGridViewPage = await testApp.mount(PublicGrid, {
      asyncDataParams: {
        slug,
      },
    })

    expect(publicGridViewPage.html()).toContain(gridViewName)
    expect(publicGridViewPage.element).toMatchSnapshot()
  })

  test('Publicly shared view is not saved as a last visited view', async () => {
    const slug = 'testSlug'
    const gridViewName = 'my public grid view name'
    givenAPubliclySharedGridViewWithSlug(gridViewName, slug)

    await testApp.mount(PublicGrid, {
      asyncDataParams: {
        slug,
      },
    })

    const cookieValue = cookiesInstance.get('defaultViewId')
    expect(cookieValue.length).toBe(0)
  })

  function givenAPubliclySharedGridViewWithSlug(name, slug) {
    const fields = [
      {
        id: 0,
        name: 'Name',
        type: 'text',
        primary: true,
      },
      {
        id: 1,
        name: 'Last name',
        type: 'text',
      },
      {
        id: 2,
        name: 'Notes',
        type: 'long_text',
      },
      {
        id: 3,
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
