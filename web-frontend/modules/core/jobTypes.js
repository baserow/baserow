import { notifyIf } from '@baserow/modules/core/utils/error'
import { Registerable } from '@baserow/modules/core/registry'
import SidebarApplicationPendingJob from '@baserow/modules/core/components/sidebar/SidebarApplicationPendingJob'
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'

/**
 * The job type base class that can be extended when creating a plugin
 * for the frontend.
 */
export class JobType extends Registerable {
  /**
   * The icon class name that is used as convenience for the user to
   * recognize certain job types. If you for example want the database
   * icon, you must return 'database' here. This will result in the classname
   * 'iconoir-database'.
   */
  getIconClass() {
    return null
  }

  /**
   * A human readable name of the job type.
   */
  getName() {
    return null
  }

  /**
   * Returns the text to show in the sidebar when the job is running.
   */
  getSidebarText(job) {
    return ''
  }

  /**
   * The sidebar component will be rendered in the sidebar if the application is
   * in the selected workspace. All the applications of a workspace are listed in the
   * sidebar and this component should give the user the possibility to select
   * that application.
   */
  getSidebarComponent() {
    return null
  }

  /**
   * The left sidebar groups the applications. This method can optionally return an
   * application type. If that's the case, then the job animation will be put in
   * that application group. If nothing is provided, then the job will be put outside
   * of the applications.
   */
  getSidebarApplicationTypeLocation(job) {
    return null
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()

    if (this.type === null) {
      throw new Error('The type name of an application type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of an application type must be set.')
    }
  }

  /**
   * Every time a fresh job object is fetched from the backend, it will
   * be populated, this is the moment to update some values. Because each
   * jobType can have unique properties, they might need to be populated.
   * This method can be overwritten in order the populate the correct values.
   */
  populate(job) {
    return job
  }

  /**
   * Returns true if the specific job is part of the workspace
   */
  isJobPartOfWorkspace(job, workspace) {
    return false
  }

  /**
   * Returns true if the specific job is part of the application
   */
  isJobPartOfApplication(job, application) {
    return false
  }

  /**
   * When an application is deleted it could be that an action should be taken,
   * like redirect the user to another page. This method is called when application
   * of this type is deleted.
   */
  beforeDelete(job) {}

  /**
   * Before the application values are updated, they can be modified here. This
   * might be needed because providing certain values could break the update.
   */
  async beforeUpdate(job, data) {}

  async afterUpdate(job, data) {
    switch (job.state) {
      case 'cancelled':
        await this.onJobCancelled(job, data)
        break
      case 'failed':
        await this.onJobFailed(job, data)
        break
      case 'finished':
        await this.onJobDone(job, data)
        break
      default:
        break
    }
  }

  async onJobDone(job, data) {}
  async onJobFailed(job, data) {}
  async onJobCancelled(job, data) {}
}

export class DuplicateApplicationJobType extends JobType {
  static getType() {
    return 'duplicate_application'
  }

  getIconClass(job) {
    const applicationTypeName = job.original_application.type
    if (!this.app.$registry.exists('application', applicationTypeName)) {
      return 'iconoir-db'
    }
    return this.app.$registry
      .get('application', applicationTypeName)
      .getIconClass()
  }

  getName() {
    return 'duplicateApplication'
  }

  getSidebarText(job) {
    const { $i18n: i18n } = this.app
    return i18n.t('duplicateApplicationJobType.duplicating') + '... '
  }

  getSidebarComponent() {
    return SidebarApplicationPendingJob
  }

  getSidebarApplicationTypeLocation(job) {
    return job.original_application.type
  }

  isJobPartOfWorkspace(job, workspace) {
    return job.original_application.workspace.id === workspace.id
  }

  async onJobDone(job) {
    const { $i18n: i18n, $store: store } = this.app
    const application = job.duplicated_application
    try {
      await store.dispatch('application/forceCreate', application)
      store.dispatch('toast/info', {
        title: i18n.t('duplicateApplicationJobType.duplicatedTitle'),
        message: application.name,
      })
    } catch (error) {
      notifyIf(error, 'application')
    } finally {
      await store.dispatch('job/forceDelete', job)
    }
  }

  async onJobFailed(job) {
    const { $i18n: i18n, $store: store } = this.app
    await store.dispatch(
      'toast/error',
      {
        title: i18n.t('clientHandler.notCompletedTitle'),
        message: job.human_readable_error,
      },
      { root: true }
    )
    await store.dispatch('job/forceDelete', job)
  }
}

