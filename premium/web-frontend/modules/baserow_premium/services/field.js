export default (client) => {
  return {
    generateAIFieldValues(fieldId, rowIds) {
      return client.post(
        `/database/fields/${fieldId}/generate-ai-field-values/`,
        { row_ids: rowIds }
      )
    },
    generateAIFormula(tableId, aiType, aiModel, temperature, prompt) {
      return client.post(
        `/database/fields/table/${tableId}/generate-ai-formula/`,
        {
          ai_type: aiType,
          ai_model: aiModel,
          ai_temperature: temperature || null,
          ai_prompt: prompt,
        }
      )
    },
    regenerateAIFieldValues(fieldId, { viewId, rowIds, skipPopulated }) {
      // TODO: Replace with actual AI field regeneration endpoint when backend is ready
      // POST /database/fields/{fieldId}/regenerate-values/async/
      // For now, this is a placeholder structure
      return client.post(
        `/database/fields/${fieldId}/regenerate-values/async/`,
        {
          view_id: viewId || null,
          row_ids: rowIds || [],
          skip_populated: skipPopulated || false,
        }
      )
    },
  }
}
