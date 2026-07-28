import { mount } from '@vue/test-utils'

import WorkflowAddNodeMenu from '@baserow/modules/automation/components/workflow/WorkflowAddNodeMenu'

const localBaserowIntegrationType = {
  name: 'Local Baserow',
  image: '/local-baserow.svg',
  iconClass: null,
  getType: () => 'local_baserow',
  getOrder: () => 10,
}

const coreGroup = {
  id: 'core',
  label: 'Core',
  icon: 'iconoir-package',
}

const localBaserowGroup = {
  id: 'integration-local_baserow',
  label: 'Local Baserow',
  image: '/local-baserow.svg',
  icon: null,
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
    group: integrationType ? localBaserowGroup : coreGroup,
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
  description: 'Run the following actions multiple times.',
  order: 5,
})
const createRowNodeType = makeNodeType({
  type: 'create_row',
  name: 'Create row',
  description: 'Add a new record to a table.',
  order: 1,
  integrationType: localBaserowIntegrationType,
})
const getRowNodeType = makeNodeType({
  type: 'get_row',
  name: 'Get row',
  description: 'Retrieve a single record from a table.',
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

const workflowTrigger = { id: 1, type: 'rows_created' }

const mountComponent = ({
  onlyTrigger = false,
  node = null,
  workflowNodes = [workflowTrigger],
} = {}) =>
  mount(WorkflowAddNodeMenu, {
    props: {
      onlyTrigger,
      node,
    },
    global: {
      provide: {
        automation: { id: 1 },
        workflow: { id: 1, nodes: workflowNodes },
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
          get: (registry, type) =>
            registry === 'node' && type === triggerNodeType.getType()
              ? triggerNodeType
              : null,
          getAll: () => ({}),
        },
        $t: (key) => key,
      },
    },
  })

describe('WorkflowAddNodeMenu', () => {
  test('shows workflow actions in integration groups', async () => {
    const wrapper = mountComponent()

    expect(
      wrapper
        .findAll('.grouped-menu__navigation .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Core', 'Local Baserow'])
    expect(
      wrapper
        .findAll('.grouped-menu__actions .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Repeat'])
    expect(
      wrapper
        .findAll('.grouped-menu__actions .menu-list__item-description')
        .map((item) => item.text())
    ).toEqual(['Run the following actions multiple times.'])
    expect(wrapper.find('.menu-search__input').exists()).toBe(true)
    expect(wrapper.find('.menu-search__input').attributes('placeholder')).toBe(
      'workflowNodeContext.searchPlaceholderActions'
    )

    await wrapper
      .findAll('.grouped-menu__navigation .menu-list__item-button')
      .find((item) => item.text().includes('Local Baserow'))
      .trigger('click')

    await wrapper
      .findAll('.grouped-menu__actions .menu-list__item-button')
      .find((item) => item.text().includes('Create row'))
      .trigger('click')

    expect(wrapper.emitted('change')[0]).toEqual(['create_row'])
  })

  test('shows triggers in integration groups with an event search', () => {
    const wrapper = mountComponent({ onlyTrigger: true, workflowNodes: [] })

    expect(wrapper.find('.menu-search__input').exists()).toBe(true)
    expect(wrapper.find('.menu-search__input').attributes('placeholder')).toBe(
      'workflowNodeContext.searchPlaceholderTrigger'
    )
    expect(
      wrapper.find('.grouped-menu__navigation .menu-list__item-label').text()
    ).toBe('Local Baserow')
    expect(
      wrapper.find('.grouped-menu__actions .menu-list__item-label').text()
    ).toBe('Rows are created')
    expect(
      wrapper.find('.grouped-menu__actions .menu-list__item-description').text()
    ).toBe('Triggered when rows are created.')
  })

  test('uses the trigger search when workflow nodes do not include a trigger', () => {
    const wrapper = mountComponent({
      workflowNodes: [{ id: 1, type: 'create_row' }],
    })

    expect(wrapper.find('.menu-search__input').attributes('placeholder')).toBe(
      'workflowNodeContext.searchPlaceholderTrigger'
    )
  })
})
