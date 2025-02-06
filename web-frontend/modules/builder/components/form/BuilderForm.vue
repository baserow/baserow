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
        {{ $t('builderForm.submit') }}
      </Button>
    </div>
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
}
</script>
