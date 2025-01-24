import DataSyncService from '@baserow/modules/database/services/dataSync'
import error from '@baserow/modules/core/mixins/error'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'

export default {
  mixins: [error, jobProgress],
  data() {
    return {
      loadingProperties: false,
      loadedProperties: false,
      properties: null,
      syncedProperties: [],
      updateLoading: false,
    }
  },
  beforeDestroy() {
    this.stopPollIfRunning()
  },
  computed: {
    orderedProperties() {
      if (!this.properties) {
        return []
      }

      // Show the properties where `initially_selected == True` first.
      return this.properties
        .slice()
        .sort((a, b) =>
          a.initially_selected === b.initially_selected
            ? 0
            : a.initially_selected
            ? -1
            : 1
        )
    },
  },
  methods: {
    toggleVisibleField(key) {
      const index = this.syncedProperties.findIndex((f) => key === f)
      if (index > -1) {
        this.syncedProperties.splice(index, 1)
      } else {
        this.syncedProperties.push(key)
      }
    },
    getFieldTypeIconClass(fieldType) {
      return this.$registry.get('field', fieldType).getIconClass()
    },
    async fetchExistingProperties(table) {
      this.loadingProperties = true

      try {
        const { data } = await DataSyncService(
          this.$client
        ).fetchPropertiesOfDataSync(table.data_sync.id)
        this.loadedProperties = true
        this.properties = data
      } catch (error) {
        if (error.handler && error.handler.code === 'ERROR_SYNC_ERROR') {
          this.showError(
            this.$t('dataSyncType.syncError'),
            error.handler.detail
          )
          error.handler.handled()
          return
        }
        this.handleError(error)
      } finally {
        this.loadingProperties = false
      }
    },
    async fetchNonExistingProperties(type, values) {
      values.type = type

      this.loadingProperties = true
      this.hideError()

      try {
        const { data } = await DataSyncService(this.$client).fetchProperties(
          values
        )
        this.loadedProperties = true
        this.properties = data
        this.syncedProperties = data
          .filter((p) => p.initially_selected)
          .map((p) => p.key)
      } catch (error) {
        if (error.handler && error.handler.code === 'ERROR_SYNC_ERROR') {
          this.showError(
            this.$t('dataSyncType.syncError'),
            error.handler.detail
          )
          error.handler.handled()
          return
        }
        this.handleError(error)
      } finally {
        this.loadingProperties = false
      }
    },
    async syncTable(table) {
      if (this.jobIsRunning) {
        return
      }

      this.hideError()
      this.job = null

      try {
        const { data: job } = await DataSyncService(this.$client).syncTable(
          table.data_sync.id
        )
        this.startJobPoller(job)
      } catch (error) {
        this.handleError(error)
      }
    },
    async update(table, values, syncTable = true) {
      this.updateLoading = true

      try {
        const { data } = await DataSyncService(this.$client).update(
          this.table.data_sync.id,
          values
        )
        await this.$store.dispatch('table/forceUpdate', {
          database: this.database,
          table: this.table,
          values: { data_sync: data },
        })
        if (syncTable) {
          await this.syncTable(this.table)
        }
      } catch (error) {
        if (error.handler && error.handler.code === 'ERROR_SYNC_ERROR') {
          this.showError(
            this.$t('dataSyncType.syncError'),
            error.handler.detail
          )
          error.handler.handled()
          return
        }
        this.handleError(error)
      } finally {
        this.updateLoading = false
      }
    },
    onJobFailed() {
      const error = new ResponseErrorMessage(
        this.$t('createDataSync.error'),
        this.job.human_readable_error
      )
      this.stopPollAndHandleError(error)
    },
    onJobPollingError(error) {
      this.stopPollAndHandleError(error)
    },
    stopPollAndHandleError(error) {
      this.stopPollIfRunning()
      error.handler ? this.handleError(error) : this.showError(error)
    },
  },
}
