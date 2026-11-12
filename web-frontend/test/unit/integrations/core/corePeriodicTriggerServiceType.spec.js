import { describe, expect, test, vi } from 'vitest'
import { ServiceType } from '@baserow/modules/core/serviceTypes'
import { CorePeriodicTriggerServiceType } from '@baserow/modules/integrations/core/serviceTypes'
import coreLocale from '@baserow/locales/en.json'
import integrationsLocale from '@baserow/modules/integrations/locales/en.json'

const makeServiceType = async () => {
  const { createI18n } = await vi.importActual('vue-i18n')
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en: { ...coreLocale, ...integrationsLocale } },
  })
  return new CorePeriodicTriggerServiceType({ app: { $i18n: i18n.global } })
}

const schedule = (values) => ({
  interval: 'DAY',
  minute: 0,
  hour: 9,
  day_of_week: 0,
  day_of_month: 1,
  timezone: 'Europe/Amsterdam',
  ...values,
})

describe('CorePeriodicTriggerServiceType', () => {
  test('names a trigger by its type while its schedule is incomplete', async () => {
    const serviceType = await makeServiceType()
    const incomplete = [
      { interval: 'MINUTE', minute: null },
      { interval: 'MINUTE', minute: 0 },
      { interval: 'HOUR', minute: null },
      { interval: 'DAY', hour: null },
      { interval: 'DAY', timezone: '' },
      { interval: 'WEEK', minute: undefined },
      { interval: 'WEEK', day_of_week: null },
      { interval: 'MONTH', timezone: null },
      { interval: 'MONTH', day_of_month: null },
    ]

    incomplete.forEach((values) => {
      expect(serviceType.getDefaultName(schedule(values))).toBe(
        'Periodic trigger'
      )
    })
  })

  test('schedules a never-scheduled service daily at 09:00', async () => {
    const serviceType = await makeServiceType()

    expect(serviceType.getDefaultValues(null, {})).toMatchObject({
      interval: 'DAY',
      hour: 9,
      minute: 0,
    })
  })

  test('keeps the schedule of a service that already has one', async () => {
    const serviceType = await makeServiceType()
    const values = schedule({ interval: 'HOUR', minute: 15 })

    expect(serviceType.getDefaultValues(values, values)).toBe(values)
  })

  test('names a service by its type unless the type words a default', () => {
    class PlainServiceType extends ServiceType {
      get name() {
        return 'Plain'
      }
    }

    expect(new PlainServiceType({ app: {} }).getDefaultName({})).toBe('Plain')
  })

  test('names a trigger by its schedule, without the timezone', async () => {
    const serviceType = await makeServiceType()
    const names = [
      { interval: 'MINUTE', minute: 1 },
      { interval: 'MINUTE', minute: 5 },
      { interval: 'HOUR', minute: 15 },
      {},
      { interval: 'WEEK', day_of_week: 2, hour: 18, minute: 30 },
      { interval: 'MONTH', day_of_month: 31, timezone: 'UTC' },
    ].map((values) => serviceType.getDefaultName(schedule(values)))

    expect(names).toEqual([
      'Every minute',
      'Every 5 minutes',
      'Every hour at minute 15',
      'Every day at 09:00',
      'Every Wednesday at 18:30',
      'On day 31 of every month at 09:00',
    ])
    expect(serviceType.getDefaultName(schedule({ interval: null }))).toBe(
      'Periodic trigger'
    )
  })
})
