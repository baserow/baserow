<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-button">
      <Button
        v-if="isValid(value)"
        tag="a"
        size="tiny"
        type="secondary"
        rel="nofollow noopener noreferrer"
        :href="getHref(value)"
        target="_blank"
      >
        {{ getLabelOrURL(value) }}
      </Button>
      <Button v-else type="secondary" tag="a" disabled>
        {{ getLabelOrURL(value) }}
      </Button>
    </div>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import gridFieldInput from '@baserow/modules/database/mixins/gridFieldInput'
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
export default {
  name: 'GridViewFieldButton',
  mixins: [gridField, gridFieldInput, linkURLField],
}
</script>
