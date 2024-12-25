<template>
  <form @submit.prevent>
    <div class="row">
      <div class="col col-12">
        <LocalBaserowTableSelector
          v-model="fakeTableId"
          :databases="databases"
          :view-id.sync="values.view_id"
        ></LocalBaserowTableSelector>
      </div>
    </div>
    <div class="row">
      <div class="col col-12">
        <Tabs>
          <Tab
            :title="$t('localBaserowListRowsForm.filterTabTitle')"
            class="data-source-form__condition-form-tab"
          >
            <LocalBaserowTableServiceConditionalForm
              v-if="values.table_id"
              v-model="dataSourceFilters"
              :fields="tableFields"
              :filter-type.sync="values.filter_type"
            >
            </LocalBaserowTableServiceConditionalForm>
            <p v-if="!values.table_id">
              {{ $t('localBaserowListRowsForm.noTableChosenForFiltering') }}
            </p>
          </Tab>
          <Tab
            :title="$t('localBaserowListRowsForm.sortTabTitle')"
            class="data-source-form__sort-form-tab"
          >
            <LocalBaserowTableServiceSortForm
              v-if="values.table_id"
              v-model="dataSourceSortings"
              :fields="tableFields"
            ></LocalBaserowTableServiceSortForm>
            <p v-if="!values.table_id">
              {{ $t('localBaserowListRowsForm.noTableChosenForSorting') }}
            </p>
          </Tab>
          <Tab
            :title="$t('localBaserowListRowsForm.searchTabTitle')"
            class="data-source-form__search-form-tab"
          >
            <InjectedFormulaInput
              v-model="values.search_query"
              small
              :placeholder="
                $t('localBaserowListRowsForm.searchFieldPlaceHolder')
              "
            />
          </Tab>
        </Tabs>
      </div>
    </div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowTableSelector from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableSelector'
import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import LocalBaserowTableServiceSortForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceSortForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'

export default {
  components: {
    InjectedFormulaInput,
    LocalBaserowTableSelector,
    LocalBaserowTableServiceSortForm,
    LocalBaserowTableServiceConditionalForm,
  },
  mixins: [form, localBaserowService],
  data() {
    return {
      allowedValues: [
        'table_id',
        'view_id',
        'search_query',
        'filters',
        'filter_type',
        'sortings',
      ],
      values: {
        table_id: null,
        view_id: null,
        search_query: '',
        filters: [],
        sortings: [],
        filter_type: 'AND',
      },
      tableLoading: false,
    }
  },
}
</script>
