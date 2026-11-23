<template>
  <div
    class="sidebar__section sidebar__section--scrollable sidebar__section--workspace"
  >
    <div class="sidebar__section-scrollable" tabindex="-1">
      <div
        class="sidebar__section-scrollable-inner"
        data-highlight="applications"
      >
        <ul v-if="pendingJobs[null].length" class="tree">
          <component
            :is="getPendingJobComponent(job)"
            v-for="job in pendingJobs[null]"
            :key="job.id"
            :job="job"
          >
          </component>
        </ul>
        <ul class="tree">
          <li
            v-for="(
              applicationGroup, index
            ) in groupedApplicationsForSelectedWorkspace"
            :key="applicationGroup.type"
          >
            <div class="tree__heading">
              <button
                type="button"
                class="tree__heading-name"
                tabindex="-1"
                :aria-expanded="!collapsedGroups[applicationGroup.key]"
                :aria-controls="`${sidebarId}-${applicationGroup.type}`"
                @click="toggleApplicationGroup(applicationGroup.key)"
              >
                {{ applicationGroup.name }}
                <span class="tree__heading-chevron" aria-hidden="true">
                  <i class="iconoir-nav-arrow-down"></i>
                  <i class="iconoir-nav-arrow-right"></i>
                </span>
              </button>
              <a
                v-if="
                  canCreateApplication &&
                  applicationGroup.applicationType.canBeCreated()
                "
                :ref="'createApplicationModalToggle' + applicationGroup.type"
                class="tree__heading-add"
                @click="openCreateApplicationModal(applicationGroup.type)"
              >
                <i class="iconoir-plus"></i>
                <component
                  :is="
                    applicationGroup.applicationType.getCreateModalComponent()
                  "
                  :ref="'createApplicationModal' + applicationGroup.type"
                  :application-type="applicationGroup.applicationType"
                  :workspace="selectedWorkspace"
                ></component>
              </a>
            </div>
            <div
              :id="`${sidebarId}-${applicationGroup.type}`"
              class="tree__group"
              :inert="collapsedGroups[applicationGroup.key] ? '' : null"
            >
              <div class="tree__group-content">
                <ul
                  class="tree"
                  :class="{
                    'margin-bottom-0':
                      pendingJobs[applicationGroup.type].length,
                  }"
                  :data-highlight="`applications-${applicationGroup.type}`"
                >
                  <component
                    :is="getApplicationComponent(application)"
                    v-for="application in applicationGroup.applications"
                    :key="application.id"
                    v-sortable="{
                      id: application.id,
                      update: orderApplications,
                      handle: '[data-sortable-handle]',
                      marginTop: -1.5,
                      enabled: $hasPermission(
                        'workspace.order_applications',
                        selectedWorkspace,
                        selectedWorkspace.id
                      ),
                    }"
                    :application="application"
                    :pending-jobs="pendingJobs[application.type]"
                    :workspace="selectedWorkspace"
                  ></component>
                </ul>
                <ul
                  v-if="pendingJobs[applicationGroup.type].length"
                  class="tree"
                >
                  <component
                    :is="getPendingJobComponent(job)"
                    v-for="job in pendingJobs[applicationGroup.type]"
                    :key="job.id"
                    :job="job"
                  >
                  </component>
                </ul>
              </div>
            </div>
            <div
              v-if="index < groupedApplicationsForSelectedWorkspace.length - 1"
              class="tree__separator"
            ></div>
          </li>
        </ul>
      </div>
    </div>
    <div
      v-if="
        $hasPermission(
          'workspace.create_application',
          selectedWorkspace,
          selectedWorkspace.id
        )
      "
      class="sidebar__new-wrapper sidebar__new-wrapper--separator"
      data-highlight="create-new"
    >
      <a
        ref="createApplicationContextLink"
        class="sidebar__new"
        @click="
          $refs.createApplicationContext.toggle(
            $refs.createApplicationContextLink
          )
        "
      >
        <i class="sidebar__new-icon iconoir-plus"></i>
        {{ $t('action.createNew') }}...
      </a>
    </div>
    <CreateApplicationContext
      ref="createApplicationContext"
      :workspace="selectedWorkspace"
    ></CreateApplicationContext>
  </div>
</template>

<script>
import { useId } from 'vue'
import { notifyIf } from '@baserow/modules/core/utils/error'
import CreateApplicationContext from '@baserow/modules/core/components/application/CreateApplicationContext'

export default {
  name: 'SidebarWithWorkspace',
  components: { CreateApplicationContext },
  props: {
    applications: {
      type: Array,
      required: true,
    },
    selectedWorkspace: {
      type: Object,
      required: true,
    },
  },
  setup() {
    const sidebarId = useId()
    const collapsedGroups = useState(
      'sidebar-collapsed-application-groups',
      () => ({})
    )
    return { sidebarId, collapsedGroups }
  },
  computed: {
    /**
     * Because all the applications that belong to the user are in the store we will
     * filter on the selected workspace here.
     */
    groupedApplicationsForSelectedWorkspace() {
      const applicationTypes = this.$registry
        .getOrderedList('application')
        .map((applicationType) => {
          const type = applicationType.getType()
          return {
            name: applicationType.getNamePlural(),
            type,
            key: `${this.selectedWorkspace.id}:${type}`,
            applicationType: applicationType,
            developmentStage: applicationType.developmentStage,
            applications: this.applications
              .filter((application) => {
                return (
                  application.workspace.id === this.selectedWorkspace.id &&
                  application.type === type &&
                  applicationType.isVisible(application)
                )
              })
              .sort((a, b) => a.order - b.order),
          }
        })
        .filter(
          ({ applicationType, applications }) =>
            applications.length > 0 || applicationType.canBeCreated()
        )
      return applicationTypes
    },
    pendingJobs() {
      const grouped = { null: [] }
      Object.values(this.$registry.getAll('application')).forEach(
        (applicationType) => {
          grouped[applicationType.getType()] = []
        }
      )
      this.$store.getters['job/getAll'].forEach((job) => {
        const jobType = this.$registry.get('job', job.type)
        if (jobType.isJobPartOfWorkspace(job, this.selectedWorkspace)) {
          grouped[jobType.getSidebarApplicationTypeLocation(job)].push(job)
        }
      })
      return grouped
    },
    canCreateApplication() {
      return this.$hasPermission(
        'workspace.create_application',
        this.selectedWorkspace,
        this.selectedWorkspace.id
      )
    },
  },
  methods: {
    toggleApplicationGroup(key) {
      this.collapsedGroups[key] = !this.collapsedGroups[key]
    },
    getApplicationComponent(application) {
      return this.$registry
        .get('application', application.type)
        .getSidebarComponent()
    },
    getPendingJobComponent(job) {
      return this.$registry.get('job', job.type).getSidebarComponent()
    },
    async orderApplications(order, oldOrder) {
      try {
        await this.$store.dispatch('application/order', {
          workspace: this.selectedWorkspace,
          order,
          oldOrder,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    openCreateApplicationModal(type) {
      if (!this.canCreateApplication) {
        return
      }

      const target = this.$refs['createApplicationModalToggle' + type]
      this.$refs['createApplicationModal' + type][0].toggle(target)
    },
  },
}
</script>
