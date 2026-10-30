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
      <CollaboratorAvatar
        class="select-collaborators__initials"
        :collaborator="{ id: value, name, agent }"
      />
      <div class="select-collaborators__dropdown-option">
        {{ name }}
      </div>
    </a>
  </li>
</template>

<script>
import CollaboratorAvatar from '@baserow/modules/core/components/CollaboratorAvatar'
import dropdownItem from '@baserow/modules/core/mixins/dropdownItem'

export default {
  name: 'FieldCollaboratorDropdownItem',
  components: { CollaboratorAvatar },
  mixins: [dropdownItem],
  props: {
    agent: { type: Boolean, default: false },
  },
}
</script>
