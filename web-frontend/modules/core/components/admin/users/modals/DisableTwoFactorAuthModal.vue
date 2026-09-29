<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('disableTwoFactorAuthModal.title') }}
    </h2>
    <Error :error="error"></Error>
    <div>
      <i18n-t
        scope="global"
        keypath="disableTwoFactorAuthModal.confirmation"
        tag="p"
      >
        <template #name>
          <strong class="user-admin-delete__strong">{{ user.username }}</strong>
        </template>
      </i18n-t>
      <p>
        {{ $t('disableTwoFactorAuthModal.comment') }}
      </p>
      <div class="actions">
        <div class="align-right">
          <Button
            type="danger"
            size="large"
            full-width
            :disabled="loading"
            :loading="loading"
            @click.prevent="disableTwoFactorAuth()"
          >
            {{ $t('disableTwoFactorAuthModal.remove') }}</Button
          >
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import UserAdminService from '@baserow/modules/core/services/admin/users'

export default {
  name: 'DisableTwoFactorAuthModal',
  mixins: [modal, error],
  props: {
    user: {
      type: Object,
      required: true,
    },
  },
  emits: ['two-factor-auth-disabled'],
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async disableTwoFactorAuth() {
      this.hideError()
      this.loading = true

      try {
        await UserAdminService(this.$client).disableTwoFactorAuth(this.user.id)
        this.$emit('two-factor-auth-disabled')
        this.hide()
      } catch (error) {
        this.handleError(error, 'application')
      }

      this.loading = false
    },
  },
}
</script>
