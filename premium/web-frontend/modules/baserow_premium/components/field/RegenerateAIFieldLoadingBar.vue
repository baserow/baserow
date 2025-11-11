<template>
  <div class="modal-progress__actions">
    <template v-if="job !== null">
      <ProgressBar :value="job.progress_percentage" :status="job.state" />
    </template>

    <Button
      v-if="job === null || job.state !== 'finished'"
      type="primary"
      size="large"
      :loading="loading"
      :disabled="disabled || loading"
      full-width
      class="modal-progress__export-button"
    >
      {{ $t('regenerateAIFieldLoadingBar.generate') }}
    </Button>
    <Button
      v-else
      type="primary"
      size="large"
      full-width
      class="modal-progress__export-button"
      @click="$emit('close')"
    >
      {{ $t('regenerateAIFieldLoadingBar.close') }}
    </Button>
  </div>
</template>

<script>
export default {
  name: 'RegenerateAIFieldLoadingBar',
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
  },
}
</script>
