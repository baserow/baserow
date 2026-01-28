<template>
  <div class="ab-file-input__wrapper">
    <div
      class="ab-file-input"
      :class="{ 'ab-file-input--drag-over': isDragOver }"
      tabindex="0"
      role="button"
      @click="triggerFileInput"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDrop"
      @keydown.enter.prevent="triggerFileInput"
      @keydown.space.prevent="triggerFileInput"
    >
      <div>{{ helpText }}</div>
      <input
        ref="fileInputRef"
        type="file"
        :multiple="multiple"
        class="ab-file-input__input"
        :accept="acceptProp"
        @change="onFileChange"
      />
    </div>

    <ul v-if="displayedFiles.length" class="ab-file-input__files">
      <li
        v-for="(file, index) in displayedFiles"
        :key="file.url"
        class="ab-file-input__file"
      >
        <ABPresentation
          :title="file.name || `File ${index + 1}`"
          :icon="getIconForType(file)"
          :image="getImage(file)"
          :subtitle="formatSize(file.size)"
        />
        <ABIcon
          icon="iconoir-bin"
          is-button
          :title="$t('abFileInput.delete')"
          @click.stop="removeFile(index)"
        />
      </li>
    </ul>
  </div>
</template>

<script>
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'

export default {
  name: 'ABFileInput',
  props: {
    modelValue: {
      type: [Array, Object, null],
      default: null,
    },
    multiple: {
      type: Boolean,
      default: true,
    },
    preview: {
      type: Boolean,
      default: true,
    },
    helpText: {
      type: String,
      default: 'Drag and drop files here or click to select',
    },
    accept: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['input', 'update:modelValue'],
  data() {
    return {
      files: this.normalizeValue(this.modelValue),
      isDragOver: false,
    }
  },
  computed: {
    displayedFiles() {
      return this.files
    },
    acceptProp() {
      if (this.accept.length === 0) {
        return null
      }
      return this.accept.join(',')
    },
  },
  watch: {
    modelValue(newVal) {
      this.files = this.normalizeValue(newVal)
    },
    multiple(newVal) {
      if (newVal && this.modelValue && !Array.isArray(this.modelValue)) {
        this.files = [this.modelValue]
        this.$emit('update:modelValue', [this.modelValue])
      } else if (!newVal && Array.isArray(this.modelValue)) {
        this.files = this.modelValue.length ? [this.modelValue[0]] : []
        this.$emit('update:modelValue', this.files[0] || null)
      }
    },
  },
  methods: {
    getIconForType(file) {
      if (!this.preview || !file?.content_type?.startsWith('image/')) {
        return mimetype2icon(file.content_type)
      }
      return null
    },
    getImage(file) {
      if (this.preview && file?.content_type?.startsWith('image/')) {
        if (file.data) {
          return URL.createObjectURL(file.data)
        }
        return file.url
      }
      return null
    },
    newFile({ name, data, contentType, size }) {
      return {
        name,
        data,
        content_type: contentType,
        size,
        __file__: true,
      }
    },
    normalizeValue(val) {
      if (!val) return []
      const list = this.multiple ? val : [val]
      return [...list]
    },
    toValueFormat(files) {
      if (this.multiple) return files
      return files.length ? files[0] : null
    },
    onFileChange(event) {
      this.addFiles(Array.from(event.target.files))
      event.target.value = ''
    },
    onDrop(event) {
      this.addFiles(Array.from(event.dataTransfer.files))
      this.isDragOver = false
    },
    addFiles(files) {
      const newFiles = files.map((file) =>
        this.newFile({
          name: file.name,
          data: file,
          contentType: file.type,
          size: file.size,
        })
      )
      if (this.multiple) {
        this.files.push(...newFiles)
      } else {
        this.files = newFiles.slice(0, 1)
      }
      const value = this.toValueFormat(this.files)
      this.$emit('input', value)
      this.$emit('update:modelValue', value)
    },
    onDragOver() {
      this.isDragOver = true
    },
    onDragLeave() {
      this.isDragOver = false
    },
    triggerFileInput() {
      this.$refs.fileInputRef.click()
    },
    removeFile(index) {
      this.files.splice(index, 1)
      const value = this.toValueFormat(this.files)
      this.$emit('input', value)
      this.$emit('update:modelValue', value)
    },
    formatSize(bytes) {
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      if (bytes === null || bytes === undefined) return null
      if (bytes === 0) return '0 Byte'
      const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)), 10)
      return Math.round(bytes / Math.pow(1024, i)) + ' ' + sizes[i]
    },
  },
}
</script>
