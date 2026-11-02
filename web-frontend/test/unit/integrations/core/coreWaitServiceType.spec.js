import { CoreWaitServiceType } from '@baserow/modules/integrations/core/serviceTypes'

describe('CoreWaitServiceType', () => {
  const makeServiceType = () =>
    new CoreWaitServiceType({
      app: {
        $i18n: { t: (key) => key },
        $registry: { get: () => ({}) },
      },
    })

  test('getType is wait', () => {
    expect(CoreWaitServiceType.getType()).toBe('wait')
  })

  test('is a workflow action', () => {
    expect(makeServiceType().isWorkflowAction).toBe(true)
  })

  test('name and description come from the i18n labels', () => {
    const serviceType = makeServiceType()
    expect(serviceType.name).toBe('serviceType.coreWait')
    expect(serviceType.description).toBe('serviceType.coreWaitDescription')
  })

  test('icon is the timer icon', () => {
    // Written out in full: the production CSS only keeps icons it can find as
    // literal class names.
    expect(makeServiceType().icon).toBe('iconoir-timer')
  })

  test('getErrorMessage is null when service is undefined', () => {
    expect(makeServiceType().getErrorMessage({ service: undefined })).toBeNull()
  })

  test.each([
    ['no seconds at all', {}],
    ['an unset formula', { seconds: {} }],
    ['an empty formula', { seconds: { formula: '', mode: 'simple' } }],
  ])('getErrorMessage requires the seconds formula: %s', (_, service) => {
    expect(makeServiceType().getErrorMessage({ service })).toBe(
      'serviceType.coreWaitSecondsRequired'
    )
  })

  test('getErrorMessage passes when the seconds formula is set', () => {
    expect(
      makeServiceType().getErrorMessage({
        service: { seconds: { formula: '60', mode: 'simple' } },
      })
    ).toBeNull()
  })

  test('getDataSchema is the schema the backend generated', () => {
    const schema = { type: 'object', properties: { seconds: {} } }
    expect(makeServiceType().getDataSchema({ schema })).toBe(schema)
  })
})
