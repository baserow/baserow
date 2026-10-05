<template>
  <div>
    <template v-if="page === 'list'">
      <h2 class="box__title">{{ $t('workspaceSkills.title') }}</h2>
      <p class="workspace-skills__description">
        {{ $t('workspaceSkills.description') }}
      </p>
      <div v-if="canCreate && skills.length > 0" class="align-right">
        <a class="button button--primary" @click.prevent="openCreate">
          {{ $t('workspaceSkills.createSkill') }}
          <i class="iconoir-plus"></i>
        </a>
      </div>
      <div v-if="loading" class="loading"></div>
      <div v-else-if="skills.length === 0" class="workspace-skills__empty">
        <div class="workspace-skills__empty-icon">
          <i class="iconoir-book"></i>
        </div>
        <h3>{{ $t('workspaceSkills.empty') }}</h3>
        <p>{{ $t('workspaceSkills.emptyDescription') }}</p>
        <Button v-if="canCreate" icon="iconoir-plus" @click="openCreate">
          {{ $t('workspaceSkills.createSkill') }}
        </Button>
      </div>
      <template v-else>
        <div
          v-for="skill in skills"
          :key="skill.id"
          class="workspace-skills__item"
        >
          <div class="workspace-skills__item-head">
            <a
              class="workspace-skills__item-name"
              @click.prevent="openEdit(skill)"
            >
              {{ skill.name }}
            </a>
            <ButtonIcon
              v-if="canUpdate || canDelete"
              :ref="`contextLink-${skill.id}`"
              type="secondary"
              size="small"
              icon="baserow-icon-more-horizontal"
              class="workspace-skills__item-more"
              @click="
                $refs[`context-${skill.id}`][0].toggle(
                  $refs[`contextLink-${skill.id}`][0].$el,
                  'bottom',
                  'right',
                  4
                )
              "
            />
            <Context
              :ref="`context-${skill.id}`"
              overflow-scroll
              max-height-if-outside-viewport
            >
              <ul class="context__menu">
                <li v-if="canUpdate" class="context__menu-item">
                  <a
                    class="context__menu-item-link"
                    @click="
                      ;($refs[`context-${skill.id}`][0].hide(), openEdit(skill))
                    "
                  >
                    <i class="context__menu-item-icon iconoir-edit-pencil"></i>
                    {{ $t('action.edit') }}
                  </a>
                </li>
                <li v-if="canDelete" class="context__menu-item">
                  <a
                    class="context__menu-item-link"
                    @click="
                      ;($refs[`context-${skill.id}`][0].hide(),
                        askDelete(skill))
                    "
                  >
                    <i class="context__menu-item-icon iconoir-bin"></i>
                    {{ $t('action.delete') }}
                  </a>
                </li>
              </ul>
            </Context>
          </div>
          <div class="workspace-skills__item-description">
            {{ skill.description || $t('workspaceSkills.noDescription') }}
          </div>
          <div class="workspace-skills__item-meta">
            {{
              $t('workspaceSkills.updated', { time: fromNow(skill.updated_on) })
            }}
          </div>
        </div>
      </template>
    </template>
    <template v-else>
      <h2 class="box__title">
        {{
          editing
            ? $t('workspaceSkills.editSkill')
            : $t('workspaceSkills.createSkill')
        }}
      </h2>
      <WorkspaceSkillForm
        ref="form"
        :default-values="editing || {}"
        :read-only="editing ? !canUpdate : !canCreate"
        @submitted="submit"
      >
        <div class="actions margin-bottom-0">
          <ul class="action__links">
            <li>
              <a @click.prevent="page = 'list'">
                <i class="iconoir-arrow-left"></i>
                {{ $t('workspaceSkills.backToOverview') }}
              </a>
            </li>
          </ul>
          <Button
            v-if="editing ? canUpdate : canCreate"
            type="primary"
            size="large"
            :loading="saving"
            :disabled="saving"
          >
            {{
              editing ? $t('action.save') : $t('workspaceSkills.createSkill')
            }}
          </Button>
        </div>
      </WorkspaceSkillForm>
    </template>
    <Modal ref="deleteModal" small>
      <h2 class="box__title">{{ $t('workspaceSkills.deleteTitle') }}</h2>
      <p>{{ $t('workspaceSkills.deleteText', { name: deleting?.name }) }}</p>
      <div class="actions actions--right actions--gap margin-bottom-0">
        <Button type="secondary" @click="$refs.deleteModal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button type="danger" :loading="deleteLoading" @click="deleteSkill">
          {{ $t('workspaceSkills.deleteSkill') }}
        </Button>
      </div>
    </Modal>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import { notifyIf } from '@baserow/modules/core/utils/error'
import WorkspaceSkillForm from '@baserow/modules/core/components/workspace/skills/WorkspaceSkillForm'

/**
 * The "Skills" page of the workspace settings modal: reusable markdown
 * instructions that every agent of the workspace can follow. Like the
 * database tokens and MCP pages it switches between the list and an inline
 * create/edit form.
 */
export default {
  name: 'WorkspaceSkillsSettings',
  components: { WorkspaceSkillForm },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      page: 'list',
      editing: null,
      deleting: null,
      loading: false,
      saving: false,
      deleteLoading: false,
    }
  },
  computed: {
    skills() {
      return this.$store.getters['workspaceSkill/getAllInWorkspace'](
        this.workspace.id
      )
    },
    canCreate() {
      return this.$hasPermission(
        'workspace.create_skill',
        this.workspace,
        this.workspace.id
      )
    },
    canUpdate() {
      return this.$hasPermission(
        'workspace.update_skill',
        this.workspace,
        this.workspace.id
      )
    },
    canDelete() {
      return this.$hasPermission(
        'workspace.delete_skill',
        this.workspace,
        this.workspace.id
      )
    },
  },
  async mounted() {
    this.loading = true
    try {
      await this.$store.dispatch('workspaceSkill/fetchAll', {
        workspaceId: this.workspace.id,
      })
    } catch (error) {
      notifyIf(error, 'workspace')
    } finally {
      this.loading = false
    }
  },
  methods: {
    fromNow(value) {
      return moment.utc(value).fromNow()
    },
    openCreate() {
      this.editing = null
      this.page = 'form'
    },
    openEdit(skill) {
      this.editing = skill
      this.page = 'form'
    },
    async submit(values) {
      this.saving = true
      try {
        if (this.editing) {
          await this.$store.dispatch('workspaceSkill/update', {
            skillId: this.editing.id,
            values,
          })
        } else {
          await this.$store.dispatch('workspaceSkill/create', {
            workspaceId: this.workspace.id,
            values,
          })
        }
        this.page = 'list'
      } catch (error) {
        if (error.handler?.code === 'ERROR_WORKSPACE_SKILL_NAME_NOT_UNIQUE') {
          error.handler.handled()
          this.$refs.form.setNameNotUnique()
        } else {
          notifyIf(error, 'workspace')
        }
      } finally {
        this.saving = false
      }
    },
    askDelete(skill) {
      this.deleting = skill
      this.$refs.deleteModal.show()
    },
    async deleteSkill() {
      this.deleteLoading = true
      try {
        await this.$store.dispatch('workspaceSkill/delete', this.deleting)
        this.$refs.deleteModal.hide()
      } catch (error) {
        notifyIf(error, 'workspace')
      } finally {
        this.deleteLoading = false
      }
    },
  },
}
</script>
