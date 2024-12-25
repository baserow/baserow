<template>
  <Modal>
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
