<template>
  <div>
    <h2 class="box__title">
      {{ $t('configureDataSyncPeriodicInterval.title') }}
    </h2>
    <div v-if="hasPermissions">
      <div v-if="fetchLoading">
        <div class="loading"></div>
      </div>
      <div v-if="!fetchLoaded">
        <Error :error="error"></Error>
      </div>
      <div v-else-if="fetchLoaded">
        <Error :error="error"></Error>
        <Alert
          v-if="periodicInterval.automatically_deactivated"
          type="info-primary"
        >
          <template #title>{{
            $t('configureDataSyncPeriodicInterval.deactivatedTitle')
          }}</template>
          <p>{{ $t('configureDataSyncPeriodicInterval.deactivatedText') }}</p>
          <template #actions>
            <Button
              type="primary"
              size="small"
              :loading="saveLoading"
              @click="activate"
              >{{ $t('configureDataSyncPeriodicInterval.activate') }}</Button
            >
          </template>
        </Alert>
        <DataSyncPeriodicIntervalForm
          v-if="!periodicInterval.automatically_deactivated"
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
    <div v-else>
      <div class="placeholder">
        <div class="placeholder__icon">
          <i class="iconoir-timer"></i>
        </div>
        <p class="placeholder__content">
          {{ $t('configureDataSyncPeriodicInterval.enterprise') }}
        </p>
        <div class="placeholder__action">
          <Button
            type="primary"
            icon="iconoir-no-lock"
            @click="$refs.paidFeaturesModal.show()"
          >
            {{ $t('configureDataSyncPeriodicInterval.more') }}
          </Button>
        </div>
      </div>
      <PaidFeaturesModal
        ref="paidFeaturesModal"
        initial-selected-type="data_sync"
        :workspace="database.workspace"
      ></PaidFeaturesModal>
    </div>
  </div>
</template>

<script>
import EnterpriseDataSyncService from '@baserow_enterprise/services/dataSync'
import error from '@baserow/modules/core/mixins/error'
import DataSyncPeriodicIntervalForm from '@baserow_enterprise/components/dataSync/DataSyncPeriodicIntervalForm'
import EnterpriseFeatures from '@baserow_enterprise/features'
import { clone } from '@baserow/modules/core/utils/object'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'ConfigureDataSyncPeriodicInterval',
  components: { PaidFeaturesModal, DataSyncPeriodicIntervalForm },
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
  computed: {
    hasPermissions() {
      return this.$hasFeature(
        EnterpriseFeatures.DATA_SYNC,
        this.database.workspace.id
      )
    },
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
    async activate() {
      const values = clone(this.periodicInterval)
      values.automatically_deactivated = false
      // Updating the periodic interval sets automatically_disabled = false.
      await this.submitted(values)
      this.periodicInterval = values
      this.saved = false
    },
    async submitted(values) {
      this.hideError()
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
