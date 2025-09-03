<template>
  <div class="two-factor-auth-empty">
    <div class="two-factor-auth-empty__content">
      <div class="two-factor-auth-empty__icon">
        <div class="baserow-icon-password-check" />
      </div>
      <div v-if="allowed">
        <h3>{{ $t('twoFactorAuthEmpty.title') }}</h3>
        <p>{{ $t('twoFactorAuthEmpty.description') }}</p>
        <Button @click="$emit('enable')">{{
          $t('twoFactorAuthEmpty.enable')
        }}</Button>
      </div>
      <div v-else>
        <h3>{{ $t('twoFactorAuthEmpty.notAllowedTitle') }}</h3>
        <p>{{ $t('twoFactorAuthEmpty.notAllowedDescription') }}</p>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    allowed: {
      type: Boolean,
      default: true,
    },
  },
}
</script>
