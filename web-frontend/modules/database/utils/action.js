import { generateUUID } from '@baserow/modules/core/utils/string'

export const createNewUndoRedoActionGroupId = () => {
  return generateUUID()
}

export const UNDO_REDO_ACTION_GROUP_HEADER = 'ClientUndoRedoActionGroupId'

export const getUndoRedoActionRequestConfig = ({ undoRedoActionGroupId }) => {
  const config = { params: {} }
  if (undoRedoActionGroupId != null) {
    config.headers = {
      [UNDO_REDO_ACTION_GROUP_HEADER]: undoRedoActionGroupId,
    }
  }
  return config
}

// The backend setting of the same name: one undo takes back at most this many
// steps of an action group, newest first.
export const MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP = 20
