<template>
  <ApplicationForm
    ref="applicationForm"
    :default-values="{ name: defaultName }"
    @submitted="$emit('submitted', $event)"
  >
  </ApplicationForm>
</template>

<script>
import ApplicationForm from '@baserow/modules/core/components/application/ApplicationForm'
export default {
  name: 'BuilderForm',
  components: { ApplicationForm },
  props: {
    defaultName: {
      type: String,
      required: true,
    },
    loading: {
      type: Boolean,
      required: true,
    },
  },
  methods: {
    submit() {
      this.$refs.applicationForm.submit()
    },
  },
}
</script>
