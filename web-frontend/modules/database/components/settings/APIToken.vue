<template>
  <div class="api-token">
    <div class="api-token__head">
      <div class="api-token__info">
        <div class="api-token__name">
          <div class="api-token__name-content">
            <Editable
              ref="rename"
              :value="token.name"
              @change="
                updateToken(
                  token,
                  { name: $event.value },
                  { name: $event.oldValue }
                )
              "
            ></Editable>
          </div>
          <a
            ref="contextLink"
            class="api-token__more"
            @click.prevent="
              $refs.context.toggle($refs.contextLink, 'bottom', 'right', 4)
            "
          >
            <i class="baserow-icon-more-horizontal"></i>
          </a>
          <Context ref="context" overflow-scroll max-height-if-outside-viewport>
            <div class="api-token__key">
              <div class="api-token__key-name">
                {{ $t('apiToken.tokenPrefix') }}
              </div>
              <div class="api-token__key-value">
                <template v-if="tokenVisible">
                  {{ token.key }}
                </template>
                <template v-else>••••••••••••••••••••••••••••••••</template>
              </div>
              <a
                class="api-token__key-visible"
                :title="$t('apiToken.showOrHide')"
                @click.prevent="tokenVisible = !tokenVisible"
              >
                <i
                  :class="
                    tokenVisible ? 'iconoir-eye-off' : 'iconoir-eye-empty'
                  "
                ></i>
              </a>
              <a
                class="api-token__key-copy"
                :title="$t('apiToken.copyToClipboard')"
                @click=";[copyTokenToClipboard(), $refs.copied.show()]"
              >
                <i class="iconoir-copy"></i>
                <Copied ref="copied"></Copied>
              </a>
            </div>
            <ul class="context__menu">
              <li class="context__menu-item">
                <nuxt-link
                  class="context__menu-item-link"
                  :to="{ name: 'database-api-docs' }"
                >
                  <i class="context__menu-item-icon iconoir-book"></i>
                  {{ $t('apiToken.viewAPIDocs') }}
                </nuxt-link>
              </li>
              <li class="context__menu-item">
                <a
                  class="context__menu-item-link"
                  :class="{
                    'context__menu-item-link--loading': rotateLoading,
                  }"
                  @click="rotateKey(token)"
                >
                  <i class="context__menu-item-icon iconoir-refresh-double"></i>
                  {{ $t('apiToken.generateNewToken') }}
                </a>
              </li>
              <li class="context__menu-item">
                <a class="context__menu-item-link" @click="enableRename()">
                  <i class="context__menu-item-icon iconoir-edit-pencil"></i>
                  {{ $t('action.rename') }}
                </a>
              </li>
              <li class="context__menu-item">
                <a
                  :class="{
                    'context__menu-item-link--loading': deleteLoading,
                  }"
                  class="context__menu-item-link"
                  @click.prevent="deleteToken(token)"
                >
                  <i class="context__menu-item-icon iconoir-bin"></i>
                  {{ $t('action.delete') }}
                </a>
              </li>
            </ul>
          </Context>
        </div>
        <div class="api-token__details">
          <div class="api-token__group">{{ workspace.name }}</div>
          <a class="api-token__expand" @click.prevent="open = !open">
            {{ $t('apiToken.showDatabases') }}
            <i
              :class="{
                'iconoir-nav-arrow-down': !open,
                'iconoir-nav-arrow-up': open,
              }"
            ></i>
          </a>
        </div>
      </div>
      <div class="api-token__permissions">
        <div
          v-for="(operationName, operation) in operations"
          :key="operation"
          class="api-token__permission"
        >
          <span class="margin-bottom-1">{{ operationName }}</span>
          <SwitchInput
            :value="isActive(operation)"
            small
            @input="toggle(operation, $event)"
          ></SwitchInput>
        </div>
      </div>
    </div>
    <div class="api-token__body" :class="{ 'api-token__body--open': open }">
      <div v-for="database in databases" :key="database.id">
        <div class="api-token__row">
          <div class="api-token__database">
            {{ database.name }} {{ database.id }}
          </div>
          <div class="api-token__permissions">
            <div
              v-for="(operationName, operation) in operations"
              :key="operation"
              class="api-token__permission"
            >
              <SwitchInput
                :value="isDatabaseActive(database, operation)"
                small
                @input="toggleDatabase(database, databases, operation, $event)"
              ></SwitchInput>
            </div>
          </div>
        </div>
        <div
          v-for="table in database.tables"
          :key="table.id"
          class="api-token__row"
        >
          <div class="api-token__table">
            {{ table.name }} <small>(id: {{ table.id }})</small>
          </div>
          <div class="api-token__permissions">
            <div
              v-for="(operationName, operation) in operations"
              :key="operation"
              class="api-token__permission"
            >
              <Checkbox
                v-if="
                  $hasPermission(
                    `database.table.${operation}_row`,
                    table,
                    workspace.id
                  )
                "
                :checked="isTableActive(table, database, operation)"
                @input="
                  toggleTable(table, database, databases, operation, $event)
                "
              ></Checkbox>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import TokenService from '@baserow/modules/database/services/token'

