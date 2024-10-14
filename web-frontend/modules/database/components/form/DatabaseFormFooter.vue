<template>
  <div>
    <ProgressBar
      v-if="importType === 'airtable' && (job.isRunning || job.hasSucceeded)"
      :value="job.progressPercentage"
      :status="job.status"
    />

    <template v-if="importType === 'airtable'">
      <Button
        v-if="!job.hasSucceeded"
        :loading="loading"
        :disabled="loading"
        @click="$emit('submit')"
      >
        {{ $t('importFromAirtable.importButtonLabel') }}
      </Button>

      <Button v-else type="secondary" @click="$emit('open-database', job)">
        {{ $t('importFromAirtable.openButtonLabel') }}</Button
      >
    </template>
    <Button
      v-else
      type="primary"
      :loading="loading"
      :disabled="loading"
      @click="$emit('submit')"
    >
      {{ $t('action.add') }}
      {{ applicationType.getName() | lowercase }}
    </Button>
  </div>
</template>

<script>
export default {
  name: 'DatabaseFormFooter',
  props: {
    applicationType: {
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
      required: false,
      default: false,
    },
    importType: {
      type: String,
      required: false,
      default: 'none',
    },
  },
}
</script>
