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
            @blur="$v.values.name.$touch()"
          >
          </FormInput>

          <template #error>
            <span
              v-if="fieldHasErrors('name') && !$v.values.name.required"
              class="error"
            >
              {{ $t('error.requiredField') }}
            </span>
            <span v-if="$v.values.name.$dirty && hasMinMaxError" class="error">
              {{
                $t('error.minMaxLength', {
                  max: $v.values.name.$params.maxLength.max,
                  min: $v.values.name.$params.minLength.min,
                })
              }}
            </span>
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
            v-model="values.default_role"
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
import { required, maxLength, minLength } from 'vuelidate/lib/validators'

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
    hasMinMaxError() {
      return !this.$v.values.name.maxLength || !this.$v.values.name.minLength
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
  validations: {
    values: {
      name: {
        required,
        minLength: minLength(2),
        maxLength: maxLength(160),
      },
    },
  },
  mounted() {
    this.$refs.name.focus()
  },
}
</script>
