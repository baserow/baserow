import { TestApp } from '@baserow/test/helpers/testApp'
import { groupAgentTools } from '@baserow/modules/agent/agentTools'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import en from '@baserow_enterprise/locales/en.json'

/** Translates to the key itself, failing on a tool key English lacks. */
const t = (key) => {
  const [section, name] = key.split('.')
  if (section === 'rowCommentTools' && !en[section][name]) {
    throw new Error(`Missing translation ${key}`)
  }
  return key
}

describe('Row comment tool presentations', () => {
  let testApp
  let registry

  beforeEach(() => {
    testApp = new TestApp()
    registry = testApp.getRegistry()
  })

  afterEach(() => testApp.afterEach())

  const activity = (tool, status, input = {}, facts = {}) =>
    registry
      .get('toolPresentation', tool)
      .getActivity({ status, input, facts }, t)
  const inTasks = { values: { table: 'Tasks' } }

  test('a locked row comment tool opens the Advanced RBAC paid feature', () => {
    const [group] = groupAgentTools(
      [
        {
          name: 'create_row_comments',
          group: 'database',
          changes_data: true,
          deactivated: true,
        },
        { name: 'search_row_comments', group: 'database', changes_data: false },
      ],
      registry,
      t
    )

    expect(group.tools.map((tool) => [tool.label, tool.deactivated])).toEqual([
      ['rowCommentTools.createRowComments', true],
      ['rowCommentTools.searchRowComments', false],
    ])
    expect(group.tools[0].description).toBe(
      'rowCommentTools.createRowCommentsDescription'
    )
    expect(group.tools[0].deactivatedClickModal).toEqual([
      PaidFeaturesModal,
      { 'initial-selected-type': 'rbac' },
    ])
    expect(group.tools[1].deactivatedClickModal).toBeNull()
  })

  test.each([
    [
      'list_row_comments',
      'waiting',
      inTasks,
      {},
      'listRowCommentsRequestedTable',
    ],
    ['list_row_comments', 'running', inTasks, {}, 'listRowCommentsRunning'],
    ['list_row_comments', 'done', inTasks, {}, 'listRowCommentsDoneTable'],
    [
      'list_row_comments',
      'done',
      inTasks,
      { count: 2 },
      'listRowCommentsDoneCountTable',
    ],
    ['list_row_comments', 'done', {}, { count: 2 }, 'listRowCommentsDoneCount'],
    ['list_row_comments', 'done', {}, {}, 'listRowCommentsDone'],
    ['search_row_comments', 'waiting', {}, {}, 'searchRowComments'],
    ['search_row_comments', 'running', {}, {}, 'searchRowCommentsRunning'],
    ['search_row_comments', 'done', {}, {}, 'searchRowCommentsDone'],
    [
      'search_row_comments',
      'done',
      {},
      { count: 3 },
      'searchRowCommentsDoneCount',
    ],
    [
      'create_row_comments',
      'waiting',
      { ...inTasks, requested_count: 2 },
      {},
      'createRowCommentsRequestedCountTable',
    ],
    [
      'create_row_comments',
      'waiting',
      { requested_count: 2 },
      {},
      'createRowCommentsRequestedCount',
    ],
    ['create_row_comments', 'running', {}, {}, 'createRowCommentsRunning'],
    [
      'create_row_comments',
      'running',
      { requested_count: 2 },
      {},
      'createRowCommentsRunningCount',
    ],
    [
      'create_row_comments',
      'done',
      inTasks,
      { count: 2 },
      'createRowCommentsDoneCountTable',
    ],
    [
      'create_row_comments',
      'done',
      {},
      { count: 2 },
      'createRowCommentsDoneCount',
    ],
  ])('%s %s %j %j reads as %s', (tool, status, input, facts, key) => {
    expect(activity(tool, status, input, facts)).toBe(`rowCommentTools.${key}`)
  })
})
