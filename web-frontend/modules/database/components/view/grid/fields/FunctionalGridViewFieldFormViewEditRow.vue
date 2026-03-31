<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-button">
      <Button
        v-if="value"
        tag="a"
        type="secondary"
        size="tiny"
        :href="value"
        target="_blank"
      >
        {{ $t('editRowLink.editRow') }}
      </Button>
      <Button v-else type="secondary" size="tiny" disabled>
        {{ $t('editRowLink.editRow') }}
      </Button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldFormViewEditRow',
  props: {
    value: {
      type: String,
      default: null,
    },
  },
}
</script>
