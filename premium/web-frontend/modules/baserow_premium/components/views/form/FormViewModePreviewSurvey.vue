<template>
  <div class="form-view-survey">
    <div v-if="isDeactivated" class="form-view-survey__deactivated">
      <div>
        <div class="form-view-survey__deactivated-content">
          <div class="margin-bottom-2">
            {{ $t('formViewModePreviewSurvey.deactivated') }}
          </div>
          <Button
            type="primary"
            icon="iconoir-no-lock"
            @click="$refs.paidFeaturesModal.show()"
          >
            {{ $t('formViewModePreviewSurvey.more') }}
          </Button>
        </div>
        <PaidFeaturesModal
          ref="paidFeaturesModal"
          :name="modeType.getName()"
        ></PaidFeaturesModal>
      </div>
    </div>
    <template v-else>
      <form>
        <div
          v-for="(field, index) in fields"
          :key="field.id"
          class="form-view-survey__center"
          :class="{
            'form-view-survey__center--before': index < questionIndex,
            'form-view-survey__center--after': index > questionIndex,
          }"
        >
          <div class="form-view-survey__center-inner-1">
            <div class="form-view-survey__center-inner-2">
              <FormViewField
                :database="database"
                :table="table"
                :view="view"
                :field="field"
                :field-options="fieldOptions[field.id]"
                :fields="fields"
                :read-only="readOnly"
                :add-order-buttons="true"
                :add-handle="false"
                @hide="hideField(view, field)"
                @updated-field-options="
                  updateFieldOptionsOfField(view, field, $event)
                "
              >
              </FormViewField>
              <div class="form-view__field-actions">
                <Button
                  v-if="index < fields.length - 1"
                  type="primary"
                  size="large"
                  @click="next()"
                  >Next</Button
                >
                <template v-else-if="index >= fields.length - 1">
                  <Editable
                    ref="submitText"
                    class="button button--primary button--large"
                    :class="{
                      'form-view__submit-button-editing': editingSubmitText,
                    }"
                    :value="view.submit_text"
                    @change="updateForm({ submit_text: $event.value })"
                    @editing="editingSubmitText = $event"
                    @click="next()"
                  ></Editable>
                  <a
                    v-if="!readOnly"
                    class="form-view__edit"
                    :class="{ 'form-view__edit--hidden': editingSubmitText }"
                    @click="$refs.submitText[0].edit()"
                  >
                    <i class="form-view__edit-icon iconoir-edit-pencil"></i
                  ></a>
                </template>
              </div>
            </div>
          </div>
        </div>
        <div
          class="form-view-survey__center"
          :class="{
            'form-view-survey__center--after': questionIndex < fields.length,
          }"
        >
          <div class="form-view-survey__center-inner-1">
            <div class="form-view-survey__center-inner-2">
              <div v-if="fields.length === 0" class="form-view__no-fields">
                <div class="form-view__no-fields-title">
                  {{ $t('formViewModePreviewForm.noFieldsTitle') }}
                </div>
                <div class="form-view__no-fields-content">
                  {{ $t('formViewModePreviewForm.noFieldsContent') }}
                </div>
              </div>
              <FormViewMetaControls
                v-else
                :view="view"
                :database="database"
                :read-only="readOnly"
                @updated-form="updateForm($event)"
              ></FormViewMetaControls>
            </div>
          </div>
        </div>
      </form>
      <div
        class="form-view-survey__footer form-view-survey__footer--absolute"
        :class="{ 'form-view-survey__footer--single': !view.show_logo }"
      >
        <FormViewPoweredBy v-if="view.show_logo"></FormViewPoweredBy>
        <div class="form-view-survey__pagination">
          <a
            v-if="!readOnly"
            ref="customizeContextLink"
            class="form-view-survey__order-fields"
            @click="
              $refs.customizeContext.toggle(
                $refs.customizeContextLink,
                'top',
                'left',
                4
              )
            "
            >{{ $t('formViewModePreviewSurvey.orderFields') }}</a
          >
          <ViewFieldsContext
            ref="customizeContext"
            :database="database"
            :view="view"
            :fields="fields"
            :field-options="fieldOptions"
            :allow-hiding-fields="false"
            @update-order="$emit('ordered-fields', $event.order)"
          ></ViewFieldsContext>
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
  </div>
</template>

<script>
import FormViewField from '@baserow/modules/database/components/view/form/FormViewField'
import formViewHelpers from '@baserow/modules/database/mixins/formViewHelpers'
import FormViewPoweredBy from '@baserow/modules/database/components/view/form/FormViewPoweredBy'
import FormViewMetaControls from '@baserow/modules/database/components/view/form/FormViewMetaControls'
import ViewFieldsContext from '@baserow/modules/database/components/view/ViewFieldsContext'

export default {
  name: 'FormViewModePreviewSurvey',
  components: {
    ViewFieldsContext,
    FormViewPoweredBy,
    FormViewField,
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
      questionIndex: 0,
      editingSubmitText: false,
    }
  },
  computed: {
    canPrevious() {
      return this.questionIndex > 0
    },
    canNext() {
      // We deliberately don't do `this.fields.length - 1`, because there is an
      // additional "question" where the success message can be configured.
      return this.questionIndex < this.fields.length
    },
    modeType() {
      return this.$registry.get('formViewMode', this.view.mode)
    },
    isDeactivated() {
      return (
        // If we're in read only mode, then it doesn't matter whether the mode is
        // disabled because we then always want to demo the survey.
        !this.readOnly &&
        this.modeType.isDeactivated(this.database.workspace.id)
      )
    },
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
    hideField(view, field) {
      this.previous()
      this.updateFieldOptionsOfField(view, field, { enabled: false })
    },
  },
}
</script>
