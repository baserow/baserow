<template>
  <div>
    <div
      v-if="coverImage !== null"
      class="form-view__cover"
      :style="{
        'background-image': `url(${coverImage.url})`,
      }"
    ></div>
    <form
      v-if="!submitted"
      class="form-view__body"
      @submit.prevent="$emit('submit')"
    >
      <div class="form-view__heading">
        <Thumbnail v-if="logoImage !== null" :src="logoImage.url" width="200" />
        <h1 v-if="title !== ''" class="form-view__title">{{ title }}</h1>
        <div v-if="description !== ''" class="form-view__description">
          <FormViewDescription
            :value="description"
            read-only
          ></FormViewDescription>
        </div>
      </div>
      <FormPageField
        v-for="field in visibleFields"
        :ref="'field-' + field.field.id"
        :key="field.field.id"
        :value="values['field_' + field.field.id]"
        :slug="$route.params.slug"
        :field="field"
        :class="{ hidden: field._.hiddenViaQueryParam }"
        @input="updateValue('field_' + field.field.id, $event)"
      ></FormPageField>
      <div class="form-view__actions">
        <FormViewFooterLinks
          :show-logo="showLogo"
          show-report-abuse
          :identifier="$route.params.slug"
        ></FormViewFooterLinks>
        <div class="form-view__submit">
          <Button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="loading"
          >
            {{ submitText }}
          </Button>
        </div>
      </div>
    </form>
    <FormViewSubmitted
      v-else-if="submitted"
      :is-redirect="isRedirect"
      :submit-action-redirect-url="submitActionRedirectUrl"
      :submit-action-message="submitActionMessage"
      :show-logo="showLogo"
    ></FormViewSubmitted>
  </div>
</template>

<script>
import baseFormViewMode from '@baserow/modules/database/mixins/baseFormViewMode'
import FormPageField from '@baserow/modules/database/components/view/form/FormPageField'
import FormViewFooterLinks from '@baserow/modules/database/components/view/form/FormViewFooterLinks'
import FormViewSubmitted from '@baserow/modules/database/components/view/form/FormViewSubmitted'
import FormViewDescription from '@baserow/modules/database/components/view/form/FormViewDescription'

export default {
  name: 'FormViewModeForm',
  components: {
    FormViewSubmitted,
    FormPageField,
    FormViewFooterLinks,
    FormViewDescription,
  },
  mixins: [baseFormViewMode],
  emits: ['submit'],
}
</script>
