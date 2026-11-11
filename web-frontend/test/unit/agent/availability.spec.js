import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import {
  createAgentPage,
  deferredReply,
  destroyAgentPage,
  mockAvailability,
  warning,
  withoutConfiguration,
} from './helpers'

describe('Agent model availability', () => {
  let testApp, allowed, mount

  beforeEach(async () => {
    ;({ testApp, allowed, mount } = await createAgentPage())
  })

  afterEach(() => destroyAgentPage(testApp))

  const modelRequests = () =>
    testApp.mock.history.get.filter(({ url }) => url === '/workspaces/')

  test('loads models when configuration access is granted', async () => {
    allowed.value = withoutConfiguration
    const wrapper = await mount()
    expect(modelRequests()).toHaveLength(0)

    allowed.value = () => true
    await flushPromises()

    expect(modelRequests()).toHaveLength(1)
    expect(wrapper.find('.agent-configuration').exists()).toBe(true)
    expect(warning(wrapper).exists()).toBe(false)
  })

  test('ignores a pending model failure after configuration access is revoked', async () => {
    testApp.dontFailOnErrorResponses()
    const models = deferredReply()
    mockAvailability(testApp, models.reply)
    const wrapper = await mount()

    allowed.value = withoutConfiguration
    await flushPromises()
    models.resolve(500, {})
    await flushPromises()

    expect(wrapper.find('.agent-configuration').exists()).toBe(false)
    expect(warning(wrapper).exists()).toBe(false)
  })
})
