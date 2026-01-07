<template>
  <a
    v-user-file-upload="getFileUploadSettings()"
    class="form-view__file"
    :class="{
      'form-view__file--dragging': dragging,
      'form-view__file--uploading': uploading,
      'form-view__file--error': !isImage,
    }"
  >
    <slot></slot>
    <div class="form-view__file-dragging">Drop here</div>
    <div class="form-view__file-uploading">Uploading</div>
    <div class="form-view__file-error">Not an image</div>
    <div
      v-if="uploading"
      class="form-view__file-progress"
      :style="{ width: percentage + '%' }"
    ></div>
  </a>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { IMAGE_FILE_TYPES } from '@baserow/modules/core/enums'

export default {
  name: 'FormViewImageUpload',
  emits: ['uploaded'],
  data() {
    return {
      dragging: false,
      uploading: false,
      percentage: 0,
      isImage: true,
    }
  },
  methods: {
    getFileUploadSettings() {
      return {
        check: (file) => {
          const isImage = IMAGE_FILE_TYPES.includes(file.type)
          this.isImage = isImage
          return isImage
        },
        accept: () => {
          return 'image/*'
        },
        enter: () => {
          this.dragging = true
        },
        leave: () => {
          this[name].dragging = false
        },
        progress: (event) => {
          const percentage = Math.round((event.loaded * 100) / event.total)
          this.dragging = false
          this.uploading = true
          this.percentage = percentage
        },
        done: (file) => {
          this.dragging = false
          this.uploading = false
          this.percentage = 0
          this.$emit('uploaded', file)
        },
        error: (error) => {
          this.dragging = false
          this.uploading = false
          this.percentage = 0
          notifyIf(error)
        },
      }
    },
  },
}
</script>
