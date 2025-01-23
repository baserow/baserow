import form from '@baserow/modules/core/mixins/form'

export default {
  mixins: [form],
  props: {
    domain: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      serverErrors: {},
    }
  },
  computed: {
    hasServerErrors() {
      return Object.values(this.serverErrors).some((value) => value !== null)
    },
  },
  watch: {
    hasServerErrors: {
      handler(val) {
        this.$emit('error', val)
      },
    },
  },
  methods: {
    handleServerError(error) {
      if (error.handler.code !== 'ERROR_REQUEST_BODY_VALIDATION') return false

      this.serverErrors = Object.fromEntries(
        Object.entries(error.handler.detail || {}).map(([key, value]) => [
          key,
          value[0],
        ])
      )

      return true
    },
  },
}
