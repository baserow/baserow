import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'

describe('Premium AIFieldType filter delegation', () => {
  let testApp = null
  let registry = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    registry = testApp.getRegistry()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  // Guards the regression where AIFieldType only delegated the contains filter
  // functions. Without a getStartsWithFilterFunction delegation the base
  // implementation returns `() => false`, marking edited rows as non-matching
  // client-side while the backend keeps them visible.
  test('getStartsWithFilterFunction delegates to the underlying output type', () => {
    const aiFieldType = registry.get('field', 'ai')
    const field = { ai_output_type: 'text' }

    const filterFunction = aiFieldType.getStartsWithFilterFunction(field)

    expect(filterFunction('Hello world', 'Hello world', 'hello')).toBe(true)
    expect(filterFunction('Goodbye world', 'Goodbye world', 'hello')).toBe(
      false
    )
  })
})
