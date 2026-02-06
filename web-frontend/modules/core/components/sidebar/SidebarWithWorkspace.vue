<template>
  <div class="sidebar__section sidebar__section--scrollable">
    <div class="sidebar__section-scrollable">
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
            <div
              class="tree__heading"
              :class="{
                'margin-bottom-2':
                  applicationGroup.applications.length === 0 &&
                  index < groupedApplicationsForSelectedWorkspace.length - 1,
              }"
            >
              <div class="tree__heading-name">
                {{ applicationGroup.name }}
              </div>
              <a
                v-if="canCreateApplication"
                :ref="'createApplicationModalToggle' + applicationGroup.type"
                class="tree__heading-add"
                @click="openCreateApplicationModal(applicationGroup.type)"
              >
                <i class="iconoir-plus"></i>
                <CreateApplicationModal
                  :ref="'createApplicationModal' + applicationGroup.type"
                  :application-type="applicationGroup.applicationType"
                  :workspace="selectedWorkspace"
                ></CreateApplicationModal>
              </a>
            </div>
            <ul
              class="tree"
              :class="{
                'margin-bottom-0': pendingJobs[applicationGroup.type].length,
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
            <ul v-if="pendingJobs[applicationGroup.type].length" class="tree">
              <component
                :is="getPendingJobComponent(job)"
                v-for="job in pendingJobs[applicationGroup.type]"
                :key="job.id"
                :job="job"
              >
              </component>
            </ul>
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
import { notifyIf } from '@baserow/modules/core/utils/error'
import CreateApplicationModal from '@baserow/modules/core/components/application/CreateApplicationModal'
import CreateApplicationContext from '@baserow/modules/core/components/application/CreateApplicationContext'

export default {
  name: 'SidebarWithWorkspace',
  components: { CreateApplicationContext, CreateApplicationModal },
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
  computed: {
    /**
     * Because all the applications that belong to the user are in the store we will
     * filter on the selected workspace here.
     */
    groupedApplicationsForSelectedWorkspace() {
      const applicationTypes = this.$registry
        .getOrderedList('application')
        .map((applicationType) => {
          return {
            name: applicationType.getNamePlural(),
            type: applicationType.getType(),
            applicationType: applicationType,
            developmentStage: applicationType.developmentStage,
            applications: this.applications
              .filter((application) => {
                return (
                  application.workspace.id === this.selectedWorkspace.id &&
                  application.type === applicationType.getType() &&
                  applicationType.isVisible(application)
                )
              })
              .sort((a, b) => a.order - b.order),
          }
        })
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
