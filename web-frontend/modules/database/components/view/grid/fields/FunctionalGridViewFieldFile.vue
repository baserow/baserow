<template>
  <div
    class="grid-view__cell grid-field-file__cell"
    @drop.prevent="onDrop"
    @dragover.prevent
    @dragenter.prevent="onDragEnter"
    @dragleave="onDragLeave"
  >
    <div
      v-show="Object.prototype.hasOwnProperty.call(state, field.id)"
      class="grid-field-file__dragging"
    >
      <div>
        <i class="grid-field-file__drop-icon iconoir-cloud-upload"></i>
        Drop here
      </div>
    </div>
    <ul v-if="Array.isArray(value)" class="grid-field-file__list">
      <li
        v-for="(file, index) in value"
        :key="file.name + index"
        class="grid-field-file__item"
      >
        <a class="grid-field-file__link">
          <img
            v-if="file.is_image"
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
    </ul>
  </div>
</template>

<script>
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'

export default {
  name: 'FunctionalGridViewFieldFile',
  props: {
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: Array,
      default: () => [],
    },
    state: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
  },
  methods: {
    getIconClass(mimeType) {
      return mimetype2icon(mimeType)
    },
    onDrop(event) {
      if (this.readOnly) {
        return
      }

      const parent = this.$parent
      parent?.selectCell(this.field.id)
      parent?.setState({})
      parent?.$nextTick(() => {
        parent?.$refs.selectedField.onDrop(event)
      })
    },
    onDragEnter(event) {
      if (this.readOnly) {
        return
      }

      const parent = this.$parent
      parent?.setState({
        [this.field.id]: event.target,
      })
    },
    onDragLeave(event) {
      if (this.readOnly) {
        return
      }

      if (
        Object.prototype.hasOwnProperty.call(this.state, this.field.id) &&
        this.state[this.field.id] === event.target
      ) {
        event.stopPropagation()
        event.preventDefault()
        this.$parent?.setState({})
      }
    },
  },
}
</script>
