<template>
  <div class="auth__wrapper">
    <h1 class="box__title">{{ $t('apiDocsComponent.title') }}</h1>
    <template v-if="isAuthenticated">
      <i18n-t scope="global" keypath="apiDocsComponent.intro" tag="p">
        <template #settingsLink>
          <a @click.prevent="$refs.settingsModal.show('tokens')">{{
            $t('apiDocsComponent.settings')
          }}</a
          >,
        </template>
      </i18n-t>
      <div class="select-application__title">
        {{ $t('apiDocsComponent.selectApplicationTitle') }}
      </div>
      <APIDocsSelectDatabase :loading="loading" />
      <nuxt-link :to="{ name: 'dashboard' }" class="select-application__back">
        <i class="iconoir-arrow-left"></i>
        {{ $t('apiDocsComponent.back') }}
      </nuxt-link>
      <SettingsModal ref="settingsModal"></SettingsModal>
    </template>
    <template v-else>
      <i18n-t scope="global" keypath="apiDocsComponent.intro" tag="p">
        <template #settingsLink>{{ $t('apiDocsComponent.settings') }},</template
        >,
      </i18n-t>

      <Button
        tag="nuxt-link"
        :to="{
          name: 'login',
          query: {
            original: $route.path,
          },
        }"
        type="secondary"
        size="large"
      >
        {{ $t('apiDocsComponent.signIn') }}</Button
      >
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useHead } from '#imports'
import { usePageAsyncData } from '@baserow/modules/core/composables/usePageAsyncData'
import SettingsModal from '@baserow/modules/core/components/settings/SettingsModal'
import APIDocsSelectDatabase from '@baserow/modules/database/components/docs/APIDocsSelectDatabase'
import {
  fetchWorkspacesAndApplications,
  getWorkspaceCookie,
} from '@baserow/modules/core/utils/workspace'
import { useRouter } from 'vue-router'

const router = useRouter()
const nuxtApp = useNuxtApp()

const {
  $store,
  $config,
  $i18n: { t: $t },
} = nuxtApp

definePageMeta({
  layout: 'login',
})

// Not left to the `workspacesAndApplications` middleware, because that would
// make the page wait for it.
const { loading: fetching } = await usePageAsyncData(
  'api-docs-databases',
  async () => {
    if ($store.getters['auth/isAuthenticated']) {
      // Also selects the remembered workspace, like the middleware does, because
      // the pages visited after this one skip that once the workspaces are loaded.
      await fetchWorkspacesAndApplications(nuxtApp, getWorkspaceCookie(nuxtApp))
    }
    return true
  }
)

useHead({
  title: 'REST API documentation',
  link: [
    {
      rel: 'canonical',
      href:
        $config.public.publicWebFrontendUrl +
        router.resolve({ name: 'database-api-docs' }).href,
    },
  ],
})

const isAuthenticated = computed(() => {
  return $store.getters['auth/isAuthenticated']
})

const loading = computed(() => isAuthenticated.value && fetching.value)
</script>
