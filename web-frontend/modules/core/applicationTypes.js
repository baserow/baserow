import { Registerable } from '@baserow/modules/core/registry'
import ApplicationForm from '@baserow/modules/core/components/application/ApplicationForm'

/**
 * The application type base class that can be extended when creating a plugin
 * for the frontend.
 */
export class ApplicationType extends Registerable {
  /**
   * The icon class name that is used as convenience for the user to
   * recognize certain application types. If you for example want the database
   * icon, you must return 'database' here. This will result in the classname
   * 'iconoir-database'.
   */
  getIconClass() {
    return null
  }

  /**
   * A human readable name of the application type.
   */
  getName() {
    return null
  }

  getNamePlural() {
    return null
  }

  /**
   * Small description of the application type, shown in the create new application
   * context menu.
   */
  getDescription() {
    return null
  }

  /**
   * A human readable default name for new applications of this type.
   */
  getDefaultName() {
    return this.getName()
  }

  /**
   * Returns whether the application type supports trash feature.
   * @returns true if tso.
   */
  supportsTrash() {
    return true
  }

  /**
   * The form component that will be rendered when creating a new instance of
   * this application. By default the ApplicationForm component is returned, but
   * this only contains a name field. If custom fields are required upon
   * creating they can be added with this component.
   */
  getApplicationFormComponent() {
    return ApplicationForm
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
   * The sidebar component that will be rendered in the sidebar of the templates
   * modal. It should represent an application that is in the template and should
   * also give the possibility to select that application.
   */
  getTemplateSidebarComponent() {
    return null
  }

  /**
   * When an application is selected in the templates modal, it must show a
   * preview. This method should return a component that shows this preview if
   * this application is selected.
   */
  getTemplatesPageComponent() {
    return null
  }

  /**
   * Should return an object that will be passed as property into the component
   * returned by the `getTemplatesPageComponent` method. It can for example
   * contain the selected application id.
   */
  getTemplatePage(application) {
    return null
  }

  /**
   * Should return an array where the first element is the describing name of the
   * dependents in singular and the second element in plural. Can be null if there
   * aren't any dependants.
   *
   * Example: ['table', 'tables']
   * Result in singular: There is 1 table
   * Result in plural: There are 2 tables
   */
  getDependentsName() {
    return [null, null]
  }

  /**
   * When deleting or listing an application we might want to give a quick overview
   * which children / dependents there are. This method should return a list
   * containing an object with an id, iconClass and name.
   */
  getDependents() {
    return []
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()

    if (this.type === null) {
      throw new Error('The type name of an application type must be set.')
    }
    if (this.iconClass === null) {
      throw new Error('The icon class of an application type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of an application type must be set.')
    }
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      name: this.getName(),
      routeName: this.routeName,
      hasSidebarComponent: this.getSidebarComponent() !== null,
    }
  }

  /**
   * Every time a fresh application object is fetched from the backend, it will
   * be populated, this is the moment to update some values. Because each
   * application can have unique properties, they might need to be populated.
   * This method can be overwritten in order the populate the correct values.
   */
  populate(application) {
    return application
  }

  /**
   * When an application is deleted it could be that an action should be taken,
   * like redirect the user to another page. This method is called when application
   * of this type is deleted.
   */
  delete(application, context) {}

  /**
   * When an application is selected, for example from the dashboard, an action needs to
   * be taken. For example when a database is selected the user will be redirected to
   * the first table of that database.
   *
   * @return Whether selecting was successful.
   */
  select(application, context) {
    return true
  }

  /**
   *
   */
  clearChildrenSelected(application) {}

  /**
   * Before the application values are updated, they can be modified here. This
   * might be needed because providing certain values could break the update.
   */
  prepareForStoreUpdate(application, data) {
    return data
  }

  /**
   * Indicates whether the given application is visible in the sidebar or dashboard view
   */
  isVisible(application) {
    return true
  }

  /**
   * Indicates whether the application can be created with the create new application
   * context.
   */
  canBeCreated() {
    return true
  }

  /**
   * Returns the development stage of the application type.
   */
  get developmentStage() {
    return null
  }

  getOrder() {
    return 50
  }
}
