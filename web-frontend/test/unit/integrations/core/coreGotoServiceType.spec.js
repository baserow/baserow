import { CoreGotoServiceType } from '@baserow/modules/integrations/core/serviceTypes'

describe('CoreGotoServiceType', () => {
  const makeServiceType = () =>
    new CoreGotoServiceType({
      app: {
        $i18n: { t: (key) => key },
        $registry: { get: () => ({}) },
      },
    })

  test('getType is goto', () => {
    expect(CoreGotoServiceType.getType()).toBe('goto')
  })

  test('icon is the long arrow up right icon', () => {
    expect(makeServiceType().icon).toBe('iconoir-long-arrow-up-right')
  })

  test('getErrorMessage is null when service is undefined', () => {
    expect(makeServiceType().getErrorMessage({ service: undefined })).toBeNull()
  })

  test('getErrorMessage requires a destination node', () => {
    expect(
      makeServiceType().getErrorMessage({
        service: { destination_node_id: null },
      })
    ).toBe('serviceType.coreGotoDestinationRequired')
  })

  test('getErrorMessage passes when a destination node is set', () => {
    expect(
      makeServiceType().getErrorMessage({
        service: { destination_node_id: 42 },
      })
    ).not.toBe('serviceType.coreGotoDestinationRequired')
  })
})
