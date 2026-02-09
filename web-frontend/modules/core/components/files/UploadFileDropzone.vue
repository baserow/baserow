<template>
  <div>
    <input
      v-show="false"
      ref="file"
      type="file"
      :multiple="multipleFiles"
      :accept="fileTypesAcceptable"
      @change="$emit('input', $event)"
    />
    <div
      class="upload-files__dropzone"
      :class="{ 'upload-files__dropzone--dragging': dragging }"
      @click.prevent="$refs.file.click($event)"
      @drop.prevent="onDrop($event)"
      @dragover.prevent
      @dragenter.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
    >
      <div class="upload-files__dropzone-content">
        <i class="upload-files__dropzone-icon iconoir-cloud-upload"></i>
        <div class="upload-files__dropzone-text">
          <template v-if="dragging"
            >{{ $t('uploadFileDropzone.drop') }}
          </template>
          <template v-else>{{ $t('uploadFileDropzone.clickOrDrop') }}</template>
        </div>
      </div>
      <div
        v-if="uploading"
        class="upload-files__dropzone-progress"
        :style="{ width: uploadingPercentage + '%' }"
      ></div>
    </div>
  </div>
</template>

<script>
import { getFilesFromEvent } from '@baserow/modules/core/utils/file'

export default {
  name: 'UploadFileDropzone',
  props: {
    uploading: {
      type: Boolean,
      required: false,
      default: false,
    },
    uploadingPercentage: {
      type: Number,
      required: false,
      default: 0,
    },
    fileTypesAcceptable: {
      type: Array,
      required: false,
      default: null,
    },
    multipleFiles: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  emits: ['input'],
  data() {
    return {
      dragging: false,
    }
  },
  methods: {
    onDrop(event) {
      this.dragging = false

      // We have to spread the result of the function since it returns a `FileList`
      // which isn't an array, and we need it to be an array to call functions like
      // `forEach`
      const files = [...getFilesFromEvent(event)]

      if (!this.multipleFiles && files.length > 1) {
        return this.$store.dispatch('toast/error', {
          title: this.$t('uploadFileDropzone.errorTooManyFilesTitle'),
          message: this.$t('uploadFileDropzone.errorTooManyFilesMessage'),
        })
      }

      if (this.fileTypesAcceptable) {
        let hasInvalidFile = false

        files.forEach((file) => {
          if (!this.fileTypesAcceptable.includes(file.type)) {
            hasInvalidFile = true
            this.$store.dispatch('toast/error', {
              title: this.$t('uploadFileDropzone.errorWrongFileTypeTitle'),
              message: this.$t('uploadFileDropzone.errorWrongFileTypeMessage', {
                type: file.type,
              }),
            })
          }
        })

        if (hasInvalidFile) {
          return
        }
      }

      this.$emit('input', event)
    },
  },
}
</script>
