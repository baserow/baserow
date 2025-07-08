<template>
  <form :class="{ 'service-form--small': small }" @submit.prevent>
    <div>
      <div class="row">
        <div class="col col-12">
          <LocalBaserowServiceForm
            :application="application"
            :default-values="defaultValues"
            :enable-integration-picker="enableIntegrationPicker"
            @values-changed="values = { ...values, ...$event }"
          ></LocalBaserowServiceForm>
        </div>
      </div>
      <div v-if="values.integration_id && values.table_id" class="row">
        <div class="col col-6">
          <FormGroup
            small-label
            :label="$t('localBaserowGetRowForm.rowFieldLabel')"
            required
          >
            <InjectedFormulaInput
              v-model="values.row_id"
              :placeholder="$t('localBaserowGetRowForm.rowFieldPlaceHolder')"
            />
            <template #helper>
              {{ $t('localBaserowGetRowForm.rowFieldHelpText') }}
            </template>
          </FormGroup>
        </div>
      </div>
      <div v-if="!small && !fieldsLoading" class="row">
        <div class="col col-12">
          <Tabs>
            <Tab
              :title="$t('localBaserowGetRowForm.filterTabTitle')"
              class="service-form__condition-form-tab"
            >
              <LocalBaserowTableServiceConditionalForm
                v-if="values.table_id"
                v-model="values.filters"
                :fields="tableFields"
                :filter-type.sync="values.filter_type"
              />
              <p v-if="!values.table_id">
                {{ $t('localBaserowGetRowForm.noTableChosenForFiltering') }}
              </p>
            </Tab>
            <Tab
              :title="$t('localBaserowGetRowForm.searchTabTitle')"
              class="service-form__search-form-tab"
            >
              <FormGroup>
                <InjectedFormulaInput
                  v-model="values.search_query"
                  :placeholder="
                    $t('localBaserowGetRowForm.searchFieldPlaceHolder')
                  "
                />
              </FormGroup>
            </Tab>
          </Tabs>
        </div>
      </div>
      <div v-if="fieldsLoading" class="loading-spinner"></div>
    </div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

export default {
  components: {
    LocalBaserowServiceForm,
    InjectedFormulaInput,
    LocalBaserowTableServiceConditionalForm,
  },
  mixins: [form, localBaserowService],
  data() {
    return {
      allowedValues: [
        'table_id',
        'view_id',
        'row_id',
        'search_query',
        'filters',
        'filter_type',
      ],
      values: {
        table_id: null,
        view_id: null,
        row_id: '',
        search_query: '',
        filters: [],
        filter_type: 'AND',
      },
    }
  },
}
</script>
