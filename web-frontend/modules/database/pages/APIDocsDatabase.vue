<template>
  <div ref="api-docs" class="api-docs">
    <div ref="header" class="api-docs__header">
      <nuxt-link :to="{ name: 'index' }" class="api-docs__logo">
        <Logo />
      </nuxt-link>
      <a
        ref="databasesToggle"
        class="api-docs__switch"
        @click.prevent="databasesOpen.value = !databasesOpen.value"
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
      <APIDocsAuth v-model:value="exampleData" />

      <div v-for="table in database.tables" :key="table.id">
        <APIDocsTableFields
          v-if="fields"
          :table="table"
          :fields="fields"
          :navigate="navigate"
        />
        <APIDocsTableListFields
          v-model:value="exampleData"
          :table="table"
          :fields="fields"
        />
        <APIDocsTableListRows
          v-model:value="exampleData"
          :table="table"
          :fields="fields"
          :navigate="navigate"
          :get-list-url="getListURL"
          :get-response-item="getResponseItem"
          :get-field-mapping="getFieldMapping"
        />
        <APIDocsTableGetRow
          v-model:value="exampleData"
          :table="table"
          :get-item-url="getItemURL"
          :get-response-item="getResponseItem"
          :get-field-mapping="getFieldMapping"
        />
        <APIDocsTableCreateRow
          v-model:value="exampleData"
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
          v-model:value="exampleData"
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
          v-model:value="exampleData"
          :table="table"
          :user-field-names="exampleData.userFieldNames"
          :get-item-url="getItemURL"
          :get-response-item="getResponseItem"
          :get-field-mapping="getFieldMapping"
        />
        <APIDocsTableDeleteRow
          v-model:value="exampleData"
          :table="table"
          :get-item-url="getItemURL"
          :get-delete-list-url="getDeleteListURL"
          :get-batch-delete-request-example="getBatchDeleteRequestExample"
        />
        <div v-for="field in passwordFields[table.id]" :key="field.id">
          <APIDocsTablePasswordFieldAuthentication
            v-model:value="exampleData"
            :field="field"
            :table="table"
          />
        </div>
      </div>
      <APIDocsUploadFile
        v-model:value="exampleData"
        :get-upload-file-list-url="getUploadFileListUrl"
        :get-upload-file-example="getUploadFileExample"
        :get-upload-file-response="getUploadFileResponse"
      />
      <APIDocsListTables v-model:value="exampleData" />
      <APIDocsUploadFileViaURL
        v-model:value="exampleData"
        :get-upload-file-response="getUploadFileResponse"
        :get-upload-file-via-url-list-url="getUploadFileViaUrlListUrl"
        :get-upload-file-via-url-request-example="
          getUploadFileViaUrlRequestExample
        "
      />
      <APIDocsFilters />
      <APIDocsErrors v-model:value="exampleData" />
    </div>
  </div>
</template>

<script setup>
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

import { computed, onMounted, onBeforeUnmount, useTemplateRef } from 'vue'
import { useHead } from '#imports'
import SettingsModal from '@baserow/modules/core/components/settings/SettingsModal'

import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const $el = useTemplateRef('api-docs')
const databasesToggle = useTemplateRef('databasesToggle')
const databases = useTemplateRef('databases')
const header = useTemplateRef('header')

const {
  $store,
  $config,
  $client,
  $registry,
  $i18n: { t: $t },
} = useNuxtApp()

const { data, status, pending, error, refresh, clear } = await useAsyncData(
  'api-docs-database-' + route.params.databaseId,
  async () => {
    const params = route.params
    const databaseId = parseInt(params.databaseId)
    const database = $store.getters['application/get'](databaseId)
    const type = DatabaseApplicationType.getType()

    if (database === undefined || database.type !== type) {
      throw new Error(`database ${databaseId} not found`)
    }

    const fieldData = {}

    for (const i in database.tables) {
      const table = database.tables[i]
      const { data } = await FieldService($client).fetchAll(table.id)
      fieldData[table.id] = data
    }

    return { database, fieldData }
  }
)

const { database, fieldData } = data.value

useHead({
  title: $t('apiDocsDatabase.pageTitle', database),
})

definePageMeta({
  middleware: ['workspacesAndApplications'],
})

const exampleData = ref({
  // Indicates which request example type is shown.
  type: 'curl',
  userFieldNames: true,
})

const navActive = ref('')
const databasesOpen = ref(false)

