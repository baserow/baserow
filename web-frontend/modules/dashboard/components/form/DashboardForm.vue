<template>
  <ApplicationForm
    :default-values="{ name: defaultName }"
    :workspace="workspace"
    :loading="loading"
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
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: true,
    },
    workspace: {
      type: Object,
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
