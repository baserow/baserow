<template>
  <div class="general-side-panel">
    <component
      :is="elementType.generalFormComponent"
      v-show="elementFormVisible"
      :key="`element-form-${element.id}`"
      ref="panelForm"
      class="element-form"
      :default-values="defaultValues"
      @values-changed="onChange($event)"
    />
    <CustomStyleForm
      v-if="!elementFormVisible"
      :key="`style-form-${element.id}`"
      :custom-styles-context="customStylesContext"
      @hide="elementFormVisible = true"
      @values-changed="onThemeValuesChanged($event)"
    />
  </div>
</template>

<script>
import elementSidePanel from '@baserow/modules/builder/mixins/elementSidePanel'
import CustomStyleForm from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleForm'

export default {
  name: 'GeneralSidePanel',
  components: { CustomStyleForm },
  mixins: [elementSidePanel],
  provide() {
    return {
      openCustomStyleForm: this.handleOpenCustomStyleForm,
    }
  },
  data() {
    return {
      elementFormVisible: true,
      customStylesContext: {
        theme: {},
        styleKey: '',
        extraArgs: null,
        defaultValues: {},
        configBlockTypes: [],
      },
    }
  },

  methods: {
    /**
     * The handler that is injected into the element's general form
     * component. When one of the element form's `CustomStyleButton` are
     * clicked, this function is called with an object that contains the
     * context needed to render the `CustomStyleForm`.
     */
    handleOpenCustomStyleForm(newCustomStylesContext) {
      this.customStylesContext = newCustomStylesContext
      this.elementFormVisible = !this.elementFormVisible
    },
    /**
     * Called when the values in the `CustomStyleForm` change. It merges
     * the new values with the default values and emits the `onChange`
     * event to update the element's styles.
     */
    onThemeValuesChanged(newValues) {
      const { styleKey, defaultValues } = this.customStylesContext
      this.onChange({
        styles: {
          [styleKey]: { ...defaultValues, ...newValues },
        },
      })
    },
  },
}
</script>
