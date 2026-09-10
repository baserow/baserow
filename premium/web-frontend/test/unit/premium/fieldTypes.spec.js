import { AIFieldType } from '@baserow_premium/fieldTypes'

import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'

describe('Premium AIFieldType', () => {
  let testApp = null
  let registry = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    registry = testApp.getRegistry()
  })

  afterEach(async () => {
    await testApp.afterEach()
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

  // Without this delegation the base getValidationError returns null, so an
  // over-limit value typed into an editable AI field shows no error and is sent.
  test('getValidationError delegates to the underlying output type', () => {
    const aiFieldType = registry.get('field', 'ai')
    const field = { ai_output_type: 'text' }
    const outputType = aiFieldType.getBaserowFieldType(field)
    const spy = vi
      .spyOn(outputType, 'getValidationError')
      .mockReturnValue('too long')

    expect(aiFieldType.getValidationError(field, 'x'.repeat(101))).toBe(
      'too long'
    )
    expect(spy).toHaveBeenCalledWith(field, 'x'.repeat(101))
  })

  test('availability respects feature eligibility without the retired flag', () => {
    const fieldType = new AIFieldType({
      app: { $i18n: { t: (key) => key } },
    })
    const workspace = {
      generative_ai_models_enabled: { openai: ['gpt-4'] },
      ai_features: { ai_fields: { models: {} } },
    }

    expect(fieldType.isEnabled(workspace)).toBe(false)
    expect(fieldType.isEnabled({ ...workspace, ai_features: undefined })).toBe(
      true
    )
  })
})
