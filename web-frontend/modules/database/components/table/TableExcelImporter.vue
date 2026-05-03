<template>
  <div>
    <div class="control margin-bottom-3">
      <template v-if="values.filename === ''">
        <label class="control__label control__label--small">{{
          $t('tableExcelImporter.chooseFileLabel')
        }}</label>
        <div class="control__description">
          {{ $t('tableExcelImporter.chooseFileDescription') }}
        </div>
      </template>
      <div class="control__elements">
        <div class="file-upload">
          <input
            v-show="false"
            ref="file"
            type="file"
            accept=".xlsx,.xls,.ods"
            @change="select($event)"
          />
          <Button
            tag="a"
            type="upload"
            size="large"
            :loading="state !== null"
            :disabled="disabled"
            icon="iconoir-cloud-upload"
            class="file-upload__button"
            @click.prevent="!disabled && $refs.file.click($event)"
          >
            {{ $t('tableExcelImporter.chooseFile') }}
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
    <div v-if="values.filename" class="row">
      <div class="col col-8">
        <div class="control">
          <label class="control__label control__label--small">{{
            $t('tableExcelImporter.sheet')
          }}</label>
          <div class="control__elements">
            <Dropdown
              v-model="selectedSheet"
              :disabled="isDisabled || sheetNames.length === 0"
              @input="reload()"
            >
              <DropdownItem
                v-for="name in sheetNames"
                :key="name"
                :name="name"
                :value="name"
              />
            </Dropdown>
          </div>
        </div>
      </div>
      <div class="col col-4">
        <div class="control">
          <label class="control__label control__label--small">{{
            $t('tableExcelImporter.firstRowHeader')
          }}</label>
          <div class="control__elements">
            <Checkbox
              v-model="firstRowHeader"
              :disabled="isDisabled"
              @input="reloadPreview()"
              >{{ $t('common.yes') }}</Checkbox
            >
          </div>
        </div>
      </div>
    </div>
    <div v-if="values.filename && error === ''" class="row">
      <div class="col col-8 margin-top-1"><slot name="upsertMapping" /></div>
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
import { useRuntimeConfig } from '#imports'

import form from '@baserow/modules/core/mixins/form'
import importer from '@baserow/modules/database/mixins/importer'
import { ExcelParser } from '@baserow/modules/database/utils/excel'

// Number of rows fetched for the preview parse. Kept small so the initial
// parse is fast even on large workbooks, but generous enough to absorb a
// header row plus the importer's preview window with room for sparse files
// (leading blank rows etc.).
const PREVIEW_ROW_LIMIT = 50

