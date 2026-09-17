import flushPromises from 'flush-promises'
import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import ViewGroupByContext from '@baserow/modules/database/components/view/ViewGroupByContext'

describe('ViewGroupByContext', () => {
  let testApp = null

  const database = { id: 1, workspace: { id: 1 } }
  const fields = [
    { id: 1, name: 'Name', type: 'text', primary: true },
    { id: 2, name: 'Team', type: 'text', primary: false },
  ]
  const makeView = (groupByLayout) => ({
    id: 1,
    ownership_type: 'collaborative',
    group_bys: [
      {
        id: 10,
        field: 2,
        order: 'ASC',
        type: 'default',
        width: 200,
        _: { loading: false },
      },
    ],
    group_by_layout: groupByLayout,
  })

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountContext = async (view) => {
    const wrapper = await testApp.mount(ViewGroupByContext, {
      props: { database, view, fields, readOnly: false, disableGroupBy: false },
    })
    await wrapper.vm.show(document.body)
    await wrapper.vm.$nextTick()
    return wrapper
  }

  const contextElement = () => document.body.querySelector('.context.group-bys')
  const segmentLabels = () =>
    [...contextElement().querySelectorAll('.segment-control__button')].map(
      (button) => button.textContent.trim()
    )
  const buttonTexts = () =>
    [...contextElement().querySelectorAll('.group-bys__footer-actions button')]
      .map((button) => button.textContent.trim())
      .filter(Boolean)

  test('section layout shows the layout switch and the collapse buttons', async () => {
    await mountContext(makeView('section'))

    expect(segmentLabels()).toEqual([
      'viewGroupByContext.layoutSection',
      'viewGroupByContext.layoutColumn',
    ])
    expect(buttonTexts()).toEqual(
      expect.arrayContaining([
        'viewGroupByContext.collapseAllGroups',
        'viewGroupByContext.expandAllGroups',
      ])
    )
  })

  test('column layout hides the collapse buttons', async () => {
    await mountContext(makeView('column'))

    expect(buttonTexts()).not.toEqual(
      expect.arrayContaining(['viewGroupByContext.collapseAllGroups'])
    )
    expect(buttonTexts()).not.toEqual(
      expect.arrayContaining(['viewGroupByContext.expandAllGroups'])
    )
    const active = contextElement().querySelector(
      '.segment-control__button--active'
    )
    expect(active.textContent.trim()).toBe('viewGroupByContext.layoutColumn')
  })

  test.each([
    ['Sections', 'column', 'section', 0],
    ['Columns', 'section', 'column', 1],
  ])(
    'choosing %s updates the view setting',
    async (_label, currentLayout, selectedLayout, index) => {
      const view = makeView(currentLayout)
      await mountContext(view)
      const dispatch = vi
        .spyOn(testApp.store, 'dispatch')
        .mockResolvedValue(undefined)

      const selected = [
        ...contextElement().querySelectorAll('.segment-control__button'),
      ][index]
      selected.click()
      await flushPromises()

      expect(dispatch).toHaveBeenCalledWith('view/update', {
        view,
        values: { group_by_layout: selectedLayout },
        readOnly: false,
      })
    }
  )
})
