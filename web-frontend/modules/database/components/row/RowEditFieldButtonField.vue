<template>
  <div class="control__elements">
    <Button
      v-if="isValidLinkURL"
      tag="a"
      size="tiny"
      type="secondary"
      :href="getHref(resolvedButtonValue)"
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
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'RowEditFieldButtonField',
  mixins: [rowEditField, linkURLField, buttonField],
  computed: {
    isValidLinkURL() {
      return this.resolvedButtonValue && this.isValid(this.resolvedButtonValue)
    },
    labelOrURL() {
      return this.getLabelOrURL(this.resolvedButtonValue)
    },
  },
}
</script>
