import { CoreResponseServiceType } from '@baserow/modules/integrations/core/serviceTypes'

describe('CoreResponseServiceType', () => {
  const serviceType = new CoreResponseServiceType({
    app: { $i18n: { t: (key) => key } },
  })

  test.each([
    [{ body_type: 'json', body: {} }, 'serviceType.errorResponseBodyMissing'],
    [
      { body_type: 'json', body: { formula: '' } },
      'serviceType.errorResponseBodyMissing',
    ],
    [
      { body_type: 'json', body: { formula: ' ' } },
      'serviceType.errorResponseBodyMissing',
    ],
    [{ body_type: 'json', body: { formula: "'{}'" } }, null],
    [{ body_type: 'text', body: { formula: '' } }, null],
    [{ body_type: 'empty', body: { formula: '' } }, null],
  ])(
    'reports whether the response body is misconfigured',
    (service, message) => {
      expect(serviceType.getErrorMessage({ service })).toBe(message)
      expect(serviceType.isInError({ service })).toBe(Boolean(message))
    }
  )
})