export class InstallTemplateJobType extends JobType {
  static getType() {
    return 'install_template'
  }

  getIconClass() {
    // TODO: This should be moved to a registry and in the database module.
    return 'iconoir-db'
  }

  getName() {
    return 'installTemplate'
  }

  getSidebarText(job) {
    const { $i18n: i18n } = this.app
    return i18n.t('InstallTemplateJobType.installing') + '... '
  }

  getSidebarComponent() {
    return SidebarApplicationPendingJob
  }

  isJobPartOfWorkspace(job, workspace) {
    return job.workspace.id === workspace.id
  }

  async onJobDone(job) {
    const { $i18n: i18n, $store: store } = this.app
    // Installing a template has just created a couple of applications in the
    // workspace. The response contains those applications and we can add them to the
    // store so that the user can view the installed template right away.
    const installedApplications = job.installed_applications
    try {
      for (const application of installedApplications) {
        await store.dispatch('application/forceCreate', application)
      }
      if (!this.showsInstallToast()) {
        store.dispatch('toast/info', {
          title: i18n.t('InstallTemplateJobType.installedTitle'),
          message: installedApplications[0].name,
        })
      }
    } catch (error) {
      notifyIf(error, 'application')
    } finally {
      // The template is installed even if adding the applications to the store
      // failed, and the toast mustn't keep showing the progress.
      if (this.showsInstallToast()) {
        await this.updateInstallToast(job)
      }
      await store.dispatch('job/forceDelete', job)
    }
  }

  async onJobFailed(job) {
    const { $i18n: i18n, $store: store } = this.app
    if (this.showsInstallToast()) {
      await this.updateInstallToast(job)
    } else {
      await store.dispatch(
        'toast/error',
        {
          title: i18n.t('clientHandler.notCompletedTitle'),
          message: i18n.t('clientHandler.notCompletedDescription'),
        },
        { root: true }
      )
    }
    await store.dispatch('job/forceDelete', job)
  }

  async onJobCancelled(job) {
    if (this.showsInstallToast()) {
      const toast = this.findInstallToast(job)
      if (toast) {
        await this.app.$store.dispatch('toast/remove', toast)
      }
    }
    // A cancelled install mustn't stay in the sidebar as a pending one.
    await this.app.$store.dispatch('job/forceDelete', job)
  }

  /**
   * The template browser behind the flag shows the progress and the result of an
   * install in an install toast. The legacy one shows a toast with the name of the
   * first installed application.
   */
  showsInstallToast() {
    return this.app.$featureFlagIsEnabled(FF_USER_TEMPLATES)
  }

  findInstallToast(job) {
    return this.app.$store.state.toast.items.find(
      (toast) =>
        toast.type === 'installTemplate' && toast.data?.jobId === job.id
    )
  }

  /**
   * Writes the final fields of the job into its install toast, or shows one if there
   * is none, because the progress was shown in the sidebar. The toast then shows the
   * result after the job is removed from the store.
   */
  async updateInstallToast(job) {
    const store = this.app.$store
    const data = {
      jobId: job.id,
      state: job.state,
      installed_applications: job.installed_applications,
      human_readable_error: job.human_readable_error,
      template_name: job.template?.name,
    }
    const toast = this.findInstallToast(job)
    if (toast) {
      await store.dispatch('toast/update', { toast, data })
    } else {
      await store.dispatch('toast/add', { type: 'installTemplate', data })
    }
  }
}

export class CreateUserTemplateJobType extends JobType {
  static getType() {
    return 'create_user_template'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('createUserTemplateJobType.name')
  }
}

export class CreateSnapshotJobType extends JobType {
  static getType() {
    return 'create_snapshot'
  }

  getName() {
    return 'createSnapshot'
  }
}

export class RestoreSnapshotJobType extends JobType {
  static getType() {
    return 'restore_snapshot'
  }

  getName() {
    return 'restoreSnapshot'
  }
}

export class ExportApplicationsJobType extends JobType {
  static getType() {
    return 'export_applications'
  }

  getName() {
    return 'exportApplications'
  }
}

export class ImportApplicationsJobType extends JobType {
  static getType() {
    return 'import_applications'
  }

  getName() {
    return 'importApplications'
  }
}
