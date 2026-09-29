<template>
  <div>
    <Modal ref="modal" wide @show="init()">
      <h2 class="box__title">{{ $t('fieldPermissionModal.title') }}</h2>
      <p>
        <i18n-t
          scope="global"
          keypath="fieldPermissionModal.description"
          tag="span"
        >
          <template #fieldName>
            <strong>{{ field.name }}</strong>
          </template>
        </i18n-t>
      </p>
      <div class="margin-bottom-2" :style="{ fontWeight: '500' }">
        {{ $t('fieldPermissionModal.question') }}
      </div>
      <div v-if="loading" class="loading"></div>
      <template v-else>
        <Dropdown
          :value="role"
          :show-search="false"
          :fixed-items="true"
          size="large"
          @input="onRoleChanged"
        >
          <DropdownItem
            v-for="r in roles"
            :key="r.uid"
            :name="r.title"
            :value="r.uid"
            :description="r.desc"
          ></DropdownItem>
        </Dropdown>
        <FormGroup v-if="showAllowInForms" class="margin-bottom-2 margin-top-3">
          <SwitchInput small :value="allowInForms" @input="toggleAllowInForms">
            {{ $t('fieldPermissionModal.allowInForms') }}
          </SwitchInput>
        </FormGroup>
        <FieldPermissionSubjectsSelector
          v-if="role === customRole"
          ref="subjectsSelector"
          :field-id="field.id"
          :subjects="subjects"
          @selection-change="customSubjectCount = $event"
        />
        <Alert v-if="isLinkRowFieldType" type="info-neutral">
          <p>{{ $t('fieldPermissionModal.linkRowWarning') }}</p>
        </Alert>
        <div
          v-if="role === customRole"
          class="actions actions--right actions--gap margin-bottom-0 margin-top-3"
        >
          <Button type="secondary" size="large" @click="cancelCustomSubjects">
            {{ $t('action.cancel') }}
          </Button>
          <Button
            size="large"
            :loading="updating"
            :disabled="customSubjectCount === 0"
            @click="saveCustomSubjects"
          >
            {{ $t('action.save') }}
          </Button>
        </div>
      </template>
    </Modal>
  </div>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import FieldPermissionSubjectsSelector from '@baserow_enterprise/components/fieldPermissions/FieldPermissionSubjectsSelector'
import FieldPermissionService from '@baserow_enterprise/services/fieldPermissions'
import { WriteFieldValuesPermissionManagerType } from '@baserow_enterprise/permissionManagerTypes'

export default {
  name: 'FieldPermissionsModal',
  components: { FieldPermissionSubjectsSelector },
  mixins: [modal],
  props: {
    field: {
      type: Object,
      required: true,
    },
    workspaceId: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      updating: false,
      role: null,
      allowInForms: false,
      subjects: [],
      customSubjectCount: 0,
      customRole: 'CUSTOM',
      roles: [
        {
          uid: 'EDITOR',
          title: this.$t('fieldPermissionModal.editorTitle'),
          desc: this.$t('fieldPermissionModal.editorDescription'),
        },
        {
          uid: 'BUILDER',
          title: this.$t('fieldPermissionModal.builderTitle'),
          desc: this.$t('fieldPermissionModal.builderDescription'),
        },
        {
          uid: 'ADMIN',
          title: this.$t('fieldPermissionModal.adminTitle'),
          desc: this.$t('fieldPermissionModal.adminDescription'),
        },
        {
          uid: 'CUSTOM',
          title: this.$t('fieldPermissionModal.customTitle'),
          desc: this.$t('fieldPermissionModal.customDescription'),
        },
        {
          uid: 'NOBODY',
          title: this.$t('fieldPermissionModal.nobodyTitle'),
          desc: this.$t('fieldPermissionModal.nobodyDescription'),
        },
      ],
    }
  },
  computed: {
    isLinkRowFieldType() {
      return this.field.type === 'link_row'
    },
    showAllowInForms() {
      return this.canAllowInForms(this.role)
    },
  },
  watch: {
    'field.id': {
      handler() {
        this.init()
      },
    },
  },
  mounted() {
    this.$bus.$on('field-permissions-updated', this.forceUpdate)
  },
  beforeUnmount() {
    this.$bus.$off('field-permissions-updated', this.forceUpdate)
  },
  methods: {
    /*
     * EDITOR is the default role and there's no need to show the allow_in_forms
     * checkbox when the role is EDITOR. Note that the toggle is reset every time the
     * role is changed to EDITOR.
     */
    canAllowInForms(role, oldRole) {
      return ![role, oldRole].includes('EDITOR')
    },
    /* Load the field permission data from the server. */
    async init() {
      this.loading = true
      const { data } = await FieldPermissionService(this.$client).get(
        this.field.id
      )
      this.role = data.role
      this.allowInForms = data.allow_in_forms
      this.subjects = data.subjects || []
      this.customSubjectCount = this.subjects.length
      this.loading = false
    },
    /* Update the field permission data on the server. */
    async update({ role, allowInForms, subjects }) {
      this.updating = true
      const originalRole = this.role
      const originalAllowInForms = this.allowInForms
      const originalSubjects = this.subjects

      this.role = role
      if (!this.canAllowInForms(role, originalRole)) {
        allowInForms = false
      }
      this.allowInForms = allowInForms
      try {
        const { data } = await FieldPermissionService(this.$client).update(
          this.field.id,
          { role, allowInForms, subjects }
        )
        this.subjects = data.subjects || []
        const opName = WriteFieldValuesPermissionManagerType.getType()
        this.$registry
          .get('permissionManager', opName)
          .updateWritePermissionsForField(
            this.workspaceId,
            this.field.id,
            data.can_write_values,
            data.allow_in_forms
          )

        return data
      } catch (error) {
        this.role = originalRole
        this.allowInForms = originalAllowInForms
        this.subjects = originalSubjects
        notifyIf(error, 'settings')
        return null
      } finally {
        this.updating = false
      }
    },
    /* Update the role and the workspace permissions to reflect the changes. */
    async onRoleChanged(role) {
      if (role === this.customRole) {
        if (!this.canAllowInForms(role, this.role)) {
          this.allowInForms = false
        }
        this.role = role
        return
      }
      await this.update({ role, allowInForms: this.allowInForms })
    },
    async saveCustomSubjects() {
      const subjects = this.$refs.subjectsSelector.getSelectedSubjects()
      const data = await this.update({
        role: this.customRole,
        allowInForms: this.allowInForms,
        subjects,
      })
      if (data) {
        this.hide()
      }
    },
    cancelCustomSubjects() {
      this.hide()
    },
    /* Update the allow_in_forms property. */
    async toggleAllowInForms(allowInForms) {
      if (this.role === this.customRole) {
        this.allowInForms = allowInForms
        return
      }
      await this.update({ role: this.role, allowInForms })
    },
    /*
     * Forcefully refresh the field permission data. This is triggered when updates
     * are received via websockets to ensure real-time synchronization.
     */
    async forceUpdate({ fieldId, role, allowInForms }) {
      if (fieldId !== this.field.id) {
        return
      }
      this.role = role
      this.allowInForms = allowInForms
      if (role === this.customRole) {
        await this.init()
      } else {
        this.subjects = []
      }
    },
  },
}
</script>
