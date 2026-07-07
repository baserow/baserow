<template>
  <div class="control__elements">
    <Button
      v-if="isValidLinkURL"
      tag="a"
      size="tiny"
      type="secondary"
      :href="getHref(copy)"
      target="_blank"
      rel="nofollow noopener noreferrer"
    >
      {{ labelOrURL }}
    </Button>
    <Button v-else tag="a" size="tiny" type="secondary" disabled>
      {{ labelOrURL }}
    </Button>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import rowEditFieldInput from '@baserow/modules/database/mixins/rowEditFieldInput'
import linkURLField from '@baserow/modules/database/mixins/linkURLField'

export default {
  mixins: [rowEditField, rowEditFieldInput, linkURLField],
  computed: {
    isValidLinkURL() {
      return this.copy && this.isValid(this.copy)
    },
    labelOrURL() {
      return this.getLabelOrURL(this.copy)
    },
  },
}
</script>
