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

async function mountForm(defaultValues) {
  const wrapper = await mountSuspended(CorePeriodicTriggerServiceForm, {
    props: { defaultValues },
    global: {
      mocks: {
        $t: (key) => key,
        $config: { public: { baserowIntegrationsPeriodicMinuteMin: '2' } },
      },
    },
  })
  await flushPromises()
  return wrapper
}

async function chooseInterval(wrapper, name) {
  await wrapper.get('.dropdown__selected').trigger('click')
  await wrapper
    .findAll('.select__item-link')
    .find((item) => item.text().includes(name))
    .trigger('click')
  await flushPromises()
}

describe('CorePeriodicTriggerServiceForm', () => {
  test('keeps the saved minute frequency when it loads', async () => {
    const wrapper = await mountForm(schedule({ interval: 'MINUTE', minute: 5 }))

    expect(wrapper.vm.values.minute).toBe(5)
    for (const [values] of wrapper.emitted('values-changed') || []) {
      expect(values.minute).toBe(5)
    }
  })

  test('starts a picked minute frequency at the instance minimum and resets it when leaving', async () => {
    const wrapper = await mountForm(schedule())

    await chooseInterval(wrapper, 'periodicForm.everyMinuteDefault')
    expect(wrapper.emitted('values-changed').at(-1)[0]).toMatchObject({
      interval: 'MINUTE',
      minute: '2',
    })

    await chooseInterval(wrapper, 'periodicForm.everyDay')
    expect(wrapper.emitted('values-changed').at(-1)[0]).toMatchObject({
      interval: 'DAY',
      minute: 0,
    })
  })
})
