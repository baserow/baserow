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
          :value="syncedProperties.includes(property.key)"
          :disabled="property.unique_primary || updateLoading"
          @input=";[toggleVisibleField(property.key), (completed = false)]"
        >
          <i :class="getFieldTypeIconClass(property.field_type)"></i>
          {{ property.name }}</SwitchInput
        >
      </FormGroup>
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
    }
  },
  mounted() {
    this.hideError()
    this.syncedProperties = this.table.data_sync.synced_properties.map(
      (p) => p.key
    )
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
        },
        this.syncTableValue
      )
      if (!this.syncTableValue) {
        this.completed = true
      }
    },
  },
}
</script>
