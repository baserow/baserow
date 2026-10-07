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

describe('service form following and derived values', () => {
  test('a save that fills in backend-derived values does not remount', () => {
    const self = component()
    const tool = {
      id: 3,
      service_type: 'local_baserow_upsert_row',
      service: { table_id: null, schema: null, sample_data: null },
    }
    self.followService(tool)
    // The form echoes the derived keys as it received them and changes the
    // table; the save answers with the table's schema filled in.
    self.formValues[3] = { table_id: 856, schema: null, sample_data: null }
    self.followService({
      ...tool,
      service: {
        table_id: 856,
        schema: { properties: { field_1: {} } },
        sample_data: null,
      },
    })
    expect(self.serviceFormKey(tool)).toBe('3-local_baserow_upsert_row-0')

    // A real change by someone else still remounts.
    self.followService({
      ...tool,
      service: { table_id: 857, schema: {}, sample_data: null },
    })
    expect(self.serviceFormKey(tool)).toBe('3-local_baserow_upsert_row-1')
  })
})

describe('service form following and own saves', () => {
  test("the response to this section's own save never remounts", async () => {
    const self = component()
    const tool = {
      id: 4,
      service_type: 'local_baserow_upsert_row',
      service: { field_mappings: [] },
    }
    self.followService(tool)
    // The form enabled a mapping; the server answers with the normalized
    // mapping while the save is still awaited.
    self.formValues[4] = {
      field_mappings: [{ field_id: 1, enabled: true, value: { formula: '' } }],
    }
    await self.ownSave(tool, async () => {
      expect(self.isSaving(tool)).toBe(true)
      self.followService({
        ...tool,
        service: {
          field_mappings: [
            {
              field_id: 1,
              enabled: true,
              value: { formula: '', mode: 'simple', version: '0.1' },
              trashed: false,
            },
          ],
        },
      })
    })
    expect(self.serviceFormKey(tool)).toBe('4-local_baserow_upsert_row-0')
    expect(self.ownSaves[4]).toBe(0)
    expect(self.isSaving(tool)).toBe(false)

    // Outside a save, the same kind of change is someone else's.
    self.followService({ ...tool, service: { field_mappings: [] } })
    expect(self.serviceFormKey(tool)).toBe('4-local_baserow_upsert_row-1')
  })
})
