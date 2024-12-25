<template>
  <Modal @show="setChosenType('')" @hidden="callCreateComponentHide()">
    <template #content>
      <div class="import-modal__header">
        <h2 class="import-modal__title">
          {{ $t('createTableModal.title') }}
        </h2>
      </div>

      <div class="control margin-bottom-2">
        <FormGroup
          :label="$t('createTableModal.importLabel')"
          small-label
          required
        >
          <ul class="choice-items margin-top-1">
            <li>
              <a
                class="choice-items__link"
                :class="{ active: chosenType === '' }"
                @click="setChosenType('')"
              >
                <i class="choice-items__icon iconoir-copy"></i>
                <span>{{ $t('createTableModal.newTable') }}</span>
                <i
                  v-if="chosenType === ''"
                  class="choice-items__icon-active iconoir-check-circle"
                ></i>
              </a>
            </li>
            <li v-for="instance in importerTypes" :key="instance.type">
              <a
                class="choice-items__link"
                :class="{ active: chosenType === instance.type }"
                @click="setChosenType(instance.type)"
              >
                <i class="choice-items__icon" :class="instance.iconClass"></i>
                <span> {{ instance.getName() }}</span>
                <i
                  v-if="chosenType === instance.type"
                  class="choice-items__icon-active iconoir-check-circle"
                ></i>
              </a>
            </li>
            <DataSyncTypeChoice
              v-for="instance in dataSyncTypes"
              :key="instance.type"
              :active="chosenType === instance.type"
              :data-sync-type="instance"
              :database="database"
              @selected="setChosenType(instance.type)"
            ></DataSyncTypeChoice>
          </ul>
        </FormGroup>
      </div>

      <CreateTable
        v-if="isImporter"
        ref="createComponent"
        :chosen-type="chosenType"
        :database="database"
        @hide="hide()"
      ></CreateTable>
      <CreateDataSync
        v-else
        ref="createComponent"
        :chosen-type="chosenType"
        :database="database"
        @hide="hide()"
      ></CreateDataSync>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import CreateTable from '@baserow/modules/database/components/table/CreateTable'
import CreateDataSync from '@baserow/modules/database/components/table/CreateDataSync'
import DataSyncTypeChoice from '@baserow/modules/database/components/dataSync/DataSyncTypeChoice.vue'

export default {
  name: 'CreateTableModal',
  components: { DataSyncTypeChoice, CreateTable, CreateDataSync },
  mixins: [modal],
  props: {
    database: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      chosenType: '',
    }
  },
  computed: {
    importerTypes() {
      return this.$registry.getAll('importer')
    },
    dataSyncTypes() {
      return this.$registry.getAll('dataSync')
    },
    isImporter() {
      return (
        this.chosenType === '' ||
        this.$registry.exists('importer', this.chosenType)
      )
    },
  },
  methods: {
    callCreateComponentHide() {
      this.$refs.createComponent.hide()
    },
    setChosenType(type) {
      if (type === this.chosenType && type !== '') {
        return
      }
      this.chosenType = type
    },
  },
}
</script>
