<template>
  <Button
    type="primary"
    :loading="loading"
    :disabled="loading"
    @click="$emit('submit')"
  >
    {{ $t('action.add') }}
    {{ applicationType.getName() | lowercase }}
  </Button>
</template>

<script>
export default {
  name: 'BuilderFormFooter',
  props: {
    applicationType: {
      type: Object,
      required: true,
    },
    loading: {
      type: Boolean,
      required: false,
      default: null,
    },
  },
  methods: {
    submit() {
      this.$refs.applicationForm.submit()
    },
  },
}
</script>
