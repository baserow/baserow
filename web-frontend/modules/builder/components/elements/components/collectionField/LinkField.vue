<template>
  <ABLink :variant="variant" :url="url" :target="target">
    {{ realLinkName }}
  </ABLink>
</template>

<script>
import collectionField from '@baserow/modules/builder/mixins/collectionField'

export default {
  name: 'LinkField',
  mixins: [collectionField],
  props: {
    url: {
      type: String,
      required: true,
    },
    linkName: {
      type: String,
      required: false,
      default: null,
    },
    target: {
      type: String,
      required: true,
    },
    variant: {
      type: String,
      required: true,
    },
  },
  computed: {
    realLinkName() {
      if (this.linkName !== null) {
        return this.linkName
      } else {
        return this.$t('linkField.details')
      }
    },
  },
}
</script>
