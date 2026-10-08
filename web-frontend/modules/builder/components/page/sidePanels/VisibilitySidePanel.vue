<template>
  <VisibilityForm
    ref="panelForm"
    :default-values="defaultValues"
    @values-changed="onChange($event)"
  />
</template>

<script>
import elementSidePanel from '@baserow/modules/builder/mixins/elementSidePanel'
import VisibilityForm from '@baserow/modules/builder/components/elements/components/forms/VisibilityForm'
export default {
  name: 'VisibilitySidePanel',
  components: { VisibilityForm },
  mixins: [elementSidePanel],
  provide() {
    return {
      applicationContext: {
        ...this.applicationContext,
        element: this.element,
        page: this.elementPage,
        // Lets the form data provider hide the form elements which this
        // element's visibility condition can't reference.
        isVisibilityCondition: true,
      },
    }
  },
  data() {
    return {}
  },
}
</script>