export default {
  name: 'APIToken',
  props: {
    token: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      open: false,
      deleteLoading: false,
      rotateLoading: false,
      tokenVisible: false,
      operations: {
        create: this.$t('apiToken.create'),
        read: this.$t('apiToken.read'),
        update: this.$t('apiToken.update'),
        delete: this.$t('apiToken.delete'),
      },
    }
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.token.workspace)
    },
    databases() {
      return this.$store.getters['application/getAllOfWorkspace'](
        this.workspace
      ).filter(
        (application) => application.type === DatabaseApplicationType.getType()
      )
    },
  },
  watch: {
    databases: {
      handler() {
        // if databases or tables change, we need to ensure that token permissions
        // are still valid
        this.removeInvalidPermissions()
      },
      deep: true,
    },
  },
  methods: {
    copyTokenToClipboard() {
      copyToClipboard(this.token.key)
    },
    enableRename() {
      this.$refs.context.hide()
      this.$refs.rename.edit()
    },
    /**
     * Updates some token properties. If the request fails the changes are going to be
     * reverted.
     */
    async updateToken(token, values, old) {
      Object.assign(token, values)

      try {
        await TokenService(this.$client).update(token.id, values)
      } catch (error) {
        Object.assign(token, old)
        notifyIf(error, 'token')
      }
    },
    /**
     * Asks the backend to rotate the key of the token.
     */
    async rotateKey(token) {
      this.rotateLoading = true

      try {
        const { data } = await TokenService(this.$client).rotateKey(token.id)
        this.token.key = data.key
        this.tokenVisible = true
        this.rotateLoading = false
      } catch (error) {
        this.rotateLoading = false
        notifyIf(error, 'token')
      }
    },
    /**
     * Deletes the token and emits a signal to the parent component such that is can
     * be removed from the list.
     */
    async deleteToken(token) {
      if (this.deleteLoading) {
        return
      }

      this.deleteLoading = true

      try {
        await TokenService(this.$client).delete(token.id)
        this.deleteLoading = false
        this.$emit('deleted')
      } catch (error) {
        this.deleteLoading = false
        notifyIf(error, 'field')
      }
    },
    /**
     * Check if a type (database or table) with the given id exists in the
     * permissions of the provided operation.
     */
    exists(operation, type, id) {
      const permissions = this.token.permissions[operation]
      if (Array.isArray(permissions)) {
        for (const i in permissions) {
          if (permissions[i][0] === type && permissions[i][1] === id) {
            return true
          }
        }
      }
      return false
    },
    /**
     * Adds a type (database or table) to the permissions of the given operation.
     */
    add(operation, type, id) {
      const permissions = this.token.permissions[operation]
      if (!Array.isArray(permissions)) {
        this.token.permissions[operation] = []
      }
      if (!this.exists(operation, type, id)) {
        this.token.permissions[operation].push([type, id])
      }
    },
    /**
     * Removes a type (database or table) to the permissions of the given operation.
     */
    remove(operation, type, id) {
      let permissions = this.token.permissions[operation]
      if (!Array.isArray(permissions)) {
        this.token.permissions[operation] = []
        permissions = []
      }
      this.token.permissions[operation] = permissions.filter((permission) => {
        return !(permission[0] === type && permission[1] === id)
      })
    },
    /**
     * Indicates if the token has permissions to all databases and tables for the given
     * operation. Returns 2 if there is only partially access.
     */
    isActive(operation) {
      const value = this.token.permissions[operation]
      if (value === true) {
        return true
      } else if (
        // If the value is false or if no permissions have been set we can show the
        // switch as if is empty.
        value === false ||
        (Array.isArray(value) && value.length === 0)
      ) {
        return false
      } else {
        return 2
      }
    },
    /**
     * Indicates if the token has permissions to the given database for the given
     * operation. Returns 2 if there is only partially access.
     */
    isDatabaseActive(database, operation) {
      if (
        this.isActive(operation) === true ||
        this.exists(operation, 'database', database.id)
      ) {
        return true
      }
      const tables = database.tables
      for (const i in tables) {
        if (this.exists(operation, 'table', tables[i].id)) {
          return 2
        }
      }
      return false
    },
    /**
     * Indicates if the token has permissions to the given table for the given
     * operation.
     */
    isTableActive(table, database, operation) {
      return (
        this.isActive(operation) === true ||
        this.exists(operation, 'database', database.id) ||
        this.exists(operation, 'table', table.id)
      )
    },
    /**
     * Indicates if the permission refer to a database or table still existent.
     * This fixes the problem that arises when user deletes a database or table from
     * another browser tab while this form is opened.
     * We need to delete the permissions that are pointing to the deleted database
     * before sending updates to the backend if we want to avoid errors.
     */
    removeInvalidPermissions() {
      const tokenPermissions = JSON.parse(
        JSON.stringify(this.token.permissions)
      )
      for (const [operation, permissions] of Object.entries(tokenPermissions)) {
        if (!Array.isArray(permissions)) {
          continue
        }
        permissions.forEach((permission) => {
          if (!this.isPermissionValid(permission)) {
            const [permType, permId] = permission
            this.remove(operation, permType, permId)
          }
        })
      }
    },
    isPermissionValid(permission) {
      const databases = this.databases
      const [permType, permId] = permission
      if (permType === 'database') {
        const database = databases.find((database) => database.id === permId)
        return database !== undefined
      } else if (permType === 'table') {
        return databases.find((database) => {
          const table = database.tables.find((table) => table.id === permId)
          return table !== undefined
        })
      }
    },
    /**
     * Changes the token permission state of all databases and tables of the given
     * operation. Also updates the permissions with the backend.
     */
    toggle(operation, value) {
      const oldPermissions = JSON.parse(JSON.stringify(this.token.permissions))
      // We can easily change the value to true or false because the permissions are
      // now going to be controlled on global (workspace) level.
      this.token.permissions[operation] = value
      this.updateToken(
        this.token,
        { permissions: this.token.permissions },
        { permissions: oldPermissions }
      )
    },
    /**
     * Changes the token permission state of a provided database and his tables of the
     * given operation. Also updates the permissions with the backend.
     */
    toggleDatabase(database, siblings, operation, value) {
      const oldPermissions = JSON.parse(JSON.stringify(this.token.permissions))

      // First we want to add all the databases that already have an active state to
      // the permissions because the permissions are not going to controlled on
      // database level.
      siblings
        .filter(
          (database) => this.isDatabaseActive(database, operation) === true
        )
        .forEach((database) => {
          this.add(operation, 'database', database.id)
        })

      // Remove all the child table permissions of the database because the
      // permissions are not going to controlled on database level.
      database.tables.forEach((table) => {
        this.remove(operation, 'table', table.id)
      })

      // Depending on the value we either need to remove the database from the list
      // or add it.
      if (value) {
        this.add(operation, 'database', database.id)
      } else {
        this.remove(operation, 'database', database.id)
      }

      // Updates the permissions with the backend.
      this.updateToken(
        this.token,
        { permissions: this.token.permissions },
        { permissions: oldPermissions }
      )
    },
    /**
     * Changes the token permission state of a provided table of the given operation.
     * Also updates the permissions with the backend.
     */
    toggleTable(table, database, databases, operation, value) {
      const oldPermissions = JSON.parse(JSON.stringify(this.token.permissions))

      // First we want to add all the databases that already have an active state to
      // the permissions because the permissions are now going to be controlled on
      // table level.
      databases
        .filter(
          (database) => this.isDatabaseActive(database, operation) === true
        )
        .forEach((database) => {
          this.add(operation, 'database', database.id)
        })

      // We also want to add all the tables that already have an active state to the
      // permissions.
      database.tables
        .filter(
          (table) => this.isTableActive(table, database, operation) === true
        )
        .forEach((table) => {
          this.add(operation, 'table', table.id)
        })

      // Depending on the value we either need to remove the database from the list
      // or add it.
      this.remove(operation, 'database', database.id)
      if (value) {
        this.add(operation, 'table', table.id)
      } else {
        this.remove(operation, 'table', table.id)
      }

      // Updates the permissions with the backend.
      this.updateToken(
        this.token,
        { permissions: this.token.permissions },
        { permissions: oldPermissions }
      )
    },
  },
}
</script>
