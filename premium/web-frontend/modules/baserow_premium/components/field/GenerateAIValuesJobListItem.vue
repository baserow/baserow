<template>
  <div class="generate-ai-values-job">
    <div class="generate-ai-values-job__header">
      <div class="generate-ai-values-job__name">
        {{ jobName }}
        <span v-if="isRunning" class="generate-ai-values-job__started">
          {{ $t(`generateAIValuesModal.started`) }} {{ timeAgo }}
        </span>
      </div>
      <ButtonText
        v-if="isRunning || cancelLoading"
        tag="a"
        type="secondary"
        class="generate-ai-values-job__cancel"
        :loading="cancelLoading"
        @click="cancelJob(jobItem.id)"
      >
        {{ $t('action.cancel') }}
      </ButtonText>
    </div>
    <div v-if="isRunning" class="generate-ai-values-job__progress-row">
      <div class="generate-ai-values-job__progress-bar">
        <ProgressBar
          :value="job.progress_percentage || 0"
          :show-value="false"
        />
      </div>
      <div class="generate-ai-values-job__progress-value">
        {{ Math.round(job.progress_percentage || 0) }}%
      </div>
    </div>
    <div v-if="job && !isRunning" class="generate-ai-values-job__detail">
      <span>
        {{ $t(`generateAIValuesModal.${job.state}`) }} {{ timeAgo }}
      </span>
    </div>
  </div>
</template>

<script>
import job from '@baserow/modules/core/mixins/job'
import timeAgo from '@baserow/modules/core/mixins/timeAgo'
import ProgressBar from '@baserow/modules/core/components/ProgressBar'
import ButtonText from '@baserow/modules/core/components/ButtonText'

export default {
  name: 'GenerateAIValuesJobListItem',
  components: { ProgressBar, ButtonText },
  mixins: [timeAgo, job],
  props: {
    jobItem: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    views: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  computed: {
    isRunning() {
      return ['pending', 'started'].includes(this.job?.state)
    },
    jobName() {
      let name = ''

      if (this.jobItem.view_id) {
        const view = this.views.find((v) => v.id === this.jobItem.view_id)
        if (view) {
          name = this.$t('generateAIValuesModal.view', { name: view.name })
        } else {
          name = this.$t('generateAIValuesModal.deletedView', {
            viewId: this.jobItem.view_id,
          })
        }
      } else if (this.jobItem.row_ids?.length) {
        name = this.$t('generateAIValuesModal.rows', {
          count: this.jobItem.row_ids.length,
        })
      } else {
        name = this.$t('generateAIValuesModal.table')
      }

      return name
    },
  },
  mounted() {
    this.job = this.jobItem
  },
}
</script>
