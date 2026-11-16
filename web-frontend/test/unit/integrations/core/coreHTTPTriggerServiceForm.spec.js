import { afterEach, beforeEach, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import CoreHTTPTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPTriggerServiceForm'

let testApp

beforeEach(() => {
  testApp = new TestApp()
})

afterEach(async () => {
  await testApp.afterEach()
})

test('keeps Automation test and published URLs and workflow response settings by default', async () => {
  const wrapper = await testApp.mount(CoreHTTPTriggerServiceForm, {
    props: {
      defaultValues: {
        uid: 'workflow-webhook',
        exclude_get: false,
        wait_for_response: false,
        response_timeout_seconds: 10,
      },
    },
  })

  expect(wrapper.get('.webhook-service-form__webhook-url').text()).toMatch(
    /\/api\/webhooks\/workflow-webhook\/\?test=true$/
  )
  await wrapper.findAll('.radio-group__radio-button')[1].trigger('click')
  expect(wrapper.get('.webhook-service-form__webhook-url').text()).toMatch(
    /\/api\/webhooks\/workflow-webhook\/$/
  )

  await wrapper.get('.checkbox').trigger('click')
  expect(wrapper.get('input[type="number"]').element.value).toBe('10')
  expect(wrapper.emitted('values-changed').at(-1)[0]).toEqual({
    exclude_get: false,
    wait_for_response: true,
    response_timeout_seconds: 10,
  })
})
