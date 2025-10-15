<template>
  <div class="two-factor-auth-empty">
    <div class="two-factor-auth-empty__content">
      <div class="two-factor-auth-empty__icon">
        <div class="baserow-icon-password-check" />
      </div>
      <h3>{{ $t('twoFactorAuthEmpty.title') }}</h3>
      <p>{{ $t('twoFactorAuthEmpty.description') }}</p>
      <Button @click="$emit('enable')">{{
        $t('twoFactorAuthEmpty.enable')
      }}</Button>
    </div>
  </div>
</template>
