import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import CorePeriodicTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CorePeriodicTriggerServiceForm'

const schedule = (values) => ({
  interval: 'HOUR',
  minute: 15,
  hour: 0,
  day_of_week: 0,
  day_of_month: 1,
  timezone: 'UTC',
  ...values,
})

/**
 * Mounts the form the way the node side panel hosts it. The side panel only saves
 * a `values-changed` if the form is valid at the moment the event arrives, so
 * `received` holds every emitted schedule together with that verdict. `valid` is
 * null for the values emitted while the form is still mounting.
 *
 * `minimum` is the instance's minimum minute frequency: a string by default, as
 * the runtime config holds it, and a number once an env var overrides it.
 */
async function mountForm(defaultValues, { minimum = '2' } = {}) {
  const received = []
  let wrapper = null
  wrapper = await mountSuspended(CorePeriodicTriggerServiceForm, {
    props: {
      defaultValues,
      onValuesChanged: (values) => {
        received.push({
          ...values,
          valid: wrapper ? wrapper.vm.isFormValid() : null,
        })
      },
    },
    global: {
      mocks: {
        $t: (key, params) =>
          params ? `${key} ${JSON.stringify(params)}` : key,
        $config: {
          public: { baserowIntegrationsPeriodicMinuteMin: minimum },
        },
      },
    },
  })
  await flushPromises()
  return { wrapper, received }
}

async function chooseInterval(wrapper, name) {
  await wrapper.get('.dropdown__selected').trigger('click')
  await wrapper
    .findAll('.select__item-link')
    .find((item) => item.text().includes(name))
    .trigger('click')
  await flushPromises()
}

async function typeMinute(wrapper, minute) {
  await wrapper.get('input[type="number"]').setValue(minute)
  await flushPromises()
}

describe('CorePeriodicTriggerServiceForm', () => {
  test.each([
    { minimum: '1', minute: 1 },
    { minimum: '1', minute: 5 },
    { minimum: 15, minute: 15 },
    { minimum: 15, minute: 45 },
  ])(
    'keeps a saved frequency of $minute when it loads with a minimum of $minimum',
    async ({ minimum, minute }) => {
      const { wrapper, received } = await mountForm(
        schedule({ interval: 'MINUTE', minute }),
        { minimum }
      )

      expect(wrapper.vm.values.minute).toBe(minute)
      expect(received.every((values) => values.minute === minute)).toBe(true)
      expect(wrapper.vm.isFormValid()).toBe(true)
      expect(wrapper.find('.error').exists()).toBe(false)
    }
  )

  test.each([{ minimum: '1' }, { minimum: 15 }])(
    'starts a picked minute frequency at the minimum of $minimum and resets it when leaving',
    async ({ minimum }) => {
      const { wrapper, received } = await mountForm(schedule(), { minimum })

      await chooseInterval(wrapper, 'periodicForm.everyMinuteDefault')
      expect(received.at(-1)).toMatchObject({
        interval: 'MINUTE',
        minute: Number(minimum),
        valid: true,
      })

      await chooseInterval(wrapper, 'periodicForm.everyDay')
      expect(received.at(-1)).toMatchObject({
        interval: 'DAY',
        minute: 0,
        valid: true,
      })
    }
  )

  test.each([
    ['periodicForm.everyHour', 'HOUR'],
    ['periodicForm.everyDay', 'DAY'],
    ['periodicForm.everyWeek', 'WEEK'],
    ['periodicForm.everyMonth', 'MONTH'],
  ])(
    'hands the host one valid schedule when a minute frequency is swapped for %s',
    async (name, interval) => {
      const { wrapper, received } = await mountForm(
        schedule({ interval: 'MINUTE', minute: 20 }),
        { minimum: 15 }
      )
      received.length = 0

      await chooseInterval(wrapper, name)

      // The minute resets to 0, which is under the frequency minimum of the
      // interval that was just left. It must not be judged against that.
      expect(received).toEqual([
        expect.objectContaining({ interval, minute: 0, valid: true }),
      ])
    }
  )

  test('accepts the instance minimum and refuses a frequency under it', async () => {
    const { wrapper, received } = await mountForm(
      schedule({ interval: 'MINUTE', minute: 20 }),
      { minimum: 15 }
    )

    await typeMinute(wrapper, '15')
    expect(received.at(-1)).toMatchObject({ minute: '15', valid: true })
    expect(wrapper.find('.error').exists()).toBe(false)

    await typeMinute(wrapper, '14')
    expect(received.at(-1)).toMatchObject({ minute: '14', valid: false })
    expect(wrapper.get('.error').text()).toContain('"min":15')
  })

  test('accepts a frequency of one minute where the instance minimum is one', async () => {
    const { wrapper, received } = await mountForm(
      schedule({ interval: 'MINUTE', minute: 5 }),
      { minimum: '1' }
    )

    await typeMinute(wrapper, '1')
    expect(received.at(-1)).toMatchObject({ minute: '1', valid: true })

    await typeMinute(wrapper, '0')
    expect(received.at(-1)).toMatchObject({ minute: '0', valid: false })
    expect(wrapper.get('.error').text()).toContain('"min":1')
  })

  test('accepts minute zero past the hour whatever the frequency minimum is', async () => {
    const { wrapper, received } = await mountForm(
      schedule({ interval: 'HOUR', minute: 30 }),
      { minimum: 15 }
    )

    await typeMinute(wrapper, '0')
    expect(received.at(-1)).toMatchObject({ minute: '0', valid: true })
  })

  test('keeps and points out a saved frequency under the instance minimum', async () => {
    const { wrapper, received } = await mountForm(
      schedule({ interval: 'MINUTE', minute: 5 }),
      { minimum: 15 }
    )

    expect(wrapper.vm.values.minute).toBe(5)
    expect(received.every((values) => values.minute === 5)).toBe(true)
    expect(wrapper.vm.isFormValid()).toBe(false)
    expect(wrapper.get('.error').text()).toContain('"min":15')
  })

  test('keeps the incoming schedule when the form is reset', async () => {
    const { wrapper, received } = await mountForm(schedule({ minute: 15 }))

    await wrapper.setProps({
      defaultValues: schedule({ interval: 'MINUTE', minute: 5 }),
    })
    await wrapper.vm.reset()
    await flushPromises()
    expect(received.at(-1)).toMatchObject({ interval: 'MINUTE', minute: 5 })

    await wrapper.setProps({
      defaultValues: schedule({ interval: 'HOUR', minute: 30 }),
    })
    await wrapper.vm.reset()
    await flushPromises()
    expect(received.at(-1)).toMatchObject({ interval: 'HOUR', minute: 30 })
  })
})
