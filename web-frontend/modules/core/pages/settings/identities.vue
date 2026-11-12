<template><IdentitiesTable :workspace="workspace" /></template>
<script>
import IdentitiesTable from '@baserow/modules/core/components/settings/identities/IdentitiesTable'
export default {
  name: 'Identities',
  components: { IdentitiesTable },
  props: { workspace: { type: Object, required: true } },
}
</script>
