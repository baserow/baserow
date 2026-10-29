import ViewFieldConditionsForm from '@baserow/modules/database/components/view/ViewFieldConditionsForm'
import { TestApp } from '@baserow/test/helpers/testApp'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

test.each([
  ['editable', {}],
  ['database read permissions', { readOnly: true }],
  ['disabled', { disableFilter: true }],
  ['read-only filters', { filterReadOnly: true }],
])('%s applies to root and nested filter controls', async (name, props) => {
  const wrapper = await testApp.mount(ViewFieldConditionsForm, {
    props: {
      fields: [{ id: 1, name: 'Name', type: 'text', primary: true }],
      filters: [
        { id: 1, field: 1, type: 'equal', value: 'Root', group: null },
        { id: 2, field: 1, type: 'equal', value: 'Outer', group: 'outer' },
        { id: 3, field: 1, type: 'equal', value: 'Inner', group: 'inner' },
        { id: 4, field: 1, type: 'equal', value: 'Second', group: 'inner' },
        { id: 5, field: 999, type: 'equal', value: 'Missing', group: 'inner' },
      ],
      filterGroups: [
        { id: 'outer', filter_type: 'AND', parent_group: null },
        { id: 'inner', filter_type: 'OR', parent_group: 'outer' },
      ],
      filterType: 'AND',
      disableFilter: false,
      readOnly: false,
      ...props,
    },
  })

  expect({
    deleteButtons: wrapper.findAll('.filters__remove').length,
    addButtons: wrapper.findAll('.filters__group-item-actions').length,
    dropdowns: wrapper
      .findAll('.dropdown')
      .map((dropdown) => dropdown.classes().includes('dropdown--disabled')),
    values: wrapper.findAll('.filters__value input').map((input) => ({
      value: input.element.value,
      disabled: input.element.disabled,
    })),
    misconfigured: wrapper.find('.filters__misconfigured-text').text(),
  }).toMatchSnapshot()
})
