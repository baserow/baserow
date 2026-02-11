<template>
  <component
    :is="elementType.styleFormComponent"
    v-if="elementType && element"
    ref="panelForm"
    :key="element.id"
    :element="element"
    :parent-element="parentElement"
    :default-values="defaultValues"
    @values-changed="onChange($event)"
  ></component>
</template>

<script>
import elementSidePanel from '@baserow/modules/builder/mixins/elementSidePanel'
export default {
  name: 'StyleSidePanel',
  mixins: [elementSidePanel],
}
</script>
