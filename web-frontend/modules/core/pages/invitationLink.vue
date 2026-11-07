<template>
  <div class="auth__wrapper">
    <!--
      The form stays up while unlocking, until the visitor is sent on to the
      signup, the login or the workspace, so that the join page doesn't flash.
    -->
    <template v-if="passwordRequired || unlocking">
      <div class="auth__logo">
        <NuxtLink :to="{ name: 'index' }">
          <Logo />
        </NuxtLink>
      </div>
      <h1 class="auth__head-title">
        {{ $t('invitationLinkPassword.title') }}
      </h1>
      <p class="mb-24">{{ $t('invitationLinkPassword.description') }}</p>
      <Error :error="error"></Error>
      <form @submit.prevent="unlock">
        <FormGroup
          small-label
          required
          :label="$t('invitationLinkPassword.passwordLabel')"
          :error="passwordError"
          class="mb-24"
        >
          <FormInput
            ref="passwordInput"
            v-model="password"
            type="password"
            size="large"
            autocomplete="off"
            :error="passwordError"
          ></FormInput>
          <template #error>{{ $t('error.requiredField') }}</template>
        </FormGroup>
        <div class="mb-32">
          <Button
            type="primary"
            full-width
            size="large"
            :loading="unlocking"
            :disabled="unlocking"
          >
            {{ $t('invitationLinkPassword.continue') }}
          </Button>
        </div>
      </form>
    </template>
    <template v-else-if="invitationLink">
      <div class="auth__logo">
        <NuxtLink :to="{ name: 'index' }">
          <Logo />
        </NuxtLink>
      </div>
      <h1 class="auth__head-title">{{ pageTitle }}</h1>
      <i18n-t
        v-if="invitationLink.invited_by"
        scope="global"
        keypath="invitationMessage"
        tag="p"
      >
        <template #invitedBy>
          <strong>{{ invitationLink.invited_by }}</strong>
        </template>
        <template #workspace>
          <strong>{{ destination }}</strong>
        </template>
      </i18n-t>
      <i18n-t v-else scope="global" keypath="invitationLinkMessage" tag="p">
        <template #workspace>
          <strong>{{ destination }}</strong>
        </template>
      </i18n-t>
      <i18n-t
        v-if="roleUpgrade"
        scope="global"
        :keypath="
          invitationLink.scope_name
            ? 'invitationLinkJoin.upgradeScopeRole'
            : 'invitationLinkJoin.upgradeRole'
        "
        tag="p"
        class="mb-24"
      >
        <template #workspace>
          <strong>{{ invitationLink.workspace }}</strong>
        </template>
        <template #name>
          <strong>{{ invitationLink.scope_name }}</strong>
        </template>
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
            roleUpgrade
              ? $t('invitationLinkJoin.upgrade')
              : $t('invitationLinkJoin.join')
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
import { computed, ref } from 'vue'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import {
  getInvitationLinkToken,
  isInvitationLinkPasswordRequired,
  setInvitationLinkToken,
} from '@baserow/modules/core/utils/invitationLink'

definePageMeta({
  layout: 'login',
  middleware: ['settings'],
})

const route = useRoute()
const nuxtApp = useNuxtApp()
const { $store: store, $client } = nuxtApp
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

// A password protected link only tells what it joins once its password was
// exchanged for a token, which is remembered for the signup or login detour.
const token = ref(await getInvitationLinkToken(nuxtApp, slug))
const password = ref('')
const passwordError = ref(false)
const unlocking = ref(false)

// Fetch the invitation link data
const {
  data: linkResponse,
  error: fetchError,
  refresh,
} = await useAsyncData(`invitation-link-${slug}`, async () => {
  try {
    const { data } = await WorkspaceService($client).fetchInvitationLinkBySlug(
      slug,
      token.value
    )
    return { link: data, passwordRequired: false }
  } catch (e) {
    if (isInvitationLinkPasswordRequired(e)) {
      return { link: null, passwordRequired: true }
    }
    throw e
  }
})
const invitationLink = computed(() => linkResponse.value?.link ?? null)
const passwordRequired = computed(
  () => linkResponse.value?.passwordRequired ?? false
)

