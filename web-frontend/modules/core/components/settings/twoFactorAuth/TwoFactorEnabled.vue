<template>
  <div class="two-factor-enabled">
    <div><span class="two-factor-enabled__type">{{ providerName }}</span><Badge color="green" rounded="true">Enabled</Badge></div>
    <div class="two-factor-enabled__description">{{ providerDescription }}</div>
    <Button type="secondary" @click="$emit('disable')">Disable 2FA</Button>
  </div>
</template>

<script>
export default {
  name: 'TwoFactorEnabled',
  props: {
    provider: {
      type: Object,
      required: true,
    },
  },
  computed: {
    providerType() {
      return this.$registry.get('twoFactorAuth', this.provider.type)
    },
    providerName() {
      return this.providerType.name
    },
    providerDescription() {
      return this.providerType.description
    },
  },
}
</script>
