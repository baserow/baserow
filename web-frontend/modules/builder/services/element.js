export default (client) => {
  return {
    fetchAll(pageId) {
      return client.get(`builder/page/${pageId}/elements/`)
    },
    create(pageId, elementType, beforeId = null, configuration = null) {
      const payload = {
        type: elementType,
        ...configuration,
      }

      if (beforeId !== null) {
        payload.before_id = beforeId
      }

      return client.post(`builder/page/${pageId}/elements/`, payload)
    },
    update(elementId, values) {
      return client.patch(`builder/element/${elementId}/`, values)
    },
    delete(elementId) {
      return client.delete(`builder/element/${elementId}/`)
    },
    move(targetPageId, elementId, beforeId, parentElementId, placeInContainer) {
      return client.patch(`builder/element/${elementId}/move/`, {
        target_page_id: targetPageId,
        before_id: beforeId,
        parent_element_id: parentElementId,
        place_in_container: placeInContainer,
      })
    },
    duplicate(elementId) {
      return client.post(`builder/element/${elementId}/duplicate/`)
    },
  }
}
