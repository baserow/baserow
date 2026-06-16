// The different types of undo/redo scopes available for the builder module.
export const BUILDER_ACTION_SCOPES = {
  // Scope for the page currently being edited. `sharedPageId` is sent alongside
  // so that edits to shared (header/footer) elements — which live on the builder's
  // shared page — are undoable while editing any content page.
  page(pageId, sharedPageId = null) {
    return {
      page: pageId,
      shared_page: sharedPageId,
    }
  },
}
