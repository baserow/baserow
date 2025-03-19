<template>
  <div>
    <div class="control">
      <template v-if="values.filename === ''">
        <label class="control__label control__label--small">{{
          $t('tableJSONImporter.fileLabel')
        }}</label>
        <div class="control__description">
          {{ $t('tableJSONImporter.fileDescription') }}
          <pre>
[
  {
    "to": "Tove",
    "from": "Jani",
    "heading": "Reminder",
    "body": "Don't forget me this weekend!"
  },
  {
    "to": "Bram",
    "from": "Nigel",
    "heading": "Reminder",
    "body": "Don't forget about the export feature this week"
  }
]
        </pre
          >
        </div>
      </template>
      <div class="control__elements">
        <div class="file-upload">
          <input
            v-show="false"
            ref="file"
            type="file"
            accept=".json"
            @change="select($event)"
          />
          <Button
            type="upload"
            size="large"
            icon="iconoir-cloud-upload"
            class="file-upload__button"
            :loading="state !== null"
            @click.prevent="$refs.file.click($event)"
          >
            {{ $t('tableJSONImporter.chooseButton') }}
          </Button>
          <div v-if="state === null" class="file-upload__file">
            {{ values.filename }}
          </div>
          <template v-else>
            <ProgressBar
              :value="fileLoadingProgress"
              :show-value="state === 'loading'"
              :status="
                state === 'loading' ? $t('importer.loading') : stateTitle
              "
            />
          </template>
        </div>
        <div v-if="v$.values.filename.$error" class="error">
          {{ v$.values.filename.$errors[0]?.$message }}
        </div>
      </div>
    </div>
    <div v-if="values.filename !== ''" class="control margin-top-2">
      <label class="control__label control__label--small">{{
        $t('tableJSONImporter.encodingLabel')
      }}</label>
      <div class="control__elements">
        <CharsetDropdown
          v-model="encoding"
          :disabled="isDisabled"
          @input="reload()"
        ></CharsetDropdown>
      </div>
    </div>

    <div v-if="values.filename !== ''" class="control margin-top-2">
      <slot name="upsertMapping" />
    </div>

    <Alert v-if="error !== ''" type="error">
      <template #title> {{ $t('common.wrong') }} </template>
      {{ error }}
    </Alert>
  </div>
</template>

<script>
import { required, helpers } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'

import form from '@baserow/modules/core/mixins/form'
import CharsetDropdown from '@baserow/modules/core/components/helpers/CharsetDropdown'
import importer from '@baserow/modules/database/mixins/importer'

export default {
  name: 'TableCSVImporter',
  components: { CharsetDropdown },
  mixins: [form, importer],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      encoding: 'utf-8',
      values: {
        filename: '',
      },
      rawData: null,
    }
  },
  validations() {
    return {
      values: {
        filename: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
  computed: {
    isDisabled() {
      return this.disabled || this.state !== null
    },
  },

  methods: {
    /**
     * Method that is called when a file has been chosen. It will check if the file is
     * not larger than 15MB. Otherwise it will take a long time and possibly a crash
     * if so many entries have to be loaded into memory. If the file is valid, the
     * contents will be loaded into memory and the reload method will be called which
     * parses the content.
     */
    select(event) {
      if (event.target.files.length === 0) {
        return
      }

      const file = event.target.files[0]

      const maxSize =
        parseInt(this.$config.BASEROW_MAX_IMPORT_FILE_SIZE_MB, 10) * 1024 * 1024

      if (file.size > maxSize) {
        this.values.filename = ''
        this.handleImporterError(
          this.$t('tableJSONImporter.limitFileSize', {
            limit: this.$config.BASEROW_MAX_IMPORT_FILE_SIZE_MB,
          })
        )
      } else {
        this.state = 'loading'
        this.$emit('changed')
        this.values.filename = file.name
        const reader = new FileReader()
        reader.addEventListener('progress', (event) => {
          this.fileLoadingProgress = (event.loaded / event.total) * 100
        })
        reader.addEventListener('load', (event) => {
          this.rawData = event.target.result
          this.fileLoadingProgress = 100
          this.reload()
        })
        reader.readAsArrayBuffer(event.target.files[0])
      }
    },
    async reload() {
      let json
      const fileName = this.values.filename
      this.resetImporterState()
      this.values.filename = fileName

      try {
        const decoder = new TextDecoder(this.encoding)
        this.state = 'parsing'
        await this.$ensureRender()
        const decoded = decoder.decode(this.rawData)

        await this.$ensureRender()
        json = JSON.parse(decoded)
      } catch (error) {
        this.handleImporterError(
          this.$t('tableJSONImporter.processingError', {
            error: error.message,
          })
        )
        return
      }

      if (json.length === 0) {
        this.handleImporterError(this.$t('tableJSONImporter.emptyError'))
        return
      }

      if (!Array.isArray(json)) {
        this.handleImporterError(this.$t('tableJSONImporter.arrayError'))
        return
      }

      const limit = this.$config.INITIAL_TABLE_DATA_LIMIT
      if (limit !== null && json.length > limit - 1) {
        this.handleImporterError(
          this.$t('tableJSONImporter.limitError', {
            limit,
          })
        )
        return
      }

      const header = []
      const data = []

      await this.$ensureRender()

      json.forEach((entry) => {
        const keys = Object.keys(entry)
        const row = []

        keys.forEach((key) => {
          if (!header.includes(key)) {
            header.push(key)
          }
        })

        header.forEach((key) => {
          const exists = Object.prototype.hasOwnProperty.call(entry, key)
          const value = exists ? entry[key] : ''
          row.push(value)
        })

        data.push(row)
      })

      const preparedHeader = this.prepareHeader(header, data)
      const getData = () => {
        return data
      }
      this.state = null
      const previewData = this.getPreview(header, data)

      this.$emit('getData', getData)
      this.$emit('data', { header: preparedHeader, previewData })
    },
  },
}
</script>
