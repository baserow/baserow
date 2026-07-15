import { mount } from '@vue/test-utils'

import WorkflowAddNodeMenu from '@baserow/modules/automation/components/workflow/WorkflowAddNodeMenu'

const localBaserowIntegrationType = {
  name: 'Local Baserow',
  image: '/local-baserow.svg',
  iconClass: null,
  getType: () => 'local_baserow',
  getOrder: () => 10,
}

function makeNodeType({
  type,
  name,
  order,
  integrationType = null,
  isTrigger = false,
  description = null,
}) {
  return {
    type,
    name,
    description,
    iconClass: `iconoir-${type}`,
    image: integrationType ? integrationType.image : null,
    isTrigger,
    isWorkflowAction: !isTrigger,
    serviceType: { integrationType },
    getType: () => type,
    getOrder: () => order,
    isDeactivated: () => false,
    isDeactivatedReason: () => null,
    getDeactivatedClickModal: () => null,
  }
}

const repeatNodeType = makeNodeType({
  type: 'iterator',
  name: 'Repeat',
  order: 5,
})
const createRowNodeType = makeNodeType({
  type: 'create_row',
  name: 'Create row',
  order: 1,
  integrationType: localBaserowIntegrationType,
})
const getRowNodeType = makeNodeType({
  type: 'get_row',
  name: 'Get row',
  order: 2,
  integrationType: localBaserowIntegrationType,
})
const triggerNodeType = makeNodeType({
  type: 'rows_created',
  name: 'Rows are created',
  description: 'Triggered when rows are created.',
  order: 1,
  integrationType: localBaserowIntegrationType,
  isTrigger: true,
})

const mountComponent = ({ onlyTrigger = false, node = null } = {}) =>
  mount(WorkflowAddNodeMenu, {
    props: {
      onlyTrigger,
      node,
    },
    global: {
      provide: {
        automation: { id: 1 },
        workflow: { id: 1 },
        workspace: { id: 1 },
      },
      directives: {
        autoOverflowScroll: {},
        tooltip: {},
      },
      mocks: {
        $registry: {
          getOrderedList: () => [
            createRowNodeType,
            getRowNodeType,
            repeatNodeType,
            triggerNodeType,
          ],
          getAll: () => ({}),
        },
        $t: (key) => key,
      },
    },
  })

describe('WorkflowAddNodeMenu', () => {
  test('shows workflow actions as a flat searchable list', async () => {
    const wrapper = mountComponent()

    expect(
      wrapper.findAll('.menu-list__item-label').map((item) => item.text())
    ).toEqual(['Create row', 'Get row', 'Repeat'])
    expect(wrapper.find('.menu-search__input').exists()).toBe(true)

    await wrapper
      .findAll('.menu-list__item-button')
      .find((item) => item.text().includes('Create row'))
      .trigger('click')

    expect(wrapper.emitted('change')[0]).toEqual(['create_row'])
  })

  test('keeps trigger choices flat and descriptive', () => {
    const wrapper = mountComponent({ onlyTrigger: true })

    expect(wrapper.find('.menu-search__input').exists()).toBe(false)
    expect(wrapper.find('.menu-list__item-label').text()).toBe(
      'Rows are created'
    )
    expect(wrapper.find('.menu-list__item-description').text()).toBe(
      'Triggered when rows are created.'
    )
  })
})
