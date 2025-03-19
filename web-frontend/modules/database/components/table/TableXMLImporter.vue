<template>
  <div>
    <div class="control">
      <template v-if="values.filename === ''">
        <label class="control__label control__label--small">{{
          $t('tableXMLImporter.fileLabel')
        }}</label>
        <div class="control__description">
          {{ $t('tableXMLImporter.fileDescription') }}
          <pre>
&lt;notes&gt;
  &lt;note&gt;
    &lt;to&gt;Tove&lt;/to&gt;
    &lt;from&gt;Jani&lt;/from&gt;
    &lt;heading&gt;Reminder&lt;/heading&gt;
    &lt;body&gt;Don't forget me this weekend!&lt;/body&gt;
  &lt;/note&gt;
  &lt;note&gt;
    &lt;heading&gt;Reminder&lt;/heading&gt;
    &lt;heading2&gt;Reminder2&lt;/heading2&gt;
    &lt;to&gt;Tove&lt;/to&gt;
    &lt;from&gt;Jani&lt;/from&gt;
    &lt;body&gt;Don't forget me this weekend!&lt;/body&gt;
  &lt;/note&gt;
&lt;/notes&gt;</pre
          >
        </div>
      </template>
      <div class="control__elements">
        <div class="file-upload margin-top-1">
          <input
            v-show="false"
            ref="file"
            type="file"
            accept=".xml"
            @change="select($event)"
          />
          <Button
            type="upload"
            size="large"
            class="file-upload__button"
            :loading="state !== null"
            icon="iconoir-cloud-upload"
            @click.prevent="$refs.file.click($event)"
          >
            {{ $t('tableXMLImporter.chooseButton') }}
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

        <div v-if="values.filename !== ''" class="control margin-top-1">
          <slot name="upsertMapping" />
        </div>
      </div>
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
import importer from '@baserow/modules/database/mixins/importer'
import { XMLParser } from '@baserow/modules/database/utils/xml'

export default {
  name: 'TableXMLImporter',
  mixins: [form, importer],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
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
        this.handleImporterError(
          this.$t('tableXMLImporter.limitFileSize', {
            limit: this.$config.BASEROW_MAX_IMPORT_FILE_SIZE_MB,
          })
        )
        this.values.filename = ''
      } else {
        this.resetImporterState()
        this.fileLoadingProgress = 0

        this.$emit('changed')
        this.state = 'loading'
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
        reader.readAsText(event.target.files[0], 'utf-8')
      }
    },
    async reload() {
      const fileName = this.values.filename
      this.resetImporterState()
      this.values.filename = fileName
      this.state = 'parsing'
      await this.$ensureRender()

      const xmlParser = new XMLParser()
      xmlParser.parse(this.rawData)

      await this.$ensureRender()
      xmlParser.loadXML(6)

      await this.$ensureRender()
      const [rawHeader, xmlData, errors] = xmlParser.transform()

      if (errors.length > 0) {
        this.handleImporterError(
          this.$t('tableXMLImporter.processingError', {
            errors: errors.join('\n'),
          })
        )
        return
      }

      if (xmlData.length === 0) {
        this.handleImporterError(this.$t('tableXMLImporter.emptyError'))
        return
      }

      const limit = this.$config.INITIAL_TABLE_DATA_LIMIT
      if (limit !== null && xmlData.length > limit) {
        this.handleImporterError(
          this.$t('tableXMLImporter.limitError', { limit })
        )
        return
      }

      const header = this.prepareHeader(rawHeader, xmlData)
      const getData = async () => {
        await this.$ensureRender()
        xmlParser.loadXML()

        await this.$ensureRender()
        const [, xmlData, errors] = xmlParser.transform()

        if (errors.length > 0) {
          throw new Error(errors)
        }

        return xmlData
      }
      this.state = null
      const previewData = this.getPreview(header, xmlData)

      this.$emit('getData', getData)
      this.$emit('data', { header, previewData })
    },
  },
}
</script>
