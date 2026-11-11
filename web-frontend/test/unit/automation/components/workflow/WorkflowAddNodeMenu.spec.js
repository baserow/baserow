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

// Carries an `order` so the menu lists it after the node type groups, which
// have none and sort alphabetically.
const recipesGroup = {
  id: 'recipes',
  label: 'Recipes',
  icon: 'iconoir-repeat',
  iconColor: 'muted-purple',
  order: 1,
}

function makeNodeType({
  type,
  name,
  order,
  integrationType = null,
  isTrigger = false,
  description = null,
  aliases = [],
  isEnabled = true,
}) {
  return {
    type,
    name,
    description,
    aliases,
    iconClass: `iconoir-${type}`,
    image: null,
    isTrigger,
    isWorkflowAction: !isTrigger,
    group: integrationType ? localBaserowGroup : coreGroup,
    serviceType: { integrationType },
    getType: () => type,
    getOrder: () => order,
    isEnabled: () => isEnabled,
    isDeactivated: () => false,
    isDeactivatedReason: () => null,
    getDeactivatedClickModal: () => null,
  }
}

function makeRecipe({
  type,
  name,
  order,
  description,
  iconClass,
  aliases = [],
  isEnabled = true,
}) {
  return {
    name,
    description,
    aliases,
    iconClass,
    iconColor: recipesGroup.iconColor,
    group: recipesGroup,
    getType: () => type,
    getOrder: () => order,
    isEnabled: () => isEnabled,
  }
}

