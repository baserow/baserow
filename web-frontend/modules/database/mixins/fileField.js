import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'

export default {
  emits: ['update'],

  methods: {
    /**
     * Removes a file at a given index and then updates the value of the field.
     */
    removeFile(value, index) {
      const newValue = JSON.parse(JSON.stringify(value))
      newValue.splice(index, 1)
      this.$emit('update', newValue, value)
    },
    /**
     * Adds multiple files to the field. This happens right after the file has been
     * uploaded to the user files.
     */
    addFiles(value, files) {
      // The file field expects the file name to be a visible name because it is
      // editable per file in the field.
      files = files.map((file) => {
        file.visible_name = file.original_name
        delete file.original_name
        return file
      })
      if (this.$refs.uploadModal) {
        this.$refs.uploadModal.hide()
      }
      const newValue = JSON.parse(JSON.stringify(value))
      newValue.push(...files)
      this.$emit('update', newValue, value)
    },
    /**
     * Updates the visible name of the file with the given index.
     */
    renameFile(value, index, newName) {
      if (newName === '' || newName === null) {
        this.$store.dispatch('toast/error', {
          title: this.$t('fileField.errorEmptyFileNameTitle'),
          message: this.$t('fileField.errorEmptyFileNameMessage'),
        })
        return false
      }

      const newValue = JSON.parse(JSON.stringify(value))
      newValue[index].visible_name = newName
      this.$emit('update', newValue, value)
      return true
    },
    getIconClass(mimeType) {
      return mimetype2icon(mimeType)
    },
  },
}
