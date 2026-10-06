import {
  serviceFollowState,
  serviceFollowMethods,
} from '@baserow_enterprise/utils/agentServiceFollow'

function component(pending = {}) {
  const methods = serviceFollowMethods({
    pendingFor(item) {
      return pending[item.id] || {}
    },
  })
  const self = { ...serviceFollowState(), ...methods }
  return self
}

describe('service form following', () => {
  test('the form is remounted when the saved service diverges from it', () => {
    const self = component()
    const trigger = {
      id: 1,
      service_type: 'periodic',
      service: { interval: 'DAY' },
    }
    self.followService(trigger)
    expect(self.serviceFormKey(trigger)).toBe('1-periodic-0')

    // The form reported its values; a save echoing them changes nothing.
    self.formValues[1] = { interval: 'HOUR', hour: 9 }
    self.followService({ ...trigger, service: { interval: 'HOUR' } })
    expect(self.serviceFormKey(trigger)).toBe('1-periodic-0')

    // An undo reverts the saved value: the form must follow.
    self.followService({ ...trigger, service: { interval: 'DAY' } })
    expect(self.serviceFormKey(trigger)).toBe('1-periodic-1')
    expect(self.formValues[1]).toBeUndefined()
  })

  test('a form that never emitted follows a remote change too', () => {
    const self = component()
    const trigger = {
      id: 1,
      service_type: 'periodic',
      service: { interval: 'DAY' },
    }
    self.followService(trigger)
    self.followService(trigger)
    expect(self.serviceFormKey(trigger)).toBe('1-periodic-0')
    self.followService({ ...trigger, service: { interval: 'WEEK' } })
    expect(self.serviceFormKey(trigger)).toBe('1-periodic-1')
  })

  test('unsaved typing is never thrown away', () => {
    const pending = { 1: { interval: 'WEEK' } }
    const self = component(pending)
    const trigger = {
      id: 1,
      service_type: 'periodic',
      service: { interval: 'DAY' },
    }
    self.followService(trigger)
    // The debounced save lands: the server now holds what is being typed.
    self.followService({ ...trigger, service: { interval: 'WEEK' } })
    expect(self.serviceFormKey(trigger)).toBe('1-periodic-0')
  })
})
