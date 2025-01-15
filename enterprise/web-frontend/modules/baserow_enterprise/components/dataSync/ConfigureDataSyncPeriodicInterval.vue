<template>
  <div>
    <h2 class="box__title">
      {{ $t('configureDataSyncPeriodicInterval.title') }}
    </h2>
    <div v-if="fetchLoading">
      <div class="loading"></div>
    </div>
    <div v-if="!fetchLoaded">
      <Error :error="error"></Error>
    </div>
    <div v-else-if="fetchLoaded">
      <Error :error="error"></Error>
      <DataSyncPeriodicIntervalForm
        :default-values="periodicInterval"
        :disabled="saveLoading"
        @submitted="submitted"
        @values-changed="saved = false"
      >
        <div class="flex align-items-center justify-content-end">
          <Button
            v-if="!saved"
            type="primary"
            size="large"
            :loading="saveLoading"
            :disabled="saveLoading"
          >
            {{ $t('action.save') }}
          </Button>
          <template v-if="saved">
            <strong class="color-success">{{
              $t('configureDataSyncPeriodicInterval.saved')
            }}</strong>
            <Button type="secondary" size="large" @click="$emit('hide')">
              {{ $t('action.hide') }}
            </Button>
          </template>
        </div>
      </DataSyncPeriodicIntervalForm>
    </div>
  </div>
</template>

<script>
import EnterpriseDataSyncService from '@baserow_enterprise/services/dataSync'
import error from '@baserow/modules/core/mixins/error'
import DataSyncPeriodicIntervalForm from '@baserow_enterprise/components/dataSync/DataSyncPeriodicIntervalForm'

export default {
  name: 'ConfigureDataSyncPeriodicInterval',
  components: { DataSyncPeriodicIntervalForm },
  mixins: [error],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      fetchLoading: false,
      fetchLoaded: false,
      periodicInterval: {},
      saveLoading: false,
      saved: false,
    }
  },
  mounted() {
    this.hideError()
    this.fetchPeriodicInterval(this.table)
  },
  methods: {
    async fetchPeriodicInterval(table) {
      this.fetchLoading = true

      try {
        const { data } = await EnterpriseDataSyncService(
          this.$client
        ).getPeriodicInterval(table.data_sync.id)
        this.periodicInterval = data
        this.fetchLoaded = true
      } catch (error) {
        this.handleError(error)
      } finally {
        this.fetchLoading = false
      }
    },
    async submitted(values) {
      this.saveLoading = true

      try {
        await EnterpriseDataSyncService(this.$client).updatePeriodicInterval(
          this.table.data_sync.id,
          values.interval,
          values.when
        )
        this.saved = true
      } catch (error) {
        this.handleError(error)
      } finally {
        this.saveLoading = false
      }
    },
  },
}
</script>
