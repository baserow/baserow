<template>
  <form @submit.prevent>
    <FormGroup small-label>
      <template #label
        ><label :for="sourceId">{{ $t('htmlElement.source') }}</label></template
      >
      <FormTextarea
        :id="sourceId"
        v-model="values.html"
        :rows="8"
        :aria-describedby="sourceId + '-help'"
      />
      <template #helper>
        <span :id="sourceId + '-help'">{{ $t('htmlElement.sourceHelp') }}</span>
      </template>
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
    return { values: { html: '' }, allowedValues: ['html'] }
  },
  setup() {
    return { sourceId: useId() }
  },
}
</script>
