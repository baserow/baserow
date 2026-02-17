import { notifyIf } from '@baserow/modules/core/utils/error'

import FieldService from '@baserow_premium/services/field'
import { AI_FIELD_STATUS } from '@baserow_premium/constants'

export default {
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
    generating() {
      const metadata = this.row?._?.metadata
      return (
        metadata?.ai_field?.[this.field.id]?.status === AI_FIELD_STATUS.GENERATING
      )
    },
    modelAvailable() {
      const aIModels =
        this.$store.getters['settings/get'].generative_ai[
          this.field.ai_generative_ai_type
        ] || []
      return (
        this.$registry
          .get('field', this.field.type)
          .isEnabled(this.workspace) &&
        aIModels.includes(this.field.ai_generative_ai_model)
      )
    },
    isDeactivated() {
      return this.$registry
        .get('field', this.field.type)
        .isDeactivated(this.workspaceId)
    },
    deactivatedClickComponent() {
      return this.$registry
        .get('field', this.field.type)
        .getDeactivatedClickModal(this.workspaceId)
    },
  },
  methods: {
    async generate() {
      if (this.isDeactivated) {
        this.$refs.clickModal.show()
        return
      }

      const rowId = this.row.id
      const previousMetadata =
        this.row?._?.metadata?.ai_field?.[this.field.id] || null

      // Optimistic update to store
      this.$store.commit('rowModal/UPDATE_ROW_METADATA', {
        rowId,
        metadata: {
          ai_field: {
            [this.field.id]: { status: AI_FIELD_STATUS.GENERATING },
          },
        },
      })

      try {
        await FieldService(this.$client).generateAIFieldValues(this.field.id, [
          rowId,
        ])
      } catch (error) {
        notifyIf(error, 'field')
        // Rollback on error
        this.$store.commit('rowModal/UPDATE_ROW_METADATA', {
          rowId,
          metadata: {
            ai_field: {
              [this.field.id]: previousMetadata,
            },
          },
        })
      }
    },
  },
}
