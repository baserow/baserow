import { CoreSMTPEmailServiceType } from '@baserow/modules/integrations/core/serviceTypes'

const app = {
  $i18n: {
    t: (key) => key,
  },
}

const service = (formula) => ({
  use_instance_smtp_settings: true,
  to_emails: { formula, mode: 'simple', version: '0.1' },
})

describe('CoreSMTPEmailServiceType recipients', () => {
  test.each(['', '   ', '\n'])(
    'recipients of only whitespace (%j) are missing',
    (formula) => {
      const serviceType = new CoreSMTPEmailServiceType({ app })

      expect(serviceType.getErrorMessage({ service: service(formula) })).toBe(
        'serviceType.errorToEmailsMissing'
      )
    }
  )

  test('a recipient formula is not missing', () => {
    const serviceType = new CoreSMTPEmailServiceType({ app })

    expect(
      serviceType.getErrorMessage({ service: service("'a@example.com'") })
    ).toBe(null)
  })
})
