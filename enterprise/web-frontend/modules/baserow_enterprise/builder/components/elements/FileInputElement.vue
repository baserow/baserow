<template>
  <ABFormGroup
    class="file-input-element"
    :label="resolvedLabel"
    :error-message="errorMessage"
    :autocomplete="isEditMode ? 'off' : ''"
    :required="element.required"
    :style="getStyleOverride('input')"
  >
    <ABFileInput
      v-model="computedInputValue"
      :multiple="element.multiple"
      :help-text="resolvedHelpText"
      :accept="allowedExtensions"
      :preview="element.preview"
    />
  </ABFormGroup>
</template>

<script>
import formElement from '@baserow/modules/builder/mixins/formElement'
import { ensureString } from '@baserow/modules/core/utils/validator'
import UserFileService from '@baserow/modules/core/services/userFile'

import { FileInputElementType } from '@baserow_enterprise/builder/elementTypes'

export default {
  name: 'FileInputElement',
  mixins: [formElement],
  props: {
    /**
     * @type {Object}
     * @property {string} label - The input's label.
     * @property {string} default_url - Initial url(s).
     * @property {string} default_name - Initial Name(s).
     * @property {string} help_text - Help text to show in the input.
     * @property {boolean} required - Whether the input is required.
     * @property {boolean} preview - Whether the user want to show the preview.
     * @property {boolean} multiple - Whether the input supports multiple files.
     * @property {Array} allowed_filetypes - List of allowed extensions.
     */
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      fileData: {},
    }
  },
  computed: {
    computedInputValue: {
      get() {
        return this.inputValue
      },
      set(value) {
        this.inputValue = value
        this.onFormElementTouch()
      },
    },
    resolvedLabel() {
      return ensureString(this.resolveFormula(this.element.label))
    },
    allowedExtensions() {
      return this.element.allowed_filetypes
        .filter((v) => v)
        .map((value) => {
          if (
            value.startsWith('.') ||
            ['image/*', 'video/*', 'audio/*'].includes(value)
          ) {
            return value
          } else {
            return `.${value}`
          }
        })
    },
    resolvedDefaultValueWithMetadata() {
      if (this.element.multiple) {
        return this.resolvedDefaultValue.map((f) => ({
          ...f,
          ...this.fileData[f.url],
        }))
      } else if (this.resolvedDefaultValue) {
        return {
          ...this.resolvedDefaultValue,
          ...this.fileData[this.resolvedDefaultValue.url],
        }
      } else {
        return null
      }
    },
    atLeastOneFileExceedSize() {
      if (this.element.multiple) {
        return this.inputValue.some(({ size }) => {
          return (
            typeof size === 'number' &&
            size / (1024 * 1024) >= this.element.max_filesize
          )
        })
      } else {
        const v = this.inputValue?.size
        return (
          typeof v === 'number' &&
          v / (1024 * 1024) >= this.element.max_filesize
        )
      }
    },
    resolvedHelpText() {
      return (
        ensureString(this.resolveFormula(this.element.help_text)) ||
        this.$t('fileInputElement.defaultHelpText')
      )
    },
  },
  watch: {
    // override the default mixin method because we want to use the one with metadata
    resolvedDefaultValue() {},
    resolvedDefaultValueWithMetadata: {
      handler(value) {
        if (process.client) {
          this.updatedMetadata()
        }
        this.inputValue = value
      },
      immediate: true,
    },
  },
  mounted() {
    this.updatedMetadata()
  },
  methods: {
    getErrorMessage() {
      switch (
        FileInputElementType.getError(
          this.element,
          this.inputValue,
          this.applicationContext
        )
      ) {
        case 'fileSize':
          return this.$t('fileInputElement.fileSizeExceeded', {
            max: this.element.max_filesize,
          })
        case 'required':
          return this.$t('error.requiredField')
        default:
          return ''
      }
    },
    updatedMetadata() {
      ;(this.element.multiple
        ? this.resolvedDefaultValue
        : [this.resolvedDefaultValue]
      ).forEach(async (fileObj) => {
        if (fileObj && !this.fileData[fileObj.url]) {
          this.fileData = {
            ...this.fileData,
            [fileObj.url]: {
              content_type: 'application/octet-stream',
              size: null,
            },
          }
          try {
            const metadata = await UserFileService(
              this.$client
            ).getFileMetadata(fileObj.url)
            this.fileData = {
              ...this.fileData,
              [fileObj.url]: {
                content_type: metadata.contentType,
                size: metadata.size,
              },
            }
          } catch {
            // If for some reason it doesn't work (head request not allowed for
            // instance) we just want to nuke the data.
            this.fileData = {
              ...this.fileData,
              [fileObj.url]: {
                content_type: 'application/octet-stream',
                size: null,
              },
            }
          }
        }
      })
    },
  },
}
</script>