const repeatNodeType = makeNodeType({
  type: 'iterator',
  name: 'Repeat',
  description: 'Run the following actions multiple times.',
  aliases: ['loop', 'for loop'],
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

// A trigger the instance is not configured for, e.g. the email trigger without
// an inbound email domain: it must be left out of the menu entirely rather than
// listed as deactivated.
const disabledTriggerNodeType = makeNodeType({
  type: 'email_trigger',
  name: 'Email Trigger',
  description: 'Triggered when an email is received.',
  order: 2,
  isTrigger: true,
  isEnabled: false,
})

const forLoopRecipe = makeRecipe({
  type: 'for_loop',
  name: 'For loop',
  description: 'Adds an Iterator that runs its child nodes 5 times.',
  iconClass: 'iconoir-repeat',
  aliases: ['loop', 'repeat'],
  order: 1,
})
const whileLoopRecipe = makeRecipe({
  type: 'while_loop',
  name: 'While loop',
  description: 'Adds a List rows node and a Go to node.',
  iconClass: 'iconoir-refresh-double',
  aliases: ['loop', 'until'],
  order: 2,
})
const disabledRecipe = makeRecipe({
  type: 'disabled_recipe',
  name: 'Disabled recipe',
  description: 'Never offered.',
  iconClass: 'iconoir-repeat',
  order: 3,
  isEnabled: false,
})

const workflowTrigger = { id: 1, type: 'rows_created' }

const mountComponent = ({
  onlyTrigger = false,
  node = null,
  workflowNodes = [workflowTrigger],
  recipes = [forLoopRecipe, whileLoopRecipe],
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
          getOrderedList: (namespace) =>
            namespace === 'node'
              ? [
                  createRowNodeType,
                  getRowNodeType,
                  repeatNodeType,
                  triggerNodeType,
                  disabledTriggerNodeType,
                ]
              : recipes,
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

const navigationLabels = (wrapper) =>
  wrapper
    .findAll('.grouped-menu__navigation .menu-list__item-label')
    .map((item) => item.text())
const actionLabels = (wrapper) =>
  wrapper
    .findAll('.grouped-menu__actions .menu-list__item-label')
    .map((item) => item.text())
const actionDescriptions = (wrapper) =>
  wrapper
    .findAll('.grouped-menu__actions .menu-list__item-description')
    .map((item) => item.text())
const clickNavigation = (wrapper, label) =>
  wrapper
    .findAll('.grouped-menu__navigation .menu-list__item-button')
    .find((item) => item.text().includes(label))
    .trigger('click')
const clickAction = (wrapper, label) =>
  wrapper
    .findAll('.grouped-menu__actions .menu-list__item-button')
    .find((item) => item.text().includes(label))
    .trigger('click')

describe('WorkflowAddNodeMenu', () => {
  test('shows workflow actions in integration groups', async () => {
    const wrapper = mountComponent()

    expect(navigationLabels(wrapper)).toEqual([
      'Core',
      'Local Baserow',
      'Recipes',
    ])
    expect(actionLabels(wrapper)).toEqual(['Repeat'])
    expect(actionDescriptions(wrapper)).toEqual([
      'Run the following actions multiple times.',
    ])
    expect(wrapper.find('.menu-search__input').exists()).toBe(true)
    expect(wrapper.find('.menu-search__input').attributes('placeholder')).toBe(
      'workflowNodeContext.searchPlaceholderActions'
    )

    await clickNavigation(wrapper, 'Local Baserow')

    expect(
      wrapper
        .findAll('.grouped-menu__actions .menu-list__item-icon')
        .map((item) => item.classes())
    ).toEqual([
      ['menu-list__item-icon', 'iconoir-create_row'],
      ['menu-list__item-icon', 'iconoir-get_row'],
    ])
    expect(
      wrapper.find('.grouped-menu__actions .menu-list__item-image').exists()
    ).toBe(false)

    await clickAction(wrapper, 'Create row')

    expect(wrapper.emitted('change')[0]).toEqual(['create_row'])
    expect(wrapper.emitted('recipe')).toBeUndefined()
  })

  test('navigates actions in their visual order', async () => {
    const wrapper = mountComponent()
    document.body.append(wrapper.element)
    const searchInput = wrapper.find('.menu-search__input')

    try {
      await wrapper.vm.focus()
      expect(document.activeElement).toBe(searchInput.element)

      await searchInput.trigger('keydown', { key: 'ArrowDown' })
      await wrapper
        .find('.grouped-menu__navigation .menu-list')
        .trigger('keydown', { key: 'ArrowDown' })
      await wrapper
        .find('.grouped-menu__navigation .menu-list')
        .trigger('keydown', { key: 'ArrowRight' })

      expect(document.activeElement.textContent).toContain('Create row')

      await wrapper
        .find('.grouped-menu__actions .menu-list')
        .trigger('keydown', { key: 'ArrowDown' })

      expect(document.activeElement.textContent).toContain('Get row')
    } finally {
      wrapper.unmount()
    }
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

  test('omits node types that are not enabled instead of listing them disabled', () => {
    const wrapper = mountComponent({ onlyTrigger: true, workflowNodes: [] })

    expect(wrapper.vm.nodeTypes.map((nodeType) => nodeType.getType())).toEqual([
      'rows_created',
    ])
    expect(actionLabels(wrapper)).toEqual(['Rows are created'])
    expect(navigationLabels(wrapper)).toEqual(['Local Baserow'])
  })

  test('uses the trigger search when workflow nodes do not include a trigger', () => {
    const wrapper = mountComponent({
      workflowNodes: [{ id: 1, type: 'create_row' }],
    })

    expect(wrapper.find('.menu-search__input').attributes('placeholder')).toBe(
      'workflowNodeContext.searchPlaceholderTrigger'
    )
  })

  describe('recipes', () => {
    test('are listed in their own group after every node type group', async () => {
      const wrapper = mountComponent()

      expect(navigationLabels(wrapper).at(-1)).toBe('Recipes')

      await clickNavigation(wrapper, 'Recipes')

      expect(actionLabels(wrapper)).toEqual(['For loop', 'While loop'])
      expect(actionDescriptions(wrapper)).toEqual([
        'Adds an Iterator that runs its child nodes 5 times.',
        'Adds a List rows node and a Go to node.',
      ])
      expect(
        wrapper
          .findAll('.grouped-menu__actions .menu-list__item-icon')
          .map((item) => item.classes())
      ).toEqual([
        ['menu-list__item-icon', 'iconoir-repeat'],
        ['menu-list__item-icon', 'iconoir-refresh-double'],
      ])
    })

    test('emit recipe instead of change when picked', async () => {
      const wrapper = mountComponent()

      await clickNavigation(wrapper, 'Recipes')
      await clickAction(wrapper, 'While loop')

      expect(wrapper.emitted('recipe')).toEqual([['while_loop']])
      expect(wrapper.emitted('change')).toBeUndefined()
    })

    test('are left out when not enabled', async () => {
      const wrapper = mountComponent({
        recipes: [forLoopRecipe, disabledRecipe],
      })

      await clickNavigation(wrapper, 'Recipes')

      expect(actionLabels(wrapper)).toEqual(['For loop'])
    })

    test('are not offered when picking a trigger', () => {
      const wrapper = mountComponent({ onlyTrigger: true, workflowNodes: [] })

      expect(navigationLabels(wrapper)).toEqual(['Local Baserow'])
    })

    test('are not offered when replacing a node', () => {
      const wrapper = mountComponent({ node: { id: 2, type: 'create_row' } })

      expect(navigationLabels(wrapper)).toEqual(['Core', 'Local Baserow'])
    })
  })

  describe('search', () => {
    test('matches node types and recipes through their aliases', async () => {
      const wrapper = mountComponent()
      const searchInput = wrapper.find('.menu-search__input')

      await searchInput.setValue('loop')

      // "Repeat" only matches through its "loop" alias; the Recipes group
      // stays last and the first group's results are shown.
      expect(navigationLabels(wrapper)).toEqual(['Core', 'Recipes'])
      expect(actionLabels(wrapper)).toEqual(['Repeat'])

      await clickNavigation(wrapper, 'Recipes')

      expect(actionLabels(wrapper)).toEqual(['For loop', 'While loop'])

      await searchInput.setValue('until')

      expect(navigationLabels(wrapper)).toEqual(['Recipes'])
      expect(actionLabels(wrapper)).toEqual(['While loop'])
    })

    test('still matches labels and descriptions', async () => {
      const wrapper = mountComponent()

      await wrapper.find('.menu-search__input').setValue('record')

      expect(navigationLabels(wrapper)).toEqual(['Local Baserow'])
      expect(actionLabels(wrapper)).toEqual(['Create row', 'Get row'])
    })
  })
})
