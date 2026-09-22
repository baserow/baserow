import { TestApp } from '@baserow/test/helpers/testApp'
import {
  CORE_ACTION_SCOPES,
  getSidebarActionScopes,
} from '@baserow/modules/core/utils/undoRedoConstants'
import { SIDEBAR_TYPES } from '@baserow/modules/core/utils/constants'

describe('undoRedo scopes', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('the all workspaces sidebar sees every workspace and no application', () => {
    expect(
      getSidebarActionScopes({
        sidebarType: SIDEBAR_TYPES.ALL_WORKSPACES,
        // Still selected in the store from a page visited before.
        workspaceId: 5,
        applicationId: 9,
      })
    ).toStrictEqual({
      all_workspaces: true,
      workspace: null,
      application: null,
    })
  })

  test('the workspace sidebar sees the selected workspace and application', () => {
    expect(
      getSidebarActionScopes({
        sidebarType: SIDEBAR_TYPES.WORKSPACE,
        workspaceId: 5,
        applicationId: 9,
      })
    ).toStrictEqual({ all_workspaces: false, workspace: 5, application: 9 })
    expect(
      getSidebarActionScopes({
        sidebarType: SIDEBAR_TYPES.WORKSPACE,
        workspaceId: 5,
        applicationId: null,
      })
    ).toStrictEqual({ all_workspaces: false, workspace: 5, application: null })
  })

  test('switching sidebars replaces the previous surface scopes', () => {
    store.dispatch('undoRedo/updateCurrentScopeSet', CORE_ACTION_SCOPES.root())
    store.dispatch(
      'undoRedo/updateCurrentScopeSet',
      getSidebarActionScopes({
        sidebarType: SIDEBAR_TYPES.WORKSPACE,
        workspaceId: 5,
        applicationId: 9,
      })
    )
    store.dispatch(
      'undoRedo/updateCurrentScopeSet',
      getSidebarActionScopes({
        sidebarType: SIDEBAR_TYPES.ALL_WORKSPACES,
        workspaceId: 5,
        applicationId: 9,
      })
    )
    expect(store.getters['undoRedo/getCurrentScope']).toStrictEqual({
      root: true,
      all_workspaces: true,
      workspace: null,
      application: null,
    })
    store.dispatch(
      'undoRedo/updateCurrentScopeSet',
      getSidebarActionScopes({
        sidebarType: SIDEBAR_TYPES.WORKSPACE,
        workspaceId: 5,
        applicationId: 9,
      })
    )
    expect(store.getters['undoRedo/getCurrentScope']).toStrictEqual({
      root: true,
      all_workspaces: false,
      workspace: 5,
      application: 9,
    })
  })
})
