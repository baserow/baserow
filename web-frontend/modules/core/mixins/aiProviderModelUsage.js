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
     *   failed: boolean}>} The counts to warn about, and whether the lookup
     *   itself failed.
     */
    async lookupModelUsage(modelId, workspaceId = null) {
      try {
        const result = await this.$store.dispatch(
          'aiProvider/fetchModelUsage',
          {
            modelId,
            ...(workspaceId === null ? {} : { workspaceId }),
          }
        )
        return { ...result, failed: false }
      } catch {
        // An unchecked model is not a safe model: confirm instead of assuming zero.
        return { usage: [], failed: true }
      }
    },
    /** @returns {boolean} Whether the model may still have dependents. */
    modelHasDependents(result) {
      return result.failed || result.usage.some((entry) => entry.count > 0)
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
