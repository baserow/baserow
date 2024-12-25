<template>
  <form @submit.prevent>
    <div>
      <div class="row">
        <div class="col col-12">
          <LocalBaserowTableSelector
            v-model="fakeTableId"
            class="local-baserow-get-row-form__table-selector"
            :databases="databases"
            :view-id.sync="values.view_id"
          ></LocalBaserowTableSelector>
        </div>
      </div>
      <div class="row">
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
      <div class="row">
        <div class="col col-12">
          <Tabs>
            <Tab
              :title="$t('localBaserowGetRowForm.filterTabTitle')"
              class="data-source-form__condition-form-tab"
            >
              <LocalBaserowTableServiceConditionalForm
                v-if="values.table_id"
                v-model="dataSourceFilters"
                :fields="tableFields"
                :filter-type.sync="values.filter_type"
              />
              <p v-if="!values.table_id">
                {{ $t('localBaserowGetRowForm.noTableChosenForFiltering') }}
              </p>
            </Tab>
            <Tab
              :title="$t('localBaserowGetRowForm.searchTabTitle')"
              class="data-source-form__search-form-tab"
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
    </div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowTableSelector from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableSelector'
import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'

export default {
  components: {
    InjectedFormulaInput,
    LocalBaserowTableSelector,
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
      tableLoading: false,
    }
  },
}
</script>
