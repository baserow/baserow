<template>
  <Modal>
    <h2 class="box__title">
      {{ application.name }} {{ $t('snapshotsModal.title') }}
    </h2>
    <p>
      {{
        $t('snapshotsModal.description', {
          applicationTypeName: applicationTypeName,
        })
      }}
      <span v-if="maxSnapshots >= 0">{{
        $tc('snapshotsModal.descriptionLimits', maxSnapshots)
      }}</span>
    </p>
    <component
      :is="component"
      v-for="(component, index) in snapshotModalAlertComponents"
      :key="index"
    ></component>
    <Error :error="error"></Error>
    <div class="snapshots-modal">
      <CreateSnapshotForm
        v-if="!limitReached"
        ref="form"
        :application-name="application.name"
        :snapshots="snapshots"
        @submitted="submitted"
      >
        <template v-if="jobIsRunning || jobIsFinished" #input>
          <div class="margin-right-2">
            <ProgressBar
              :value="job.progress_percentage"
              :status="jobHumanReadableState"
            />
          </div>
        </template>
        <template #default>
          <Button
            v-if="!createFinished"
            size="large"
            :loading="createLoading"
            :disabled="createLoading || snapshotsLoading"
          >
            {{ $t('snapshotsModal.create') }}
          </Button>
          <Button v-else type="secondary" tag="a" size="large" @click="reset()">
            {{ $t('snapshotsModal.reset') }}
          </Button>
        </template>
        <template #cancel-action>
          <ButtonText
            v-if="jobIsRunning || cancelLoading"
            tag="a"
            type="secondary"
            class="snapshots-modal__cancel-button"
            :loading="cancelLoading"
            @click="cancelJob(job.id)"
          >
            {{ $t('snapshotsModal.cancel') }}
          </ButtonText>
        </template>
      </CreateSnapshotForm>
      <div v-else>
        {{ $t('snapshotsModal.limitReached') }}
      </div>
      <div class="snapshots-modal__list">
        <div
          v-if="snapshotsLoading"
          class="loading snapshots-modal__list--loading"
        ></div>
        <div v-else-if="snapshots.length > 0">
          <SnapshotListItem
            v-for="snapshot in snapshots"
            ref="snapshotsList"
            :key="snapshot.id"
            :snapshot="snapshot"
            :last-updated="snapshot.created_at"
            @snapshot-deleted="snapshotDeleted"
          ></SnapshotListItem>
        </div>
        <div v-else>
          {{ $t('snapshotsModal.noSnapshots') }}
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import CreateSnapshotForm from '@baserow/modules/core/components/snapshots/CreateSnapshotForm'
import SnapshotListItem from '@baserow/modules/core/components/snapshots/SnapshotListItem'
import SnapshotsService from '@baserow/modules/core/services/snapshots'
import job from '@baserow/modules/core/mixins/job'
import { CreateSnapshotJobType } from '@baserow/modules/core/jobTypes'

export default {
  name: 'SnapshotsModal',
  components: {
    CreateSnapshotForm,
    SnapshotListItem,
  },
  mixins: [modal, error, job],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      createLoading: false,
      createFinished: false,
      snapshotsLoading: false,
      snapshots: [],
      // Currently we don't query the backend to fetch the limit
      limitReached: false,
    }
  },
  computed: {
    applicationTypeName() {
      return this.$registry
        .get('application', this.application.type)
        .getName()
        .toLowerCase()
    },
    maxSnapshots() {
      return parseInt(this.$config.BASEROW_MAX_SNAPSHOTS_PER_GROUP)
    },
    snapshotModalAlertComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) =>
          plugin.getExtraSnapshotModalComponents(this.application.workspace)
        )
        .filter((component) => component !== null)
    },
  },
  methods: {
    show(...args) {
      this.hideError()
      this.loadSnapshots()
      modal.methods.show.bind(this)(...args)
    },
    async submitted(values) {
      this.createLoading = true
      this.hideError()
      try {
        const { data: job } = await SnapshotsService(this.$client).create(
          this.application.id,
          values
        )
        await this.createAndMonitorJob(job)
      } catch (error) {
        this.createLoading = false
        this.handleError(error)
      }
    },
    onJobFinished() {
      this.createLoading = false
      this.createFinished = true
      if (
        this.job.snapshot &&
        this.job.type === CreateSnapshotJobType.getType()
      ) {
        this.snapshots.unshift(this.job.snapshot)
      }
      this.$refs.form.v$.$reset()
    },
    onJobFailed() {
      this.createLoading = false
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.job.human_readable_error
      )
    },
    onJobCancelled() {
      this.createLoading = false
    },
    async loadSnapshots() {
      this.snapshotsLoading = true

      try {
        const { data: snapshots } = await SnapshotsService(this.$client).list(
          this.application.id
        )
        this.snapshots = snapshots
      } catch (error) {
        this.handleError(error)
      } finally {
        this.snapshotsLoading = false
      }
      this.loadRunningJob()
    },
    snapshotDeleted(deletedSnapshot) {
      this.snapshots = this.snapshots.filter(
        (snapshot) => snapshot.id !== deletedSnapshot.id
      )
    },
    loadRunningJob() {
      const runningJob = this.$store.getters['job/getUnfinishedJobs'].find(
        (job) => {
          return (
            job.type === CreateSnapshotJobType.getType() &&
            job.snapshot.snapshot_from_application === this.application.id
          )
        }
      )
      if (runningJob) {
        this.job = runningJob
        this.createLoading = true
      }
    },
    reset() {
      this.job = null
      this.createFinished = false
      this.createLoading = false
      this.$refs.form.resetName()
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
