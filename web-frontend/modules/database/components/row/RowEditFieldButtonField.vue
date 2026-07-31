<template>
  <div class="control__elements">
    <Button
      v-if="hasWorkflowActions"
      size="tiny"
      type="secondary"
      :loading="dispatching"
      @click="dispatchWorkflowActions"
    >
      {{ field.label }}
    </Button>
    <Button
      v-else-if="isValidLinkURL"
      tag="a"
      size="tiny"
      type="secondary"
      :href="getHref(resolvedButtonValue)"
      target="_blank"
      rel="nofollow noopener noreferrer"
    >
      {{ resolvedButtonValue.label }}
    </Button>
    <Button v-else tag="a" size="tiny" type="secondary" disabled>
      {{ resolvedButtonValue.label }}
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
  },
}
</script>
