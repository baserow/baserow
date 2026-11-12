<template>
  <li
    v-if="visible"
    class="select__item select__item--no-options"
    :class="{
      hidden: !isVisible(query),
      visible: isVisible(query),
      active: isActive(value),
      disabled,
      hover: isHovering(value),
    }"
    role="listitem"
  >
    <a
      class="select__item-link"
      @click="select(value, disabled)"
      @mousemove="hover(value, disabled)"
    >
      <div class="select__item-name">
        <div class="field-permission-subjects__dropdown-option">
          <component
            :is="$registry.get('subject', result.subjectType).avatarComponent"
            v-if="result.subjectType === userSubjectType"
            :subject="result.subject"
            size="large"
          />
          <span
            v-else
            class="field-permission-subjects__team-icon field-permission-subjects__team-icon--dropdown"
          >
            <i
              :class="$registry.get('subject', result.subjectType).iconClass"
            ></i>
          </span>
          <span class="field-permission-subjects__details">
            <span class="field-permission-subjects__label">
              {{ result.label }}
            </span>
            <small v-if="result.description">
              {{ result.description }}
            </small>
          </span>
        </div>
      </div>
    </a>
    <i class="select__item-active-icon iconoir-check"></i>
  </li>
</template>

<script>
import dropdownItem from '@baserow/modules/core/mixins/dropdownItem'

const USER_SUBJECT_TYPE = 'auth.User'

export default {
  name: 'FieldPermissionSubjectDropdownItem',
  mixins: [dropdownItem],
  props: {
    result: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      userSubjectType: USER_SUBJECT_TYPE,
    }
  },
}
</script>
