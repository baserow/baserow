<template>
  <form @submit.prevent>
    <FormGroup small-label :error="invalidHTML">
      <template #label
        ><label :for="sourceId">{{ $t('htmlElement.source') }}</label></template
      >
      <FormTextarea
        :id="sourceId"
        v-model="values.html"
        :rows="8"
        :error="invalidHTML"
        :aria-invalid="invalidHTML"
        :aria-describedby="
          invalidHTML
            ? sourceId + '-error ' + sourceId + '-help'
            : sourceId + '-help'
        "
      />
      <template #helper>
        <span :id="sourceId + '-help'">{{ $t('htmlElement.sourceHelp') }}</span>
      </template>
      <template #error
        ><span :id="sourceId + '-error'" role="alert">{{
          $t('htmlElement.invalid')
        }}</span></template
      >
    </FormGroup>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import form from '@baserow/modules/core/mixins/form'
import { parseStaticHTML } from '@baserow_enterprise/builder/staticHtml'
import { useId } from 'vue'

export default {
  name: 'BuilderHTMLElementForm',
  mixins: [elementForm],
  data() {
    return {
      values: { html: '' },
      allowedValues: ['html'],
      serverInvalidHTML: false,
    }
  },
  setup() {
    return { sourceId: useId() }
  },
  computed: {
    localInvalidHTML() {
      return (
        typeof document !== 'undefined' &&
        parseStaticHTML(this.values.html) === null
      )
    },
    invalidHTML() {
      return this.localInvalidHTML || this.serverInvalidHTML
    },
  },
  watch: {
    'values.html'() {
      this.serverInvalidHTML = false
    },
  },
  methods: {
    isFormValid(deep = false) {
      return !this.localInvalidHTML && form.methods.isFormValid.call(this, deep)
    },
    handleErrorByForm(error) {
      if (
        error.response?.data?.detail?.html?.some(
          ({ code }) => code === 'invalid_html'
        )
      ) {
        this.serverInvalidHTML = true
        error.handler.handled()
        return true
      }
      return false
    },
  },
}
</script>
