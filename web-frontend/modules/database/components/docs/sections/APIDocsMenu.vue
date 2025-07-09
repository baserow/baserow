<template>
  <div class="api-docs__nav">
    <ul class="api-docs__nav-list">
      <li>
        <a
          class="api-docs__nav-link"
          :class="{ active: navActive === 'section-introduction' }"
          @click.prevent="navigate('section-introduction')"
          >{{ $t('apiDocs.intro') }}</a
        >
      </li>
      <li>
        <a
          class="api-docs__nav-link"
          :class="{ active: navActive === 'section-authentication' }"
          @click.prevent="navigate('section-authentication')"
          >{{ $t('apiDocs.authent') }}</a
        >
      </li>
      <li v-for="table in database.tables" :key="table.id">
        <a
          class="api-docs__nav-link"
          :class="{ active: navActive === 'section-table-' + table.id }"
          @click.prevent="navigate('section-table-' + table.id)"
          >{{ $t('apiDocs.table', table) }}
          <small>(id: {{ table.id }})</small></a
        >
        <ul
          class="api-docs__nav-sub"
          :class="{
            open:
              navActive === 'section-table-' + table.id ||
              navActive === 'section-table-' + table.id + '-fields' ||
              navActive === 'section-table-' + table.id + '-field-list' ||
              navActive === 'section-table-' + table.id + '-list' ||
              navActive === 'section-table-' + table.id + '-get' ||
              navActive === 'section-table-' + table.id + '-create' ||
              navActive === 'section-table-' + table.id + '-update' ||
              navActive === 'section-table-' + table.id + '-move' ||
              navActive === 'section-table-' + table.id + '-delete' ||
              isPasswordFieldInTable(table.id),
          }"
        >
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-table-' + table.id + '-fields',
              }"
              @click.prevent="navigate('section-table-' + table.id + '-fields')"
              >{{ $t('apiDocs.fields') }}</a
            >
          </li>
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active:
                  navActive === 'section-table-' + table.id + '-field-list',
              }"
              @click.prevent="
                navigate('section-table-' + table.id + '-field-list')
              "
              >{{ $t('apiDocs.listFields') }}</a
            >
          </li>
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-table-' + table.id + '-list',
              }"
              @click.prevent="navigate('section-table-' + table.id + '-list')"
              >{{ $t('apiDocs.listRows') }}</a
            >
          </li>
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-table-' + table.id + '-get',
              }"
              @click.prevent="navigate('section-table-' + table.id + '-get')"
              >{{ $t('apiDocs.getRow') }}</a
            >
          </li>
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-table-' + table.id + '-create',
              }"
              @click.prevent="navigate('section-table-' + table.id + '-create')"
              >{{ $t('apiDocs.createRow') }}</a
            >
          </li>
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-table-' + table.id + '-update',
              }"
              @click.prevent="navigate('section-table-' + table.id + '-update')"
              >{{ $t('apiDocs.updateRow') }}</a
            >
          </li>
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-table-' + table.id + '-move',
              }"
              @click.prevent="navigate('section-table-' + table.id + '-move')"
              >{{ $t('apiDocs.moveRow') }}</a
            >
          </li>
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-table-' + table.id + '-delete',
              }"
              @click.prevent="navigate('section-table-' + table.id + '-delete')"
              >{{ $t('apiDocs.deleteRow') }}</a
            >
          </li>
          <li v-for="field in passwordFields[table.id]" :key="field.id">
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === getPasswordFieldNav(field.id),
              }"
              @click.prevent="navigate(getPasswordFieldNav(field.id))"
              >{{
                $t('apiDocsPasswordFieldAuthentication.title', {
                  name: field.name,
                })
              }}</a
            >
          </li>
        </ul>
      </li>
      <li>
        <a
          class="api-docs__nav-link"
          @click.prevent="navigate('section-upload-file')"
          >{{ $t('apiDocs.fileUploads') }}</a
        >
        <ul
          class="api-docs__nav-sub"
          :class="{
            open:
              navActive === 'section-upload-file' ||
              navActive === 'section-upload-file-via-url',
          }"
        >
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-upload-file',
              }"
              @click.prevent="navigate('section-upload-file')"
              >{{ $t('apiDocs.uploadFile') }}</a
            >
          </li>
          <li>
            <a
              class="api-docs__nav-link"
              :class="{
                active: navActive === 'section-upload-file-via-url',
              }"
              @click.prevent="navigate('section-upload-file-via-url')"
              >{{ $t('apiDocs.uploadFileViaUrl') }}</a
            >
          </li>
        </ul>
      </li>
      <li>
        <a
          class="api-docs__nav-link"
          :class="{ active: navActive === 'section-list-tables' }"
          @click.prevent="navigate('section-list-tables')"
          >{{ $t('apiDocs.listTables') }}</a
        >
      </li>
      <li>
        <a
          class="api-docs__nav-link"
          :class="{ active: navActive === 'section-filters' }"
          @click.prevent="navigate('section-filters')"
          >{{ $t('apiDocs.filters') }}</a
        >
      </li>
      <li>
        <a
          class="api-docs__nav-link"
          :class="{ active: navActive === 'section-errors' }"
          @click.prevent="navigate('section-errors')"
          >{{ $t('apiDocs.errors') }}</a
        >
      </li>
    </ul>
  </div>
</template>

<script>
export default {
  name: 'APIDocsMenu',
  props: {
    database: {
      type: Object,
      required: true,
    },
    navigate: {
      type: Function,
      required: true,
    },
    navActive: {
      type: String,
      required: true,
    },
    passwordFields: {
      type: Object,
      required: true,
    },
  },
  methods: {
    getPasswordFieldNav(fieldId) {
      return 'section-password-field-' + fieldId + '-authentication'
    },
    isPasswordFieldInTable(tableId) {
      const passwordFields = this.passwordFields[tableId]
      const navNames = passwordFields.map((field) => {
        return this.getPasswordFieldNav(field.id)
      })
      return navNames.includes(this.navActive)
    },
  },
}
</script>
