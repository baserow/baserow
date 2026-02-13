<template>
  <div
    ref="cell"
    class="grid-view__cell grid-field-file__cell"
    :class="{ active: selected }"
    @drop.prevent="onDrop($event)"
    @dragover.prevent
    @dragenter.prevent="dragEnter($event)"
    @dragleave="dragLeave($event)"
  >
    <div v-show="dragging" class="grid-field-file__dragging">
      <div>
        <i class="grid-field-file__drop-icon iconoir-cloud-upload"></i>
        {{ $t('gridViewFieldFile.dropHere') }}
      </div>
    </div>
    <ul v-if="Array.isArray(value)" class="grid-field-file__list">
      <li
        v-for="(file, index) in value"
        :key="file.name + index"
        class="grid-field-file__item"
      >
        <a
          v-tooltip="file.visible_name"
          class="grid-field-file__link"
          @click.prevent="showFileModal(index)"
        >
          <img
            v-if="file.is_image && file.thumbnails?.tiny?.url"
            class="grid-field-file__image"
            :src="file.thumbnails.tiny.url"
          />
          <i
            v-else
            class="grid-field-file__icon"
            :class="getIconClass(file.mime_type)"
          ></i>
        </a>
      </li>
      <li
        v-for="loading in loadings"
        :key="loading.id"
        class="grid-field-file__item"
      >
        <div class="grid-field-file__loading"></div>
      </li>
      <li v-if="!readOnly" v-show="selected" class="grid-field-file__item">
        <a class="grid-field-file__item-add" @click.prevent="showUploadModal()">
          <i class="iconoir-plus"></i>
        </a>
        <div v-if="value.length == 0" class="grid-field-file__drop">
          <i class="grid-field-file__drop-icon iconoir-cloud-upload"></i>
          {{ $t('gridViewFieldFile.dropFileHere') }}
        </div>
      </li>
    </ul>
    <UserFilesModal
      v-if="Array.isArray(value) && !readOnly"
      ref="uploadModal"
      @uploaded="addFiles(value, $event)"
      @hidden="hideModal"
    ></UserFilesModal>
    <FileFieldModal
      v-if="Array.isArray(value)"
      ref="fileModal"
      :files="value"
      :read-only="readOnly"
      @hidden="hideModal"
      @removed="removeFile(value, $event)"
      @renamed="renameFile(value, $event.index, $event.value)"
    ></FileFieldModal>
  </div>
</template>

<script>
import { uuid } from '@baserow/modules/core/utils/string'
import { isElement } from '@baserow/modules/core/utils/dom'
import { notifyIf } from '@baserow/modules/core/utils/error'
import UserFilesModal from '@baserow/modules/core/components/files/UserFilesModal'
import { UploadFileUserFileUploadType } from '@baserow/modules/core/userFileUploadTypes'
import UserFileService from '@baserow/modules/core/services/userFile'
import FileFieldModal from '@baserow/modules/database/components/field/FileFieldModal'
import gridField from '@baserow/modules/database/mixins/gridField'
import fileField from '@baserow/modules/database/mixins/fileField'

export default {
  name: 'GridViewFieldFile',
  components: { UserFilesModal, FileFieldModal },
  mixins: [gridField, fileField],
  emits: ['add-keep-alive', 'remove-keep-alive', 'select'],
  data() {
    return {
      modalOpen: false,
      dragging: false,
      loadings: [],
      dragTarget: null,
      // Event handler reference for cleanup
      keydownEvent: null,
    }
  },
  methods: {
    /**
     * Method is called when the user drops his files into the field. The files should
     * automatically be uploaded to the user files and added to the field after that.
     */
    async onDrop(event) {
      const files = [...event.dataTransfer.items].map((item) =>
        item.getAsFile()
      )
      await this.uploadFiles(files)
    },
    async uploadFiles(fileArray) {
      if (this.readOnly) {
        return
      }

      this.dragging = false

      // Indicates that this component must not be destroyed even though the user might
      // select another cell.
      this.$emit('add-keep-alive')

      const files = fileArray.map((file) => {
        return {
          id: uuid(),
          file,
        }
      })

      if (files === null) {
        return
      }

      this.$emit('select')

      // First add the file ids to the loading list so the user sees a visual loading
      // indication for each file.
      files.forEach((file) => {
        this.loadings.push({ id: file.id })
      })

      // Now upload the files one by one to not overload the backend. When finished,
      // regardless of is has succeeded, the loading state for that file can be removed
      // because it has already been added as a file.
      for (let i = 0; i < files.length; i++) {
        const id = files[i].id
        const file = files[i].file

        try {
          const { data } = await UserFileService(this.$client).uploadFile(file)
          this.addFiles(this.value, [data])
        } catch (error) {
          notifyIf(error, 'userFile')
        }

        const index = this.loadings.findIndex((l) => l.id === id)
        this.loadings.splice(index, 1)
      }

      // Indicates that this component can be destroyed if it is not selected.
      this.$emit('remove-keep-alive')
    },
    select() {
      // While the field is selected we want to open the select row toast by pressing
      // the enter key.
      this.keydownEvent = (event) => {
        if (event.key === 'Enter' && !this.modalOpen) {
          this.showUploadModal()
        }
      }
      document.body.addEventListener('keydown', this.keydownEvent)
    },
    beforeUnSelect() {
      document.body.removeEventListener('keydown', this.keydownEvent)
    },
    /**
     * If the user clicks inside the select row modal we do not want to unselect the
     * field. The modal lives in the root of the body element and not inside the cell,
     * so the system naturally wants to unselect when the user clicks inside one of
     * these contexts.
     */
    canUnselectByClickingOutside(event) {
      return (
        (!this.$refs.uploadModal ||
          !isElement(this.$refs.uploadModal.$el, event.target)) &&
        !isElement(this.$refs.fileModal.$el, event.target)
      )
    },
    /**
     * Prevent unselecting the field cell by changing the event. Because the deleted
     * item is not going to be part of the dom anymore after deleting it will get
     * noticed as if the user clicked outside the cell which wasn't the case.
     */
    removeFile(event, index) {
      event.preventFieldCellUnselect = true
      return fileField.methods.removeFile.call(this, event, index)
    },
    showUploadModal() {
      if (this.readOnly) {
        return
      }

      this.modalOpen = true
      this.$refs.uploadModal.show(UploadFileUserFileUploadType.getType())
    },
    showFileModal(index) {
      this.modalOpen = true
      this.$refs.fileModal.show(index)
    },
    hideModal() {
      this.modalOpen = false
    },
    /**
     * While the modal is open, all key combinations related to the field must be
     * ignored.
     */
    canSelectNext() {
      return !this.modalOpen
    },
    canKeyDown() {
      return !this.modalOpen
    },
    canKeyboardShortcut() {
      return !this.modalOpen
    },
    dragEnter(event) {
      if (this.readOnly) {
        return
      }

      this.dragging = true
      this.dragTarget = event.target
    },
    dragLeave(event) {
      if (this.dragTarget === event.target && !this.readOnly) {
        event.stopPropagation()
        event.preventDefault()
        this.dragging = false
        this.dragTarget = null
      }
    },
    onPaste(event) {
      if (
        !event.clipboardData.types.includes('text/plain') ||
        event.clipboardData.getData('text/plain').startsWith('file:///')
      ) {
        const { items } = event.clipboardData
        for (let i = 0; i < items.length; i++) {
          const item = items[i]
          if (item.type.includes('image')) {
            const file = item.getAsFile()
            this.uploadFiles([file])
            return true
          }
        }
      }
      return false
    },
  },
}
</script>
