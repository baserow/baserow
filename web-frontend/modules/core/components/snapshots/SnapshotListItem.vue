<template>
  <li
    class="snapshots-modal__row"
    :class="{ 'snapshots-modal__row--confirm': confirmingDelete }"
  >
    <template v-if="confirmingDelete">
      <div class="snapshots-modal__row-body">
        <div class="snapshots-modal__row-name">
          {{ $t('snapshotListItem.confirmDelete', { name: snapshot.name }) }}
        </div>
        <div class="snapshots-modal__row-meta">
          {{
            $t('snapshotListItem.confirmDeleteDescription', {
              applicationTypeName,
            })
          }}
        </div>
      </div>
      <Button
        type="secondary"
        size="small"
        :disabled="deleteLoading"
        @click="confirmingDelete = false"
        >{{ $t('action.cancel') }}</Button
      >
      <Button
        type="danger"
        size="small"
        :loading="deleteLoading"
        :disabled="deleteLoading"
        @click="deleteSnapshot"
        >{{ $t('snapshotListItem.deleteConfirm') }}</Button
      >
    </template>

    <template v-else>
      <div
        class="snapshots-modal__row-avatar"
        :class="{
          'snapshots-modal__row-avatar--automatic':
            snapshot.created_automatically,
        }"
      >
        <i v-if="snapshot.created_automatically" class="iconoir-clock"></i>
        <template v-else>{{ creatorInitial }}</template>
      </div>
      <div class="snapshots-modal__row-body">
        <template v-if="jobIsRunning">
          <div class="snapshots-modal__row-progress-head">
            <span class="snapshots-modal__row-name">{{ snapshot.name }}</span>
            <span class="snapshots-modal__row-meta">{{
              $t('snapshotListItem.restoring', {
                percentage: job.progress_percentage,
              })
            }}</span>
          </div>
          <ProgressBar :value="job.progress_percentage" :show-value="false" />
        </template>
        <template v-else>
          <div class="snapshots-modal__row-name">
            <span class="snapshots-modal__row-name-text">{{
              snapshot.name
            }}</span>
            <i
              v-if="snapshot.protected"
              class="iconoir-shield-check snapshots-modal__row-protected"
              :title="$t('snapshotListItem.protectedTooltip')"
            ></i>
          </div>
          <div v-if="jobIsFinished" class="snapshots-modal__row-restored">
            <i class="iconoir-check-circle"></i>
            {{
              $t('snapshotListItem.restored', {
                applicationTypeName,
              })
            }}
          </div>
          <div v-else class="snapshots-modal__row-meta" :title="meta">
            {{ meta }}
          </div>
        </template>
      </div>

      <Button
        v-if="jobIsRunning || cancelLoading"
        type="secondary"
        size="small"
        :loading="cancelLoading"
        @click="cancelJob(job.id)"
        >{{ $t('snapshotsModal.cancel') }}</Button
      >
      <ButtonText v-else-if="jobIsFinished" @click="job = null">{{
        $t('snapshotListItem.dismiss')
      }}</ButtonText>
      <template v-else>
        <Button type="secondary" size="small" @click="restore">{{
          $t('snapshotListItem.restore')
        }}</Button>
        <ButtonIcon
          ref="menuButton"
          icon="iconoir-more-horiz"
          type="secondary"
          :aria-label="
            $t('snapshotListItem.moreActions', { name: snapshot.name })
          "
          @click="
            $refs.context.toggle($refs.menuButton.$el, 'bottom', 'right', 4)
          "
        ></ButtonIcon>
      </template>

      <Context ref="context" overflow-scroll max-height-if-outside-viewport>
        <ul class="context__menu">
          <li class="context__menu-item">
            <a
              class="context__menu-item-link"
              :class="{ 'context__menu-item-link--loading': protectLoading }"
              @click.prevent="toggleProtected"
            >
              <i
                class="context__menu-item-icon"
                :class="
                  snapshot.protected
                    ? 'iconoir-shield-cross'
                    : 'iconoir-shield-check'
                "
              ></i>
              {{
                snapshot.protected
                  ? $t('snapshotListItem.unprotect')
                  : $t('snapshotListItem.protect')
              }}
            </a>
          </li>
          <li class="context__menu-item">
            <a
              class="context__menu-item-link context__menu-item-link--delete"
              @click.prevent="showDeleteConfirmation"
            >
              <i class="context__menu-item-icon iconoir-bin"></i>
              {{ $t('snapshotListItem.delete') }}
            </a>
          </li>
        </ul>
      </Context>
    </template>
  </li>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import SnapshotsService from '@baserow/modules/core/services/snapshots'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { isSnapshotGoneError } from '@baserow/modules/core/utils/snapshots'
import job from '@baserow/modules/core/mixins/job'
import timeAgo from '@baserow/modules/core/mixins/timeAgo'
import { RestoreSnapshotJobType } from '@baserow/modules/core/jobTypes'

export default {
  mixins: [job, timeAgo],
  props: {
    snapshot: {
      type: Object,
      required: true,
    },
    applicationTypeName: {
      type: String,
      required: true,
    },
    /**
     * After how many days snapshots are deleted, `null` when it's unknown.
     */
    expirationDays: {
      type: [Number, null],
      required: false,
      default: null,
    },
  },
  emits: ['snapshot-deleted', 'snapshot-updated'],
  data() {
    return {
      confirmingDelete: false,
      deleteLoading: false,
      protectLoading: false,
    }
  },
  computed: {
    creatorInitial() {
      const username = this.snapshot.created_by?.username || '?'
      return username.charAt(0).toUpperCase()
    },
    meta() {
      const parts = [
        this.snapshot.created_automatically
          ? this.$t('snapshotListItem.automatic')
          : this.snapshot.created_by?.username,
        this.timeAgo,
        this.snapshot.protected ? this.$t('snapshotListItem.protected') : null,
      ]
      if (this.expirationDays !== null) {
        parts.push(
          this.$t('snapshotListItem.keptUntil', {
            date: moment
              .utc(this.snapshot.created_at)
              .add(this.expirationDays, 'days')
              .local()
              .format('D MMM YYYY'),
          })
        )
      }
      return parts.filter(Boolean).join(' · ')
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
        this.handleActionError(error)
      }
    },
    async toggleProtected() {
      this.protectLoading = true
      try {
        const { data } = await SnapshotsService(this.$client).updateProtected(
          this.snapshot.id,
          !this.snapshot.protected
        )
        this.$refs.context.hide()
        this.$emit('snapshot-updated', data)
      } catch (error) {
        this.handleActionError(error)
      } finally {
        this.protectLoading = false
      }
    },
    showDeleteConfirmation() {
      this.$refs.context.hide()
      this.confirmingDelete = true
    },
    async deleteSnapshot() {
      this.deleteLoading = true
      try {
        await SnapshotsService(this.$client).delete(this.snapshot.id)
        this.$emit('snapshot-deleted', this.snapshot)
      } catch (error) {
        if (isSnapshotGoneError(error)) {
          this.$emit('snapshot-deleted', this.snapshot)
        } else {
          notifyIf(error)
        }
      } finally {
        this.deleteLoading = false
      }
    },
    /**
     * Shows the error of an action on the snapshot. A snapshot that no longer
     * exists, for example because a newer snapshot replaced it, leaves the list.
     */
    handleActionError(error) {
      notifyIf(error)
      if (isSnapshotGoneError(error)) {
        this.$emit('snapshot-deleted', this.snapshot)
      }
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
