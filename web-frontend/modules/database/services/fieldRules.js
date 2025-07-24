function getUrl(tableId, ruleId = null) {
  // /api/database/field_rules/{table_id}/
  // /api/database/field_rules/{table_id}/rule/{rule_id}/
  if (ruleId === null) {
    return `/database/field_rules/${tableId}/`
  }
  return `/database/field_rules/${tableId}/rule/${ruleId}/`
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
