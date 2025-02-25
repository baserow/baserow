<template>
  <form @submit.prevent="submit">
    <div class="row margin-bottom-2">
      <div class="col col-7">
        <FormGroup
          :error="fieldHasErrors('name')"
          :label="$t('manageTeamForm.nameTitle')"
          small-label
          required
        >
          <FormInput
            ref="name"
            v-model="values.name"
            :error="fieldHasErrors('name')"
            @blur="v$.values.name.$touch()"
          >
          </FormInput>

          <template #error>
            {{ v$.values.name.$errors[0]?.$message }}
          </template>
        </FormGroup>
      </div>
      <div class="col col-5">
        <FormGroup small-label required>
          <template #label>
            {{ $t('manageTeamForm.roleTitle') }}
            <HelpIcon
              class="margin-left-1"
              :tooltip="$t('manageTeamForm.roleHelpText')"
            />
          </template>

          <Dropdown
            v-model="v$.values.default_role.$model"
            :show-search="false"
            :fixed-items="true"
          >
            <DropdownItem
              v-for="role in roles"
              :key="role.uid"
              :name="role.name"
              :value="role.uid"
              :description="role.description"
            >
              {{ role.name }}
              <Badge
                v-if="role.showIsBillable && role.isBillable"
                color="cyan"
                size="small"
                bold
                >{{ $t('common.billable') }}
              </Badge>
              <Badge
                v-else-if="
                  role.showIsBillable &&
                  !role.isBillable &&
                  atLeastOneBillableRole
                "
                color="yellow"
                size="small"
                bold
                class="margin-left-1"
                >{{ $t('common.free') }}
              </Badge>
            </DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
    </div>
    <div class="row">
      <div class="col col-12">
        <h3>{{ $t('manageTeamForm.membersTitle') }}</h3>
        <div v-if="subjectsLoading" class="loading"></div>
        <p v-if="!invitedUserSubjects.length">
          {{
            $t('manageTeamForm.noSubjectsSelected', {
              buttonLabel: $t('manageTeamForm.inviteMembers'),
            })
          }}
        </p>
        <List
          v-if="invitedUserSubjects.length && !subjectsLoading"
          class="select-members-list__items"
          :items="invitedUserSubjects"
          :attributes="[]"
        >
          <template #left-side="{ item }">
            <Avatar
              rounded
              size="medium"
              :initials="item.name | nameAbbreviation"
            ></Avatar>
            <span class="margin-left-1">
              {{ item.name }}
            </span>
          </template>
          <template #right-side="{ item }">
            <span class="margin-right-1">{{ item.email }}</span>
            <ButtonIcon
              size="small"
              icon="iconoir-bin"
              @click="$emit('remove-subject', item)"
            ></ButtonIcon>
          </template>
        </List>
      </div>
    </div>
    <div class="row margin-top-2">
      <div class="col col-6">
        <Button
          type="secondary"
          :loading="loading"
          :disabled="loading"
          tag="a"
          @click="$emit('invite')"
          >{{ $t('manageTeamForm.inviteMembers') }}
        </Button>
      </div>
      <div class="col col-6 align-right">
        <Button type="primary" :disabled="loading" :loading="loading">
          {{ $t('manageTeamForm.submit') }}</Button
        >
      </div>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, maxLength, minLength, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import { filterRoles } from '@baserow_enterprise/utils/roles'

export default {
  name: 'ManageTeamForm',
  mixins: [form],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    invitedUserSubjects: {
      type: Array,
      required: true,
    },
    loading: {
      type: Boolean,
      required: true,
    },
    subjectsLoading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        name: '',
        default_role: 'VIEWER',
        subjects: [],
      },
    }
  },
  computed: {
    roles() {
      return filterRoles(this.workspace._.roles, {
        scopeType: 'workspace',
        subjectType: 'baserow_enterprise.Team',
      })
    },
    defaultRole() {
      return this.roles.length > 0 ? this.roles[this.roles.length - 1] : null
    },
    atLeastOneBillableRole() {
      return this.roles.some((role) => role.isBillable)
    },
  },
  watch: {
    invitedUserSubjects(newValue) {
      this.values.subjects = []
      for (let s = 0; s < this.invitedUserSubjects.length; s++) {
        this.values.subjects.push({
          subject_id: this.invitedUserSubjects[s].user_id,
          subject_type: 'auth.User',
        })
      }
    },
  },

  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          minLength: helpers.withMessage(
            this.$t('error.minMaxLength', {
              max: 160,
              min: 2,
            }),
            minLength(2)
          ),
          maxLength: helpers.withMessage(
            this.$t('error.minMaxLength', {
              max: 160,
              min: 2,
            }),
            maxLength(160)
          ),
        },
        default_role: {},
      },
    }
  },
  mounted() {
    this.$refs.name.focus()
  },
}
</script>
