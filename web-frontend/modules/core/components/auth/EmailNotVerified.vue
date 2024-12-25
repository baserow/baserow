<template>
  <div class="auth__wrapper">
    <div class="auth__wrapper auth__wrapper--small-centered">
      <ButtonIcon icon="iconoir-mail-out" />
      <p>
        {{ $t('emailNotVerified.description') }}
      </p>
      <Button
        type="secondary"
        size="large"
        :disabled="resendLoading || resendSuccess"
        :loading="resendLoading"
        @click="resend(email)"
      >
        {{ $t('emailNotVerified.resend') }}
      </Button>
    </div>
  </div>
</template>

<script>
import resendEmailVerification from '@baserow/modules/core/mixins/resendEmailVerification'

export default {
  mixins: [resendEmailVerification],
  props: {
    email: {
      type: String,
      required: true,
    },
  },
}
</script>
