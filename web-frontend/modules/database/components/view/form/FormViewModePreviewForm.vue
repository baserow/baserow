<template>
  <div>
    <div
      class="form-view__cover"
      :style="{
        'background-image': view.cover_image
          ? `url(${view.cover_image.url})`
          : null,
      }"
    >
      <template v-if="!readOnly">
        <FormViewImageUpload
          v-if="!view.cover_image"
          @uploaded="updateForm({ cover_image: $event })"
          >{{ $t('formViewModePreviewForm.addCoverImage') }}
        </FormViewImageUpload>
        <a
          v-else
          class="form-view__file-delete"
          @click="updateForm({ cover_image: null })"
        >
          <i class="iconoir-cancel"></i>
          {{ $t('action.remove') }}
        </a>
      </template>
    </div>
    <div class="form-view__body">
      <div class="form-view__heading">
        <Thumbnail
          v-if="view.logo_image !== null"
          class="margin-bottom-3"
          removable
          width="200"
          :src="view.logo_image.url"
          @remove="updateForm({ logo_image: null })"
        ></Thumbnail>
        <FormViewImageUpload
          v-else-if="!readOnly"
          class="margin-bottom-3"
          @uploaded="updateForm({ logo_image: $event })"
          >{{ $t('formViewModePreviewForm.addLogo') }}
        </FormViewImageUpload>
        <h1 class="form-view__title">
          <Editable
            ref="title"
            :value="view.title"
            :placeholder="$t('formViewModePreviewForm.titlePlaceholder')"
            @change="updateForm({ title: $event.value })"
            @editing="editingTitle = $event"
          ></Editable>
          <a
            v-if="!readOnly"
            class="form-view__edit"
            :class="{ 'form-view__edit--hidden': editingTitle }"
            @click="$refs.title.edit()"
          >
            <i class="form-view__edit-icon iconoir-edit-pencil"></i
          ></a>
        </h1>
        <p v-if="!readOnly || view.description" class="form-view__description">
          <Editable
            ref="description"
            :value="view.description"
            :placeholder="$t('formViewModePreviewForm.descriptionPlaceholder')"
            :multiline="true"
            @change="updateForm({ description: $event.value })"
            @editing="editingDescription = $event"
          ></Editable>
          <a
            v-if="!readOnly"
            class="form-view__edit"
            :class="{ 'form-view__edit--hidden': editingDescription }"
            @click="$refs.description.edit()"
          >
            <i class="form-view__edit-icon iconoir-edit-pencil"></i
          ></a>
        </p>
        <div v-if="fields.length === 0" class="form-view__no-fields">
          <div class="form-view__no-fields-title">
            {{ $t('formViewModePreviewForm.noFieldsTitle') }}
          </div>
          <div class="form-view__no-fields-content">
            {{ $t('formViewModePreviewForm.noFieldsContent') }}
          </div>
        </div>
      </div>
      <div class="form-view__fields">
        <FormViewField
          v-for="field in fields"
          :key="field.id"
          v-sortable="{
            enabled: !readOnly,
            id: field.id,
            update: order,
            handle: '[data-field-handle]',
          }"
          :database="database"
          :table="table"
          :view="view"
          :field="field"
          :field-options="fieldOptions[field.id]"
          :fields="fields"
          :read-only="readOnly"
          @hide="updateFieldOptionsOfField(view, field, { enabled: false })"
          @updated-field-options="
            updateFieldOptionsOfField(view, field, $event)
          "
        >
        </FormViewField>
      </div>
      <div
        class="form-view__actions"
        :class="{ 'form-view__actions--single': !view.show_logo }"
      >
        <FormViewPoweredBy v-if="view.show_logo"></FormViewPoweredBy>
        <div class="form-view__submit">
          <Editable
            ref="submit_text"
            class="button button--primary button--large"
            :class="{ 'form-view__submit-button-editing': editingSubmitText }"
            :value="view.submit_text"
            @change="updateForm({ submit_text: $event.value })"
            @editing="editingSubmitText = $event"
          ></Editable>

          <a
            v-if="!readOnly"
            class="form-view__edit"
            :class="{ 'form-view__edit--hidden': editingSubmitText }"
            @click="$refs.submit_text.edit()"
          >
            <i class="form-view__edit-icon iconoir-edit-pencil"></i
          ></a>
        </div>
      </div>
    </div>
    <div class="form-view__meta">
      <div class="form-view__body">
        <FormViewMetaControls
          :view="view"
          :database="database"
          :read-only="readOnly"
          @updated-form="updateForm($event)"
        ></FormViewMetaControls>
      </div>
    </div>
  </div>
</template>

<script>
import FormViewField from '@baserow/modules/database/components/view/form/FormViewField'
import FormViewImageUpload from '@baserow/modules/database/components/view/form/FormViewImageUpload'
import formViewHelpers from '@baserow/modules/database/mixins/formViewHelpers'
import FormViewPoweredBy from '@baserow/modules/database/components/view/form/FormViewPoweredBy'
import FormViewMetaControls from '@baserow/modules/database/components/view/form/FormViewMetaControls'

export default {
  name: 'FormViewModePreviewForm',
  components: {
    FormViewPoweredBy,
    FormViewField,
    FormViewImageUpload,
    FormViewMetaControls,
  },
  mixins: [formViewHelpers],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      editingTitle: false,
      editingSubmitText: false,
      editingDescription: false,
    }
  },
  methods: {
    order(order) {
      this.$emit('ordered-fields', order)
    },
  },
}
</script>
