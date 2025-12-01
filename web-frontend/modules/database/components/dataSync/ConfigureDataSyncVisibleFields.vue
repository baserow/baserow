<template>
  <div>
    <h2 class="box__title">{{ $t('configureDataSyncVisibleFields.title') }}</h2>
    <div v-if="loadingProperties">
      <div class="loading"></div>
    </div>
    <div v-if="!loadedProperties">
      <Error :error="error"></Error>
    </div>
    <div v-else-if="loadedProperties">
      <FormGroup small-label>
        <template #label>
          {{ $t('configureDataSyncVisibleFields.fields') }}</template
        >
        <SwitchInput
          v-for="property in orderedProperties"
          :key="property.key"
          class="margin-top-2"
          small
          :value="
            syncedProperties.includes(property.key) || autoAddNewProperties
          "
          :disabled="
            property.unique_primary || autoAddNewProperties || updateLoading
          "
          @input=";[toggleVisibleField(property.key), (completed = false)]"
        >
          <i :class="getFieldTypeIconClass(property.field_type)"></i>
          {{ property.name }}</SwitchInput
        >
      </FormGroup>
      <FormGroup
        small-label
        class="margin-top-2"
        :helper-text="$t('createDataSync.autoAddHelper')"
      >
        <SwitchInput
          v-model="autoAddNewProperties"
          class="margin-top-2"
          small
          :disabled="updateLoading"
          @input="completed = false"
        >
          {{ $t('createDataSync.autoAddLabel') }}</SwitchInput
        >
      </FormGroup>
      <FormGroup
        v-if="twoWaySyncStrategy"
        small-label
        class="margin-top-2"
        :helper-text="twoWaySyncStrategy.getDescription()"
      >
        <SwitchInput
          v-model="twoWayDataSync"
          class="margin-top-2"
          small
          :disabled="updateLoading || isTwoWaySyncDeactivated"
          @input="completed = false"
          @click="clickTwoWaySync"
        >
          {{ $t('createDataSync.twoWaySyncLabel') }}
          <i v-if="isTwoWaySyncDeactivated" class="iconoir-lock"></i>
        </SwitchInput>
      </FormGroup>
      <component
        :is="twoWaySyncDeactivatedModal[0]"
        v-if="twoWaySyncDeactivatedModal !== null"
        ref="twoWaySyncDeactivatedModal"
        v-bind="twoWaySyncDeactivatedModal[1]"
      ></component>
      <Error :error="error"></Error>
      <div class="modal-progress__actions margin-top-2">
        <ProgressBar
          v-if="jobIsRunning || jobHasSucceeded"
          :value="job.progress_percentage"
          :status="jobHumanReadableState"
        />
        <div class="align-right">
          <div class="flex">
            <Button
              v-if="completed"
              tag="a"
              type="secondary"
              size="large"
              @click="$emit('hide')"
              >{{ $t('action.hide') }}</Button
            >
            <template v-if="!completed">
              <Checkbox
                v-model="syncTableValue"
                :disabled="updateLoading || jobIsRunning"
                >{{ $t('configureDataSyncVisibleFields.syncTable') }}</Checkbox
              >
              <Button
                type="primary"
                size="large"
                :loading="updateLoading || jobIsRunning"
                :disabled="updateLoading || jobIsRunning"
                @click="submit"
              >
                {{ $t('action.save') }}
              </Button>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import dataSync from '@baserow/modules/database/mixins/dataSync'

export default {
  name: 'ConfigureDataSyncVisibleFields',
  mixins: [dataSync],
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
      completed: false,
      syncTableValue: true,
      autoAddNewProperties: false,
      twoWayDataSync: false,
    }
  },
  computed: {
    dataSyncType() {
      return this.$registry.get('dataSync', this.table.data_sync.type)
    },
    twoWaySyncStrategy() {
      const strategy = this.dataSyncType.getTwoWayDataSyncStrategy()
      if (!strategy) {
        return null
      }

      return this.$registry.get('twoWaySyncStrategy', strategy)
    },
    isTwoWaySyncDeactivated() {
      if (!this.twoWaySyncStrategy) {
        return true
      }
      return this.twoWaySyncStrategy.isDeactivated(this.database.workspace.id)
    },
    twoWaySyncDeactivatedModal() {
      if (!this.twoWaySyncStrategy) {
        return null
      }
      return this.twoWaySyncStrategy.getDeactivatedClickModal()
    },
  },
  mounted() {
    this.hideError()
    this.syncedProperties = this.table.data_sync.synced_properties.map(
      (p) => p.key
    )
    this.autoAddNewProperties = this.table.data_sync.auto_add_new_properties
    this.twoWayDataSync = this.isTwoWaySyncDeactivated
      ? false
      : this.table.data_sync.two_way_sync
    this.fetchExistingProperties(this.table)
  },
  methods: {
    onJobDone() {
      this.completed = true
    },
    async submit() {
      await this.update(
        this.table,
        {
          synced_properties: this.syncedProperties,
          auto_add_new_properties: this.autoAddNewProperties,
          two_way_sync: this.twoWayDataSync,
        },
        this.syncTableValue
      )
      if (!this.syncTableValue) {
        this.completed = true
      }
    },
    clickTwoWaySync() {
      if (this.isTwoWaySyncDeactivated) {
        this.$refs.twoWaySyncDeactivatedModal.show()
      }
    },
  },
}
</script>
