<template>
  <form @submit.prevent="submit">
    <p class="margin-bottom-2">
      {{ $t('importFromAirtable.airtableShareLinkDescription') }}
      <br /><br />
      {{ $t('importFromAirtable.airtableShareLinkBeta') }}
    </p>
    <FormGroup
      :label="$t('importFromAirtable.airtableShareLinkTitle')"
      :error="v$.airtableUrl.$error"
      small-label
      required
      class="margin-bottom-2"
    >
      <FormInput
        v-model="values.airtableUrl"
        :error="v$.airtableUrl.$error"
        :placeholder="$t('importFromAirtable.airtableShareLinkPaste')"
        size="large"
        @blur="v$.airtableUrl.$touch"
        @input="
          $emit('input', v$.airtableUrl.$invalid ? '' : v$.airtableUrl.$model)
        "
      ></FormInput>
      <template #error>
        {{ $t('importFromAirtable.linkError') }}
      </template>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'

export default {
  name: 'AirtableImportForm',
  mixins: [form],
  data() {
    return {
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      airtableUrl: '',
    })

    const rules = computed(() => ({
      airtableUrl: {
        valid(value) {
          const regex = /https:\/\/airtable.com\/[shr|app](.*)$/g
          return !!value.match(regex)
        },
        $lazy: true,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
