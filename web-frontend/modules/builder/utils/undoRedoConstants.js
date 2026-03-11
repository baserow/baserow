// The different types of undo/redo scopes available for the builder module.
export const BUILDER_ACTION_SCOPES = {
  page(pageId) {
    return {
      page: pageId,
    }
  },
}