/**
 * What the link joins: the workspace, or one of its objects such as "Sales in
 * Acme" when the link gives a role on that object only.
 */
const destination = computed(() => {
  const link = invitationLink.value
  if (!link) {
    return ''
  }
  return link.scope_name
    ? t('invitationLinkJoin.scopeIn', {
        name: link.scope_name,
        workspace: link.workspace,
      })
    : link.workspace
})

const pageTitle = computed(() => {
  if (passwordRequired.value) {
    return t('invitationLinkPassword.title')
  }
  const link = invitationLink.value
  if (!link) {
    return ''
  }
  if (!roleUpgrade.value) {
    return t('invitationLinkJoin.title', { workspace: destination.value })
  }
  return link.scope_name
    ? t('invitationLinkJoin.upgradeScopeTitle', { name: link.scope_name })
    : t('invitationLinkJoin.upgradeTitle', { workspace: link.workspace })
})

useHead({ title: () => pageTitle.value })

/**
 * Navigates away and tells the caller that this page is being left.
 */
async function navigateToPage(to, options) {
  await navigateTo(to, options)
  return true
}

/**
 * Sends the visitor where the link leads them: newcomers to the signup, members
 * into the workspace, and everyone else stays to confirm joining.
 *
 * @returns {boolean} Whether the visitor was sent to another page.
 */
async function routeVisitor() {
  // Handle error - the link doesn't exist (anymore)
  if (fetchError.value) {
    if (store.getters['auth/isAuthenticated']) {
      return await navigateToPage({ name: 'all-workspaces' }, { replace: true })
    } else {
      return await navigateToPage({ name: 'login' }, { replace: true })
    }
  } else if (invitationLink.value && !store.getters['auth/isAuthenticated']) {
    // A link doesn't tell who opens it, so new people sign up from it when they
    // are allowed to, and everyone else logs in and comes back here.
    const settings = store.getters['settings/get']
    const signupAllowed =
      settings.allow_new_signups ||
      settings.allow_signups_via_workspace_invitations
    return await navigateToPage(
      signupAllowed
        ? { name: 'signup', query: { invitationLinkSlug: slug } }
        : { name: 'login', query: { original: route.fullPath } },
      { replace: true }
    )
  } else if (invitationLink.value) {
    // Members land in the workspace, unless the link raises their role, on its
    // object if it has one. Then they confirm the change first, like newcomers
    // confirm joining.
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
      return await navigateToPage(
        { name: 'workspace', params: { workspaceId } },
        { replace: true }
      )
    }
  }
  return false
}

await routeVisitor()

/**
 * Joins the workspace once the logged in user confirms it, because joining
 * shares their name and email address with the workspace's members, or
 * because it raises the role of a member.
 */
async function join() {
  joining.value = true
  error.value = { visible: false, title: '', message: '' }
  try {
    const { data: workspace } = await WorkspaceService(
      $client
    ).joinInvitationLink(slug, token.value)

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

/**
 * Exchanges the password for the token of the link, then shows the link like
 * any other.
 */
async function unlock() {
  passwordError.value = !password.value
  if (passwordError.value) {
    return
  }
  unlocking.value = true
  error.value = { visible: false, title: '', message: '' }
  try {
    const { data } = await WorkspaceService($client).authInvitationLink(
      slug,
      password.value
    )
    await setInvitationLinkToken(nuxtApp, slug, data.access_token)
    token.value = data.access_token
    await refresh()
    if (await routeVisitor()) {
      // Keep the form until the next page has replaced this one.
      return
    }
  } catch (e) {
    const wrongPassword = (e.response || e.handler?.response)?.status === 401
    error.value = {
      visible: true,
      title: wrongPassword
        ? t('invitationLinkPassword.incorrectTitle')
        : t('invitationLinkJoin.failed'),
      message: wrongPassword
        ? t('invitationLinkPassword.incorrectMessage')
        : t('invitationLinkJoin.failedMessage'),
    }
  }
  unlocking.value = false
}
</script>
