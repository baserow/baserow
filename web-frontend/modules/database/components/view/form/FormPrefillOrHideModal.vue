<template>
  <Modal ref="modal">
    <h1>{{ $t('formSidebar.modal.title') }}</h1>
    <p>{{ $t('formSidebar.modal.descriptionPartOne') }}</p>
    <p>{{ $t('formSidebar.modal.descriptionPartTwo') }}</p>

    <h2>{{ $t('formSidebar.modal.howToPrefill.title') }}</h2>
    <p>{{ $t('formSidebar.modal.howToPrefill.description') }}</p>

    <h3>{{ $t('formSidebar.modal.format.title') }}</h3>
    <p>{{ $t('formSidebar.modal.format.description') }}</p>
    <pre>
      <code>
        {{ $t('formSidebar.modal.format.codeSnippet') }}
      </code>
    </pre>

    <h3>{{ $t('formSidebar.modal.example.title') }}</h3>
    <p>{{ $t('formSidebar.modal.example.description') }}</p>
    <pre>
      <code>
        {{ $t('formSidebar.modal.example.codeSnippet') }}
      </code>
    </pre>

    <h3>{{ $t('formSidebar.modal.spaces.title') }}</h3>
    <p>{{ $t('formSidebar.modal.spaces.description') }}</p>
    <pre>
      <code>
        {{ $t('formSidebar.modal.spaces.codeSnippet') }}
      </code>
    </pre>

    <h3>{{ $t('formSidebar.modal.multipleValues.title') }}</h3>
    <p>{{ $t('formSidebar.modal.multipleValues.description') }}</p>
    <pre>
      <code>
        {{ $t('formSidebar.modal.multipleValues.codeSnippet') }}
      </code>
    </pre>

    <h3>{{ $t('formSidebar.modal.specialFieldTypes.title') }}</h3>
    <p>{{ $t('formSidebar.modal.specialFieldTypes.description') }}</p>

    <h4>{{ $t('formSidebar.modal.specialFieldTypes.ratingField.title') }}</h4>
    <p>
      {{ $t('formSidebar.modal.specialFieldTypes.ratingField.description') }}
    </p>
    <pre>
      <code>
        {{ $t('formSidebar.modal.specialFieldTypes.ratingField.codeSnippet') }}
      </code>
    </pre>

    <h4>{{ $t('formSidebar.modal.specialFieldTypes.linkRowField.title') }}</h4>
    <p>
      {{ $t('formSidebar.modal.specialFieldTypes.linkRowField.description') }}
    </p>
    <pre>
      <code>
        {{ $t('formSidebar.modal.specialFieldTypes.linkRowField.codeSnippet') }}
      </code>
    </pre>

    <h4>{{ $t('formSidebar.modal.specialFieldTypes.selectField.title') }}</h4>
    <p>
      {{ $t('formSidebar.modal.specialFieldTypes.selectField.description') }}
    </p>
    <pre>
      <code>
        {{ $t('formSidebar.modal.specialFieldTypes.selectField.codeSnippet') }}
      </code>
    </pre>

    <h4>{{ $t('formSidebar.modal.specialFieldTypes.dateField.title') }}</h4>
    <p>
      {{ $t('formSidebar.modal.specialFieldTypes.dateField.description') }}
    </p>
    <pre>
      <code>
        {{ $t('formSidebar.modal.specialFieldTypes.dateField.codeSnippet') }}
      </code>
    </pre>

    <h2>{{ $t('formSidebar.modal.howToHide.title') }}</h2>
    <p>{{ $t('formSidebar.modal.howToHide.description') }}</p>
    <pre><code>?hide_&lt;field_name&gt;
?hide_Name
?hide_Full+Name</code></pre>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'FormPrefillOrHideModal',
  mixins: [modal],
}
</script>

<style scoped></style>
