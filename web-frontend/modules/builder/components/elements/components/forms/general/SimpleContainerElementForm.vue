<template>
  <form @submit.prevent @keydown.enter.prevent></form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'

export default {
  name: 'SimpleContainerElementForm',
  mixins: [elementForm],
  data() {
    return {
      values: {
        styles: {},
      },
      allowedValues: ['styles'],
    }
  },
}
</script>
