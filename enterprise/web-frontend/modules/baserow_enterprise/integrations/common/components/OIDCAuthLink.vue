<template>
  <div class="oidc-auth-link">
    <ABButton @click.prevent="onClick()">
      {{ buttonLabel }}
    </ABButton>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import { required, email } from 'vuelidate/lib/validators'
import ThemeProvider from '@baserow/modules/builder/components/theme/ThemeProvider'

export default {
  components: { ThemeProvider },
  mixins: [form, error],
  props: {
    userSource: { type: Object, required: true },
    authProviders: {
      type: Array,
      required: true,
    },
    loginButtonLabel: {
      type: String,
      required: true,
    },
    readonly: {
      type: Boolean,
      required: false,
      default: false,
    },
    authenticate: {
      type: Function,
      required: true,
    },
    beforeLogin: {
      type: Function,
      required: false,
      default: () => {
        return () => {}
      },
    },
  },
  data() {
    return {
      loading: false,
      values: { email: '' },
    }
  },
  computed: {
    buttonLabel() {
      return this.$t('OIDCAuthLink.placeholderWithOIDC', {
        login: this.loginButtonLabel,
      })
    },
  },
  methods: {
    onClick() {
      console.log('clicked')
    },
  },
  validations: {},
}
</script>
