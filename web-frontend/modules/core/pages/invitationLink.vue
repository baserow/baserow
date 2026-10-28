<template>
  <div class="auth__wrapper">
    <template v-if="invitationLink">
      <div class="auth__logo">
        <NuxtLink :to="{ name: 'index' }">
          <Logo />
        </NuxtLink>
      </div>
      <h1 class="auth__head-title">
        {{
          $t(
            roleUpgrade
              ? 'invitationLinkJoin.upgradeTitle'
              : 'invitationLinkJoin.title',
            { workspace: invitationLink.workspace }
          )
        }}
      </h1>
      <i18n-t
        scope="global"
        :keypath="
          invitationLink.invited_by
            ? 'invitationMessage'
            : 'invitationLinkMessage'
        "
        tag="p"
      >
        <template #invitedBy>
          <strong>{{ invitationLink.invited_by }}</strong>
        </template>
        <template #workspace>
          <strong>{{ invitationLink.workspace }}</strong>
        </template>
      </i18n-t>
      <i18n-t
        v-if="roleUpgrade"
        scope="global"
        keypath="invitationLinkJoin.upgradeRole"
        tag="p"
        class="mb-24"
      >
        <template #from>
          <strong>{{ roleUpgrade.from }}</strong>
        </template>
        <template #to>
          <strong>{{ roleUpgrade.to }}</strong>
        </template>
      </i18n-t>
      <i18n-t
        v-else
        scope="global"
        keypath="invitationLinkJoin.joinAs"
        tag="p"
        class="mb-24"
      >
        <template #email>
          <strong>{{ username }}</strong>
        </template>
      </i18n-t>
      <Error :error="error"></Error>
      <div class="mb-32">
        <Button
          type="primary"
          full-width
          size="large"
          :loading="joining"
          :disabled="joining"
          @click="join"
        >
          {{
            $t(
              roleUpgrade
                ? 'invitationLinkJoin.upgrade'
                : 'invitationLinkJoin.join'
            )
          }}
        </Button>
      </div>
      <ul class="auth__action-links">
        <li class="auth__action-link">
          <NuxtLink :to="{ name: 'all-workspaces' }">
            {{ $t('action.cancel') }}
          </NuxtLink>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import WorkspaceService from '@baserow/modules/core/services/workspace'

definePageMeta({
  layout: 'login',
  middleware: ['settings'],
})

const route = useRoute()
const { $store: store, $client } = useNuxtApp()
const { t } = useI18n()

// Joining is confirmed with a click, so the page must not be framed
// (clickjacking).
if (import.meta.server) {
  useResponseHeader('Content-Security-Policy').value = "frame-ancestors 'none'"
  useResponseHeader('X-Frame-Options').value = 'DENY'
}

const slug = route.params.slug
const username = store.getters['auth/getUsername']
const joining = ref(false)
const roleUpgrade = ref(null)
const error = ref({ visible: false, title: '', message: '' })

// Fetch the invitation link data
const { data: invitationLink, error: fetchError } = await useAsyncData(
  `invitation-link-${slug}`,
  async () => {
    const { data } =
      await WorkspaceService($client).fetchInvitationLinkBySlug(slug)
    return data
  }
)

useHead({
  title: () =>
    invitationLink.value
      ? t(
          roleUpgrade.value
            ? 'invitationLinkJoin.upgradeTitle'
            : 'invitationLinkJoin.title',
          { workspace: invitationLink.value.workspace }
        )
      : '',
})

// Handle error - the link doesn't exist (anymore)
if (fetchError.value) {
  if (store.getters['auth/isAuthenticated']) {
    await navigateTo({ name: 'all-workspaces' }, { replace: true })
  } else {
    await navigateTo({ name: 'login' }, { replace: true })
  }
} else if (invitationLink.value && !store.getters['auth/isAuthenticated']) {
  // A link doesn't tell who opens it, so new people sign up from it when they
  // are allowed to, and everyone else logs in and comes back here.
  const settings = store.getters['settings/get']
  const signupAllowed =
    settings.allow_new_signups ||
    settings.allow_signups_via_workspace_invitations
  await navigateTo(
    signupAllowed
      ? { name: 'signup', query: { invitationLinkSlug: slug } }
      : { name: 'login', query: { original: route.fullPath } },
    { replace: true }
  )
} else if (invitationLink.value) {
  // Members land in the workspace, unless the link raises their role. Then they
  // confirm the change first, like newcomers confirm joining.
  await store.dispatch('workspace/loadAll')
  const workspaceId = invitationLink.value.workspace_id
  const workspace = store.getters['workspace/get'](workspaceId)
  if (workspace && invitationLink.value.role_upgrade) {
    await store.dispatch('workspace/fetchRoles', workspace)
    const roleName = (uid) =>
      workspace._.roles.find((role) => role.uid === uid)?.name || uid
    roleUpgrade.value = {
      from: roleName(invitationLink.value.role_upgrade.current_permissions),
      to: roleName(invitationLink.value.role_upgrade.permissions),
    }
  } else if (workspace) {
    await navigateTo(
      { name: 'workspace', params: { workspaceId } },
      { replace: true }
    )
  }
}

/**
 * Joins the workspace once the logged in user confirms it, because joining
 * shares their name and email address with the workspace's members, or
 * because it raises the role of a member.
 */
async function join() {
  joining.value = true
  error.value = { visible: false, title: '', message: '' }
  try {
    const { data: workspace } =
      await WorkspaceService($client).joinInvitationLink(slug)

    // Clear workspace loaded state so it gets refetched on next page
    store.commit('workspace/SET_LOADED', false)
    store.commit('application/SET_LOADED', false)

    await navigateTo(
      { name: 'workspace', params: { workspaceId: workspace.id } },
      { replace: true }
    )
  } catch (e) {
    joining.value = false
    const notFound = e.handler?.response?.status === 404
    error.value = {
      visible: true,
      title: t('invitationLinkJoin.failed'),
      message: notFound
        ? t('invitationLinkJoin.invalidLinkMessage')
        : t('invitationLinkJoin.failedMessage'),
    }
  }
}
</script>
