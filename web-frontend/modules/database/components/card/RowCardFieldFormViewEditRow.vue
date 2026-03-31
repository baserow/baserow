<template>
  <div>
    <Button
      v-if="value"
      :href="value"
      tag="a"
      target="_blank"
      rel="nofollow noopener noreferrer"
      size="tiny"
      type="secondary"
      class="forced-pointer-events-auto"
      @mousedown.stop
    >
      {{ $t('editRowLink.editRow') }}
    </Button>
    <Button v-else type="secondary" size="tiny" disabled>
      {{ $t('editRowLink.editRow') }}
    </Button>
  </div>
</template>

<script>
export default {
  name: 'RowCardFieldFormViewEditRow',
  height: 26,
  props: {
    value: {
      type: String,
      default: null,
    },
  },
}
</script>
