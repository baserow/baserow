<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <div class="api-docs__heading-wrapper">
        <h3 :id="'section-upload-file'" class="api-docs__heading-3">
          <span>
            {{ $t('apiDocs.uploadFile') }}
          </span>
        </h3>
        <div class="api-docs__endpoint-type"></div>
      </div>

      <MarkdownIt
        class="api-docs__content"
        :content="
          $t('apiDocsUploadFile.description', {
            PUBLIC_BACKEND_URL: `${$config.PUBLIC_BACKEND_URL}`,
          })
        "
      />

      <h4 class="api-docs__heading-4">{{ $t('apiDocs.requestBodySchema') }}</h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter name="file" :optional="false" type="multipart">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocs.uploadFileDescription')"
          />
        </APIDocsParameter>
      </ul>
    </div>

    <div class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="POST"
        :url="getUploadFileListUrl()"
        :file-request="getUploadFileExample()"
        :response="getUploadFileResponse()"
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
  name: 'APIDocsUploadFile',
  components: {
    APIDocsParameter,
    APIDocsExample,
  },
  props: {
    value: {
      type: Object,
      required: true,
    },
    getUploadFileListUrl: { type: Function, required: true },
    getUploadFileExample: { type: Function, required: true },
    getUploadFileResponse: { type: Function, required: true },
  },
}
</script>
