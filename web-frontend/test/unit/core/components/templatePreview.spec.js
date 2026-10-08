import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'

describe('TemplatePreview', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('registers the template workspace so its content can be read', async () => {
    testApp.mock.onGet('/applications/workspace/42/').reply(200, [])
    const isTemplateWorkspace =
      testApp.store.getters['templateWorkspace/isTemplateWorkspace']
    expect(isTemplateWorkspace(42)).toBe(false)

    await testApp.mount(TemplatePreview, {
      props: { template: { id: 1, workspace_id: 42, open_application: null } },
    })

    expect(isTemplateWorkspace(42)).toBe(true)
    expect(testApp.mock.history.get.map((r) => r.url)).toContain(
      '/applications/workspace/42/'
    )
  })
})
