<template>
  <div class="auth__wrapper">
    <h1 class="box__title">{{ $t('apiDocsComponent.title') }}</h1>
    <template v-if="isAuthenticated">
      <i18n-t keypath="apiDocsComponent.intro" tag="p">
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
      <APIDocsSelectDatabase />
      <nuxt-link :to="{ name: 'dashboard' }" class="select-application__back">
        <i class="iconoir-arrow-left"></i>
        {{ $t('apiDocsComponent.back') }}
      </nuxt-link>
      <SettingsModal ref="settingsModal"></SettingsModal>
    </template>
    <template v-else>
      <i18n-t keypath="apiDocsComponent.intro" tag="p">
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
import SettingsModal from '@baserow/modules/core/components/settings/SettingsModal'
import APIDocsSelectDatabase from '@baserow/modules/database/components/docs/APIDocsSelectDatabase'
import { useRouter } from 'vue-router'

const router = useRouter()

const {
  $store,
  $config,
  $i18n: { t: $t },
} = useNuxtApp()

definePageMeta({
  layout: 'login',
  middleware: ['workspacesAndApplications'],
})

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
</script>
