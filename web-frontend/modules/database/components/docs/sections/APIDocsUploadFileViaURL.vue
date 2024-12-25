<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <div class="api-docs__heading-wrapper">
        <h3 :id="'section-upload-file-via-url'" class="api-docs__heading-3">
          <span>
            {{ $t('apiDocs.uploadFileViaUrl') }}
          </span>
        </h3>
        <div class="api-docs__endpoint-type"></div>
      </div>

      <MarkdownIt
        class="api-docs__content"
        :content="
          $t('apiDocsUploadFileViaURL.description', {
            PUBLIC_BACKEND_URL: `${$config.PUBLIC_BACKEND_URL}`,
          })
        "
      />

      <h4 class="api-docs__heading-4">{{ $t('apiDocs.requestBodySchema') }}</h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter name="url" :optional="false" type="string">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocs.uploadFileViaUrlDescription')"
          />
        </APIDocsParameter>
      </ul>
    </div>

    <div class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="POST"
        :url="getUploadFileViaUrlListUrl()"
        :response="getUploadFileResponse()"
        :request="getUploadFileViaUrlRequestExample()"
        :include-user-fields-checkbox="false"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
  </div>
</template>

<script>
import APIDocsExample from '@baserow/modules/database/components/docs/APIDocsExample'
import APIDocsParameter from '@baserow/modules/database/components/docs/APIDocsParameter'

export default {
  name: 'APIDocsUploadFileViaURL',
  components: {
    APIDocsParameter,
    APIDocsExample,
  },
  props: {
    value: {
      type: Object,
      required: true,
    },
    getUploadFileViaUrlListUrl: { type: Function, required: true },
    getUploadFileViaUrlRequestExample: { type: Function, required: true },
    getUploadFileResponse: { type: Function, required: true },
  },
}
</script>
