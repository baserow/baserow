<template>
  <Modal ref="modal">
    <div class="snapshots-modal">
      <header class="snapshots-modal__header">
        <div class="snapshots-modal__header-icon">
          <i :class="applicationIconClass"></i>
        </div>
        <div class="snapshots-modal__header-body">
          <h2
            class="snapshots-modal__title"
            :title="$t('snapshotsModal.heading', { name: application.name })"
          >
            {{ $t('snapshotsModal.heading', { name: application.name }) }}
          </h2>
          <p class="snapshots-modal__intro">
            {{
              $t('snapshotsModal.intro', {
                applicationTypeName: applicationTypeName,
              })
            }}
            <a
              href="https://baserow.io/user-docs/snapshots"
              target="_blank"
              rel="noopener noreferrer"
              >{{ $t('snapshotsModal.learnMore') }}</a
            >
          </p>
        </div>
      </header>

      <div v-if="usage" class="snapshots-modal__usage">
        <div class="snapshots-modal__usage-head">
          <span>{{ $t('snapshotsModal.workspaceUsage') }}</span>
          <span class="snapshots-modal__usage-count">{{ usageText }}</span>
        </div>
        <div v-if="usage.limit" class="snapshots-modal__usage-bar">
          <div
            class="snapshots-modal__usage-fill"
            :class="{
              'snapshots-modal__usage-fill--full': usage.over_allowance,
            }"
            :style="{ width: `${usagePercentage}%` }"
          ></div>
        </div>
        <div v-if="usage.over_allowance" class="snapshots-modal__usage-warning">
          <i class="iconoir-warning-circle"></i>
          {{ $t('snapshotsModal.overAllowance') }}
        </div>
      </div>

      <MaxSnapshots
        v-if="usage && !snapshotsDisabled"
        ref="maxSnapshots"
        :application="application"
        :usage="usage"
        :snapshots="snapshots"
        :can-update="canUpdateMaxSnapshots"
        @updated="maxSnapshotsUpdated"
        @stale="loadSnapshots()"
      ></MaxSnapshots>

      <Error :error="error"></Error>

      <component
        :is="component"
        v-for="(component, index) in snapshotModalComponents"
        :key="`component-${index}`"
        :application="application"
        :snapshot-usage="usage"
      ></component>

      <section class="snapshots-modal__card">
        <div
          class="snapshots-modal__card-icon"
          :class="{ 'snapshots-modal__card-icon--error': blockedReason }"
        >
          <i
            :class="blockedReason ? 'iconoir-warning-circle' : 'iconoir-camera'"
          ></i>
        </div>
        <div class="snapshots-modal__card-body">
          <h3 class="snapshots-modal__card-title">
            <template v-if="blockedReason">
              {{
                $t(blockedCopy.title, {
                  name: application.name,
                })
              }}
            </template>
            <template v-else>{{ $t('snapshotsModal.takeTitle') }}</template>
          </h3>
          <div class="snapshots-modal__card-description">
            <template v-if="canRaiseAndCreate">
              {{ $t(raiseCopy, { count: raisedMaxSnapshots }) }}
              <Alert
                v-if="raiseGoesOverAllowance"
                type="warning"
                class="snapshots-modal__raise-warning"
              >
                {{
                  $t('maxSnapshots.overAllowance', {
                    used: usage.used + 1,
                    limit: usage.limit,
                  })
                }}
              </Alert>
            </template>
            <template v-else-if="raiseProblem === 'permission'">
              {{ $t(blockedCopy.description) }}
              {{ $t('snapshotsModal.askAnAdmin') }}
            </template>
            <template v-else-if="raiseProblem">
              <template v-if="blockedReason === 'protected'">
                {{ $t('snapshotsModal.allProtectedCantRaise') }}
              </template>
              {{ raiseProblemText }}
            </template>
            <template v-else-if="blockedReason">
              {{ $t(blockedCopy.description) }}
            </template>
            <template v-else>
              <component
                :is="component"
                v-for="(component, index) in snapshotModalAlertComponents"
                :key="index"
                :application="application"
              ></component>
              <div
                v-if="snapshotToReplace && !jobIsRunning && !createFinished"
                class="snapshots-modal__replaces"
              >
                {{
                  $t('snapshotsModal.replaces', {
                    name: snapshotToReplace.name,
                  })
                }}
              </div>
            </template>
          </div>
          <div
            v-if="confirmingReplace"
            class="snapshots-modal__confirm-replace"
          >
            <span>{{
              $t('snapshotsModal.confirmReplace', {
                name: snapshotToReplace ? snapshotToReplace.name : '',
              })
            }}</span>
            <Button
              type="secondary"
              size="small"
              @click="confirmingReplace = false"
              >{{ $t('action.cancel') }}</Button
            >
            <Button size="small" @click="confirmReplace()">{{
              $t('snapshotsModal.replaceAndCreate')
            }}</Button>
          </div>
          <CreateSnapshotForm
            v-if="!blockedReason || canRaiseAndCreate"
            v-show="!confirmingReplace"
            ref="form"
            class="snapshots-modal__form"
            :application-name="application.name"
            :snapshots="snapshots"
            @submitted="submitted"
          >
            <template v-if="jobIsRunning || jobIsFinished" #input>
              <div class="snapshots-modal__progress">
                <ProgressBar
                  :value="job.progress_percentage"
                  :status="jobHumanReadableState"
                />
              </div>
            </template>
            <template #default>
              <Button
                v-if="!createFinished"
                :loading="createLoading"
                :disabled="createLoading || snapshotsLoading"
              >
                <template v-if="canRaiseAndCreate">
                  {{
                    $t('snapshotsModal.raiseAndCreate', {
                      count: raisedMaxSnapshots,
                    })
                  }}
                </template>
                <template v-else>{{ $t('snapshotsModal.create') }}</template>
              </Button>
              <Button v-else type="secondary" tag="a" @click="reset()">
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
        </div>
      </section>

      <section class="snapshots-modal__list">
        <div class="snapshots-modal__list-head">
          <h3 class="snapshots-modal__card-title">
            {{ $t('snapshotsModal.listTitle') }}
            <span class="snapshots-modal__list-count">{{
              snapshots.length
            }}</span>
          </h3>
          <SegmentControl
            v-if="hasAutomaticSnapshots"
            :segments="filterSegments"
            :active-index="filterIndex"
            size="small"
            class="snapshots-modal__filter"
            @update:active-index="filterIndex = $event"
          ></SegmentControl>
        </div>
        <div
          v-if="snapshotsLoading && snapshots.length === 0"
          class="loading snapshots-modal__loading"
        ></div>
        <ul
          v-else-if="filteredSnapshots.length > 0"
          class="snapshots-modal__rows"
        >
          <SnapshotListItem
            v-for="snapshot in filteredSnapshots"
            :key="snapshot.id"
            :snapshot="snapshot"
            :last-updated="snapshot.created_at"
            :application-type-name="applicationTypeName"
            :expiration-days="usage ? usage.expiration_days : null"
            @snapshot-deleted="snapshotDeleted"
            @snapshot-updated="snapshotUpdated"
          ></SnapshotListItem>
        </ul>
        <div v-else class="snapshots-modal__empty">
          <i class="iconoir-camera snapshots-modal__empty-icon"></i>
          <template v-if="snapshots.length === 0">
            <div
              class="snapshots-modal__empty-title"
              :title="
                $t('snapshotsModal.noSnapshots', { name: application.name })
              "
            >
              {{ $t('snapshotsModal.noSnapshots', { name: application.name }) }}
            </div>
            <div>{{ $t('snapshotsModal.noSnapshotsDescription') }}</div>
          </template>
          <div v-else>{{ $t('snapshotsModal.noFilteredSnapshots') }}</div>
        </div>
      </section>

      <footer v-if="usage" class="snapshots-modal__footer">
        <i class="iconoir-info-empty"></i>
        {{ $t('snapshotsModal.expiry', { days: usage.expiration_days }) }}
      </footer>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import CreateSnapshotForm from '@baserow/modules/core/components/snapshots/CreateSnapshotForm'
