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

    <div v-if="pending" class="loading__wrapper">
      <div class="loading loading-absolute-center" />
    </div>

    <Alert v-else-if="fetchError" type="error">
      <template #title>{{
        $t('deleteAccountSettings.workspaceLoadingError')
      }}</template>
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

    <Error :error="error" />

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
import {
  defineComponent,
  ref,
  reactive,
  computed,
  getCurrentInstance,
} from 'vue'

import { useStore } from 'vuex'
import { useFetch, useRouter, useNuxtApp } from '#app'

import { notifyIf } from '@baserow/modules/core/utils/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { logoutAndRedirectToLogin } from '@baserow/modules/core/utils/auth'

export default defineComponent({
  name: 'DeleteAccountSettings',
  mixins: [error],
  setup() {
    const store = useStore()
    const router = useRouter()
    const { $client, $t } = useNuxtApp()
    const { proxy } = getCurrentInstance()

    const loading = ref(false)
    const success = ref(false)
    const workspaceMembers = ref({})

    const userId = computed(() => store.getters['auth/getUserId'])
    const settings = computed(() => store.getters['settings/get'])
    const sortedWorkspaces = computed(
      () => store.getters['workspace/getAllSorted']
    )

    const loadWorkspaceMembersInternal = async () => {
      const entries = await Promise.all(
        sortedWorkspaces.value
          .filter(({ permissions }) => permissions === 'ADMIN')
          .map(async ({ id }) => {
            const { data } = await WorkspaceService($client).fetchAllUsers(id)
            return [
              id,
              data.filter(({ user_id: member }) => member !== userId.value),
            ]
          })
      )

      return Object.fromEntries(entries)
    }

    const { pending, error: fetchError } = useFetch(async () => {
      workspaceMembers.value = await loadWorkspaceMembersInternal()
      return workspaceMembers.value
    })

    const orphanWorkspaces = computed(() =>
      sortedWorkspaces.value.filter(({ id }) => {
        const members = workspaceMembers.value[id]
        return (
          members && members.every(({ permissions }) => permissions !== 'ADMIN')
        )
      })
    )

    const logoff = () => {
      logoutAndRedirectToLogin(router, store, false, false, true)
      store.dispatch('toast/success', {
        title: $t('deleteAccountSettings.accountDeletedSuccessTitle'),
        message: $t('deleteAccountSettings.accountDeletedSuccessMessage'),
      })
    }

    const deleteAccount = async () => {
      loading.value = true
      proxy.hideError()

      try {
        await AuthService($client).deleteAccount()
        success.value = true
        logoff()
      } catch (err) {
        proxy.handleError(err, 'deleteAccount', {
          ERROR_USER_IS_LAST_ADMIN: new ResponseErrorMessage(
            $t('deleteAccountSettings.errorUserIsLastAdminTitle'),
            $t('deleteAccountSettings.errorUserIsLastAdminMessage')
          ),
        })
      } finally {
        loading.value = false
      }
    }

    return {
      // State
      loading,
      success,
      workspaceMembers,
      settings,
      orphanWorkspaces,

      // Fetch state
      pending,
      fetchError,

      // Methods
      deleteAccount,
    }
  },
})
</script>
