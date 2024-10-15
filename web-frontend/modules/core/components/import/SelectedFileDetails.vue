<template>
  <div>
    <div class="import-workspace__file">
      <div class="import-workspace__file-wrapper">
        <div class="import-workspace__file-icon">
          <i class="baserow-icon-file-archive"></i>
        </div>

        <div class="import-workspace__file-details">
          <div class="import-workspace__file-name">
            <div class="import-workspace__file-name-text">
              {{ importFile.name }}
            </div>
          </div>

          <div class="import-workspace__file-size">
            {{ formatSize(importFile.size) }}
          </div>
        </div>
      </div>

      <span>
        <ButtonIcon icon="iconoir-bin" @click="handleRemove()"></ButtonIcon>
      </span>
    </div>
    <div class="import-workspace-separator"></div>
  </div>
</template>

<script>
import ImportWorkspaceService from '@baserow/modules/core/services/importWorkspaceService'
import error from '@baserow/modules/core/mixins/error'

export default {
  name: 'SelectedFileDetails',
  components: {},
  mixins: [error],
  props: {
    importFile: {
      required: true,
      validator(value) {
        return value instanceof File
      },
    },
    workspaceId: {
      type: Number,
      required: true,
    },
    resourceId: {
      type: String,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      deleting: false,
    }
  },

  methods: {
    formatSize(bytes) {
      if (bytes === 0) return '0 ' + this.$i18n.t(`rowEditFieldFile.sizes.0`)
      const k = 1024
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      const float = parseFloat((bytes / k ** i).toFixed(2)).toLocaleString(
        this.$i18n.locale
      )
      return float + ' ' + this.$i18n.t(`rowEditFieldFile.sizes.${i}`)
    },
    async handleRemove() {
      if (this.resourceId) {
        await this.deleteResource()
      }
      this.$emit('import-workspace-reset')
    },
    async deleteResource() {
      this.deleting = true
      try {
        await ImportWorkspaceService(this.$client).deleteResource(
          this.workspaceId,
          this.resourceId
        )
      } catch (error) {
        this.handleError(error)
      } finally {
        this.deleting = false
      }
    },
  },
}
</script>
