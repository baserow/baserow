<template>
  <div class="api-docs">
    <div ref="header" class="api-docs__header">
      <nuxt-link :to="{ name: 'index' }" class="api-docs__logo">
        <Logo />
      </nuxt-link>
      <a
        ref="databasesToggle"
        class="api-docs__switch"
        @click.prevent="databasesOpen = !databasesOpen"
      >
        <i class="api-docs__switch-icon iconoir-db"></i>
        {{ $t('apiDocsDatabase.pageTitle', database) }}
      </a>
      <div class="api-docs__open">
        <Button
          v-if="database.tables.length > 0"
          tag="nuxt-link"
          :to="{
            name: 'database-table',
            params: {
              databaseId: database.id,
              tableId: database.tables[0].id,
            },
          }"
          type="secondary"
          >{{ $t('apiDocsDatabase.openDatabase') }}</Button
        >
      </div>
    </div>
    <div v-show="databasesOpen" ref="databases" class="api-docs__databases">
      <div class="api-docs__databases-inner">
        <APIDocsSelectDatabase :selected="database.id" />
        <nuxt-link :to="{ name: 'dashboard' }" class="select-application__back">
          <i class="iconoir-arrow-left"></i>
          {{ $t('apiDocsDatabase.back') }}
        </nuxt-link>
      </div>
    </div>
    <APIDocsMenu
      :database="database"
      :navigate="navigate"
      :nav-active="navActive"
      :password-fields="passwordFields"
    />
    <div class="api-docs__body">
      <APIDocsIntro :database="database" />
      <APIDocsAuth v-model="exampleData" />

      <div v-for="table in database.tables" :key="table.id">
        <APIDocsTableFields
          v-if="fields"
          :table="table"
          :fields="fields"
          :navigate="navigate"
        />
        <APIDocsTableListFields
          v-model="exampleData"
          :table="table"
          :fields="fields"
        />
        <APIDocsTableListRows
          v-model="exampleData"
          :table="table"
          :fields="fields"
          :navigate="navigate"
          :get-list-url="getListURL"
          :get-response-item="getResponseItem"
          :get-field-mapping="getFieldMapping"
        />
        <APIDocsTableGetRow
          v-model="exampleData"
          :table="table"
          :get-item-url="getItemURL"
          :get-response-item="getResponseItem"
          :get-field-mapping="getFieldMapping"
        />
        <APIDocsTableCreateRow
          v-model="exampleData"
          :table="table"
          :without-read-only="withoutReadOnly"
          :user-field-names="exampleData.userFieldNames"
          :get-list-url="getListURL"
          :get-request-example="getRequestExample"
          :get-batch-request-example="getBatchRequestExample"
          :get-batch-response-item="getBatchResponseItems"
          :get-response-item="getResponseItem"
          :get-field-mapping="getFieldMapping"
        />
        <APIDocsTableUpdateRow
          v-model="exampleData"
          :table="table"
          :without-read-only="withoutReadOnly"
          :user-field-names="exampleData.userFieldNames"
          :get-item-url="getItemURL"
          :get-list-url="getListURL"
          :get-request-example="getRequestExample"
          :get-batch-request-example="getBatchRequestExample"
          :get-batch-response-item="getBatchResponseItems"
          :get-response-item="getResponseItem"
          :get-field-mapping="getFieldMapping"
        />
        <APIDocsTableMoveRow
          v-model="exampleData"
          :table="table"
          :user-field-names="exampleData.userFieldNames"
          :get-item-url="getItemURL"
          :get-response-item="getResponseItem"
          :get-field-mapping="getFieldMapping"
        />
        <APIDocsTableDeleteRow
          v-model="exampleData"
          :table="table"
          :get-item-url="getItemURL"
          :get-delete-list-url="getDeleteListURL"
          :get-batch-delete-request-example="getBatchDeleteRequestExample"
        />
        <div v-for="field in passwordFields[table.id]" :key="field.id">
          <APIDocsTablePasswordFieldAuthentication
            v-model="exampleData"
            :field="field"
            :table="table"
          />
        </div>
      </div>
      <APIDocsUploadFile
        v-model="exampleData"
        :get-upload-file-list-url="getUploadFileListUrl"
        :get-upload-file-example="getUploadFileExample"
        :get-upload-file-response="getUploadFileResponse"
      />
      <APIDocsListTables v-model="exampleData" />
      <APIDocsUploadFileViaURL
        v-model="exampleData"
        :get-upload-file-response="getUploadFileResponse"
        :get-upload-file-via-url-list-url="getUploadFileViaUrlListUrl"
        :get-upload-file-via-url-request-example="
          getUploadFileViaUrlRequestExample
        "
      />
      <APIDocsFilters />
      <APIDocsErrors v-model="exampleData" />
    </div>
  </div>
