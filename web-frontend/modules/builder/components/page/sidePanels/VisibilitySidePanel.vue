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
      },
    }
  },
  data() {
    return {}
  },
}
</script>
