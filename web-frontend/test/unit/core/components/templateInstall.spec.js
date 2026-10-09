import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplateInstall from '@baserow/modules/core/components/template/TemplateInstall'

const template = { id: 5, slug: 'project-tracker', name: 'Project Tracker' }

describe('TemplateInstall', () => {
  let testApp = null
  let push = null

  beforeEach(() => {
    testApp = new TestApp()
    push = vi.spyOn(testApp.nuxtApp.$router, 'push').mockResolvedValue()
  })

  afterEach(async () => {
    push.mockRestore()
    await testApp.afterEach()
  })

  const signIn = () => {
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    testApp.store.dispatch('workspace/forceCreate', { id: 1, name: 'First' })
    testApp.store.dispatch('workspace/forceCreate', { id: 2, name: 'Second' })
  }

  const mockInstall = (workspaceId) =>
    testApp.mock
      .onPost(`/templates/install/${workspaceId}/${template.id}/async/`)
      .reply(202, { id: 10, type: 'install_template', state: 'finished' })

  const clickUse = async (wrapper) => {
    await wrapper.find('.template-install__use').trigger('click')
    await flushPromises()
  }

  test('sends an anonymous visitor to the login page and back', async () => {
    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template },
    })

    expect(wrapper.find('.template-install__workspace').exists()).toBe(false)

    await clickUse(wrapper)

    expect(push).toHaveBeenCalledWith({
      name: 'login',
      query: { original: '/template/project-tracker' },
    })
    expect(testApp.mock.history.post).toHaveLength(0)
    expect(wrapper.emitted('installed')).toBeUndefined()
  })

  test('installs into the provided workspace without redirecting', async () => {
    signIn()
    mockInstall(2)

    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template, workspace: { id: 2 } },
    })
    await clickUse(wrapper)

    expect(testApp.mock.history.post.map((r) => r.url)).toStrictEqual([
      '/templates/install/2/5/async/',
    ])
    expect(wrapper.emitted('installed')).toHaveLength(1)
    expect(push).not.toHaveBeenCalled()
  })

  test('installs into the first workspace and opens it when none is provided', async () => {
    signIn()
    mockInstall(1)

    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template },
    })
    await clickUse(wrapper)

    expect(testApp.mock.history.post.map((r) => r.url)).toStrictEqual([
      '/templates/install/1/5/async/',
    ])
    expect(wrapper.emitted('installed')).toHaveLength(1)
    expect(push).toHaveBeenCalledWith({
      name: 'workspace',
      params: { workspaceId: 1 },
    })
  })

  test('does not report a failed install as installed', async () => {
    signIn()
    testApp.dontFailOnErrorResponses()
    testApp.mock
      .onPost(`/templates/install/1/${template.id}/async/`)
      .reply(400, { error: 'ERROR_USER_NOT_IN_GROUP' })

    const wrapper = await testApp.mount(TemplateInstall, {
      props: { template, workspace: { id: 1 } },
    })
    await clickUse(wrapper)

    expect(wrapper.emitted('installed')).toBeUndefined()
    expect(push).not.toHaveBeenCalled()
    expect(
      wrapper.find('.template-install__use').attributes('disabled')
    ).toBeUndefined()
  })
})
