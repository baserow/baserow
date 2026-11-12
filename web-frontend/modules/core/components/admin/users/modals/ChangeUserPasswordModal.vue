<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('changeUserPasswordModal.changePassword', user) }}
    </h2>
    <Error :error="error"></Error>
    <ChangePasswordForm
      :loading="loading"
      @submitted="changePassword"
    ></ChangePasswordForm>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import UserAdminService from '@baserow/modules/core/services/admin/users'
import ChangePasswordForm from '@baserow/modules/core/components/admin/users/forms/ChangePasswordForm'
import { loginAgainAfterPasswordChange } from '@baserow/modules/core/utils/auth'

export default {
  name: 'ChangePasswordModal',
  components: { ChangePasswordForm },
  mixins: [modal, error],
  props: {
    user: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async changePassword(values) {
      this.loading = true
      this.hideError()

      try {
        await UserAdminService(this.$client).update(this.user.id, {
          password: values.password,
        })
        // Changing a password signs that user out everywhere. When admins change
        // their own, log them back in with the new password so this session
        // carries on.
        if (
          this.user.id === this.$store.getters['auth/getUserId'] &&
          !(await loginAgainAfterPasswordChange(
            this.$router,
            this.$store,
            values.password
          ))
        ) {
          return
        }
        this.loading = false
        this.hide()
      } catch (error) {
        this.loading = false
        this.handleError(error, 'application')
      }
    },
  },
}
</script>
