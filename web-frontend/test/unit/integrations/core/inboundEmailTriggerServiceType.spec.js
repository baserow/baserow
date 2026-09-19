import {
  CoreInboundEmailTriggerServiceType,
  CoreSMTPEmailServiceType,
} from '@baserow/modules/integrations/core/serviceTypes'

const app = {
  $i18n: {
    t: (key) => key,
  },
}

describe('CoreInboundEmailTriggerServiceType sample data', () => {
  test('returns the html sample data content type', () => {
    const serviceType = new CoreInboundEmailTriggerServiceType({ app })

    expect(serviceType.getSampleDataContentType({})).toBe('html')
  })

  test('extracts the html body from the sample data envelope', () => {
    const serviceType = new CoreInboundEmailTriggerServiceType({ app })

    expect(
      serviceType.getSampleDataHtml({
        sample_data: { data: { body_html: '<p>Hi</p>' } },
      })
    ).toBe('<p>Hi</p>')
    expect(serviceType.getSampleDataHtml({ sample_data: null })).toBe(null)
    expect(
      serviceType.getSampleDataHtml({
        sample_data: { data: { body_html: '' } },
      })
    ).toBe(null)
  })

  test('other service types default to the json content type', () => {
    const serviceType = new CoreSMTPEmailServiceType({ app })

    expect(serviceType.getSampleDataContentType({})).toBe('json')
    expect(serviceType.getSampleDataHtml({})).toBe(null)
  })
})
