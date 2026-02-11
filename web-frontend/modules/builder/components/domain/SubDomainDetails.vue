<template>
  <div>
    <p>
      {{ $t('subDomainDetails.text') }}
    </p>
    <div class="actions actions--right">
      <Button
        type="danger"
        :loading="domain._.loading"
        :disabled="domain._.loading"
        @click="$emit('delete')"
      >
        {{ $t('action.delete') }}</Button
      >
    </div>
  </div>
</template>

<script>
export default {
  name: 'SubDomainDetails',
  props: {
    domain: {
      type: Object,
      required: true,
    },
  },
  emits: ['delete'],
}
</script>
