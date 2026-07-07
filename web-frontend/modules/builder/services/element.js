export default (client) => {
  return {
    fetchAll(pageId) {
      return client.get(`builder/page/${pageId}/elements/`)
    },
    create(
      pageId,
      elementType,
      referenceElementId = null,
      position = 'south',
      placeInContainer = '',
      configuration = {}
    ) {
      const payload = {
        type: elementType,
        position,
        place_in_container: placeInContainer,
        ...configuration,
      }

      if (referenceElementId !== null) {
        payload.reference_element_id = referenceElementId
      }

      return client.post(`builder/page/${pageId}/elements/`, payload)
    },
    update(elementId, values) {
      return client.patch(`builder/element/${elementId}/`, values)
    },
    delete(elementId) {
      return client.delete(`builder/element/${elementId}/`)
    },
    move(
      elementId,
      referenceElementId,
      position,
      placeInContainer,
      targetPageId
    ) {
      return client.patch(`builder/element/${elementId}/move/`, {
        reference_element_id: referenceElementId,
        position,
        place_in_container: placeInContainer,
        target_page_id: targetPageId,
      })
    },
    duplicate(elementId) {
      return client.post(`builder/element/${elementId}/duplicate/`)
    },
  }
}