import MaxSnapshots from '@baserow/modules/core/components/snapshots/MaxSnapshots'
import SnapshotListItem from '@baserow/modules/core/components/snapshots/SnapshotListItem'
import {
  getSnapshotRoom,
  getSnapshotToReplace,
  goesOverSnapshotAllowance,
  isOutOfDateSnapshotsError,
  validateMaxSnapshots,
} from '@baserow/modules/core/utils/snapshots'
import SnapshotsService from '@baserow/modules/core/services/snapshots'
import job from '@baserow/modules/core/mixins/job'
import { CreateSnapshotJobType } from '@baserow/modules/core/jobTypes'

const FILTERS = ['all', 'automatic', 'manual']

export default {
  name: 'SnapshotsModal',
  components: {
    CreateSnapshotForm,
    MaxSnapshots,
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
      usage: null,
      filterIndex: 0,
      confirmingReplace: false,
      pendingValues: null,
    }
  },
  computed: {
    applicationType() {
      return this.$registry.get('application', this.application.type)
    },
    applicationTypeName() {
      return this.applicationType.getName().toLowerCase()
    },
    applicationIconClass() {
      return this.applicationType.getIconClass()
    },
    snapshotsDisabled() {
      return this.usage !== null && this.usage.limit === 0
    },
    canUpdateMaxSnapshots() {
      return this.$hasPermission(
        'application.update_max_snapshots',
        this.application,
        this.application.workspace.id
      )
    },
    /**
     * Why no snapshot can be taken now: `disabled` when snapshots are turned off,
     * `none` when the application keeps no snapshots, `protected` when every
     * snapshot it keeps is protected. `null` when one can be taken.
     */
    blockedReason() {
      if (
        this.usage === null ||
        this.snapshotsLoading ||
        this.jobIsRunning ||
        this.createFinished
      ) {
        return null
      }
      if (this.snapshotsDisabled) {
        return 'disabled'
      }
      if (this.usage.blocked) {
        return 'blocked'
      }
      const room = getSnapshotRoom(
        this.snapshots,
        this.usage.effective_max_snapshots
      )
      return room === 'ok' ? null : room
    },
    blockedCopy() {
      return {
        disabled: {
          title: 'snapshotsModal.disabledTitle',
          description: 'snapshotsModal.disabled',
        },
        none: {
          title: 'snapshotsModal.maxSnapshotsZeroTitle',
          description: 'snapshotsModal.maxSnapshotsZero',
        },
        protected: {
          title: 'snapshotsModal.allProtectedTitle',
          description: 'snapshotsModal.allProtected',
        },
        blocked: {
          title: 'snapshotsModal.blockedTitle',
          description: 'snapshotsModal.blocked',
        },
      }[this.blockedReason]
    },
    /**
     * Whether raising the max snapshots makes room for a snapshot.
     */
    canRaiseMaxSnapshots() {
      return ['none', 'protected'].includes(this.blockedReason)
    },
    /**
     * The max snapshots that makes room for one more snapshot.
     */
    raisedMaxSnapshots() {
      return this.usage.effective_max_snapshots + 1
    },
    /**
     * Why the max snapshots can't be raised to make room: `permission` when the user can't
     * change it, otherwise the translation key of the validation error. `null`
     * when it can be raised, or raising it doesn't make room.
     */
    raiseProblem() {
      if (!this.canRaiseMaxSnapshots) {
        return null
      }
      if (!this.canUpdateMaxSnapshots) {
        return 'permission'
      }
      return validateMaxSnapshots({
        maxSnapshots: this.raisedMaxSnapshots,
        originalMaxSnapshots: this.usage.effective_max_snapshots,
        used: this.usage.used,
        newUsed: this.usage.used + 1,
        limit: this.usage.limit,
        maxSnapshotsLimit: this.usage.max_snapshots_limit,
        protectedCount: this.usage.protected_count,
        canExceedAllowance: this.usage.can_exceed_allowance,
      })
    },
    /**
     * Whether the snapshot can be taken by raising the max snapshots by one first.
     */
    canRaiseAndCreate() {
      return this.canRaiseMaxSnapshots && this.raiseProblem === null
    },
    raiseProblemText() {
      if (this.raiseProblem === 'maxSnapshots.errorAboveMaximum') {
        return this.$t('snapshotsModal.cantRaiseAboveMaximum', {
          count: this.usage.max_snapshots_limit,
        })
      }
      return this.$t('snapshotsModal.cantRaiseAllowance')
    },
    raiseCopy() {
      return this.blockedReason === 'none'
        ? 'snapshotsModal.maxSnapshotsZeroRaise'
        : 'snapshotsModal.allProtectedRaise'
    },
    raiseGoesOverAllowance() {
      return goesOverSnapshotAllowance({
        used: this.usage.used,
        newUsed: this.usage.used + 1,
        limit: this.usage.limit,
      })
    },
    snapshotToReplace() {
      if (this.usage === null) {
        return null
      }
      return getSnapshotToReplace(
        this.snapshots,
        this.usage.effective_max_snapshots
      )
    },
    usagePercentage() {
      return Math.min(100, (this.usage.used / this.usage.limit) * 100)
    },
    usageText() {
      if (this.usage.limit === 0) {
        return this.$t('snapshotsModal.usageDisabled')
      }
      if (this.usage.limit === null) {
        return this.$t('snapshotsModal.usageWithoutLimit', {
          used: this.usage.used,
        })
      }
      return this.$t('snapshotsModal.usage', {
        used: this.usage.used,
        limit: this.usage.limit,
      })
    },
    hasAutomaticSnapshots() {
      return this.snapshots.some((snapshot) => snapshot.created_automatically)
    },
    filterSegments() {
      return [
        { label: this.$t('snapshotsModal.filterAll') },
        { label: this.$t('snapshotsModal.filterAutomatic') },
        { label: this.$t('snapshotsModal.filterManual') },
      ]
    },
    filteredSnapshots() {
      const filter = this.hasAutomaticSnapshots
        ? FILTERS[this.filterIndex]
        : 'all'
      if (filter === 'all') {
        return this.snapshots
      }
      const automatic = filter === 'automatic'
      return this.snapshots.filter(
        (snapshot) => snapshot.created_automatically === automatic
      )
    },
    snapshotModalAlertComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) =>
          plugin.getExtraSnapshotModalComponents(
            this.application.workspace,
            this.application
          )
        )
        .filter((component) => component !== null)
    },
    snapshotModalComponents() {
      return Object.values(this.$registry.getAll('plugin')).flatMap((plugin) =>
        plugin.getSnapshotModalComponents(
          this.application.workspace,
          this.application
        )
      )
    },
  },
  methods: {
    show(...args) {
      this.hideError()
      this.confirmingReplace = false
      this.loadSnapshots()
      modal.methods.show.bind(this)(...args)
    },
    submitted(values) {
      if (this.canRaiseAndCreate) {
        return this.create({ ...values, raise_max_snapshots: true })
      }
      if (this.snapshotToReplace) {
        this.pendingValues = values
        this.confirmingReplace = true
        return
      }
      return this.create(values)
    },
    confirmReplace() {
      this.confirmingReplace = false
      return this.create(this.pendingValues)
    },
    async create(values) {
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
        if (isOutOfDateSnapshotsError(error)) {
          this.loadSnapshots()
        }
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
      // The oldest unprotected snapshots beyond the max snapshots are deleted once the new
      // one is created, so the list is loaded again.
      this.loadSnapshots()
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
    getJobNotCancellableMessage() {
      return this.$t('job.errorJobCannotBeCancelledDescription')
    },
    async loadSnapshots() {
      this.snapshotsLoading = true

      try {
        const [{ data: snapshots }] = await Promise.all([
          SnapshotsService(this.$client).list(this.application.id),
          this.loadUsage(),
        ])
        this.snapshots = snapshots
      } catch (error) {
        this.handleError(error)
      } finally {
        this.snapshotsLoading = false
      }
      this.loadRunningJob()
    },
    async loadUsage() {
      try {
        const { data } = await SnapshotsService(this.$client).usage(
          this.application.id
        )
        this.usage = data
      } catch (error) {
        // The usage only adds context, the snapshots can be managed without it.
        this.usage = null
      }
    },
    maxSnapshotsUpdated(usage) {
      this.usage = usage
      // Lowering the max snapshots can delete snapshots, so the list is loaded again.
      this.loadSnapshots()
    },
    snapshotUpdated(updatedSnapshot) {
      this.snapshots = this.snapshots.map((snapshot) =>
        snapshot.id === updatedSnapshot.id ? updatedSnapshot : snapshot
      )
      this.loadUsage()
    },
    snapshotDeleted(deletedSnapshot) {
      this.snapshots = this.snapshots.filter(
        (snapshot) => snapshot.id !== deletedSnapshot.id
      )
      this.loadUsage()
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
