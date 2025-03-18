import form from '@baserow/modules/core/mixins/form'

export default {
  mixins: [form],
  props: {
    authProviders: {
      type: Object,
      required: true,
    },
    authProvider: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    authProviderType: {
      type: Object,
      required: true,
    },
  },
  data() {
    return { serverErrors: {} }
  },
  computed: {
    providerName() {
      return this.authProviderType.getProviderName(this.authProvider)
    },
  },
  methods: {
    submit() {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }
      this.$emit('submit', this.values)
    },
    handleServerError(error) {
      return this.authProviderType.handleServerError(this, error)
    },
  },
}
