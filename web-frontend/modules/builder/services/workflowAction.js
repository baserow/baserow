export default (client) => {
  return {
    create(pageId, workflowActionType, eventType, configuration = null) {
      const payload = {
        type: workflowActionType,
        event: eventType,
        ...configuration,
      }

      return client.post(`builder/page/${pageId}/workflow_actions/`, payload)
    },
    fetchAll(pageId) {
      return client.get(`builder/page/${pageId}/workflow_actions/`)
    },
    delete(workflowActionId) {
      return client.delete(`builder/workflow_action/${workflowActionId}/`)
    },
    update(workflowActionId, values) {
      return client.patch(
        `builder/workflow_action/${workflowActionId}/`,
        values
      )
    },
    order(pageId, order, elementId = null) {
      const payload = { workflow_action_ids: order }

      if (elementId) {
        payload.element_id = elementId
      }

      return client.post(
        `builder/page/${pageId}/workflow_actions/order/`,
        payload
      )
    },
    dispatch(workflowActionId, data, files) {
      const formData = new FormData()

      Object.entries(files).forEach(([key, file]) => {
        formData.append(key, file)
      })
      formData.append('metadata', JSON.stringify(data))

      return client.post(
        `builder/workflow_action/${workflowActionId}/dispatch/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      )
    },
  }
}
