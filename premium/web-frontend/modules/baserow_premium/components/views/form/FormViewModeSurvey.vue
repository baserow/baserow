<template>
  <div class="form-view-survey">
    <template v-if="!submitted">
      <form @submit.prevent="validateAndNext(questionIndex)">
        <!-- This component must exist for validation purposes. -->
        <FormPageField
          v-for="field in visibleFieldsWithHiddenViaQueryParam"
          :key="field.field.id"
          :ref="'field-' + field.field.id"
          :value="values['field_' + field.field.id]"
          :slug="$route.params.slug"
          :field="field"
          :class="{ hidden: true }"
        ></FormPageField>
        <div
          v-for="(field, index) in visibleFieldsWithoutHiddenViaQueryParam"
          :key="field.field.id"
          class="form-view-survey__center"
          :class="{
            'form-view-survey__center--before': index < questionIndex,
            'form-view-survey__center--after': index > questionIndex,
          }"
        >
          <div class="form-view-survey__center-inner-1">
            <div class="form-view-survey__center-inner-2">
              <FormPageField
                :ref="'field-' + field.field.id"
                :value="values['field_' + field.field.id]"
                :slug="$route.params.slug"
                :field="field"
                @input="updateValue('field_' + field.field.id, $event)"
                @focussed="questionIndex = index"
              ></FormPageField>
              <div class="form-view__field-actions">
                <Button
                  v-if="
                    index < visibleFieldsWithoutHiddenViaQueryParam.length - 1
                  "
                  type="primary"
                  size="large"
                  @click="validateAndNext(index)"
                  >Next</Button
                >

                <Button
                  v-else-if="
                    index >= visibleFieldsWithoutHiddenViaQueryParam.length - 1
                  "
                  type="primary"
                  size="large"
                  :loading="loading"
                  :disabled="loading"
                >
                  {{ submitText }}</Button
                >
              </div>
            </div>
          </div>
        </div>
      </form>
      <div
        class="form-view-survey__footer"
        :class="{ 'form-view-survey__footer--single': !showLogo }"
      >
        <FormViewPoweredBy v-if="showLogo"></FormViewPoweredBy>
        <div class="form-view-survey__pagination">
          <div class="form-view-survey__pagination-buttons">
            <a
              class="form-view-survey__pagination-button"
              :class="{
                'form-view-survey__pagination-button--disabled': !canPrevious,
              }"
              @click="previous"
            >
              <i class="iconoir-nav-arrow-up"></i>
            </a>
            <a
              class="form-view-survey__pagination-button"
              :class="{
                'form-view-survey__pagination-button--disabled': !canNext,
              }"
              @click="next"
            >
              <i class="iconoir-nav-arrow-down"></i>
            </a>
          </div>
        </div>
      </div>
    </template>
    <div v-else-if="submitted" class="form-view-survey__center">
      <div class="form-view-survey__center-inner">
        <FormViewSubmitted
          :show-logo="showLogo"
          :is-redirect="isRedirect"
          :submit-action-redirect-url="submitActionRedirectUrl"
          :submit-action-message="submitActionMessage"
        ></FormViewSubmitted>
      </div>
    </div>
  </div>
</template>

<script>
import baseFormViewMode from '@baserow/modules/database/mixins/baseFormViewMode'
import FormPageField from '@baserow/modules/database/components/view/form/FormPageField'
import FormViewPoweredBy from '@baserow/modules/database/components/view/form/FormViewPoweredBy'
import FormViewSubmitted from '@baserow/modules/database/components/view/form/FormViewSubmitted'

export default {
  name: 'FormViewModeSurvey',
  components: {
    FormPageField,
    FormViewPoweredBy,
    FormViewSubmitted,
  },
  mixins: [baseFormViewMode],
  data() {
    return {
      questionIndex: 0,
    }
  },
  computed: {
    canPrevious() {
      return this.questionIndex > 0
    },
    canNext() {
      return (
        this.questionIndex <
        this.visibleFieldsWithoutHiddenViaQueryParam.length - 1
      )
    },
    visibleFieldsWithoutHiddenViaQueryParam() {
      return this.visibleFields.filter((field) => !field._.hiddenViaQueryParam)
    },
    visibleFieldsWithHiddenViaQueryParam() {
      return this.visibleFields.filter((field) => field._.hiddenViaQueryParam)
    },
  },
  mounted() {
    // Intercept Tab key to navigate through questions instead of default browser
    // behavior
    const navigateOnTab = (e) => {
      if (e.key === 'Tab') {
        e.preventDefault()
        if (e.shiftKey) {
          this.previous()
        } else {
          this.next()
        }
      }
    }
    document.addEventListener('keydown', navigateOnTab)
    this.$once('hook:beforeDestroy', () => {
      document.removeEventListener('keydown', navigateOnTab)
    })
  },
  methods: {
    previous() {
      if (!this.canPrevious) {
        return
      }

      this.questionIndex--
    },
    next() {
      if (!this.canNext) {
        return
      }

      this.questionIndex++
    },
    validateAndNext(fieldIndex) {
      const field = this.visibleFieldsWithoutHiddenViaQueryParam[fieldIndex]
      field._.touched = true

      const ref = this.$refs['field-' + field.field.id][0]

      if (!ref.isValid()) {
        return
      }

      if (
        fieldIndex ===
        this.visibleFieldsWithoutHiddenViaQueryParam.length - 1
      ) {
        this.$emit('submit')
      } else {
        this.next()
      }
    },
  },
}
</script>
