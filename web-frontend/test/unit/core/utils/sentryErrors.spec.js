import { isSilencedErrorMessage } from '@baserow/modules/core/utils/sentryErrors'

describe('sentryErrors', () => {
  test('silences the browser-extension "Object Not Found" rejection', () => {
    expect(
      isSilencedErrorMessage(
        'Non-Error promise rejection captured with value: Object Not Found ' +
          'Matching Id:1, MethodName:update, ParamCount:4'
      )
    ).toBe(true)
  })

  test('does not silence a first-party error message', () => {
    expect(
      isSilencedErrorMessage('TypeError: cannot read property x of undefined')
    ).toBe(false)
  })
})
