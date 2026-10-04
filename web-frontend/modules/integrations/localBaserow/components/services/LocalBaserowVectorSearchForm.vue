<template>
  <form @submit.prevent>
    <LocalBaserowServiceForm
      :application="application"
      :service-type="serviceType"
      :default-values="defaultValues"
      :databases="databases"
      :enable-view-picker="false"
      @values-changed="values = { ...values, ...$event }"
    ></LocalBaserowServiceForm>
    <FormGroup
      small-label
      :label="$t('localBaserowVectorSearchForm.fieldLabel')"
      :helper-text="$t('localBaserowVectorSearchForm.fieldHelper')"
      required
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="values.field_id"
        :disabled="fieldsLoading || vectorFields.length === 0"
        :placeholder="$t('localBaserowVectorSearchForm.fieldPlaceholder')"
      >
        <DropdownItem
          v-for="field in vectorFields"
          :key="field.id"
          :name="field.name"
          :value="field.id"
        ></DropdownItem>
      </Dropdown>
      <p
        v-if="!fieldsLoading && values.table_id && vectorFields.length === 0"
        class="control__helper-text"
      >
        {{ $t('localBaserowVectorSearchForm.noVectorFields') }}
      </p>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('localBaserowVectorSearchForm.includedFieldsLabel')"
      :helper-text="$t('localBaserowVectorSearchForm.includedFieldsHelper')"
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="values.included_field_ids"
        :disabled="fieldsLoading || tableFields.length === 0"
        :placeholder="
          $t('localBaserowVectorSearchForm.includedFieldsPlaceholder')
        "
        multiple
      >
        <DropdownItem
          v-for="field in tableFields"
          :key="field.id"
          :name="field.name"
          :value="field.id"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('localBaserowVectorSearchForm.maxResultsLabel')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        v-model="values.max_results"
        type="number"
        :min="1"
        :max="50"
      ></FormInput>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('localBaserowVectorSearchForm.searchQueryLabel')"
      :helper-text="$t('localBaserowVectorSearchForm.searchQueryHelper')"
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.search_query"
        :placeholder="$t('localBaserowVectorSearchForm.searchQueryPlaceholder')"
      />
    </FormGroup>
    <div v-if="fieldsLoading" class="loading-spinner"></div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm.vue'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'LocalBaserowVectorSearchForm',
  components: { LocalBaserowServiceForm, InjectedFormulaInput },
  mixins: [form, localBaserowService],
  data() {
    return {
      allowedValues: [
        'table_id',
        'field_id',
        'included_field_ids',
        'max_results',
        'search_query',
      ],
      values: {
        table_id: null,
        field_id: null,
        included_field_ids: [],
        max_results: 5,
        search_query: '',
      },
    }
  },
  computed: {
    // Only fields that keep embeddings can be searched.
    vectorFields() {
      return this.tableFields.filter((field) => field.vector_search_enabled)
    },
  },
}
</script>
