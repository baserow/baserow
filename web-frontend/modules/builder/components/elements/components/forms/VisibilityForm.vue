<template>
  <form @submit.prevent @keydown.enter.prevent>
    <Radio v-model="selectedVisibility" :value="visibilityAll">
      {{ $t('visibilityForm.allVisitors') }}
    </Radio>
    <Expandable :force-expanded="selectedVisibility === visibilityLoggedIn">
      <template #header="{ toggle }">
        <Radio
          v-model="selectedVisibility"
          :value="visibilityLoggedIn"
          @click="toggle"
        >
          {{ $t('visibilityForm.loggedInVisitors') }}
        </Radio>
      </template>

      <template #default>
        <FormElement class="control visibility-form__expanded-form-element">
          <Dropdown
            v-model="selectedRoleType"
            :placeholder="$t('visibilityForm.roleTypesHint')"
          >
            <DropdownItem
              v-for="(value, key) in roleTypeOptions"
              :key="key"
              :name="value"
              :value="key"
            >
            </DropdownItem>
          </Dropdown>

          <div
            v-if="allowAllRolesExceptSelected || disallowAllRolesExceptSelected"
            class="visibility-form__role-list"
          >
            <template v-if="loadingRoles">
              <div class="loading margin-bottom-1"></div>
            </template>
            <template v-else>
              <div
                v-for="roleName in allRoles"
                :key="roleName"
                class="visibility-form__role-checkbox"
              >
                <Checkbox
                  :checked="isChecked(roleName)"
                  @input="checkRole(roleName)"
                >
                  {{ getRoleName(roleName) }}
                </Checkbox>
              </div>

              <div class="visibility-form__actions">
                <a @click.prevent="selectAllRoles">
                  {{ $t('visibilityForm.rolesSelectAll') }}
                </a>
                <a @click.prevent="deselectAllRoles">
                  {{ $t('visibilityForm.rolesDeselectAll') }}
                </a>
              </div>
            </template>
          </div>
        </FormElement>
      </template>
    </Expandable>
    <Radio v-model="selectedVisibility" :value="visibilityNotLogged">
      {{ $t('visibilityForm.notLoggedInVisitors') }}
    </Radio>
    <Alert class="margin-bottom-2">
      <slot name="title">{{ $t('visibilityForm.warningTitle') }}</slot>
      <!-- eslint-disable-next-line vue/no-v-html vue/no-v-text-v-html-on-component -->
      <p v-html="$t('visibilityForm.warningMessage')"></p>
    </Alert>

    <FormGroup
      small-label
      :label="$t('visibilityForm.visibilityCondition')"
      class="margin-bottom-2"
      :helper-text="$t('visibilityForm.visibilityConditionHelper')"
      required
    >
      <InjectedFormulaInput
        v-model="values.visibility_condition"
        :placeholder="$t('visibilityForm.visibilityConditionPlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import visibilityForm from '@baserow/modules/builder/mixins/visibilityForm'
import elementForm from '@baserow/modules/builder/mixins/elementForm'

import {
  VISIBILITY_ALL,
  ROLE_TYPE_ALLOW_ALL,
} from '@baserow/modules/builder/constants'

export default {
  name: 'VisibilityForm',
  components: {
    InjectedFormulaInput,
  },
  mixins: [elementForm, visibilityForm],
  data() {
    return {
      values: {
        visibility: VISIBILITY_ALL,
        roles: [],
        role_type: ROLE_TYPE_ALLOW_ALL,
        visibility_condition: { formula: '' },
      },
    }
  },
}
</script>
