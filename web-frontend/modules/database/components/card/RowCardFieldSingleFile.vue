<template>
  <div class="card-file__list-wrapper">
    <ul class="card-file__list">
      <li class="card-file__item">
        <template v-if="value">
          <img
            v-if="value.is_image"
            class="card-file__image"
            :src="value.thumbnails?.tiny?.url"
          />
          <i
            v-else
            class="card-file__icon"
            :class="getIconClass(value.mime_type)"
          ></i>
        </template>
      </li>
    </ul>
  </div>
</template>

<script>
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'

export default {
  height: 22,
  name: 'RowCardFieldSingleFile',
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
  methods: {
    getIconClass(mimeType) {
      return mimetype2icon(mimeType)
    },
  },
}
</script>
