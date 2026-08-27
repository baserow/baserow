<template>
  <div class="tag-field">
    <ABTag
      v-for="(tag, index) in tags"
      :key="`${index}-${tag.value}`"
      :color="resolveColor(tag.color, colorVariables)"
    >
      <FormattedText :content="tag.value" :format="format" preset="inline" />
    </ABTag>
  </div>
</template>

<script>
import collectionField from '@baserow/modules/builder/mixins/collectionField'
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import FormattedText from '@baserow/modules/builder/components/FormattedText'

export default {
  name: 'TagsField',
  components: { FormattedText },
  mixins: [collectionField],
  props: {
    tags: {
      type: Array,
      default: () => [],
    },
    format: {
      type: String,
      default: TEXT_FORMAT_TYPES.PLAIN,
    },
  },
}
</script>
