<template>
  <div :style="getStyleOverride('button')">
    <div
      v-if="
        mode === 'editing' &&
        children.length === 0 &&
        $hasPermission('builder.page.create_element', currentPage, workspace.id)
      "
    >
      <AddElementZone @add-element="showAddElementModal"></AddElementZone>
      <AddElementModal
        ref="addElementModal"
        :page="elementPage"
      ></AddElementModal>
    </div>
    <div v-else>
      <template v-for="child in children">
        <ElementPreview
          v-if="mode === 'editing'"
          :key="child.id"
          :element="child"
          @move="$emit('move', $event)"
        />
        <PageElement
          v-else
          :key="`${child.id}else`"
          :element="child"
          :mode="mode"
        />
      </template>
    </div>
    <div class="form-container-element__submit-button margin-top-2">
      <ABButton
        :loading="workflowActionsInProgress"
        @click="validateAndSubmitEvent"
      >
        {{ submitButtonLabelResolved || $t('buttonElement.missingValue') }}
      </ABButton>
    </div>
  </div>
</template>

<script>
import AddElementZone from '@baserow/modules/builder/components/elements/AddElementZone.vue'
import containerElement from '@baserow/modules/builder/mixins/containerElement'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal.vue'
import ElementPreview from '@baserow/modules/builder/components/elements/ElementPreview.vue'
import PageElement from '@baserow/modules/builder/components/page/PageElement.vue'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'FormContainerElement',
  components: {
    PageElement,
    ElementPreview,
    AddElementModal,
    AddElementZone,
  },
  mixins: [containerElement],
  props: {
    /**
     * @type {Object}
     * @property submit_button_label - The label of the submit button
     * @property reset_initial_values_post_submission - Whether to reset the form
     *  elements to their initial value or not, following a successful submission.
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    submitButtonLabelResolved() {
      return (
        ensureString(this.resolveFormula(this.element.submit_button_label)) ||
        this.$t('formContainerElement.defaultSubmitButtonLabel')
      )
    },
    getFormElementDescendants() {
      const descendants = this.$store.getters['element/getDescendants'](
        this.elementPage,
        this.element
      )
      return descendants
        .map((descendant) => {
          const descendantType = this.$registry.get('element', descendant.type)
          return { descendant, descendantType }
        })
        .filter(({ descendantType }) => descendantType.isFormElement)
    },
    /*
     * Responsible for determining if any of the form's form elements are invalid. They
     * will be if: 1) they don't have any form data, or 2) they have form data but their
     * value is invalid.
     */
    formElementChildrenAreInvalid() {
      return this.getFormElementDescendants.some(
        ({ descendant, descendantType }) => {
          const uniqueElementId = descendantType.uniqueElementId({
            element: descendant,
            applicationContext: this.applicationContext,
          })
          return this.$store.getters['formData/getElementInvalid'](
            this.elementPage,
            uniqueElementId
          )
        }
      )
    },
  },
  methods: {
    /*
     * Responsible for marking all form element descendents in this form container
     * as touched, or not touched, depending on what we're achieving in validation.
     */
    setFormElementDescendantsTouched(wasTouched) {
      this.getFormElementDescendants.forEach(
        ({ descendant, descendantType }) => {
          const uniqueElementId = descendantType.uniqueElementId({
            element: descendant,
            applicationContext: this.applicationContext,
          })
          this.$store.dispatch('formData/setElementTouched', {
            page: this.elementPage,
            wasTouched,
            uniqueElementId,
          })
        }
      )
    },
    /*
     * Responsible for resetting a form container's elements, depending on
     * value of the reset_initial_values_post_submission property. If true, the
     * form elements will be reset to their initial values, if false, they will
     * be left intact.
     */
    resetFormContainerElements() {
      if (this.element.reset_initial_values_post_submission) {
        this.getFormElementDescendants.forEach(
          ({ descendant, descendantType }) => {
            const uniqueElementId = descendantType.uniqueElementId({
              element: descendant,
              applicationContext: this.applicationContext,
            })
            const initialValue = descendantType.getInitialFormDataValue(
              descendant,
              this.applicationContext
            )
            const payload = {
              touched: false,
              value: initialValue,
              elementId: this.element.id,
              type: descendantType.formDataType(descendant),
              isValid: descendantType.isValid(
                descendant,
                initialValue,
                this.applicationContext
              ),
            }
            this.$store.dispatch('formData/setFormData', {
              page: this.elementPage,
              payload,
              uniqueElementId,
            })
          }
        )
      } else {
        // If we don't want to reset to initial values, we still
        // want to mark the form elements as not touched.
        this.setFormElementDescendantsTouched(false)
      }
    },
    /*
     * Responsible for validating the form container's elements and submitting the form.
     */
    async validateAndSubmitEvent() {
      this.setFormElementDescendantsTouched(true)
      if (!this.formElementChildrenAreInvalid) {
        await this.fireEvent(
          this.elementType.getEventByName(this.element, 'submit')
        )
        this.resetFormContainerElements()
      }
    },
    showAddElementModal() {
      this.$refs.addElementModal.show({
        placeInContainer: null,
        parentElementId: this.element.id,
      })
    },
  },
}
</script>
