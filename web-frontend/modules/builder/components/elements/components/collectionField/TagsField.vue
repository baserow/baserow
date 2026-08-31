<template>
  <div class="tag-field">
    <ABTag
      v-for="(tag, index) in tags"
      :key="`${index}-${tag.value}`"
      :color="resolveColor(tag.color, colorVariables)"
    >
      {{ tag.value }}
    </ABTag>
  </div>
</template>

<script>
import collectionField from '@baserow/modules/builder/mixins/collectionField'

export default {
  name: 'TagsField',
  mixins: [collectionField],
  props: {
    tags: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
