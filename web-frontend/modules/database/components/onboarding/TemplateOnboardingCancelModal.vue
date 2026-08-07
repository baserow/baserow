<template>
  <Modal ref="modal" wide @hidden="$emit('hidden')">
    <h2 class="box__title">
      {{ $t('templateOnboardingCancelModal.title') }}
    </h2>
    <p>{{ $t('templateOnboardingCancelModal.description') }}</p>
    <TemplateImportForm
      :provided-categories="categories"
      auto-select-default
      wide
      :limit="8"
      @selected-template="selectTemplate"
    ></TemplateImportForm>
    <div class="margin-top-3">
      <Button
        ph-autocapture="onboarding-cancel-template-continue"
        type="primary"
        size="large"
        full-width
        :disabled="selectedTemplate === null"
        :loading="installing"
        @click="install()"
        >{{ $t('templateOnboardingCancelModal.continue') }}</Button
      >
    </div>
    <div class="template-onboarding-cancel-modal__skip">
      <ButtonText
        ph-autocapture="onboarding-cancel-template-skip"
        tag="a"
        type="secondary"
        :loading="skipping"
        @click="skip()"
        >{{ $t('templateOnboardingCancelModal.skip') }}</ButtonText
      >
      <div class="template-onboarding-cancel-modal__skip-description">
        {{ $t('templateOnboardingCancelModal.skipDescription') }}
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import TemplateImportForm from '@baserow/modules/database/components/onboarding/TemplateImportForm'

export default {
  name: 'TemplateOnboardingCancelModal',
  components: { TemplateImportForm },
  mixins: [modal],
  props: {
    categories: {
      type: Array,
      required: true,
    },
    // The database onboarding step type the emitted data belongs to.
    stepType: {
      type: String,
      required: true,
    },
  },
  emits: ['selected', 'cancel', 'hidden'],
  data() {
    return {
      selectedTemplate: null,
      installing: false,
      skipping: false,
    }
  },
  mounted() {
    this.show()
  },
  beforeUnmount() {
    // The parent unmounts this component when the onboarding continues, so the modal
    // must clean up after itself without emitting that the user dismissed it.
    this.hide(false)
  },
  methods: {
    selectTemplate(template) {
      this.selectedTemplate = template
    },
    install() {
      this.installing = true
      this.$emit('selected', {
        type: this.stepType,
        template: this.selectedTemplate,
      })
    },
    skip() {
      this.skipping = true
      this.$emit('cancel')
    },
  },
}
</script>
