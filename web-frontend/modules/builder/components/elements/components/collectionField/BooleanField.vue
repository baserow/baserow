<template>
  <ABCheckbox :value="value" :read-only="true" />
</template>

<script>
import ABCheckbox from '@baserow/modules/builder/components/elements/baseComponents/ABCheckbox'
import collectionField from '@baserow/modules/builder/mixins/collectionField'

export default {
  name: 'BooleanField',
  components: { ABCheckbox },
  mixins: [collectionField],
  props: {
    value: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
