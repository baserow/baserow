<template>
  <div
    class="auth-provider-buttons"
    :class="{
      'auth-provider-buttons--small': showSmallLoginButtons,
      'auth-provider-buttons__no-buttons': loginButtons.length === 0,
      'auth-provider-buttons__no-buttons--hide':
        loginButtons.length === 0 && hideIfNoButtons === true,
    }"
  >
    <template v-for="loginButton in loginButtons">
      <component
        :is="getLoginButtonComponent(loginButton)"
        :key="loginButton.redirect_url"
        :redirect-url="addOriginalParamToUrl(loginButton.redirect_url)"
        :name="loginButton.name"
        :icon="getLoginButtonIcon(loginButton)"
        :small="showSmallLoginButtons"
        :invitation="invitation"
      >
      </component>
    </template>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { isRelativeUrl } from '@baserow/modules/core/utils/url'

export default {
  name: 'LoginButtons',
  props: {
    original: {
      type: String,
      required: false,
      default: null,
    },
    hideIfNoButtons: {
      type: Boolean,
      default: false,
    },
    invitation: {
      required: false,
      validator: (prop) => typeof prop === 'object' || prop === null,
      default: null,
    },
  },
  computed: {
    ...mapGetters({
      loginButtons: 'authProvider/getAllLoginButtons',
    }),
    showSmallLoginButtons() {
      return this.loginButtons.length > 2
    },
    computedOriginal() {
      let original = this.original
      if (!original) {
        original = this.$route.query.original
      }
      return original
    },
  },
  methods: {
    getLoginButtonComponent(loginButton) {
      return this.$registry
        .get('authProvider', loginButton.type)
        .getLoginButtonComponent()
    },
    getLoginButtonIcon(loginButton) {
      return this.$registry.get('authProvider', loginButton.type).getIcon()
    },
    addOriginalParamToUrl(url) {
      const original = this.computedOriginal
      if (original && isRelativeUrl(original)) {
        const parsedUrl = new URL(url)
        parsedUrl.searchParams.append('original', original)
        return parsedUrl.toString()
      } else {
        return url
      }
    },
  },
}
</script>
