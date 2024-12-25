<template>
  <div class="snapshots-modal__snapshot">
    <div class="snapshots-modal__info">
      <div v-if="!jobIsRunning && !jobIsFinished">
        <div class="snapshots-modal__name">
          {{ snapshot.name }}
        </div>
        <div class="snapshots-modal__detail">
          {{ snapshot.created_by ? `${snapshot.created_by.username} - ` : '' }}
          {{ $t('snapshotListItem.created') }} {{ timeAgo }}
        </div>
      </div>
      <ProgressBar
        v-else
        :value="job.progress_percentage"
        :status="jobHumanReadableState"
      />
    </div>
    <div class="snapshots-modal__actions">
      <a
        :class="{ 'snapshots-modal__restore--loading': jobIsRunning }"
        @click="restore"
        >{{ $t('snapshotListItem.restore') }}</a
      >
      <a
        v-if="jobIsRunning || cancelLoading"
        class="snapshots-modal__delete"
        @click="cancelJob(job.id)"
      >
        {{ $t('snapshotsModal.cancel') | lowercase }}
      </a>
      <a v-else class="snapshots-modal__delete" @click="showDelete">{{
        $t('snapshotListItem.delete')
      }}</a>
      <DeleteSnapshotModal
        ref="deleteSnapshotModal"
        :snapshot="snapshot"
        @snapshot-deleted="$emit('snapshot-deleted', $event)"
      ></DeleteSnapshotModal>
    </div>
  </div>
</template>

<script>
import SnapshotsService from '@baserow/modules/core/services/snapshots'
import DeleteSnapshotModal from '@baserow/modules/core/components/snapshots/DeleteSnapshotModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import job from '@baserow/modules/core/mixins/job'
import timeAgo from '@baserow/modules/core/mixins/timeAgo'
import { RestoreSnapshotJobType } from '@baserow/modules/core/jobTypes'

export default {
  components: {
    DeleteSnapshotModal,
  },
  mixins: [job, timeAgo],
  props: {
    snapshot: {
      type: Object,
      required: true,
    },
  },
  mounted() {
    if (!this.job) {
      this.restoreRunningState()
    }
  },
  methods: {
    restoreRunningState() {
      const runningJob = this.$store.getters['job/getUnfinishedJobs'].find(
        (job) => {
          return (
            job.type === RestoreSnapshotJobType.getType() &&
            job.snapshot.id === this.snapshot.id
          )
        }
      )
      if (runningJob) {
        this.job = runningJob
      }
    },
    showError(error, message) {
      if (error.message && !message) {
        message = error.message
      }
      if (message) {
        this.$store.dispatch('toast/error', error, message)
      } else {
        notifyIf(error)
      }
    },
    async restore() {
      try {
        const { data: job } = await SnapshotsService(this.$client).restore(
          this.snapshot.id
        )
        await this.createAndMonitorJob(job)
      } catch (error) {
        notifyIf(error)
      }
    },
    showDelete() {
      this.$refs.deleteSnapshotModal.show()
    },
    onJobFailed() {
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.$t('clientHandler.notCompletedDescription')
      )
    },
    getCustomHumanReadableJobState(jobState) {
      if (jobState.startsWith('importing')) {
        return this.$t('snapshotsModal.importingState')
      }
      return ''
    },
  },
}
</script>
