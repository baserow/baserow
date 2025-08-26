<template>
  <div
    class="application-selector"
    :class="{ 'application-selector--disabled': disabled }"
  >
    <div class="application-selector__header">
      <h4 class="application-selector__title">
        {{ $t('importWorkspaceForm.selectApplicationsToImport') }}
      </h4>
      <div class="application-selector__actions">
        <button
          type="button"
          class="application-selector__action-btn"
          @click="selectAll"
        >
          {{ $t('exportWorkspaceForm.selectAll') }}
        </button>
        <button
          type="button"
          class="application-selector__action-btn"
          @click="deselectAll"
        >
          {{ $t('exportWorkspaceForm.deselectAll') }}
        </button>
      </div>
    </div>

    <div class="application-selector__tree">
      <div
        v-for="group in applicationGroups"
        :key="group.type"
        class="application-selector__group"
      >
        <div class="application-selector__group-header">
          <div class="application-selector__group-left">
            <Checkbox
              :checked="isGroupSelected(group)"
              :indeterminate="isGroupIndeterminate(group)"
              @input="(value) => handleGroupToggle(group, value)"
              @click.stop
            />
            <span
              class="application-selector__group-title"
              @click="handleGroupToggle(group, !isGroupSelected(group))"
            >
              {{ $t(`applicationType.${group.type}s`) }}
            </span>
          </div>
          <Icon
            :icon="
              groupExpanded[group.type]
                ? 'iconoir-nav-arrow-down'
                : 'iconoir-nav-arrow-right'
            "
            class="application-selector__group-arrow"
            @click="toggleGroupExpanded(group.type)"
          />
        </div>

        <div
          v-if="groupExpanded[group.type]"
          class="application-selector__group-items"
        >
          <div
            v-for="application in group.applications"
            :key="application.id"
            class="application-selector__item"
          >
            <div class="application-selector__item-main">
              <Checkbox
                :checked="selectedApplicationIds.includes(application.id)"
                @input="(value) => handleApplicationToggle(application, value)"
                @click.stop
              />
              <span
                class="application-selector__item-name"
                @click="
                  handleApplicationToggle(
                    application,
                    !selectedApplicationIds.includes(application.id)
                  )
                "
              >
                {{ application.name }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ImportApplicationSelector',
  props: {
    applicationGroups: {
      type: Array,
      required: true,
    },
    selectedApplicationIds: {
      type: Array,
      default: () => [],
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      groupExpanded: {},
    }
  },
  mounted() {
    this.applicationGroups.forEach((group) => {
      this.$set(this.groupExpanded, group.type, true)
    })
  },
  methods: {
    isGroupSelected(group) {
      const groupAppIds = group.applications.map((app) => app.id)
      return groupAppIds.every((id) => this.selectedApplicationIds.includes(id))
    },
    isGroupIndeterminate(group) {
      const groupAppIds = group.applications.map((app) => app.id)
      const selectedInGroup = groupAppIds.filter((id) =>
        this.selectedApplicationIds.includes(id)
      )
      return (
        selectedInGroup.length > 0 &&
        selectedInGroup.length < groupAppIds.length
      )
    },

    selectAll() {
      if (this.disabled) return
      const allApplicationIds = this.applicationGroups
        .flatMap((group) => group.applications)
        .map((app) => app.id)
      this.$emit('update', allApplicationIds)
    },
    deselectAll() {
      if (this.disabled) return
      this.$emit('update', [])
    },
    toggleGroupExpanded(groupType) {
      if (this.disabled) return
      this.$set(this.groupExpanded, groupType, !this.groupExpanded[groupType])
    },
    handleApplicationToggle(application, isChecked) {
      if (this.disabled) return
      const currentIds = [...this.selectedApplicationIds]
      const index = currentIds.indexOf(application.id)

      if (isChecked && index === -1) {
        currentIds.push(application.id)
      } else if (!isChecked && index !== -1) {
        currentIds.splice(index, 1)
      }

      this.$emit('update', currentIds)
    },
    handleGroupToggle(group, isChecked) {
      if (this.disabled) return
      const groupAppIds = group.applications.map((app) => app.id)
      let newIds = [...this.selectedApplicationIds]

      if (isChecked) {
        groupAppIds.forEach((id) => {
          if (!newIds.includes(id)) {
            newIds.push(id)
          }
        })
      } else {
        newIds = newIds.filter((id) => !groupAppIds.includes(id))
      }

      this.$emit('update', newIds)
    },
  },
}
</script>
