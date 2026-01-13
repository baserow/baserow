<template>
  <div
    v-tooltip="selected ? value.visible_name : null"
    class="array-field__file"
  >
    <a class="array-field__file-link" @click.prevent="onClick">
      <img
        v-if="value.is_image"
        class="array-field__file-image"
        :src="value.thumbnails?.tiny?.url"
      />
      <i
        v-else
        class="array-field__file-icon"
        :class="getIconClass(value.mime_type)"
      ></i>
    </a>
  </div>
</template>

<script>
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'

export default {
  name: 'FunctionalFormulaFileArrayItem',
  props: {
    selected: {
      type: Boolean,
      default: false,
    },
    value: {
      type: Object,
      required: true,
    },
    index: {
      type: null,
      default: null,
    },
  },
  emits: ['show'],
  methods: {
    getIconClass(mimeType) {
      return mimetype2icon(mimeType)
    },
    onClick() {
      this.$emit('show', this.index)
    },
  },
}
</script>