const userFieldNamesParam = computed(() => {
  return exampleData.value.userFieldNames ? '?user_field_names=true' : ''
})
const fields = computed(() => {
  const { $registry } = useNuxtApp()
  return Object.fromEntries(
    Object.entries(fieldData).map(([key, fields]) => {
      return [key, fields.map((field) => populateField(field, $registry))]
    })
  )
})
const passwordFields = computed(() => {
  return Object.fromEntries(
    Object.entries(fieldData).map(([key, fields]) => {
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
})

const withoutReadOnly = computed(() => {
  return Object.fromEntries(
    Object.entries(fields.value).map(([key, fields]) => {
      return [key, fields.filter((field) => !isReadOnlyField(field))]
    })
  )
})

onMounted(() => {
  // When the user clicks outside the databases sidebar and it is open then it must
  // be closed.
  $el.value.clickOutsideEvent = (event) => {
    if (
      databasesOpen.value &&
      !isElement(databasesToggle.value, event.target) &&
      !isElement(databases.value, event.target)
    ) {
      databasesOpen.value = false
    }
  }
  document.body.addEventListener('click', $el.value.clickOutsideEvent)

  // When the user scrolls in the body or when the window is resized, the active
  // navigation item must be updated.
  $el.value.scrollEvent = () => updateNav()
  $el.value.resizeEvent = () => updateNav()
  window.addEventListener('scroll', $el.value.scrollEvent)
  window.addEventListener('resize', $el.value.resizeEvent)
  updateNav()
})
onBeforeUnmount(() => {
  document.body.removeEventListener('click', $el.value.clickOutsideEvent)
  window.removeEventListener('scroll', $el.value.scrollEvent)
  window.removeEventListener('resize', $el.value.resizeEvent)
})

/** methods **/

const populateField = (field) => {
  const fieldType = $registry.get('field', field.type)
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
}

/**
 * Called when the user scrolls or when the window is resized. It will check which
 * navigation item is active based on the scroll position of the available ids.
 */
const updateNav = () => {
  const body = document.documentElement
  const sections = body.querySelectorAll('[id^="section-"]')
  sections.forEach((section, index) => {
    const top = section.offsetTop
    const nextIndex = (index + 1).toString()
    const next =
      nextIndex in sections ? sections[nextIndex].offsetTop : body.scrollHeight
    if (top <= body.scrollTop && body.scrollTop < next) {
      navActive.value = section.id
    }
  })
}

const navigate = (to) => {
  const section = document.querySelector(`[id='${to}']`)
  document.documentElement.scrollTop =
    section.offsetTop - 20 + header.value.clientHeight
}
/**
 * Generates an example request object based on the available fields of the table.
 */
const getRequestExample = (table, response = false, includeId = false) => {
  const item = {}

  // In case we are creating a sample response
  // read only fields need to be included.
  // They should be left out in the case of
  // creating a sample request.
  let fieldsToLoopOver = fields.value[table.id]
  if (!response) {
    fieldsToLoopOver = fieldsToLoopOver.filter(
      (field) => !isReadOnlyField(field)
    )
  }

  if (includeId) {
    item.id = 0
  }

  fieldsToLoopOver.forEach((field) => {
    const example = response ? field._.responseExample : field._.requestExample
    if (exampleData.value.userFieldNames) {
      item[field.name] = example
    } else {
      item[`field_${field.id}`] = example
    }
  })
  return item
}

/**
 * Generates an example request object when providing multiple items.
 */
const getBatchRequestExample = (table, response = false) => {
  return {
    items: [getRequestExample(table, response, true)],
  }
}
/**
 * Generates an example request object for deleting multiple items.
 */
const getBatchDeleteRequestExample = (table, response = false) => {
  return {
    items: [0],
  }
}
/**
 * Generates an example response object based on the available fields of the table.
 */
const getResponseItem = (table) => {
  const item = { id: 0, order: '1.00000000000000000000' }
  Object.assign(item, getRequestExample(table, true))
  return item
}
/**
 * Generates an example response object when multiple items are returned.
 */
const getBatchResponseItems = (table) => {
  return {
    items: [getResponseItem(table)],
  }
}
/**
 * Returns the mapping of the field id as key and the field name as value.
 */
const getFieldMapping = (table) => {
  const mapping = {}
  fields.value[table.id].forEach((field) => {
    if (exampleData.value.userFieldNames) {
      mapping[field.name] = `field_${field.id}`
    } else {
      mapping[`field_${field.id}`] = field.name
    }
  })
  return mapping
}
const getListURL = (table, addUserFieldParam, batch = false) => {
  return `${$config.public.publicBackendUrl}/api/database/rows/table/${
    table.id
  }/${batch ? 'batch/' : ''}${
    addUserFieldParam ? userFieldNamesParam.value : ''
  }`
}
const getDeleteListURL = (table) => {
  return `${$config.public.publicBackendUrl}/api/database/rows/table/${table.id}/batch-delete/`
}
/**
 * Generates the 'upload file' file example.
 */
const getUploadFileExample = () => {
  return 'photo.png'
}
/**
 * Generates the 'upload file' and 'upload via URL' file example response.
 */
const getUploadFileResponse = () => {
  return $registry
    .get('field', FileFieldType.getType())
    .getDocsResponseExample()[0]
}
/**
 * Generates the 'upload file' URI.
 */
const getUploadFileListUrl = () => {
  return $config.public.publicBackendUrl + '/api/user-files/upload-file/'
}
/**
 * Generates the 'upload file' request example.
 */
const getUploadFileViaUrlRequestExample = () => {
  return {
    url: 'https://baserow.io/assets/photo.png',
  }
}
/**
 * Returns true if the field is read only.
 */
const isReadOnlyField = (field) => {
  return !$registry.get('field', field.type).canWriteFieldValues(field)
}
/**
 * Generates the 'upload file via URL' URI.
 */
const getUploadFileViaUrlListUrl = () => {
  return $config.public.publicBackendUrl + '/api/user-files/upload-via-url/'
}
const getItemURL = (table, addUserFieldParam) => {
  return (
    getListURL(table) +
    '{row_id}/' +
    (addUserFieldParam ? userFieldNamesParam.value : '')
  )
}
</script>
