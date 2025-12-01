<template>
  <div>
    <div class="modal-sidebar__head">
      <Dropdown
        :value="selectedTrashWorkspace"
        :fixed-items="true"
        class="max-width-100"
        @input="emitIfNotAlreadySelectedTrashWorkspace($event)"
      >
        <DropdownItem
          v-for="workspace in workspaces"
          :key="workspace.id"
          :value="workspace"
          :name="workspace.name"
          :icon="workspace.trashed ? 'iconoir-bin' : null"
        ></DropdownItem>
      </Dropdown>
    </div>

    <template v-for="group in groupedApplicationsForSelectedWorkspace">
      <div :key="'title-' + group.type" class="modal-sidebar__title">
        {{ group.name }}
      </div>
      <ul :key="group.type" class="modal-sidebar__nav">
        <li v-for="application in group.applications" :key="application.id">
          <a
            class="modal-sidebar__nav-link"
            :class="{
              active: isSelectedApp(application),
              'text-decoration-line-through': application.trashed,
            }"
            @click="
              emitIfNotAlreadySelectedTrashApplication(
                selectedTrashWorkspace,
                application
              )
            "
          >
            <i class="modal-sidebar__nav-icon" :class="group.iconClass"></i>
            {{ application.name || 'Unnamed application ' + application.id }}
          </a>
        </li>
      </ul>
    </template>
  </div>
</template>

<script>
export default {
  name: 'TrashSidebar',
  props: {
    workspaces: {
      type: Array,
      required: true,
    },
    selectedTrashWorkspace: {
      type: Object,
      required: false,
      default: null,
    },
    selectedTrashApplication: {
      type: Object,
      required: false,
      default: null,
    },
  },
  computed: {
    groupedApplicationsForSelectedWorkspace() {
      const applicationTypes = Object.values(
        this.$registry.getAll('application')
      )
        .map((applicationType) => {
          const applications = this.selectedTrashWorkspace?.applications || []
          return {
            name: applicationType.getNamePlural(),
            type: applicationType.getType(),
            iconClass: applicationType.getIconClass(),
            applications: applications
              .filter((application) => {
                return application.type === applicationType.getType()
              })
              .sort((a, b) => a.order - b.order),
          }
        })
        .filter((group) => group.applications.length > 0)
      return applicationTypes
    },
  },
  methods: {
    isSelectedApp(app) {
      return (
        this.selectedTrashApplication !== null &&
        app.id === this.selectedTrashApplication.id
      )
    },
    emitIfNotAlreadySelectedTrashWorkspace(workspace) {
      if (!this.selectedTrashApplication !== null) {
        this.emitSelected({ workspace })
      }
    },
    emitIfNotAlreadySelectedTrashApplication(workspace, application) {
      if (!this.isSelectedApp(application)) {
        this.emitSelected({ workspace, application })
      }
    },
    emitSelected(selected) {
      this.$emit('selected', selected)
    },
  },
}
</script>
