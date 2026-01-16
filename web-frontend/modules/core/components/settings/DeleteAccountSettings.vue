<template>
  <div>
    <h2 class="box__title">{{ $t('deleteAccountSettings.title') }}</h2>
    <p>
      {{
        $t('deleteAccountSettings.description', {
          days: settings.account_deletion_grace_delay,
        })
      }}
    </p>
    <div v-if="fetchPending" class="loading__wrapper">
      <div class="loading loading-absolute-center" />
    </div>
    <Alert v-else-if="fetchError" type="error">
      <template #title>
        {{ $t('deleteAccountSettings.workspaceLoadingError') }}
      </template>
      <p>{{ $t('deleteAccountSettings.workspaceLoadingErrorDescription') }}</p>
    </Alert>
    <div v-else-if="orphanWorkspaces.length" class="delete-section">
      <div class="delete-section__label">
        <div class="delete-section__label-icon">
          <i class="iconoir-warning-triangle"></i>
        </div>
        {{ $t('deleteAccountSettings.orphanWorkspaces') }}
      </div>
      <p class="delete-section__description">
        {{ $t('deleteAccountSettings.workspaceNoticeDescription') }}
      </p>
      <ul class="delete-section__list">
        <li v-for="workspace in orphanWorkspaces" :key="workspace.id">
          <i class="delete-section__list-icon iconoir-community"></i>
          {{ workspace.name }}
          <small>
            {{
              $t('deleteAccountSettings.orphanWorkspaceMemberCount', {
                count: workspaceMembers[workspace.id].length,
              })
            }}</small
          >
        </li>
      </ul>
    </div>
    <Error :error="error"></Error>
    <form
      v-if="!success"
      class="delete-account-settings__form"
      @submit.prevent="deleteAccount"
    >
      <div class="actions actions--right">
        <Button
          type="danger"
          size="large"
          :loading="loading"
          :disabled="loading"
          icon="iconoir-bin"
        >
          {{ $t('deleteAccountSettings.submitButton') }}
        </Button>
      </div>
    </form>
  </div>
</template>
<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapGetters } from 'vuex'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { logoutAndRedirectToLogin } from '@baserow/modules/core/utils/auth'
export default {
  mixins: [error],

  data() {
    return {
      loading: false,
      success: false,
      account: {
        password: '',
        passwordConfirm: '',
      },
      workspaceMembers: {},
      fetchPending: true,
      fetchError: null,
    }
  },
  computed: {
    ...mapGetters({
      userId: 'auth/getUserId',
      settings: 'settings/get',
      sortedWorkspaces: 'workspace/getAllSorted',
    }),

    orphanWorkspaces() {
      return this.sortedWorkspaces.filter(({ id: workspaceId }) => {
        return (
          this.workspaceMembers[workspaceId] &&
          this.workspaceMembers[workspaceId].every(
            ({ permissions }) => permissions !== 'ADMIN'
          )
        )
      })
    },
  },
  async mounted() {
    try {
      this.fetchPending = true
      this.fetchError = null

      this.workspaceMembers = Object.fromEntries(
        await Promise.all(
          this.sortedWorkspaces
            .filter(({ permissions }) => permissions === 'ADMIN')
            .map(async ({ id: workspaceId }) => {
              const { data } = await WorkspaceService(
                this.$client
              ).fetchAllUsers(workspaceId)
              return [
                workspaceId,
                data.filter(({ user_id: userId }) => userId !== this.userId),
              ]
            })
        )
      )
    } catch (error) {
      this.fetchError = error
    } finally {
      this.fetchPending = false
    }
  },
  methods: {
    async logoff() {
      await logoutAndRedirectToLogin(
        this.$router,
        this.$store,
        false,
        false,
        true
      )
      this.$store.dispatch('toast/success', {
        title: this.$t('deleteAccountSettings.accountDeletedSuccessTitle'),
        message: this.$t('deleteAccountSettings.accountDeletedSuccessMessage'),
      })
    },
    async loadWorkspaceMembers() {
      this.workspaceLoading = true
      try {
        this.workspaceMembers = Object.fromEntries(
          await Promise.all(
            this.sortedWorkspaces
              .filter(({ permissions }) => permissions === 'ADMIN')
              .map(async ({ id: workspaceId }) => {
                const { data } = await WorkspaceService(
                  this.$client
                ).fetchAllUsers(workspaceId)
                return [
                  workspaceId,
                  data.filter(({ user_id: userId }) => userId !== this.userId),
                ]
              })
          )
        )
      } catch (error) {
        notifyIf(error, 'workspace')
      } finally {
        this.workspaceLoading = false
      }
    },
    async deleteAccount() {
      this.loading = true
      this.hideError()
      try {
        await AuthService(this.$client).deleteAccount()
        this.success = true
        this.logoff()
      } catch (error) {
        this.handleError(error, 'deleteAccount', {
          ERROR_USER_IS_LAST_ADMIN: new ResponseErrorMessage(
            this.$t('deleteAccountSettings.errorUserIsLastAdminTitle'),
            this.$t('deleteAccountSettings.errorUserIsLastAdminMessage')
          ),
        })
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
