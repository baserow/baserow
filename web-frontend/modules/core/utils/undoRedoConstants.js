import { SIDEBAR_TYPES } from '@baserow/modules/core/utils/constants'

export const UNDO_REDO_STATES = {
  // The undo has successfully completed
  UNDONE: 'UNDONE',
  // The redo has successfully completed
  REDONE: 'REDONE',
  // The undo action is currently executing
  UNDOING: 'UNDOING',
  // The redo action is currently executing
  REDOING: 'REDOING',
  // An undo was requested but there were no more actions to undo
  NO_MORE_UNDO: 'NO_MORE_UNDO',
  // An redo was requested but there were no more actions to undo
  NO_MORE_REDO: 'NO_MORE_REDO',
  // Something went wrong whilst undoing and so the undo was skipped over
  ERROR_WITH_UNDO: 'ERROR_WITH_UNDO',
  // Something went wrong whilst redoing and so the redo was skipped over
  ERROR_WITH_REDO: 'ERROR_WITH_REDO',
  // There is no recent undo/redo action
  HIDDEN: 'HIDDEN',
}
// The core types of undo/redo scopes available.
export const CORE_ACTION_SCOPES = {
  root(enabled = true) {
    return {
      root: enabled,
    }
  },
  workspace(workspaceId) {
    return {
      workspace: workspaceId,
    }
  },
  allWorkspaces(enabled = true) {
    return {
      all_workspaces: enabled,
    }
  },
  application(applicationId) {
    return {
      application: applicationId,
    }
  },
}

/**
 * The scopes that follow from which sidebar is shown and what is selected in the
 * store. The sidebar is what lets the user change workspaces and applications on
 * every page of the app layout, so deriving these scopes from it in one place
 * means no page has to know about undo scopes to be able to undo what its
 * sidebar can change.
 *
 * @param {object} options
 * @param {string} options.sidebarType One of `SIDEBAR_TYPES`.
 * @param {number|null} options.workspaceId The selected workspace.
 * @param {number|null} options.applicationId The selected application.
 * @returns {object} A partial scope set for `undoRedo/updateCurrentScopeSet`.
 */
export function getSidebarActionScopes({
  sidebarType,
  workspaceId,
  applicationId,
}) {
  if (sidebarType === SIDEBAR_TYPES.ALL_WORKSPACES) {
    return {
      ...CORE_ACTION_SCOPES.workspace(null),
      ...CORE_ACTION_SCOPES.application(null),
    }
  }
  return {
    ...CORE_ACTION_SCOPES.workspace(workspaceId),
    ...CORE_ACTION_SCOPES.application(applicationId),
  }
}

// Please keep in sync with baserow.api.user.serializers.UndoRedoResponseSerializer
export const UNDO_REDO_RESULT_CODES = {
  NOTHING_TO_DO: 'NOTHING_TO_DO',
  SUCCESS: 'SUCCESS',
  SKIPPED_DUE_TO_ERROR: 'SKIPPED_DUE_TO_ERROR',
}
