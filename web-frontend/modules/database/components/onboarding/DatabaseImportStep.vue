<template>
  <div>
    <h1>{{ $t('databaseImportStep.title') }}</h1>
    <p>{{ $t('databaseImportStep.description') }}</p>

    <FormGroup
      :label="$t('databaseImportStep.tableNameLabel')"
      :error="v$.tableName.$error"
      small-label
      required
      class="margin-bottom-3"
    >
      <FormInput
        v-model="tableName"
        :placeholder="$t('databaseImportStep.tableNameLabel') + '...'"
        size="large"
        :error="v$.tableName.$error"
        @input="updateValue"
        @blur="v$.tableName.$touch"
      />

      <template #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <FormGroup class="margin-bottom-3">
      <ul class="choice-items">
        <li v-for="importerType in importerTypes" :key="importerType.type">
          <a
            class="choice-items__link"
            :class="{ active: importer === importerType.type }"
            @click="importer = importerType.type"
          >
            <i class="choice-items__icon" :class="importerType.iconClass"></i>
            <span> {{ importerType.getName() }}</span>
            <i
              v-if="importer === importerType.type"
              class="choice-items__icon-active iconoir-check-circle"
            ></i>
          </a>
        </li>
      </ul>
    </FormGroup>

    <div class="margin-bottom-2">
      <component
        :is="importerComponent"
        ref="importer"
        @data="onData($event)"
        @getData="onGetData($event)"
      />
    </div>

    <SimpleGrid
      v-if="dataLoaded"
      :rows="previewFileData"
      :fields="fileFields"
      :border="true"
    />
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import { uuid } from '@baserow/modules/core/utils/string'
import SimpleGrid from '@baserow/modules/database/components/view/grid/SimpleGrid'

export default {
  name: 'DatabaseImportStep',
  components: { SimpleGrid },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    const importers = Object.values(this.$registry.getAll('importer'))
    return {
      importer: importers[0].getType(),
      tableName: '',
      header: [],
      previewData: [],
      getData: null,
      dataLoaded: false,
    }
  },
  computed: {
    importerTypes() {
      return this.$registry.getAll('importer')
    },
    importerComponent() {
      return this.importer === ''
        ? null
        : this.$registry.get('importer', this.importer).getFormComponent()
    },
    fileFields() {
      return this.header.map((header, index) => ({
        type: 'text',
        name: header,
        id: uuid(),
        order: index,
      }))
    },
    previewFileData() {
      return this.previewData.map((row) => {
        const newRow = Object.fromEntries(
          this.fileFields.map((field, index) => [
            `field_${field.id}`,
            `${row[index]}`,
          ])
        )
        newRow.id = uuid()
        return newRow
      })
    },
  },
  mounted() {
    this.updateValue()
  },
  methods: {
    isValid() {
      return (
        !this.v$.$invalid &&
        this.v$.tableName.$dirty &&
        this.getData !== null &&
        this.dataLoaded
      )
    },
    updateValue() {
      const tableName = this.tableName
      const getData = this.getData
      const header = this.header
      this.$emit('update-data', { tableName, getData, header })
    },
    onData({ header, previewData }) {
      this.header = header
      this.previewData = previewData
      this.dataLoaded = header.length > 0 || previewData.length > 0
      this.updateValue()
    },
    onGetData(getData) {
      this.getData = getData
      this.updateValue()
    },
  },
  validations() {
    return {
      tableName: { required },
    }
  },
}
</script>
