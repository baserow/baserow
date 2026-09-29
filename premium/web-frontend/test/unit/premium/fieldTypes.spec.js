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

  describe('rich text output', () => {
    const richTextField = {
      type: 'ai',
      ai_output_type: 'text',
      long_text_enable_rich_text: true,
    }
    const plainTextField = {
      ...richTextField,
      long_text_enable_rich_text: false,
    }
    const choiceField = {
      type: 'ai',
      ai_output_type: 'choice',
      select_options: [
        { id: 1, value: 'Yes', color: 'green' },
        { id: 2, value: 'No', color: 'red' },
      ],
    }

    test('only a text output with the flag is rich text', () => {
      const aiFieldType = registry.get('field', 'ai')

      expect(aiFieldType.hasRichTextOutput(richTextField)).toBe(true)
      expect(aiFieldType.hasRichTextOutput(plainTextField)).toBe(false)
      expect(
        aiFieldType.hasRichTextOutput({
          ...choiceField,
          long_text_enable_rich_text: true,
        })
      ).toBe(false)
    })

    test('reserves the card height of the output card', () => {
      const aiFieldType = registry.get('field', 'ai')
      const longTextFieldType = registry.get('field', 'long_text')

      expect(aiFieldType.getCardValueHeight(richTextField)).toBe(
        longTextFieldType.getCardValueHeight(richTextField)
      )
      expect(aiFieldType.getCardValueHeight(plainTextField)).toBe(
        longTextFieldType.getCardValueHeight(plainTextField)
      )
      expect(aiFieldType.getCardValueHeight(choiceField)).toBe(
        registry.get('field', 'single_select').getCardValueHeight(choiceField)
      )
      expect(aiFieldType.getCardValueHeight(richTextField)).not.toBe(
        aiFieldType.getCardValueHeight(plainTextField)
      )
    })

    test('copies and pastes Markdown unchanged between rich text values', () => {
      const aiFieldType = registry.get('field', 'ai')
      const copied = aiFieldType.prepareRichValueForCopy(
        richTextField,
        '# Title\n\n**bold**'
      )

      expect(
        aiFieldType.prepareValueForPaste(
          richTextField,
          '# Title\n\n**bold**',
          copied
        )
      ).toBe('# Title\n\n**bold**')
    })

    test('pastes a rich long text value into a plain AI text field as text', () => {
      const aiFieldType = registry.get('field', 'ai')
      const copied = registry
        .get('field', 'long_text')
        .prepareRichValueForCopy(
          { type: 'long_text', long_text_enable_rich_text: true },
          'one  \ntwo'
        )

      expect(
        aiFieldType.prepareValueForPaste(plainTextField, 'one  \ntwo', copied)
      ).toBe('one\ntwo')
    })

    test('pastes a choice by its name, ignoring the option id of another field', () => {
      const aiFieldType = registry.get('field', 'ai')
      const otherFieldOption = { id: 99, value: 'No', color: 'red' }

      expect(
        aiFieldType.prepareRichValueForCopy(choiceField, otherFieldOption)
      ).toBe('No')
      expect(
        aiFieldType.prepareValueForPaste(choiceField, 'No', otherFieldOption)
      ).toEqual(choiceField.select_options[1])
    })

    test('documents that a rich text value is Markdown', () => {
      const aiFieldType = registry.get('field', 'ai')

      expect(aiFieldType.getDocsDescription(richTextField)).toBe(
        'premiumFieldType.aiRichTextDescription'
      )
      expect(aiFieldType.getDocsDescription(plainTextField)).toBe(
        'premiumFieldType.aiDescription'
      )
      expect(
        aiFieldType.getDocsDescription({
          ...choiceField,
          long_text_enable_rich_text: true,
        })
      ).toBe('premiumFieldType.aiDescription')
    })
  })

  test('availability respects feature eligibility', () => {
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
