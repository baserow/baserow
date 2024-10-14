<template>
  <Button
    type="primary"
    :loading="loading"
    :disabled="loading"
    @click="$emit('submit')"
  >
    {{ $t('action.add') }}
    {{ dashboardApplicationType.getName() | lowercase }}
  </Button>
</template>

<script>
export default {
  name: 'DashboardForm',
  props: {
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    dashboardApplicationType() {
      return this.$registry.get('application', 'dashboard')
    },
  },
}
</script>
