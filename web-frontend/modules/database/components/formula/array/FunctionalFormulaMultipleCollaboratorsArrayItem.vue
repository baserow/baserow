<template functional>
  <span class="array-field__multiple-collaborators-container">
    <div
      v-for="item in props.value"
      :key="item.id"
      class="field-multiple-collaborators__item"
    >
      <template v-if="item.id && item.name">
        <div
          class="field-multiple-collaborators__name background-color--light-gray"
        >
          <span class="field-multiple-collaborators__name-text">{{
            $options.methods.getCollaboratorName(item, parent.$store)
          }}</span>
        </div>
        <div class="field-multiple-collaborators__initials">
          {{
            $options.methods.getCollaboratorNameInitials(item, parent.$store)
          }}
        </div>
      </template>
    </div>
  </span>
</template>

<script>
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'FunctionalFormulaMultipleCollaboratorsArrayItem',
  mixins: [collaboratorName],
}
</script>
