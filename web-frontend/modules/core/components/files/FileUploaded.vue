<template>
  <div class="upload-files__file-uploaded">
    <div class="field-file__preview">
      <a class="field-file__icon" @click="$emit('click')">
        <img v-if="file.is_image" :src="file.thumbnails.small.url" />
        <i v-else :class="iconClass"></i>
      </a>
    </div>
    <div class="field-file__description">
      <div class="field-file__name">
        <Editable
          ref="nameEditable"
          :value="file.visible_name"
          @change="$emit('rename', $event.value)"
        ></Editable>
      </div>
      <div class="field-file__info">
        <div>
          {{ getDate(file.uploaded_at) }} -
          {{ formatSize(file.size) }}
        </div>
      </div>
    </div>
    <div class="field-file__actions">
      <ButtonIcon
        v-if="!readOnly"
        v-tooltip="$t('action.rename')"
        tag="a"
        size="small"
        icon="iconoir-edit-pencil"
        @click="$refs.nameEditable.edit()"
      ></ButtonIcon>
      <DownloadLink
        :filename="file.visible_name"
        :url="file.url"
        class="button-icon button-icon--small"
        loading-class="button-icon--loading"
      >
        <template #default="{ loading }">
          <i v-if="!loading" class="button-icon__icon iconoir-download" />
        </template>
      </DownloadLink>
      <ButtonIcon
        v-if="!readOnly"
        v-tooltip="$t('action.delete')"
        tag="a"
        size="small"
        icon="iconoir-bin"
        @click="$emit('delete')"
      ></ButtonIcon>
    </div>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import { formatFileSize } from '@baserow/modules/core/utils/file'

export default {
  name: 'FileUploaded',
  props: {
    file: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
    iconClass: {
      type: String,
      required: false,
      default: null,
    },
  },
  methods: {
    resetName() {
      this.$refs.nameEditable.set()
    },
    getDate(value) {
      return moment.utc(value).format('MMM Do YYYY [at] H:mm')
    },
    formatSize(size) {
      return formatFileSize(this.$i18n, size)
    },
  },
}
</script>
