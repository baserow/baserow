export const createNewUndoRedoActionGroupId = () => {
  return crypto.randomUUID()
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
