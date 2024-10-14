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
  name: 'DashboardForm',
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
  computed: {
    dashboardApplicationType() {
      return this.$registry.get('application', 'dashboard')
    },
  },
  methods: {
    submit() {
      this.$refs.applicationForm.submit()
    },
  },
}
</script>
