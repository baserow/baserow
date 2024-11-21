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

<script>
export default {
  layout: 'login',
  asyncData({ route, i18n }) {
    const { error } = route.query
    const errorMessageI18nKey = `loginError.${error}`
    let errorMessage = i18n.t('loginError.defaultErrorMessage')
    if (i18n.te(errorMessageI18nKey)) {
      errorMessage = i18n.t(`loginError.${error}`)
    }
    return {
      errorMessage,
    }
  },
  head() {
    return {
      title: this.$t('loginError.title'),
    }
  },
}
</script>
