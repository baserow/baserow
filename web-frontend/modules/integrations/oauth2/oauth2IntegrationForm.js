import { helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

/**
 * Shared by the Google and Microsoft integration forms: the app credentials,
 * of which the secret is write-only and kept when left blank. Vue does not
 * merge `setup` from mixins, so each form creates its own `v$`.
 */
export default {
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      // An empty secret is dropped on submit to keep the stored one.
      values: { client_id: '', client_secret: null },
      allowedValues: ['client_id', 'client_secret'],
    }
  },
  computed: {
    hasClientSecret() {
      return this.defaultValues.has_client_secret === true
    },
  },
  methods: {
    getFormValues(deep = false) {
      const values = Object.assign(
        {},
        this.values,
        this.getChildFormsValues(deep)
      )
      if (!values.client_secret) {
        delete values.client_secret
      }
      return values
    },
  },
  validations() {
    return {
      values: {
        client_id: {
          required: helpers.withMessage(
            this.$t('oauth2Credentials.required'),
            (value) => !!value
          ),
        },
        client_secret: {
          required: helpers.withMessage(
            this.$t('oauth2Credentials.required'),
            (value) => this.hasClientSecret || !!value
          ),
        },
      },
    }
  },
}
