import {
  NodeRecipeType,
  ForLoopNodeRecipeType,
  WhileLoopNodeRecipeType,
  getRecipesGroup,
} from '@baserow/modules/automation/nodeRecipeTypes'
import { TestApp } from '@baserow/test/helpers/testApp'

// An app stub whose i18n returns the key, or the text given in `translations`
// for that key, so alias parsing can be checked against real strings.
const makeApp = (translations = {}) => ({
  $i18n: { t: (key) => translations[key] ?? key },
})

// Records every `addNode` call and resolves each one to a stored node with a
// server id and service id, the way the store helper does.
const makeAddNode = () => {
  const calls = []
  const addNode = vi.fn(async (values) => {
    calls.push(values)
    const index = calls.length
    return { id: 100 + index, type: values.type, service: { id: 200 + index } }
  })
  return { addNode, calls }
}

// Where the user opened the picker: on the edge after node 1.
const target = {
  workflow: { id: 7 },
  referenceNode: { id: 1 },
  position: 'south',
  output: '',
}

describe('NodeRecipeType', () => {
  class TestRecipeType extends NodeRecipeType {
    static getType() {
      return 'test'
    }
  }

  test('belongs to the Recipes group, listed after the node type groups', () => {
    const recipe = new TestRecipeType({ app: makeApp() })

    expect(recipe.group).toEqual(getRecipesGroup(recipe.app))
    expect(recipe.group).toEqual({
      id: 'recipes',
      label: 'nodeRecipe.groupLabel',
      icon: 'iconoir-repeat',
      iconColor: 'muted-purple',
      order: 1,
    })
    expect(recipe.iconColor).toBe('muted-purple')
  })

  test('is enabled and has no aliases by default', () => {
    const recipe = new TestRecipeType({ app: makeApp() })

    expect(recipe.isEnabled()).toBe(true)
    expect(recipe.aliases).toEqual([])
  })

  test('requires a name, a description, an icon and a create implementation', async () => {
    const recipe = new TestRecipeType({ app: makeApp() })

    expect(() => recipe.name).toThrow('Must be set on the type.')
    expect(() => recipe.description).toThrow('Must be set on the type.')
    expect(() => recipe.iconClass).toThrow('Must be set on the type.')
    await expect(
      recipe.create({ ...target, addNode: vi.fn() })
    ).rejects.toThrow('This method must be implemented')
  })
})

describe('ForLoopNodeRecipeType', () => {
  test('is the first recipe', () => {
    const recipe = new ForLoopNodeRecipeType({ app: makeApp() })

    expect(ForLoopNodeRecipeType.getType()).toBe('for_loop')
    expect(recipe.getOrder()).toBe(1)
    expect(recipe.name).toBe('nodeRecipe.forLoopName')
    expect(recipe.description).toBe('nodeRecipe.forLoopDescription')
    expect(recipe.iconClass).toBe('iconoir-repeat')
  })

  test('parses its aliases from one translatable string', () => {
    const recipe = new ForLoopNodeRecipeType({
      app: makeApp({ 'nodeRecipe.forLoopAliases': 'loop, for each, repeat' }),
    })

    expect(recipe.aliases).toEqual(['loop', 'for each', 'repeat'])
  })

  test('inserts one Iterator over range(5) where the picker was opened', async () => {
    const recipe = new ForLoopNodeRecipeType({ app: makeApp() })
    const { addNode, calls } = makeAddNode()

    await recipe.create({ ...target, addNode })

    expect(calls).toEqual([
      {
        type: 'iterator',
        referenceNode: target.referenceNode,
        position: 'south',
        output: '',
        label: 'nodeRecipe.forLoopIteratorLabel',
        // Advanced mode: a bare string would be stored as a simple formula
        // and the editor would show the function call as plain text.
        service: { source: { formula: 'range(5)', mode: 'advanced' } },
      },
    ])
  })
})

describe('WhileLoopNodeRecipeType', () => {
  test('is the second recipe', () => {
    const recipe = new WhileLoopNodeRecipeType({ app: makeApp() })

    expect(WhileLoopNodeRecipeType.getType()).toBe('while_loop')
    expect(recipe.getOrder()).toBe(2)
    expect(recipe.name).toBe('nodeRecipe.whileLoopName')
    expect(recipe.description).toBe('nodeRecipe.whileLoopDescription')
    expect(recipe.iconClass).toBe('iconoir-refresh-double')
  })

  test('parses its aliases from one translatable string', () => {
    const recipe = new WhileLoopNodeRecipeType({
      app: makeApp({ 'nodeRecipe.whileLoopAliases': 'loop,until , retry' }),
    })

    expect(recipe.aliases).toEqual(['loop', 'until', 'retry'])
  })

  test('inserts an unconfigured List rows node and a Go to node jumping back to it', async () => {
    const recipe = new WhileLoopNodeRecipeType({ app: makeApp() })
    const { addNode, calls } = makeAddNode()

    await recipe.create({ ...target, addNode })

    expect(calls).toHaveLength(2)
    expect(calls[0]).toEqual({
      type: 'local_baserow_list_rows',
      referenceNode: target.referenceNode,
      position: 'south',
      output: '',
      label: 'nodeRecipe.whileLoopListRowsLabel',
    })
    // No table, integration or filters: the node is left exactly as a
    // hand-added List rows node, so the backend's single-integration
    // preselection decides on its own.
    expect(calls[0]).not.toHaveProperty('service')
    expect(calls[1]).toEqual({
      type: 'goto',
      referenceNode: {
        id: 101,
        type: 'local_baserow_list_rows',
        service: { id: 201 },
      },
      position: 'south',
      output: '',
      label: 'nodeRecipe.whileLoopGotoLabel',
      service: {
        destination_service_id: 201,
        condition: {
          formula: "greater_than(length(get('previous_node.101')), 0)",
          mode: 'advanced',
        },
      },
    })
  })

  test('places the Go to node right after the List rows node whatever the first insertion was', async () => {
    const recipe = new WhileLoopNodeRecipeType({ app: makeApp() })
    const { addNode, calls } = makeAddNode()

    // Opened inside a container, on one of its child slots.
    await recipe.create({
      ...target,
      referenceNode: { id: 5 },
      position: 'child',
      output: 'branch-uuid',
      addNode,
    })

    expect(calls[0]).toMatchObject({
      referenceNode: { id: 5 },
      position: 'child',
      output: 'branch-uuid',
    })
    expect(calls[1]).toMatchObject({
      referenceNode: { id: 101 },
      position: 'south',
      output: '',
    })
  })

  test('stops at the first node that cannot be inserted', async () => {
    const recipe = new WhileLoopNodeRecipeType({ app: makeApp() })
    const addNode = vi.fn().mockRejectedValueOnce(new Error('boom'))

    await expect(recipe.create({ ...target, addNode })).rejects.toThrow('boom')

    expect(addNode).toHaveBeenCalledTimes(1)
  })
})

describe('Registered node recipes', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('lists the For loop before the While loop, both enabled, in the Recipes group', () => {
    const recipes = testApp.getRegistry().getOrderedList('automationNodeRecipe')

    expect(recipes.map((recipe) => recipe.getType())).toEqual([
      'for_loop',
      'while_loop',
    ])
    expect(recipes.map((recipe) => recipe.isEnabled())).toEqual([true, true])
    expect(recipes.map((recipe) => recipe.group.id)).toEqual([
      'recipes',
      'recipes',
    ])
  })
})
