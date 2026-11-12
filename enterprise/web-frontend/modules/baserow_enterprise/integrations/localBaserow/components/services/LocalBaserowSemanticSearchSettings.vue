<template>
  <div>
    <FormGroup
      small-label
      :label="$t('localBaserowSemanticSearchForm.searchQuery')"
      :helper-text="$t('localBaserowSemanticSearchForm.searchQueryHelper')"
      :help-icon-tooltip="
        $t('localBaserowSemanticSearchForm.searchQueryTooltip')
      "
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.search_query"
        :placeholder="
          $t('localBaserowSemanticSearchForm.searchQueryPlaceholder')
        "
      />
    </FormGroup>

    <Alert
      v-if="searchFieldOptions.length === 0"
      type="info-neutral"
      class="margin-bottom-2"
    >
      <template #title>
        {{ $t('localBaserowSemanticSearchForm.noFieldsTitle') }}
      </template>
      <p>{{ $t('localBaserowSemanticSearchForm.noFields') }}</p>
    </Alert>
    <FormRow class="margin-bottom-2">
      <FormGroup
        v-if="searchFieldOptions.length > 0"
        small-label
        :label="$t('localBaserowSemanticSearchForm.fields')"
        :helper-text="$t('localBaserowSemanticSearchForm.fieldsHelper')"
        :error-message="
          searchFieldsGone
            ? $t('localBaserowSemanticSearchForm.searchFieldsGone')
            : null
        "
      >
        <Dropdown
          :model-value="values.search_field_ids"
          :placeholder="$t('localBaserowSemanticSearchForm.fieldsPlaceholder')"
          multiple
          @update:model-value="
            emit(
              'choose-fields',
              'search_field_ids',
              'search_all_fields',
              $event
            )
          "
        >
          <DropdownItem
            v-for="field in searchFieldOptions"
            :key="field.id"
            :name="field.name"
            :value="field.id"
          ></DropdownItem>
        </Dropdown>
      </FormGroup>

      <FormGroup
        small-label
        :label="$t('localBaserowSemanticSearchForm.includedFields')"
        :helper-text="$t('localBaserowSemanticSearchForm.includedFieldsHelper')"
        :error-message="
          includedFieldsGone
            ? $t('localBaserowSemanticSearchForm.includedFieldsGone')
            : null
        "
      >
        <Dropdown
          :model-value="values.included_field_ids"
          :placeholder="
            $t('localBaserowSemanticSearchForm.includedFieldsPlaceholder')
          "
          multiple
          @update:model-value="
            emit(
              'choose-fields',
              'included_field_ids',
              'include_all_fields',
              $event
            )
          "
        >
          <DropdownItem
            v-for="field in tableFields"
            :key="field.id"
            :name="field.name"
            :value="field.id"
          ></DropdownItem>
        </Dropdown>
      </FormGroup>
    </FormRow>

    <FormRow class="margin-bottom-2">
      <FormGroup
        small-label
        :label="$t('localBaserowSemanticSearchForm.maxResults')"
        :helper-text="
          maxResults
            ? $t('localBaserowSemanticSearchForm.maxResultsHelper', {
                max: maxResults,
              })
            : null
        "
        required
        :error-message="maxResultsError"
      >
        <FormInput
          v-model="v$.values.max_results.$model"
          type="number"
          :to-value="(value) => parseInt(value)"
        />
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('localBaserowSemanticSearchForm.minSimilarity')"
        :helper-text="$t('localBaserowSemanticSearchForm.minSimilarityHelper')"
        :help-icon-tooltip="
          $t('localBaserowSemanticSearchForm.minSimilarityTooltip')
        "
        :error-message="minSimilarityError"
      >
        <FormInput
          v-model="v$.values.min_similarity.$model"
          type="number"
          :placeholder="
            $t('localBaserowSemanticSearchForm.minSimilarityPlaceholder')
          "
          :to-value="(value) => (value === '' ? null : parseFloat(value))"
        />
      </FormGroup>
    </FormRow>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

// The values and validation belong to the service form, which shows these
// settings in a tab, or below the refinements when it's small.
const props = defineProps({
  values: { type: Object, required: true },
  tableFields: { type: Array, required: true },
  v$: { type: Object, required: true },
  maxResults: { type: Number, default: null },
  maxResultsError: { type: String, default: null },
  minSimilarityError: { type: String, default: null },
})

const emit = defineEmits(['choose-fields'])

const semanticSearchFields = computed(() =>
  props.tableFields.filter((field) => field.semantic_search_enabled)
)

// A chosen field of which semantic search was disabled stays chosen, so it can be
// deselected.
const searchFieldOptions = computed(() =>
  props.tableFields.filter(
    (field) =>
      field.semantic_search_enabled ||
      props.values.search_field_ids.includes(field.id)
  )
)

// The search fails, instead of searching the fields that were left out.
const searchFieldsGone = computed(
  () =>
    props.values.search_all_fields === false &&
    !props.values.search_field_ids.some((id) =>
      semanticSearchFields.value.some((field) => field.id === id)
    )
)

// No values are returned, instead of the values of the fields that were left out.
const includedFieldsGone = computed(
  () =>
    props.values.include_all_fields === false &&
    !props.values.included_field_ids.some((id) =>
      props.tableFields.some((field) => field.id === id)
    )
)
</script>
