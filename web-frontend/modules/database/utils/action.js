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
