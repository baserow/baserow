<template>
  <div class="thumbnail">
    <img v-bind="$attrs" class="thumbnail__image" :src="src" />
    <a v-if="removable" class="thumbnail__remove" @click="$emit('remove')">
      <i class="iconoir-cancel"></i>
      {{ $t('action.remove') }}
    </a>
  </div>
</template>

<script>
export default {
  name: 'Thumbnail',
  props: {
    src: {
      type: String,
      required: true,
    },
    removable: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['remove'],
}
</script>
