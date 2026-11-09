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
        :aria-describedby="invalidHTML ? sourceId + '-error' : undefined"
      />
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
import { useId } from 'vue'

export default {
  name: 'BuilderHTMLElementForm',
  mixins: [elementForm],
  data() {
    return { values: { html: '' }, allowedValues: ['html'], invalidHTML: false }
  },
  setup() {
    return { sourceId: useId() }
  },
  watch: {
    'values.html'() {
      this.invalidHTML = false
    },
  },
  methods: {
    handleErrorByForm(error) {
      if (
        error.response?.data?.detail?.html?.some(
          ({ code }) => code === 'invalid_html'
        )
      ) {
        this.invalidHTML = true
        error.handler.handled()
        return true
      }
      return false
    },
  },
}
</script>
