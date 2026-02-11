<template>
  <div class="upload-files__file-failed">
    <div class="field-file__preview">
      <a class="field-file__icon">
        <img v-if="file.is_image" :src="file.thumbnails.small.url" />
        <i v-else :class="iconClass"></i>
      </a>
    </div>
    <div class="field-file__description">
      <div class="field-file__name">
        <div>
          {{ file.visible_name }}
        </div>
      </div>
      <div class="field-file__info">
        <div class="upload-files__error">
          {{ file.error }}
        </div>
      </div>
    </div>
    <div class="upload-files__state">
      <a
        v-if="!readOnly"
        v-tooltip="$t('action.delete')"
        class="field-file__action upload-files__state-failed"
        @click="$emit('delete')"
      >
        <i class="iconoir-cancel"></i>
      </a>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FileFailed',
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
  emits: ['delete'],
}
</script>
