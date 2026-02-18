<template>
  <div class="control__elements">
    <ul class="field-file__list">
      <li
        v-for="(file, index) in files"
        :key="file.name + '-' + index"
        class="field-file__item"
      >
        <FileInProgress
          v-if="file.state === 'loading'"
          :file="file"
          :read-only="readOnly"
          :icon-class="getIconClass(file.mime_type)"
          @delete="forceRemoveFile(getFileInProgressIndex(file.id))"
        />
        <FileFailed
          v-else-if="file.state === 'failed'"
          :file="file"
          :read-only="readOnly"
          :icon-class="getIconClass(file.mime_type)"
          @delete="forceRemoveFile(getFileInProgressIndex(file.id))"
        />
        <FileUploaded
          v-else
          :ref="`file-uploaded-${index}`"
          :file="file"
          :read-only="readOnly"
          :icon-class="getIconClass(file.mime_type)"
          @delete="removeFile(value, index)"
          @rename="(name) => renameFile(value, index, name)"
          @click="$refs.fileModal.show(index)"
        />
      </li>
    </ul>
    <UploadFileDropzone v-if="!readOnly" @input="filesAdded($event)" />
    <ButtonText
      v-if="!readOnly"
      icon="iconoir-plus"
      tag="a"
      @click.prevent="showModal()"
    >
      {{ $t('rowEditFieldFile.addFile') }}
    </ButtonText>
    <UserFilesModal
      v-if="!readOnly"
      ref="uploadModal"
      :upload-file="uploadFile"
      :user-file-upload-types="userFileUploadTypes"
      @uploaded="addFiles(value, $event)"
    ></UserFilesModal>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
    <FileFieldModal
      v-if="Boolean(value)"
      ref="fileModal"
      :files="value"
      :read-only="readOnly"
      @removed="removeFile(value, $event)"
      @renamed="renameFile(value, $event.index, $event.value)"
    ></FileFieldModal>
  </div>
</template>

<script>
import { uuid } from '@baserow/modules/core/utils/string'
import FileFieldModal from '@baserow/modules/database/components/field/FileFieldModal'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import fileField from '@baserow/modules/database/mixins/fileField'
import UploadFileDropzone from '@baserow/modules/core/components/files/UploadFileDropzone'
import UserFileService from '@baserow/modules/core/services/userFile'
import { UploadFileUserFileUploadType } from '@baserow/modules/core/userFileUploadTypes'
import UserFilesModal from '@baserow/modules/core/components/files/UserFilesModal'
import axios from 'axios'
import FileInProgress from '@baserow/modules/core/components/files/FileInProgress'
import FileFailed from '@baserow/modules/core/components/files/FileFailed'
import FileUploaded from '@baserow/modules/core/components/files/FileUploaded'
import { IMAGE_FILE_TYPES } from '@baserow/modules/core/enums'

export default {
  components: {
    FileUploaded,
    FileFailed,
    FileInProgress,
    UploadFileDropzone,
    FileFieldModal,
    UserFilesModal,
  },
  mixins: [rowEditField, fileField],
  props: {
    uploadFile: {
      type: Function,
      required: false,
      default: null,
    },
    userFileUploadTypes: {
      type: Array,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      filesInProgress: [],
      currentFileUploading: null,
      cancelToken: null,
    }
  },
  computed: {
    files() {
      return this.value?.concat(this.filesInProgress)
    },
    uploadFileFunction() {
      return this.uploadFile || UserFileService(this.$client).uploadFile
    },
  },
  methods: {
    showModal() {
      this.$refs.uploadModal.show(UploadFileUserFileUploadType.getType())
    },
    async filesAdded(event) {
      const files = event.target.files || event.dataTransfer?.files

      if (!files) {
        return
      }

      let successfulUploads = []
      const filesWithData = Array.from(files).map((file) => ({
        file,
        fileData: this.forceAddFile(file, { state: 'loading' }),
      }))

      for (const { file, fileData } of filesWithData) {
        // File has been removed in the meantime
        if (this.getFileInProgressIndex(fileData.id) === -1) {
          continue
        }

        const progress = (event) => {
          fileData.percentage = Math.round((event.loaded * 100) / event.total)
        }

        try {
          this.currentFileUploading = fileData
          this.cancelToken = axios.CancelToken.source()
          const { data } = await this.uploadFileFunction(
            file,
            progress,
            this.cancelToken.token
          )
          successfulUploads.push({
            id: fileData.id,
            order: this.getFileInProgressIndex(fileData.id),
            data,
          })
        } catch (error) {
          const message = error.handler.getMessage('userFile')
          error.handler.handled()
          this.forceUpdateFile(fileData.id, {
            state: 'failed',
            error: message.message,
          })
        }
      }

      // Make sure a file has not been removed after it has been uploaded
      successfulUploads = successfulUploads.filter(
        ({ id }) => this.getFileInProgressIndex(id) !== -1
      )

      // Make sure to re-establish the order in which the files have been submitted
      successfulUploads.sort((a, b) => a.order - b.order)

      successfulUploads.forEach(({ id }) =>
        this.forceRemoveFile(this.getFileInProgressIndex(id))
      )
      this.addFiles(
        this.value,
        successfulUploads.map(({ data }) => data)
      )
    },
    forceUpdateFile(id, values) {
      const fileIndex = this.getFileInProgressIndex(id)
      this.filesInProgress[fileIndex] = {
        ...this.files[fileIndex],
        ...values,
      }
    },
    forceRemoveFile(index) {
      if (this.getFileInProgressIndex(this.currentFileUploading.id) === index) {
        this.cancelToken.cancel()
      }
      this.filesInProgress.splice(index, 1)
    },
    forceAddFile(file, additionalData = {}) {
      const id = uuid()
      const fileData = {
        id,
        visible_name: file.name,
        isImage: IMAGE_FILE_TYPES.includes(file.type),
        percentage: 0,
        ...additionalData,
      }

      this.filesInProgress.push(fileData)

      return fileData
    },
    removeFile(...args) {
      fileField.methods.removeFile.call(this, ...args)
      this.touch()
    },
    addFiles(...args) {
      fileField.methods.addFiles.call(this, ...args)
      this.touch()
    },
    renameFile(value, index, newName) {
      const success = fileField.methods.renameFile.call(
        this,
        value,
        index,
        newName
      )

      if (!success) {
        this.$refs[`file-uploaded-${index}`][0].resetName()
      }

      this.touch()
    },
    getFileInProgressIndex(id) {
      return this.filesInProgress.findIndex((file) => file.id === id)
    },
  },
}
</script>
