<template>
  <div class="auth__wrapper">
    <div class="auth__logo">
      <nuxt-link :to="{ name: 'index' }">
        <Logo />
      </nuxt-link>
    </div>
    <div class="auth__head">
      <h1 class="auth__head-title">
        {{ $t('loginError.title') }} {{ errorMessage }}
      </h1>
    </div>
    <p class="auth__error-help">
      {{ $t('loginError.help') }}
    </p>
    <div>
      <ul class="auth__action-links">
        <li>
          {{ $t('loginError.loginText') }}
          <nuxt-link :to="{ name: 'login', query: { noredirect: null } }">
            {{ $t('action.login') }}
          </nuxt-link>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

definePageMeta({
  layout: 'login',
})

const route = useRoute()
const { t, te } = useI18n()

// Compute error message based on query param
const errorMessage = computed(() => {
  const { error } = route.query
  const errorMessageI18nKey = `loginError.${error}`
  if (te(errorMessageI18nKey)) {
    return t(errorMessageI18nKey)
  }
  return t('loginError.defaultErrorMessage')
})

// Head
useHead({
  title: t('loginError.title'),
})
</script>
