import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import ApplicationSelector from '@baserow/modules/core/components/export/ApplicationSelector'

describe('ApplicationSelector', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (props = {}) =>
    testApp.mount(ApplicationSelector, {
      props: { workspace: { id: 1 }, ...props },
    })

  test.each([
    [
      'shows the export title by default',
      {},
      'exportWorkspaceForm.selectDataToExport',
    ],
    ['shows the given title', { title: 'Content' }, 'Content'],
  ])('%s', async (_title, props, title) => {
    const wrapper = await mountComponent(props)

    expect(wrapper.find('.application-selector__title').text()).toBe(title)
  })

  test('disables its buttons and checkboxes, also for the keyboard', async () => {
    await testApp.store.dispatch('application/forceCreate', {
      id: 11,
      name: 'CRM',
      type: 'database',
      tables: [],
      workspace: { id: 1 },
    })
    const wrapper = await mountComponent({
      selectedApplicationIds: [11],
      disabled: true,
    })

    const buttons = wrapper.findAll('.application-selector__action-btn')
    expect(buttons).toHaveLength(2)
    for (const button of buttons) {
      expect(button.attributes('disabled')).toBeDefined()
    }
    const inputs = wrapper.findAll('.checkbox__native')
    expect(inputs).toHaveLength(2)
    for (const input of inputs) {
      expect(input.attributes('disabled')).toBeDefined()
      await input.trigger('change')
    }
    await buttons[1].trigger('click')

    expect(wrapper.emitted('update')).toBeUndefined()
  })
})
