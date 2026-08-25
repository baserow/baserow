<template>
  <MarkdownIt
    v-if="format === TEXT_FORMAT_TYPES.MARKDOWN"
    :content="value"
    :rules="markdownRules"
    @click="onMarkdownClick"
  />
  <span v-else class="ab-text">{{ value }}</span>
</template>

<script>
import collectionField from '@baserow/modules/builder/mixins/collectionField'
import markdownContent from '@baserow/modules/builder/mixins/markdownContent'
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'

export default {
  name: 'TextField',
  mixins: [collectionField, markdownContent],
  props: {
    value: {
      type: String,
      required: true,
    },
    format: {
      type: String,
      default: TEXT_FORMAT_TYPES.PLAIN,
    },
  },
  computed: {
    TEXT_FORMAT_TYPES() {
      return TEXT_FORMAT_TYPES
    },
  },
}
</script>
