<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <div class="api-docs__heading-wrapper">
        <h3
          :id="'section-table-' + table.id + '-update'"
          class="api-docs__heading-3"
        >
          <span v-if="batchMode === false">
            {{ $t('apiDocs.updateRow') }}
          </span>
          <span v-else>
            {{ $t('apiDocs.updateRows') }}
          </span>
        </h3>
        <div class="api-docs__endpoint-type">
          <Checkbox v-model="batchMode">batch mode</Checkbox>
        </div>
      </div>

      <p v-if="batchMode === false" class="api-docs__content">
        {{ $t('apiDocsTableUpdateRow.description', table) }}
      </p>
      <p v-else class="api-docs__content">
        {{ $t('apiDocsTableUpdateRows.description', table) }}
      </p>

      <div v-if="batchMode === false">
        <h4 class="api-docs__heading-4">{{ $t('apiDocs.pathParameters') }}</h4>
        <ul class="api-docs__parameters">
          <APIDocsParameter name="row_id" type="integer">
            {{ $t('apiDocsTableUpdateRow.rowId') }}
          </APIDocsParameter>
        </ul>
        <h4 class="api-docs__heading-4">{{ $t('apiDocs.queryParameters') }}</h4>
        <ul class="api-docs__parameters">
          <APIDocsParameter name="user_field_names" :optional="true" type="any">
            <MarkdownIt
              class="api-docs__content"
              :content="$t('apiDocs.userFieldNamesDescription')"
            />
          </APIDocsParameter>
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
        <h4 class="api-docs__heading-4">
          {{ $t('apiDocs.requestBodySchema') }}
        </h4>
        <ul class="api-docs__parameters">
          <APIDocsParameter
            v-for="field in withoutReadOnly[table.id]"
            :key="field.id"
            :name="'field_' + field.id"
            :visible-name="field.name"
            :optional="true"
            :type="field._.type"
            :user-field-names="userFieldNames"
          >
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div v-html="field._.description"></div>
          </APIDocsParameter>
        </ul>
      </div>
      <div v-else>
        <h4 class="api-docs__heading-4">{{ $t('apiDocs.queryParameters') }}</h4>
        <ul class="api-docs__parameters">
          <APIDocsParameter name="user_field_names" :optional="true" type="any">
            <MarkdownIt
              class="api-docs__content"
              :content="$t('apiDocs.userFieldNamesDescription')"
            />
          </APIDocsParameter>
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
        <h4 class="api-docs__heading-4">
          {{ $t('apiDocs.requestBodySchema') }}
        </h4>
        <ul class="api-docs__parameters api-docs__parameters-parent">
          <APIDocsParentParameter name="items" :optional="false" type="array">
            <ul class="api-docs__parameters">
              <APIDocsParameter name="id" type="integer">
                {{ $t('apiDocsTableUpdateRows.id') }}
              </APIDocsParameter>
              <APIDocsParameter
                v-for="field in withoutReadOnly[table.id]"
                :key="field.id"
                :name="'field_' + field.id"
                :visible-name="field.name"
                :optional="true"
                :type="field._.type"
                :user-field-names="userFieldNames"
              >
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div v-html="field._.description"></div>
              </APIDocsParameter>
            </ul>
          </APIDocsParentParameter>
        </ul>
      </div>
    </div>

    <div v-if="batchMode === false" class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="PATCH"
        :url="getItemUrl(table, true)"
        :request="getRequestExample(table)"
        :response="getResponseItem(table)"
        :mapping="getFieldMapping(table)"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
    <div v-else class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="PATCH"
        :url="getListUrl(table, true, true)"
        :request="getBatchRequestExample(table)"
        :response="getBatchResponseItem(table)"
        :mapping="getFieldMapping(table)"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
  </div>
</template>

<script>
import APIDocsExample from '@baserow/modules/database/components/docs/APIDocsExample'
import APIDocsParameter from '@baserow/modules/database/components/docs/APIDocsParameter'
import APIDocsParentParameter from '@baserow/modules/database/components/docs/APIDocsParentParameter'

export default {
  name: 'APIDocsTableUpdateRow',
  components: {
    APIDocsParameter,
    APIDocsParentParameter,
    APIDocsExample,
  },
  props: {
    value: {
      type: Object,
      required: true,
    },
    table: { type: Object, required: true },
    withoutReadOnly: { type: Object, required: true },
    userFieldNames: { type: Boolean, required: true },
    getItemUrl: { type: Function, required: true },
    getListUrl: { type: Function, required: true },
    getRequestExample: { type: Function, required: true },
    getResponseItem: { type: Function, required: true },
    getBatchRequestExample: { type: Function, required: true },
    getBatchResponseItem: { type: Function, required: true },
    getFieldMapping: { type: Function, required: true },
  },
  data() {
    return {
      batchMode: false,
    }
  },
}
</script>
