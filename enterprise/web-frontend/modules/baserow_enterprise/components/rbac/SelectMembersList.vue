<template>
  <div class="select-members-list">
    <div>
      <FormInput
        v-model="activeSearchTerm"
        size="large"
        :placeholder="$t('selectMembersList.searchPlaceholder')"
        @keyup="search(activeSearchTerm)"
      ></FormInput>

      <div class="margin-top-2">
        {{
          $t('selectMembersList.selectedAmountLabel', {
            count: usersSelected.length,
          })
        }}
      </div>
    </div>
    <List
      class="margin-top-2 select-members-list__items"
      :items="usersFiltered"
      :attributes="['email']"
      selectable
      @selected="userSelected"
    >
      <template #left-side="{ item }">
        <Avatar
          class="margin-left-1"
          rounded
          size="medium"
          :initials="item.name | nameAbbreviation"
        ></Avatar>

        <span
          v-tooltip="item.name"
          class="margin-left-1 select-members-list__user-name"
        >
          {{ item.name }}
        </span>
      </template>
    </List>
  </div>
</template>

<script>
import SelectSubjectsListFooter from '@baserow_enterprise/components/rbac/SelectSubjectsListFooter'

export default {
  name: 'SelectMembersList',
  components: { SelectSubjectsListFooter },
  props: {
    users: {
      type: Array,
      required: false,
      default: () => [],
    },
    showRoleSelector: {
      type: Boolean,
      default: false,
    },
    scopeType: {
      type: String,
      required: true,
    },
    usersSelected: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  data() {
    return {
      usersFiltered: this.users,
      activeSearchTerm: null,
    }
  },
  computed: {
    searchAbleAttributes() {
      return ['name', 'email']
    },
  },
  methods: {
    search(value) {
      if (value === null || value === '' || this.users.length === 0) {
        this.usersFiltered = this.users
      } else {
        const valueSanitised = value.trim().toLowerCase()
        this.usersFiltered = this.users.filter((user) =>
          this.searchAbleAttributes.some((attribute) =>
            user[attribute].toLowerCase().includes(valueSanitised)
          )
        )
      }
    },
    userSelected({ value, item }) {
      if (value) {
        this.usersSelected.push(item)
      } else {
        const index = this.usersSelected.findIndex(
          (user) => user.id === item.id
        )
        this.usersSelected.splice(index, 1)
      }
    },
  },
}
</script>
