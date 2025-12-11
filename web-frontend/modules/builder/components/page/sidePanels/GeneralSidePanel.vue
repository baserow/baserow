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
        defaultStyleValues: {},
        configBlockTypes: [],
        // Optional callback to allow the form component to
        // modify the final object before sending it to onChange.
        onStylesChanged: null,
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
     * Called when the values in the `CustomStyleForm` change. If the form
     * component provided an onStylesChanged callback, use that to build the
     * update object. Otherwise, apply to root element styles (default behavior).
     */
    onThemeValuesChanged(newStyleValues) {
      const { styleKey, defaultStyleValues, onStylesChanged } =
        this.customStylesContext

      // If we have a callback for final modification of the full element,
      // pass the new style values and context to it. This will most often
      // be to update a table element's field styles.
      if (onStylesChanged) {
        this.onChange(onStylesChanged(newStyleValues, this.customStylesContext))
      } else {
        // Otherwise, most of the time, we're just updating this element's root-styles.
        this.onChange({
          styles: {
            [styleKey]: { ...defaultStyleValues, ...newStyleValues },
          },
        })
      }
    },
  },
}
</script>
