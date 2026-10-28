import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplatePagePage from '@baserow/modules/core/pages/template'

describe('template page', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const pageStub = (name) =>
    defineComponent({ name, template: `<div class="${name}" />` })

  const stubs = {
    TemplatePage: pageStub('TemplatePage'),
    LegacyTemplatePage: pageStub('LegacyTemplatePage'),
  }

  const mountPage = (enabled) =>
    mountSuspended(TemplatePagePage, {
      global: {
        mocks: {
          $featureFlagIsEnabled: (flag) => enabled && flag === 'user_templates',
        },
        stubs,
      },
    })

  it.each([
    [
      'renders the new template page when user_templates is enabled',
      true,
      'TemplatePage',
      'LegacyTemplatePage',
    ],
    [
      'renders the legacy template page when user_templates is disabled',
      false,
      'LegacyTemplatePage',
      'TemplatePage',
    ],
  ])('%s', async (_title, enabled, shown, hidden) => {
    const wrapper = await mountPage(enabled)

    expect(wrapper.find(`.${shown}`).exists()).toBe(true)
    expect(wrapper.find(`.${hidden}`).exists()).toBe(false)
  })
})
