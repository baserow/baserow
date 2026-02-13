<template>
  <div ref="cell" class="grid-view__cell grid-field-file__cell active">
    <div v-if="value" class="grid-field-file__item">
      <a class="grid-field-file__link" @click.prevent="onClick">
        <img
          v-if="value.is_image"
          class="grid-field-file__image"
          :src="value?.thumbnails?.tiny?.url"
        />
        <i
          v-else
          class="grid-field-file__icon"
          :class="getIconClass(value.mime_type)"
        ></i>
      </a>
      <SingleFileArrayModal ref="modal" :value="[value]"></SingleFileArrayModal>
    </div>
  </div>
</template>

<script>
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'
import SingleFileArrayModal from '@baserow/modules/database/components/view/grid/fields/SingleFileArrayModal'
import gridField from '@baserow/modules/database/mixins/gridField'

export default {
  name: 'GridViewSingleFile',
  components: { SingleFileArrayModal },
  mixins: [gridField],
  props: {
    value: {
      type: Object,
      required: false,
      default: null,
    },
  },
  methods: {
    getIconClass(mimeType) {
      return mimetype2icon(mimeType)
    },
    onClick() {
      this.$refs?.modal?.show(0)
    },
  },
}
</script>
