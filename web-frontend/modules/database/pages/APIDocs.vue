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

import {computed, onMounted, onBeforeUnmount} from 'vue'

import {useHead} from '#imports'


import SettingsModal from '@baserow/modules/core/components/settings/SettingsModal'
import APIDocsSelectDatabase
  from '@baserow/modules/database/components/docs/APIDocsSelectDatabase'
import {useRoute, useRouter} from "vue-router";

definePageMeta({
  layout: 'login',
  middleware: ['workspacesAndApplications'],
})

const router = useRouter()
const config = useAppConfig()
const nuxtApp = useNuxtApp()


const {
  $store,
  $i18n: {t: $t},
} = nuxtApp

useHead(
  {
    title: 'REST API documentation',
    link: [
      {
        rel: 'canonical',
        href:
          config.PUBLIC_WEB_FRONTEND_URL +
          router.resolve({name: 'database-api-docs'}).href,
      },
    ],
  })

const isAuthenticated = computed(() => {
  return $store.getters['auth/isAuthenticated']
})

</script>


<sscript>
import { mapGetters } from 'vuex'

import SettingsModal from '@baserow/modules/core/components/settings/SettingsModal'
import APIDocsSelectDatabase from '@baserow/modules/database/components/docs/APIDocsSelectDatabase'

export default {
  name: 'APIDocs',
  components: { SettingsModal, APIDocsSelectDatabase },
  layout: 'login',
  middleware: ['workspacesAndApplications'],
  head() {
    return {
      title: 'REST API documentation',
      link: [
        {
          rel: 'canonical',
          href:
            this.$config.PUBLIC_WEB_FRONTEND_URL +
            this.$router.resolve({ name: 'database-api-docs' }).href,
        },
      ],
    }
  },
  computed: {
    ...mapGetters({
      isAuthenticated: 'auth/isAuthenticated',
    }),
  },
}
</sscript>
