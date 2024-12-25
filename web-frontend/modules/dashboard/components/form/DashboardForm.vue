<template>
  <ApplicationForm
    :default-values="{ name: defaultName }"
    @submitted="$emit('submitted', $event)"
  >
    <div class="actions actions--right">
      <Button
        type="primary"
        size="large"
        :loading="loading"
        :disabled="loading"
      >
        {{ $t('action.add') }}
        {{ dashboardApplicationType.getName() | lowercase }}
      </Button>
    </div>
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
}
</script>
