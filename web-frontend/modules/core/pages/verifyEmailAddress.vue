<template>
  <div class="auth__wrapper">
    <div class="auth__wrapper auth__wrapper--small-centered">
      <ButtonIcon icon="iconoir-mail-out" />
      <p>
        {{ $t('verifyEmailAddress.confirmation') }}
      </p>
      <p v-if="emailMismatchWarning">
        {{ $t('verifyEmailAddress.emailMismatchWarning') }}
      </p>
      <Button
        tag="nuxt-link"
        :to="{ name: 'login' }"
        type="secondary"
        size="large"
      >
        {{ $t('verifyEmailAddress.goToDashboard') }}</Button
      >
    </div>
  </div>
</template>

<script>
import AuthService from '@baserow/modules/core/services/auth'
import { setToken } from '@baserow/modules/core/utils/auth'

export default {
  layout: 'login',
  async asyncData({ store, params, error, app, redirect }) {
    const { token } = params
    try {
      const isAuthenticated = store.getters['auth/isAuthenticated']
      const shouldLoginUser = !isAuthenticated
      const { data } = await AuthService(app.$client).verifyEmail(
        token,
        shouldLoginUser
      )
      if (shouldLoginUser) {
        store.dispatch('auth/setUserData', data)
        setToken(app, data.refresh_token)
      } else {
        const loggedInUserEmail = store.getters['auth/getUserObject'].username
        if (data.email !== loggedInUserEmail) {
          return {
            emailMismatchWarning: true,
          }
        } else {
          store.dispatch('auth/forceUpdateUserData', {
            user: {
              email_verified: true,
            },
          })
        }
      }
    } catch (err) {
      if (err.handler) {
        const response = err.handler.response
        if (response && response.status === 401) {
          if (response.data?.error === 'ERROR_DEACTIVATED_USER') {
            return error({
              statusCode: 401,
              message: app.i18n.t('error.disabledAccountMessage'),
              content: '',
            })
          } else if (response.data?.error === 'ERROR_AUTH_PROVIDER_DISABLED') {
            return error({
              statusCode: 401,
              message: app.i18n.t(
                'verifyEmailAddress.disabledPasswordProvider'
              ),
              content: '',
            })
          }
        }
      }
      return error({
        statusCode: 404,
        message: app.i18n.t('verifyEmailAddress.invalidToken'),
        content: '',
      })
    }
  },
  data() {
    return {
      emailMismatchWarning: false,
    }
  },
}
</script>
