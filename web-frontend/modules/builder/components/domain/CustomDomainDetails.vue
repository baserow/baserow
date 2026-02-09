<template>
  <div class="custom-domain-details">
    <DnsStatus :domain="domain" />

    <div class="actions actions--right">
      <Button
        type="danger"
        :loading="domain._.loading"
        :disabled="domain._.loading"
        @click="$emit('delete')"
      >
        {{ $t('action.delete') }}
      </Button>
    </div>
  </div>
</template>

<script>
import DnsStatus from '@baserow/modules/builder/components/domain/DnsStatus'
export default {
  name: 'CustomDomainDetails',
  components: { DnsStatus },
  props: {
    domain: {
      type: Object,
      required: true,
    },
  },
  emits: ['delete'],
}
</script>
