<template>
  <div class="form-view__submitted">
    <template v-if="isRedirect">
      <div class="form-view__submitted-message">{{ defaultActionMessage }}</div>
      <div class="form-view__redirecting-description">
        You're being redirected to {{ submitActionRedirectUrl }}.
      </div>
      <div class="form-view__redirecting-loading">
        <div class="loading-absolute-center"></div>
      </div>
    </template>
    <!-- prettier-ignore -->
    <div v-else class="form-view__submitted-message whitespace-pre-wrap">{{ submitActionMessageOrDefault }}</div>
    <FormViewFooterLinks
      :show-logo="showLogo"
      show-report-abuse
    ></FormViewFooterLinks>
  </div>
</template>

<script>
import FormViewFooterLinks from '@baserow/modules/database/components/view/form/FormViewFooterLinks'

export default {
  name: 'FormViewSubmitted',
  components: {
    FormViewFooterLinks,
  },
  props: {
    isRedirect: {
      type: Boolean,
      required: true,
    },
    submitActionRedirectUrl: {
      type: String,
      required: true,
    },
    submitActionMessage: {
      type: String,
      required: true,
    },
    showLogo: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    defaultActionMessage() {
      return 'Thanks for submitting the form!'
    },
    submitActionMessageOrDefault() {
      return this.submitActionMessage || this.defaultActionMessage
    },
  },
}
</script>