export default {
  name: 'TableExcelImporter',
  mixins: [form, importer],
  emits: ['changed', 'data', 'getData'],
  setup() {
    const config = useRuntimeConfig()
    return { v$: useVuelidate({ $lazy: true }), config }
  },
  data() {
    return {
      firstRowHeader: true,
      rawData: null,
      parser: null,
      sheetNames: [],
      selectedSheet: '',
      parsedData: null,
      values: {
        filename: '',
      },
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
     * Method that is called when a file has been chosen. It will check if the file
     * is not larger than the configured limit. Otherwise the file is read into
     * memory and reload is called which parses the workbook and prepares the
     * preview.
     */
    select(event) {
      if (event.target.files.length === 0) {
        return
      }

      const file = event.target.files[0]
      const maxSize =
        parseInt(this.config.public.baserowMaxImportFileSizeMb, 10) *
        1024 *
        1024

      if (file.size > maxSize) {
        this.values.filename = ''
        this.handleImporterError(
          this.$t('tableExcelImporter.limitFileSize', {
            limit: this.config.public.baserowMaxImportFileSizeMb,
          })
        )
        return
      }

      this.resetImporterState()
      this.fileLoadingProgress = 0
      this.parser = null
      this.sheetNames = []
      this.selectedSheet = ''
      this.parsedData = null

      this.$emit('changed')
      this.values.filename = file.name
      this.state = 'loading'
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
    },
    /**
     * Parses the raw workbook data with SheetJS and prepares the preview for
     * the currently selected sheet. To keep the initial parse fast even on
     * large workbooks we only read the first `PREVIEW_ROW_LIMIT` rows here;
     * the full file is re-parsed on demand from `getData()` when the user
     * actually submits the import. Cell values are read as formatted text so
     * that dates, numbers and booleans are imported the way the user sees
     * them in their spreadsheet.
     */
    async reload() {
      const fileName = this.values.filename
      const previousSheet = this.selectedSheet
      this.resetImporterState()
      this.values.filename = fileName

      this.state = 'parsing'
      await this.$ensureRender()

      try {
        if (this.parser === null) {
          const parser = new ExcelParser()
          this.sheetNames = await parser.parse(this.rawData, {
            previewRows: PREVIEW_ROW_LIMIT,
          })
          if (this.sheetNames.length === 0) {
            this.handleImporterError(this.$t('tableExcelImporter.emptyError'))
            return
          }
          this.parser = parser
          this.selectedSheet =
            previousSheet && this.sheetNames.includes(previousSheet)
              ? previousSheet
              : this.sheetNames[0]
        }
      } catch (error) {
        this.handleImporterError(
          this.$t('tableExcelImporter.processingError', {
            error: error.message,
          })
        )
        return
      }

      await this.$ensureRender()

      let rows
      let totalRowCount
      try {
        rows = this.parser.getSheetRows(this.selectedSheet)
        totalRowCount = this.parser.getTotalRowCount(this.selectedSheet)
      } catch (error) {
        this.handleSheetError(
          this.$t('tableExcelImporter.processingError', {
            error: error.message,
          })
        )
        return
      }

      if (rows.length === 0) {
        this.handleSheetError(this.$t('tableExcelImporter.emptySheetError'))
        return
      }

      // Limit check uses the sheet's full range (preserved on `!fullref`
      // through the partial parse) so we can reject oversized files before
      // the user fills out the rest of the form.
      const limit = parseInt(this.config.public.initialTableDataLimit, 10)
      if (limit && totalRowCount > limit) {
        this.handleSheetError(
          this.$t('tableExcelImporter.limitError', { limit })
        )
        return
      }

      this.parsedData = rows
      this.reloadPreview()
      this.state = null

      const getData = async () => {
        // Re-parse the whole file now that the user is committing to import.
        // The progress bar in the parent submit flow covers the wait.
        const fullParser = new ExcelParser()
        await fullParser.parse(this.rawData)
        const allRows = fullParser.getSheetRows(this.selectedSheet)
        if (this.firstRowHeader) {
          const [, ...data] = allRows
          return data
        }
        return allRows
      }
      this.$emit('getData', getData)
    },
    /**
     * Handle an error that's specific to the currently selected sheet (empty
     * sheet, oversized sheet, sheet decoding failure). Unlike
     * `handleImporterError` from the importer mixin, this preserves
     * `values.filename` and the cached workbook/parser state so the user can
     * recover by switching to a different sheet via the sheet picker, rather
     * than being forced to re-upload the file.
     */
    handleSheetError(message) {
      this.state = null
      this.fileLoadingProgress = 0
      this.parsedData = null
      this.error = message
      this.$emit('getData', null)
      this.$emit('data', { header: [], previewData: [] })
    },
    /**
     * Reload the preview without re-parsing the workbook.
     */
    reloadPreview() {
      if (!Array.isArray(this.parsedData) || this.parsedData.length === 0) {
        return
      }

      const [rawHeader, ...rawData] = this.firstRowHeader
        ? this.parsedData
        : [[], ...this.parsedData]

      const header = this.prepareHeader(rawHeader, rawData)
      const previewData = this.getPreview(header, rawData)
      this.$emit('data', { header, previewData })
    },
  },
}
</script>