</template>

<script>
import { isElement } from '@baserow/modules/core/utils/dom'
import APIDocsSelectDatabase from '@baserow/modules/database/components/docs/APIDocsSelectDatabase'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import FieldService from '@baserow/modules/database/services/field'

// All sections
import APIDocsIntro from '@baserow/modules/database/components/docs/sections/APIDocsIntro'
import APIDocsAuth from '@baserow/modules/database/components/docs/sections/APIDocsAuth'
import APIDocsTableFields from '@baserow/modules/database/components/docs/sections/APIDocsTableFields'
import APIDocsTableListFields from '@baserow/modules/database/components/docs/sections/APIDocsTableListFields'
import APIDocsTableListRows from '@baserow/modules/database/components/docs/sections/APIDocsTableListRows'
import APIDocsTableGetRow from '@baserow/modules/database/components/docs/sections/APIDocsTableGetRow'
import APIDocsTableCreateRow from '@baserow/modules/database/components/docs/sections/APIDocsTableCreateRow'
import APIDocsTableUpdateRow from '@baserow/modules/database/components/docs/sections/APIDocsTableUpdateRow'
import APIDocsTableMoveRow from '@baserow/modules/database/components/docs/sections/APIDocsTableMoveRow'
import APIDocsTableDeleteRow from '@baserow/modules/database/components/docs/sections/APIDocsTableDeleteRow'
import APIDocsUploadFile from '@baserow/modules/database/components/docs/sections/APIDocsUploadFile'
import APIDocsUploadFileViaURL from '@baserow/modules/database/components/docs/sections/APIDocsUploadFileViaURL'
import APIDocsListTables from '@baserow/modules/database/components/docs/sections/APIDocsListTables'
import APIDocsFilters from '@baserow/modules/database/components/docs/sections/APIDocsFilters'
import APIDocsErrors from '@baserow/modules/database/components/docs/sections/APIDocsErrors'
import APIDocsMenu from '@baserow/modules/database/components/docs/sections/APIDocsMenu'
import APIDocsTablePasswordFieldAuthentication from '@baserow/modules/database/components/docs/sections/APIDocsPasswordFieldAuthentication.vue'

// Re-use the FileFieldType docs response example.
import {
  FileFieldType,
  PasswordFieldType,
} from '@baserow/modules/database/fieldTypes'

