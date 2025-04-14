<template>
  <Modal :left-sidebar="true" @hidden="$emit('hidden')">
    <template #sidebar>
      <div class="modal-sidebar__title">
        {{ $t('userFilesModal.title') }}
      </div>
      <ul class="modal-sidebar__nav">
        <li v-for="upload in registeredUserFileUploads" :key="upload.type">
          <a
            class="modal-sidebar__nav-link"
            :class="{ active: page === upload.type }"
            @click="setPage(upload.type)"
          >
            <i class="modal-sidebar__nav-icon" :class="upload.iconClass"></i>
            {{ upload.getName() }}
          </a>
        </li>
      </ul>
    </template>
    <template #content>
      <component
        :is="userFileUploadComponent"
        :upload-file="uploadFile"
        :multiple-files="multipleFiles"
        :file-types-acceptable="fileTypesAcceptable"
        @uploaded="$emit('uploaded', $event)"
      ></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'UserFilesModal',
  mixins: [modal],
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
    multipleFiles: {
      type: Boolean,
      required: false,
      default: true,
    },
    fileTypesAcceptable: {
      type: Array,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      page: null,
    }
  },
  computed: {
    registeredUserFileUploads() {
      const uploadTypes = this.$registry.getAll('userFileUpload')
      // The `userFileUploadTypes` contains an array of allowed upload types. If not
      // `null`, we need to remove the ones that are not allowed from `uploadTypes`
      // because that one contains all the available upload files.
      if (this.userFileUploadTypes !== null) {
        Object.keys(uploadTypes).forEach((typeName) => {
          if (!this.userFileUploadTypes.includes(typeName)) {
            delete uploadTypes[typeName]
          }
        })
      }
      return uploadTypes
    },
    userFileUploadComponent() {
      const active = Object.values(
        this.$registry.getAll('userFileUpload')
      ).find((upload) => upload.type === this.page)
      return active ? active.getComponent() : null
    },
  },
  methods: {
    setPage(page) {
      this.page = page
    },
    isPage(page) {
      return this.page === page
    },
    show(page, ...args) {
      this.page = page
      return modal.methods.show.call(this, ...args)
    },
  },
}
</script>
