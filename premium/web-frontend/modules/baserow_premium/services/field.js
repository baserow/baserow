import { GenerateAIValuesJobType } from '@baserow_premium/jobTypes'

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
    generateAIValues(fieldId, { viewId, rowIds, onlyEmpty }) {
      const payload = {
        type: 'generate_ai_values',
        field_id: fieldId,
        only_empty: onlyEmpty || false,
      }

      // Only include view_id if provided
      if (viewId) {
        payload.view_id = viewId
      }

      // Only include row_ids if provided and not empty
      if (rowIds && rowIds.length > 0) {
        payload.row_ids = rowIds
      }

      return client.post(`/jobs/`, payload)
    },
    listGenerateAIValuesJobs(fieldId, { offset, limit = 10 } = {}) {
      const params = new URLSearchParams()
      params.append('type', GenerateAIValuesJobType.getType())
      params.append(GenerateAIValuesJobType.getType() + '_field_id', fieldId)
      if (offset !== undefined) {
        params.append('offset', offset)
      }
      if (limit !== undefined) {
        params.append('limit', limit)
      }

      const config = { params }
      return client.get(`/jobs/`, config)
    },
  }
}
