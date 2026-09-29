import { setAIFieldErrorFromGenerationError } from '@baserow_premium/utils/aiField'

describe('AI field generation error handling', () => {
  test('stores a model-unavailable generation error on the field', () => {
    const store = { dispatch: vi.fn() }
    const field = { id: 12, error: null }
    const error = {
      response: {
        data: {
          error: 'ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE',
          detail: 'Untranslated backend detail',
        },
      },
    }

    expect(
      setAIFieldErrorFromGenerationError(
        store,
        field,
        error,
        'Translated model unavailable message'
      )
    ).toBe(true)
    expect(store.dispatch).toHaveBeenCalledWith('field/setItemError', {
      field,
      value: 'Translated model unavailable message',
    })
  })

  test('ignores unrelated generation errors', () => {
    const store = { dispatch: vi.fn() }

    expect(
      setAIFieldErrorFromGenerationError(
        store,
        { id: 12 },
        {
          response: { data: { error: 'ERROR_OTHER' } },
        }
      )
    ).toBe(false)
    expect(store.dispatch).not.toHaveBeenCalled()
  })
})
