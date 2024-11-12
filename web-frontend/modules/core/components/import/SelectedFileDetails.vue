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
        <ButtonIcon
          icon="iconoir-bin"
          :disabled="disabled"
          @click="handleRemove()"
        ></ButtonIcon>
      </span>
    </div>
    <div class="import-workspace-separator"></div>
  </div>
</template>

<script>
import ImportWorkspaceService from '@baserow/modules/core/services/importExportService'
import error from '@baserow/modules/core/mixins/error'
import { formatFileSize } from '@baserow/modules/core/utils/file'

export default {
  name: 'SelectedFileDetails',
  components: {},
  mixins: [error],
  props: {
    importFile: {
      required: true,
      validator(value) {
        return value instanceof File || value instanceof Object
      },
    },
    workspaceId: {
      type: Number,
      required: true,
    },
    resourceId: {
      type: Number,
      required: false,
      default: null,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      deleting: false,
    }
  },

  methods: {
    formatSize(bytes) {
      return formatFileSize(this.$i18n, bytes)
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
