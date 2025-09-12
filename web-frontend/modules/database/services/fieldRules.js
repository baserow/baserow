function getUrl(tableId, ruleId = null) {
  if (ruleId === null) {
    return `/database/field-rules/${tableId}/`
  }
  return `/database/field-rules/${tableId}/rule/${ruleId}/`
}

export default (client) => {
  return {
    getRules(tableId) {
      return client.get(getUrl(tableId))
    },
    createRule(tableId, rule) {
      return client.post(getUrl(tableId), rule)
    },
    updateRule(tableId, ruleId, rule) {
      return client.put(getUrl(tableId, ruleId), rule)
    },
    deleteRule(tableId, ruleId) {
      return client.delete(getUrl(tableId, ruleId))
    },
  }
}
