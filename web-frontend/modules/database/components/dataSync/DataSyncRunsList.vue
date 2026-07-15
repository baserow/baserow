<template>
  <div>
    <div v-if="loading" class="loading margin-top-2"></div>
    <template v-else>
      <Error :error="error"></Error>
      <template v-if="loaded">
        <p v-if="rows.length === 0" class="data-sync-runs__empty">
          <i class="iconoir-data-transfer-down data-sync-runs__empty-icon"></i>
          {{ $t('dataSyncRuns.noRuns') }}
        </p>
        <div v-else class="data-sync-runs">
          <div
            v-for="row in rows"
            :key="row.id"
            class="data-sync-runs__item"
            :class="{ 'data-sync-runs__item--open': isExpanded(row.id) }"
          >
            <DataSyncRunHead
              :expandable="Boolean(row.human_readable_error)"
              :expanded="isExpanded(row.id)"
              :controls="`data-sync-run-error-${row.id}`"
              @toggle="toggleExpanded(row.id)"
            >
              <Badge :color="stateColor(row.state)" rounded>{{
                stateLabel(row.state)
              }}</Badge>
              <Badge
                :color="row.triggered_by === 'periodic' ? 'cyan' : 'neutral'"
                rounded
                >{{
                  row.triggered_by === 'periodic'
                    ? $t('dataSyncRuns.triggerPeriodic')
                    : $t('dataSyncRuns.triggerManual')
                }}</Badge
              >
              <span class="data-sync-runs__info">
                {{ timestamp(row) }}
                <template v-if="row.user_name">
                  {{ $t('dataSyncRuns.byUser', { name: row.user_name }) }}
                </template>
              </span>
              <span class="data-sync-runs__duration">
                <template v-if="isEnded(row)">{{
                  $t('dataSyncRuns.duration', { seconds: duration(row) })
                }}</template>
                <template v-else>{{ row.progress_percentage }}%</template>
              </span>
              <i
                v-if="row.human_readable_error"
                class="data-sync-runs__toggle-icon"
                :class="
                  isExpanded(row.id)
                    ? 'iconoir-nav-arrow-up'
                    : 'iconoir-nav-arrow-down'
                "
              ></i>
            </DataSyncRunHead>
            <div
              v-if="isExpanded(row.id)"
              :id="`data-sync-run-error-${row.id}`"
              class="data-sync-runs__error"
            >
              {{ row.human_readable_error }}
            </div>
          </div>
        </div>
        <Paginator
          v-if="totalPages > 1"
          class="data-sync-runs__paginator"
          :total-pages="totalPages"
          :page="page"
          @change-page="changePage"
        ></Paginator>
      </template>
    </template>
  </div>
</template>

<script>
import Paginator from '@baserow/modules/core/components/Paginator'
import error from '@baserow/modules/core/mixins/error'
import { FINISHED_STATES } from '@baserow/modules/core/store/job'
import DataSyncService from '@baserow/modules/database/services/dataSync'
import DataSyncRunHead from '@baserow/modules/database/components/dataSync/DataSyncRunHead'
import moment from '@baserow/modules/core/moment'

export default {
  name: 'DataSyncRunsList',
  components: { DataSyncRunHead, Paginator },
  mixins: [error],
  props: {
    dataSyncId: {
      type: Number,
      required: true,
    },
    limit: {
      type: Number,
      required: false,
      default: 10,
    },
  },
  emits: ['running-job'],
  data() {
    return {
      loading: false,
      loaded: false,
      jobs: [],
      count: 0,
      page: 1,
      expandedJobIds: [],
    }
  },
  computed: {
    storeJobs() {
      return this.$store.getters['job/getAll']
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.count / this.limit))
    },
    rows() {
      // Store copies win (live via poller); page 1 also shows store-only new runs.
      const rowsById = new Map()
      if (this.page === 1) {
        for (const job of this.storeJobs) {
          if (
            job.type === 'sync_data_sync_table' &&
            job.data_sync?.id === this.dataSyncId
          ) {
            rowsById.set(job.id, job)
          }
        }
      }
      for (const job of this.jobs) {
        if (!rowsById.has(job.id)) {
          rowsById.set(
            job.id,
            this.storeJobs.find((item) => item.id === job.id) || job
          )
        }
      }
      return [...rowsById.values()].sort((a, b) => b.id - a.id)
    },
    unfinishedTrackedJobCount() {
      return this.storeJobs.filter(
        (item) =>
          !FINISHED_STATES.includes(item.state) &&
          this.rows.some((row) => row.id === item.id)
      ).length
    },
  },
  watch: {
    unfinishedTrackedJobCount(newCount, oldCount) {
      // Page 1 only: elsewhere a drop can be pagination swapping rows out.
      if (newCount < oldCount && this.page === 1) {
        this.reload()
      }
    },
  },
  mounted() {
    this.reload()
  },
  methods: {
    async reload(page = this.page) {
      if (!this.loaded) {
        this.loading = true
      }
      try {
        const { data } = await DataSyncService(this.$client).fetchSyncJobs(
          this.dataSyncId,
          { limit: this.limit, offset: (page - 1) * this.limit }
        )
        this.hideError()
        this.page = page
        this.jobs = data.jobs
        this.count = data.count ?? data.jobs.length
        const unfinished = data.jobs.filter(
          (job) => !FINISHED_STATES.includes(job.state)
        )
        await Promise.all(
          unfinished.map((job) => this.$store.dispatch('job/create', job))
        )
        if (unfinished.length > 0) {
          this.$emit('running-job', unfinished[0])
        }
        this.loaded = true
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
      }
    },
    changePage(page) {
      if (page >= 1 && page <= this.totalPages && page !== this.page) {
        this.reload(page)
      }
    },
    isEnded(job) {
      return FINISHED_STATES.includes(job.state)
    },
    isExpanded(jobId) {
      return this.expandedJobIds.includes(jobId)
    },
    stateColor(state) {
      const colors = {
        finished: 'green',
        failed: 'red',
        cancelled: 'yellow',
      }
      return colors[state] || 'cyan'
    },
    stateLabel(state) {
      const translations = {
        pending: this.$t('job.statePending'),
        started: this.$t('job.stateStarted'),
        failed: this.$t('job.stateFailed'),
        finished: this.$t('job.stateFinished'),
        cancelled: this.$t('job.stateCanceled'),
      }
      return translations[state] || this.$t('job.stateStarted')
    },
    timestamp(job) {
      return moment.utc(job.created_on).local().format('YYYY-MM-DD HH:mm:ss')
    },
    duration(job) {
      return Math.max(
        0,
        Math.round(
          (moment.utc(job.updated_on) - moment.utc(job.created_on)) / 1000
        )
      )
    },
    toggleExpanded(jobId) {
      const index = this.expandedJobIds.indexOf(jobId)
      if (index > -1) {
        this.expandedJobIds.splice(index, 1)
      } else {
        this.expandedJobIds.push(jobId)
      }
    },
  },
}
</script>
