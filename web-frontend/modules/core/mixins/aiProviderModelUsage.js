import { aiProviderModelUsageMessage } from '@baserow/modules/core/utils/aiProvider'

/**
 * Shared model-usage lookup and copy for the surfaces that disable, delete or
 * narrow an AI provider model.
 */
export default {
  methods: {
    /**
     * @param {number} modelId The provider model to count consumers for.
     * @param {number|null} workspaceId The workspace scope, null for instance.
     * @returns {Promise<{usage: Array<{featureType: string, count: number}>,
     *   blockingFeatureTypes: string[]}>} The counts to warn about and the
     *   features that refuse the change, both empty when the lookup fails.
     */
    async lookupModelUsage(modelId, workspaceId = null) {
      try {
        return await this.$store.dispatch('aiProvider/fetchModelUsage', {
          modelId,
          ...(workspaceId === null ? {} : { workspaceId }),
        })
      } catch {
        // Counts only sharpen a warning; a failed lookup must not block the action.
        return { usage: [], blockingFeatureTypes: [] }
      }
    },
    /** @returns {boolean} Whether anything still depends on the model. */
    modelHasDependents(result) {
      return (
        result.usage.some((entry) => entry.count > 0) ||
        result.blockingFeatureTypes.length > 0
      )
    },
    /** @returns {string} The description, prefixed with what depends on the model. */
    modelUsageMessage(result, description) {
      return aiProviderModelUsageMessage(
        result,
        description,
        this.$t.bind(this),
        this.$registry
      )
    },
  },
}
