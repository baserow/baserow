<template>
  <ABFormattedText
    :value="value"
    :format="field.value?.format"
    profile="block"
  />
</template>

<script>
import collectionField from '@baserow/modules/builder/mixins/collectionField'

export default {
  name: 'TextField',
  mixins: [collectionField],
  props: {
    value: {
      type: String,
      required: true,
    },
  },
}
</script>