export default {
  name: 'APIDocsDatabase',
  components: {
    APIDocsTablePasswordFieldAuthentication,
    APIDocsSelectDatabase,
    APIDocsIntro,
    APIDocsAuth,
    APIDocsTableFields,
    APIDocsTableListFields,
    APIDocsTableListRows,
    APIDocsTableGetRow,
    APIDocsTableCreateRow,
    APIDocsTableUpdateRow,
    APIDocsTableMoveRow,
    APIDocsTableDeleteRow,
    APIDocsUploadFile,
    APIDocsUploadFileViaURL,
    APIDocsFilters,
    APIDocsErrors,
    APIDocsMenu,
    APIDocsListTables,
  },
  middleware: ['authenticated', 'workspacesAndApplications'],
  async asyncData({ store, params, error, app }) {
    const databaseId = parseInt(params.databaseId)
    const database = store.getters['application/get'](databaseId)
    const type = DatabaseApplicationType.getType()

    if (database === undefined || database.type !== type) {
      return error({ statusCode: 404, message: 'Database not found.' })
    }

    const fieldData = {}

    for (const i in database.tables) {
      const table = database.tables[i]
      const { data } = await FieldService(app.$client).fetchAll(table.id)
      fieldData[table.id] = data
    }

    return { database, fieldData }
  },
  data() {
    return {
      exampleData: {
        // Indicates which request example type is shown.
        type: 'curl',
        userFieldNames: true,
      },
      // Indicates which navigation item is active.
      navActive: '',
      // Indicates if the databases sidebar is open.
      databasesOpen: false,
    }
  },
  head() {
    return {
      title: this.$t('apiDocsDatabase.pageTitle', this.database),
    }
  },
  computed: {
    userFieldNamesParam() {
      return this.exampleData.userFieldNames ? '?user_field_names=true' : ''
    },
    fields() {
      return Object.fromEntries(
        Object.entries(this.fieldData).map(([key, fields]) => {
          return [key, fields.map((field) => this.populateField(field))]
        })
      )
    },
    passwordFields() {
      return Object.fromEntries(
        Object.entries(this.fieldData).map(([key, fields]) => {
          return [
            key,
            fields.filter(
              (field) =>
                field.type === PasswordFieldType.getType() &&
                field.allow_endpoint_authentication
            ),
          ]
        })
      )
    },
    withoutReadOnly() {
      return Object.fromEntries(
        Object.entries(this.fields).map(([key, fields]) => {
          return [key, fields.filter((field) => !this.isReadOnlyField(field))]
        })
      )
    },
  },
  mounted() {
    // When the user clicks outside the databases sidebar and it is open then it must
    // be closed.
    this.$el.clickOutsideEvent = (event) => {
      if (
        this.databasesOpen &&
        !isElement(this.$refs.databasesToggle, event.target) &&
        !isElement(this.$refs.databases, event.target)
      ) {
        this.databasesOpen = false
      }
    }
    document.body.addEventListener('click', this.$el.clickOutsideEvent)

    // When the user scrolls in the body or when the window is resized, the active
    // navigation item must be updated.
    this.$el.scrollEvent = () => this.updateNav()
    this.$el.resizeEvent = () => this.updateNav()
    window.addEventListener('scroll', this.$el.scrollEvent)
    window.addEventListener('resize', this.$el.resizeEvent)
    this.updateNav()
  },
  beforeDestroy() {
    document.body.removeEventListener('click', this.$el.clickOutsideEvent)
    window.removeEventListener('scroll', this.$el.scrollEvent)
    window.removeEventListener('resize', this.$el.resizeEvent)
  },
  methods: {
    /**
     * Add metadata to fields
     */
    populateField(field) {
      const fieldType = this.$registry.get('field', field.type)
      field._ = {
        type: fieldType.getDocsDataType(field),
        description: fieldType.getDocsDescription(field),
        requestExample: fieldType.getDocsRequestExample(field),
        responseExample: fieldType.getDocsResponseExample(field),
        fieldResponseExample: fieldType.getDocsFieldResponseExample(
          field,
          fieldType.isReadOnlyField(field)
        ),
      }
      return field
    },
    /**
     * Called when the user scrolls or when the window is resized. It will check which
     * navigation item is active based on the scroll position of the available ids.
     */
    updateNav() {
      const body = document.documentElement
      const sections = body.querySelectorAll('[id^="section-"]')
      sections.forEach((section, index) => {
        const top = section.offsetTop
        const nextIndex = (index + 1).toString()
        const next =
          nextIndex in sections
            ? sections[nextIndex].offsetTop
            : body.scrollHeight
        if (top <= body.scrollTop && body.scrollTop < next) {
          this.navActive = section.id
        }
      })
    },
    navigate(to) {
      const section = document.querySelector(`[id='${to}']`)
      document.documentElement.scrollTop =
        section.offsetTop - 20 + this.$refs.header.clientHeight
    },
    /**
     * Generates an example request object based on the available fields of the table.
     */
    getRequestExample(table, response = false, includeId = false) {
      const item = {}

      // In case we are creating a sample response
      // read only fields need to be included.
      // They should be left out in the case of
      // creating a sample request.
      let fieldsToLoopOver = this.fields[table.id]
      if (!response) {
        fieldsToLoopOver = fieldsToLoopOver.filter(
          (field) => !this.isReadOnlyField(field)
        )
      }

      if (includeId) {
        item.id = 0
      }

      fieldsToLoopOver.forEach((field) => {
        const example = response
          ? field._.responseExample
          : field._.requestExample
        if (this.exampleData.userFieldNames) {
          item[field.name] = example
        } else {
          item[`field_${field.id}`] = example
        }
      })
      return item
    },
    /**
     * Generates an example request object when providing multiple items.
     */
    getBatchRequestExample(table, response = false) {
      return {
        items: [this.getRequestExample(table, response, true)],
      }
    },
    /**
     * Generates an example request object for deleting multiple items.
     */
    getBatchDeleteRequestExample(table, response = false) {
      return {
        items: [0],
      }
    },
    /**
     * Generates an example response object based on the available fields of the table.
     */
    getResponseItem(table) {
      const item = { id: 0, order: '1.00000000000000000000' }
      Object.assign(item, this.getRequestExample(table, true))
      return item
    },
    /**
     * Generates an example response object when multiple items are returned.
     */
    getBatchResponseItems(table) {
      return {
        items: [this.getResponseItem(table)],
      }
    },
    /**
     * Returns the mapping of the field id as key and the field name as value.
     */
    getFieldMapping(table) {
      const mapping = {}
      this.fields[table.id].forEach((field) => {
        if (this.exampleData.userFieldNames) {
          mapping[field.name] = `field_${field.id}`
        } else {
          mapping[`field_${field.id}`] = field.name
        }
      })
      return mapping
    },
    getListURL(table, addUserFieldParam, batch = false) {
      return `${this.$config.PUBLIC_BACKEND_URL}/api/database/rows/table/${
        table.id
      }/${batch ? 'batch/' : ''}${
        addUserFieldParam ? this.userFieldNamesParam : ''
      }`
    },
    getDeleteListURL(table) {
      return `${this.$config.PUBLIC_BACKEND_URL}/api/database/rows/table/${table.id}/batch-delete/`
    },
    /**
     * Generates the 'upload file' file example.
     */
    getUploadFileExample() {
      return 'photo.png'
    },
    /**
     * Generates the 'upload file' and 'upload via URL' file example response.
     */
    getUploadFileResponse() {
      return this.$registry
        .get('field', FileFieldType.getType())
        .getDocsResponseExample()[0]
    },
    /**
     * Generates the 'upload file' URI.
     */
    getUploadFileListUrl() {
      return this.$config.PUBLIC_BACKEND_URL + '/api/user-files/upload-file/'
    },
    /**
     * Generates the 'upload file' request example.
     */
    getUploadFileViaUrlRequestExample() {
      return {
        url: 'https://baserow.io/assets/photo.png',
      }
    },
    /**
     * Returns true if the field is read only.
     */
    isReadOnlyField(field) {
      return !this.$registry.get('field', field.type).canWriteFieldValues(field)
    },
    /**
     * Generates the 'upload file via URL' URI.
     */
    getUploadFileViaUrlListUrl() {
      return this.$config.PUBLIC_BACKEND_URL + '/api/user-files/upload-via-url/'
    },
    getItemURL(table, addUserFieldParam) {
      return (
        this.getListURL(table) +
        '{row_id}/' +
        (addUserFieldParam ? this.userFieldNamesParam : '')
      )
    },
  },
}
</script>
