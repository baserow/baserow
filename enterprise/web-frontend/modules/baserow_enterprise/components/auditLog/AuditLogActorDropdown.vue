<template>
  <PaginatedDropdown
    ref="dropdown"
    :value="selectedKey"
    :fetch-page="fetchPage"
    :empty-item-display-name="$t('auditLog.allActors')"
    :not-selected-text="$t('auditLog.allActors')"
    :show-search="false"
    include-display-name-in-selected-event
    @input="selectActor"
  >
    <template #items="{ results }">
      <template v-for="subjectType in subjectTypes" :key="subjectType.type">
        <DropdownSection
          v-if="resultsForType(results, subjectType.type).length"
          :title="subjectType.getPluralTypeDisplayName()"
        >
          <DropdownItem
            v-for="actor in resultsForType(results, subjectType.type)"
            :key="actor.id"
            :name="actor.value"
            :value="actor.id"
            :icon="subjectType.iconClass"
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
    subjectTypes() {
      return this.$registry.getList('subject')
    },
    selectedKey() {
      return this.value ? `${this.value.type}:${this.value.id}` : null
    },
  },
  methods: {
    clear() {
      this.$refs.dropdown.clear()
    },
    resultsForType(results, type) {
      return results.filter((result) => result.actor_type === type)
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
