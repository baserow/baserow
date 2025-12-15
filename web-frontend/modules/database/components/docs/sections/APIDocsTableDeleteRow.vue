<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <div class="api-docs__heading-wrapper">
        <h3
          :id="'section-table-' + table.id + '-delete'"
          class="api-docs__heading-3"
        >
          <span v-if="batchMode === false">
            {{ $t('apiDocs.deleteRow') }}
          </span>
          <span v-else>
            {{ $t('apiDocs.deleteRows') }}
          </span>
        </h3>
        <div class="api-docs__endpoint-type">
          <Checkbox v-model="batchMode">batch mode</Checkbox>
        </div>
      </div>

      <p v-if="batchMode === false" class="api-docs__content">
        {{ $t('apiDocsTableDeleteRow.description', table) }}
      </p>
      <p v-else class="api-docs__content">
        {{ $t('apiDocsTableDeleteRows.description', table) }}
      </p>

      <div v-if="batchMode === false">
        <h4 class="api-docs__heading-4">{{ $t('apiDocs.pathParameters') }}</h4>
        <ul class="api-docs__parameters">
          <APIDocsParameter name="row_id" type="integer">
            {{ $t('apiDocsTableDeleteRow.rowId') }}
          </APIDocsParameter>
        </ul>
      </div>
      <h4 class="api-docs__heading-4">{{ $t('apiDocs.queryParameters') }}</h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter
          name="send_webhook_events"
          :optional="true"
          type="any"
        >
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocs.sendWebhookEventsDescription')"
          />
        </APIDocsParameter>
      </ul>
      <div v-if="batchMode === true">
        <h4 class="api-docs__heading-4">
          {{ $t('apiDocs.requestBodySchema') }}
        </h4>
        <ul class="api-docs__parameters">
          <APIDocsParameter name="items" :optional="false" type="array">
            {{ $t('apiDocsTableDeleteRows.items') }}
          </APIDocsParameter>
        </ul>
      </div>
    </div>

    <div v-if="batchMode === false" class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="DELETE"
        :url="getItemUrl(table, false)"
        :include-user-fields-checkbox="false"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
    <div v-else class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="POST"
        :url="getDeleteListUrl(table, false)"
        :request="getBatchDeleteRequestExample(table)"
        :include-user-fields-checkbox="false"
        @input="$emit('input', $event)"
      >
      </APIDocsExample>
    </div>
  </div>
</template>

<script>
import APIDocsExample from '@baserow/modules/database/components/docs/APIDocsExample'
import APIDocsParameter from '@baserow/modules/database/components/docs/APIDocsParameter'

export default {
  name: 'APIDocsTableDeleteRow',
  components: {
    APIDocsParameter,
    APIDocsExample,
  },
  props: {
    value: {
      type: Object,
      required: true,
    },
    table: { type: Object, required: true },
    getItemUrl: { type: Function, required: true },
    getDeleteListUrl: { type: Function, required: true },
    getBatchDeleteRequestExample: { type: Function, required: true },
  },
  data() {
    return {
      batchMode: false,
    }
  },
}
</script>
