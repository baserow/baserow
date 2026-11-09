<template>
  <li
    class="select-collaborators__dropdown-item"
    :class="{
      hidden: !isVisible(query),
      active: isActive(value),
      disabled: disabled,
      hover: isHovering(value),
    }"
  >
    <a
      class="select-collaborators__dropdown-link"
      @click="select(value, disabled)"
      @mousemove="hover(value, disabled)"
    >
      <component
        :is="collaboratorType.avatarComponent"
        class="select-collaborators__avatar"
        :subject="{ id: value, name, type: subjectType }"
        size="medium"
      />
      <div class="select-collaborators__dropdown-option">
        {{ name }}
      </div>
    </a>
  </li>
</template>

<script>
import dropdownItem from '@baserow/modules/core/mixins/dropdownItem'
import { UserSubjectType } from '@baserow/modules/core/subjectTypes'
import { getCollaboratorSubjectType } from '@baserow/modules/core/utils/collaborator'

export default {
  name: 'FieldCollaboratorDropdownItem',
  mixins: [dropdownItem],
  props: {
    subjectType: { type: String, default: UserSubjectType.getType() },
  },
  computed: {
    collaboratorType() {
      return getCollaboratorSubjectType(
        { type: this.subjectType },
        this.$registry
      )
    },
  },
}
</script>
