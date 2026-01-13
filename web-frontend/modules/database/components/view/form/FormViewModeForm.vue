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
        <!-- prettier-ignore -->
        <p
          v-if="description !== ''"
          class="form-view__description whitespace-pre-wrap"
        >{{ description }}</p>
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
      <div
        class="form-view__actions"
        :class="{ 'form-view__actions--single': !showLogo }"
      >
        <FormViewPoweredBy v-if="showLogo"></FormViewPoweredBy>
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
import FormViewPoweredBy from '@baserow/modules/database/components/view/form/FormViewPoweredBy'
import FormViewSubmitted from '@baserow/modules/database/components/view/form/FormViewSubmitted'

export default {
  name: 'FormViewModeForm',
  components: {
    FormViewSubmitted,
    FormPageField,
    FormViewPoweredBy,
  },
  mixins: [baseFormViewMode],
  emits: ['submit'],
}
</script>
