import { describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import workspaceSkillStore from '@baserow/modules/core/store/workspaceSkill'

describe('workspaceSkill store', () => {
  let testApp = null
  let store = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mockServer = testApp.mock
    store.registerModule('workspaceSkillTest', workspaceSkillStore)
  })

  afterEach(() => {
    store.unregisterModule('workspaceSkillTest')
    testApp.afterEach()
  })

  const skill = (values = {}) => ({
    id: 1,
    workspace_id: 10,
    name: 'Formulas',
    description: 'Use when writing formulas.',
    content: '# Formulas',
    ...values,
  })

  test('fetches, creates, updates and deletes skills per workspace', async () => {
    mockServer
      .onGet('/skills/workspace/10/')
      .replyOnce(200, [skill(), skill({ id: 2, name: 'Tone' })])
    await store.dispatch('workspaceSkillTest/fetchAll', { workspaceId: 10 })
    expect(
      store.getters['workspaceSkillTest/getAllInWorkspace'](10).map(
        (s) => s.name
      )
    ).toEqual(['Formulas', 'Tone'])
    expect(store.getters['workspaceSkillTest/isLoaded'](10)).toBe(true)
    expect(store.getters['workspaceSkillTest/isLoaded'](11)).toBe(false)

    mockServer
      .onPost('/skills/workspace/10/')
      .replyOnce(200, skill({ id: 3, name: 'Data entry' }))
    await store.dispatch('workspaceSkillTest/create', {
      workspaceId: 10,
      values: { name: 'Data entry' },
    })
    expect(
      store.getters['workspaceSkillTest/getAllInWorkspace'](10).map(
        (s) => s.name
      )
    ).toEqual(['Data entry', 'Formulas', 'Tone'])

    mockServer
      .onPatch('/skills/3/')
      .replyOnce(200, skill({ id: 3, name: 'Data entry rules' }))
    await store.dispatch('workspaceSkillTest/update', {
      skillId: 3,
      values: { name: 'Data entry rules' },
    })
    expect(store.getters['workspaceSkillTest/get'](3).name).toBe(
      'Data entry rules'
    )

    mockServer.onDelete('/skills/3/').replyOnce(204)
    await store.dispatch(
      'workspaceSkillTest/delete',
      store.getters['workspaceSkillTest/get'](3)
    )
    expect(store.getters['workspaceSkillTest/get'](3)).toBeUndefined()
  })

  test('realtime updates upsert and remove without a request', () => {
    store.dispatch('workspaceSkillTest/forceCreate', skill())
    store.dispatch('workspaceSkillTest/forceUpdate', skill({ name: 'Renamed' }))
    expect(store.getters['workspaceSkillTest/get'](1).name).toBe('Renamed')
    store.dispatch('workspaceSkillTest/forceDelete', 1)
    expect(store.getters['workspaceSkillTest/getAllInWorkspace'](10)).toEqual(
      []
    )
  })
})
