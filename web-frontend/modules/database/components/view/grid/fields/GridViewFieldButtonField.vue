<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-button">
      <Button
        v-if="isValid(resolvedButtonValue)"
        tag="a"
        size="tiny"
        type="secondary"
        rel="nofollow noopener noreferrer"
        :href="getHref(resolvedButtonValue)"
        target="_blank"
      >
        {{ getLabelOrURL(resolvedButtonValue) }}
      </Button>
      <Button v-else type="secondary" tag="a" disabled>
        {{ getLabelOrURL(resolvedButtonValue) }}
      </Button>
    </div>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'GridViewFieldButtonField',
  mixins: [gridField, linkURLField, buttonField],
}
</script>
