<template>
  <Modal>
    <h2 class="box__title">{{ $t('deleteUserModal.title', user) }}</h2>
    <Error :error="error"></Error>
    <div>
      <i18n path="deleteUserModal.confirmation" tag="p">
        <template #name>
          <strong class="user-admin-delete__strong">{{ user.username }}</strong>
        </template>
      </i18n>
      <p>
        {{ $t('deleteUserModal.comment1') }}
      </p>
      <p>
        {{ $t('deleteUserModal.comment2') }}
      </p>
      <div class="actions">
        <div class="align-right">
          <Button
            type="danger"
            size="large"
            full-width
            :disabled="loading"
            :loading="loading"
            @click.prevent="deleteUser()"
          >
            {{ $t('deleteUserModal.delete', user) }}</Button
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
  name: 'DeleteUserModal',
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
    async deleteUser() {
      this.hideError()
      this.loading = true

      try {
        await UserAdminService(this.$client).delete(this.user.id)
        this.$emit('delete-user', this.user.id)
        this.hide()
      } catch (error) {
        this.handleError(error, 'application')
      }

      this.loading = false
    },
  },
}
</script>
