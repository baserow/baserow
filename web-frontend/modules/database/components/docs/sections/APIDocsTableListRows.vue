<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <h3
        :id="'section-table-' + table.id + '-list'"
        class="api-docs__heading-3"
      >
        {{ $t('apiDocs.listRows') }}
      </h3>
      <MarkdownIt
        class="api-docs__content"
        :content="$t('apiDocsTableListRows.description', table)"
      />
      <h4 class="api-docs__heading-4">
        {{ $t('apiDocs.queryParameters') }}
      </h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter
          name="page"
          :optional="true"
          type="integer"
          standard="1"
        >
          {{ $t('apiDocsTableListRows.page') }}
        </APIDocsParameter>
        <APIDocsParameter
          name="size"
          :optional="true"
          type="integer"
          standard="100"
        >
          {{ $t('apiDocsTableListRows.size') }}
        </APIDocsParameter>
        <APIDocsParameter name="user_field_names" :optional="true" type="any">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.userFieldNames')"
          />
        </APIDocsParameter>
        <APIDocsParameter
          name="search"
          :optional="true"
          type="string"
          standard="''"
        >
          {{ $t('apiDocsTableListRows.search') }}
        </APIDocsParameter>
        <APIDocsParameter
          name="order_by"
          :optional="true"
          type="string"
          standard="'id'"
        >
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.orderBy')"
          />
        </APIDocsParameter>
        <APIDocsParameter name="filters" :optional="true" type="JSON">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.filters')"
          />
          <Button
            type="secondary"
            size="small"
            @click.prevent="$refs.filtersModal.show()"
          >
            {{ $t('apiDocsTableListRows.filtersBuilder') }}</Button
          >
          <APIDocsFiltersBuilderModal
            ref="filtersModal"
            :user-field-names="value.userFieldNames"
            :fields="fields[table.id]"
          ></APIDocsFiltersBuilderModal>
        </APIDocsParameter>
        <APIDocsParameter
          name="filter__{field}__{filter}"
          :optional="true"
          type="string"
        >
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.filter', table)"
          />
          <a @click.prevent="navigate('section-filters')">
            {{ $t('apiDocsTableListRows.filterLink') }}</a
          >
        </APIDocsParameter>
        <APIDocsParameter
          name="filter_type"
          :optional="true"
          type="string"
          standard="'AND'"
        >
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.filterType')"
          />
        </APIDocsParameter>
        <APIDocsParameter name="include" :optional="true" type="string">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.include')"
          />
        </APIDocsParameter>
        <APIDocsParameter name="exclude" :optional="true" type="string">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.exclude')"
          />
        </APIDocsParameter>
        <APIDocsParameter name="view_id" :optional="true" type="integer">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.viewId')"
          />
        </APIDocsParameter>
        <APIDocsParameter
          name="{link_row_field}__join"
          :optional="true"
          type="string"
        >
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocsTableListRows.join')"
          />
        </APIDocsParameter>
      </ul>
    </div>
    <div class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="GET"
        :url="getListUrl(table, true)"
        :response="{
          count: 1024,
          next: getListUrl(table, false) + '?page=2',
          previous: null,
          results: [getResponseItem(table)],
        }"
        :mapping="getFieldMapping(table)"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
  </div>
</template>

<script>
import APIDocsExample from '@baserow/modules/database/components/docs/APIDocsExample'
import APIDocsParameter from '@baserow/modules/database/components/docs/APIDocsParameter'
import APIDocsFiltersBuilderModal from '@baserow/modules/database/components/docs/APIDocsFiltersBuilderModal.vue'

export default {
  name: 'APIDocsTableListRows',
  components: {
    APIDocsFiltersBuilderModal,
    APIDocsParameter,
    APIDocsExample,
  },
  props: {
    value: {
      type: Object,
      required: true,
    },
    fields: {
      type: Object,
      required: true,
    },
    table: { type: Object, required: true },
    getListUrl: { type: Function, required: true },
    navigate: { type: Function, required: true },
    getResponseItem: { type: Function, required: true },
    getFieldMapping: { type: Function, required: true },
  },
  emits: ['input'],
  methods: {},
}
</script>
