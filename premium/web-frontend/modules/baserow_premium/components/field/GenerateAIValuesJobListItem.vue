<template>
  <div class="generate-ai-values-job">
    <div class="generate-ai-values-job__info">
      <div>
        <div
          class="generate-ai-values-job__name"
          :class="{ 'deleted-view': viewDeleted }"
        >
          {{ jobName }}
        </div>
        <div class="generate-ai-values-job__detail">
          <span v-if="isRunning">
            {{ $t('generateAIValuesModal.running') }} ({{
              job.progress_percentage
            }}%)
          </span>
          <span v-else-if="job.state === 'finished'">
            {{ $t('generateAIValuesModal.completed') }} {{ timeAgo }}
          </span>
          <span v-else-if="job.state === 'failed'">
            {{ $t('generateAIValuesModal.failed') }} {{ timeAgo }}
          </span>
          <span v-else-if="job.state === 'cancelled'">
            {{ $t('generateAIValuesModal.cancelled') }} {{ timeAgo }}
          </span>
          <span v-else>
            {{ $t('generateAIValuesModal.pending') }}
          </span>
        </div>
        <div v-if="isRunning" class="generate-ai-values-job__progress">
          <ProgressBar :value="job.progress_percentage || 0" />
        </div>
      </div>
    </div>
    <div v-if="isRunning" class="generate-ai-values-job__actions">
      <ButtonText
        tag="a"
        type="secondary"
        class="generate-ai-values-job__cancel"
        :loading="cancelLoading"
        @click="$emit('cancel-job', job.id)"
      >
        {{ $t('action.cancel') }}
      </ButtonText>
    </div>
  </div>
</template>

<script>
import timeAgo from '@baserow/modules/core/mixins/timeAgo'
import moment from '@baserow/modules/core/moment'
import ProgressBar from '@baserow/modules/core/components/ProgressBar'
import ButtonText from '@baserow/modules/core/components/ButtonText'

export default {
  name: 'GenerateAIValuesJobListItem',
  components: { ProgressBar, ButtonText },
  mixins: [timeAgo],
  props: {
    job: {
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
    cancelLoading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    isRunning() {
      return this.job.state === 'pending' || this.job.state === 'started'
    },
    viewDeleted() {
      if (!this.job.view_id) return false
      return !this.views.find((v) => v.id === this.job.view_id)
    },
    jobName() {
      const mode = this.job.mode || 'table'
      let name = ''

      if (mode === 'view' && this.job.view_id) {
        const view = this.views.find((v) => v.id === this.job.view_id)
        if (view) {
          name = view.name
        } else {
          name = this.$t('generateAIValuesModal.deletedView')
        }
      } else if (mode === 'rows' && this.job.row_count) {
        name = this.$t('generateAIValuesModal.selectedRows', {
          count: this.job.row_count,
        })
      } else {
        name = this.$t(`generateAIValuesModal.mode_${mode}`)
      }

      const date = moment(this.job.created_on).format('YYYY-MM-DD HH:mm')
      return `${name} - ${date}`
    },
  },
}
</script>
