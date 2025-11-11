<template>
  <component
    :is="elementType.generalFormComponent"
    :key="element.id"
    ref="panelForm"
    class="element-form"
    :default-values="defaultValues"
    @values-changed="onChange($event)"
  />
</template>

<script>
import elementSidePanel from '@baserow/modules/builder/mixins/elementSidePanel'

export default {
  name: 'GeneralSidePanel',
  mixins: [elementSidePanel],
}
</script>
