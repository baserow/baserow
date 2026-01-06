import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import Sidebar from '@baserow/modules/database/components/sidebar/Sidebar'
import TemplateSidebar from '@baserow/modules/database/components/sidebar/TemplateSidebar'
import TableTemplate from '@baserow/modules/database/components/table/TableTemplate'
import { populateTable } from '@baserow/modules/database/store/table'
import GridViewRowExpandButton from '@baserow/modules/database/components/view/grid/GridViewRowExpandButton'
import DatabaseForm from '@baserow/modules/database/components/form/DatabaseForm'
import ApplicationContext from '@baserow/modules/database/components/application/ApplicationContext'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick } from '#imports'

export class DatabaseApplicationType extends ApplicationType {
  static getType() {
    return 'database'
  }

  /**
   * @return The component to use as the button the user clicks to expand and view the
   *    row edit modal for a particular row. Takes a single row prop and should emit a
   *    'edit-modal' event when clicked with the row as the event.
   */
  getRowExpandButtonComponent() {
    return GridViewRowExpandButton
  }

  getIconClass() {
    return 'iconoir-db'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.database')
  }

  getNamePlural() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.databases')
  }

  getDescription() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.databaseDesc')
  }

  getDefaultName() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.databaseDefaultName')
  }

  getSidebarComponent() {
    return Sidebar
  }

  getApplicationContextComponent() {
    return ApplicationContext
  }

  getTemplateSidebarComponent() {
    return TemplateSidebar
  }

  getTemplatesPageComponent() {
    return TableTemplate
  }

  getTemplatePage(application) {
    if (application.tables.length === 0) {
      return null
    }
    return {
      database: application,
      table: application.tables[0],
    }
  }

  getDependentsName() {
    return ['table', 'tables']
  }

  getDependents(database) {
    return database.tables.map((table) => {
      return {
        id: table.id,
        iconClass: 'table',
        name: table.name,
      }
    })
  }

  populate(application) {
    const tables = application.tables.map((table) => populateTable(table))
    return {
      ...super.populate(application),
      tables,
    }
  }

  /**
   * When a table of the deleted database is selected we must redirect back to
   * the dashboard because that page doesn't exist anymore.
   */
  delete(application, { $router }) {
    const tableSelected = application.tables.some((table) => table._.selected)
    if (tableSelected) {
      $router.push({ name: 'dashboard' })
    }
  }

  async select(application, { $router, $store, $i18n }) {
    const tables = application.tables
      .map((t) => t)
      .sort((a, b) => a.order - b.order)

    if (tables.length > 0) {
      await $router.push({
        name: 'database-table',
        params: {
          databaseId: application.id,
          tableId: tables[0].id,
        },
      })
      await pageFinished()
      await nextTick()
      return true
    } else {
      $store.dispatch('toast/error', {
        title: $i18n.t('applicationType.cantSelectTableTitle'),
        message: $i18n.t('applicationType.cantSelectTableDescription'),
      })
      return false
    }
  }

  /**
   * When another database is selected in the sidebar we have the change the
   * selected state of all the table children.
   */
  // TODO MIG see comment in application store to understand why it was removed
  /*clearChildrenSelected(application) {
    Object.values(application.tables).forEach((table) => {
      if (table._.selected) {
        table._.selected = false
      }
    })
  }*/

  /**
   * It is not possible to update the tables by updating the application. In fact,
   * providing the tables as value could break the current table state. That is why
   * we remove it here.
   */
  prepareForStoreUpdate(application, data) {
    if (Object.prototype.hasOwnProperty.call(data, 'tables')) {
      delete data.tables
    }
    return data
  }

  getApplicationFormComponent() {
    return DatabaseForm
  }

  getOrder() {
    return 20
  }
}
