<template>
  <div>
    <FormGroup
      :label="$t('tablePasteImporter.pasteLabel')"
      small-label
      :error="v$.content.$error"
      class="margin-bottom-2"
      required
      :helper-text="$t('tablePasteImporter.pasteDescription')"
    >
      <FormTextarea
        v-model="v$.content.$model"
        :rows="10"
        @input="changed($event)"
      ></FormTextarea>

      <template #error>{{ $t('error.requiredField') }}</template>
    </FormGroup>

    <FormGroup
      :label="$t('tablePasteImporter.firstRowHeader')"
      small-label
      class="margin-bottom-2"
      required
    >
      <Checkbox v-model="firstRowHeader" @input="reload()">
        {{ $t('common.yes') }}
      </Checkbox>
    </FormGroup>

    <Alert v-if="error !== ''" type="error">
      <template #title> {{ $t('common.wrong') }} </template>
      {{ error }}
    </Alert>
  </div>
</template>

<script>
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'

import form from '@baserow/modules/core/mixins/form'
import importer from '@baserow/modules/database/mixins/importer'

export default {
  name: 'TablePasteImporter',
  mixins: [form, importer],
  data() {
    return {
      firstRowHeader: true,
      v$: null,
      values: null,
    }
  },
  created() {
    const values = reactive({
      content: '',
    })

    const rules = computed(() => ({
      content: {
        required,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    changed(content) {
      console.log('changed', content)
      this.$emit('changed')
      console.log('changed2', content)
      this.resetImporterState()
      this.values.content = content
      this.reload()
    },
    async reload() {
      if (this.values.content === '') {
        this.resetImporterState()
        return
      }
      const limit = this.$config.INITIAL_TABLE_DATA_LIMIT
      const count = this.values.content.split(/\r\n|\r|\n/).length
      if (limit !== null && count > limit) {
        this.handleImporterError(
          this.$t('tablePasteImporter.limitError', {
            limit,
          })
        )
        return
      }
      this.state = 'parsing'
      await this.$ensureRender()
      this.$papa.parse(this.values.content, {
        delimiter: '\t',
        complete: (parsedResult) => {
          // If parsed successfully and it is not empty then the initial data can be
          // prepared for creating the table. We store the data stringified because it
          // doesn't need to be reactive.

          let data
          let header
          if (this.firstRowHeader) {
            const [rawHeader, ...rest] = parsedResult.data
            data = rest
            header = this.prepareHeader(rawHeader, data)
          } else {
            data = parsedResult.data
            header = this.prepareHeader([], data)
          }
          const getData = () => {
            return new Promise((resolve) => {
              resolve(data)
            })
          }
          this.error = ''
          this.state = null
          const previewData = this.getPreview(header, data)
          this.$emit('getData', getData)

          this.$emit('data', { header, previewData })
        },
        error(error) {
          // Papa parse has resulted in an error which we need to display to the user.
          // All previously loaded data will be removed.
          this.handleImporterError(error.errors[0].message)
        },
      })
    },
  },
}
</script>
