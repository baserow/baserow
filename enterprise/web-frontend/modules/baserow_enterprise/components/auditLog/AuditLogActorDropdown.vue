<template>
  <PaginatedDropdown
    ref="dropdown"
    :value="selectedKey"
    :fetch-page="fetchPage"
    :empty-item-display-name="$t('auditLog.allActors')"
    :not-selected-text="$t('auditLog.allActors')"
    show-search
    include-display-name-in-selected-event
    @input="selectActor"
  >
    <template #items="{ results }">
      <template v-for="group in actorGroups" :key="group.key">
        <DropdownSection
          v-if="resultsForGroup(results, group).length"
          :title="group.label"
        >
          <DropdownItem
            v-for="actor in resultsForGroup(results, group)"
            :key="actor.id"
            :name="actor.value"
            :value="actor.id"
            :icon="group.icon"
          />
        </DropdownSection>
      </template>
    </template>
  </PaginatedDropdown>
</template>

<script>
import DropdownItem from '@baserow/modules/core/components/DropdownItem'
import DropdownSection from '@baserow/modules/core/components/DropdownSection'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'

export default {
  name: 'AuditLogActorDropdown',
  components: { DropdownItem, DropdownSection, PaginatedDropdown },
  props: {
    value: {
      type: Object,
      default: null,
    },
    fetchPage: {
      type: Function,
      required: true,
    },
  },
  emits: ['input'],
  computed: {
    actorGroups() {
      return this.$registry.getList('subject').flatMap((type) => {
        const group = {
          key: type.type,
          type: type.type,
          label: type.getPluralTypeDisplayName(),
          icon: type.iconClass,
        }
        return type.isUser()
          ? [
              { ...group, userType: 'human' },
              {
                key: `${type.type}:identity`,
                type: type.type,
                userType: 'identity',
                label: this.$t('subjectType.identities'),
                icon: 'iconoir-lock',
              },
            ]
          : [group]
      })
    },
    selectedKey() {
      return this.value ? `${this.value.type}:${this.value.id}` : null
    },
  },
  methods: {
    clear() {
      this.$refs.dropdown.clear()
    },
    resultsForGroup(results, group) {
      return results.filter(
        (result) =>
          result.actor_type === group.type &&
          (!group.userType || (result.user_type || 'human') === group.userType)
      )
    },
    selectActor(selection) {
      const actor = selection?.item
      this.$emit(
        'input',
        actor ? { id: actor.actor_id, type: actor.actor_type } : null
      )
    },
  },
}
</script>
