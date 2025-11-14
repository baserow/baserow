<template>
  <div class="modal-progress__actions">
    <template v-if="job !== null">
      <ProgressBar :value="job.progress_percentage" :status="job.state" />

      <ButtonText
        v-if="loading || cancelLoading"
        tag="a"
        type="secondary"
        class="modal-progress__cancel-button"
        :loading="cancelLoading"
        @click="$emit('cancel-job')"
      >
        {{ $t('action.cancel') }}
      </ButtonText>
    </template>

    <Button
      type="primary"
      size="large"
      :loading="loading"
      :disabled="disabled || loading"
      full-width
      class="modal-progress__primary-button generate-ai-values__generate-button"
    >
      {{ $t('generateAIValuesFormFooter.generate') }}
    </Button>
  </div>
</template>

<script>
export default {
  name: 'GenerateAIValuesFormFoote',
  props: {
    field: {
      type: Object,
      required: true,
    },
    job: {
      type: Object,
      required: false,
      default: null,
    },
    loading: {
      type: Boolean,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: true,
    },
    cancelLoading: {
      type: Boolean,
      required: true,
    },
  },
}
</script>
