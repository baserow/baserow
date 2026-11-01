import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import {
  mockTemplateApplications,
  template,
} from '@baserow/test/fixtures/templates'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'

describe('TemplatePreview', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    mockTemplateApplications(testApp.mock)
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('switches the selected application in the default sidebar', async () => {
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template },
      global: { stubs: { TableTemplate: true } },
    })
    await flushPromises()

    const selectedTables = () =>
      wrapper.findAll('.tree__sub-link').map((link) => link.text())

    expect(wrapper.find('.sidebar').exists()).toBe(true)
    expect(selectedTables()).toEqual(['Second table'])

    await wrapper.findAll('.tree__link')[0].trigger('click')

    expect(selectedTables()).toEqual(['First table'])
  })
})
