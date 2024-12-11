<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('pageVisibilitySettings.description')"
      small-label
      class="margin-bottom-2"
      required
    >
      <div>
        <Alert v-if="showLoginPageAlert && showLogInPageWarning" type="warning">
          <slot name="title">{{
            $t('pageVisibilitySettingsTypes.logInPageWarningTitle')
          }}</slot>
          <p>{{ $t('pageVisibilitySettingsTypes.logInPagewarningMessage') }}</p>
        </Alert>
        <Alert
          v-else-if="showLoginPageAlert && !showLogInPageWarning"
          type="info-primary"
        >
          <slot name="title">{{
            $t('pageVisibilitySettingsTypes.logInPageInfoTitle')
          }}</slot>
          <p>
            {{
              $t('pageVisibilitySettingsTypes.logInPageInfoMessage', {
                logInPageName: loginPageName,
              })
            }}
          </p>
        </Alert>
      </div>
      <div class="margin-top-1 visibility-form__visibility-all">
        <div>
          <Radio v-model="values.visibility" :value="visibilityAll">
            {{ $t('pageVisibilitySettings.allVisitors') }}
          </Radio>
        </div>

        <div class="margin-left-2 visibility-form__visibility-logged-in">
          <Expandable
            :force-expanded="selectedVisibility === visibilityLoggedIn"
          >
            <template #header="{ toggle }">
              <Radio
                v-model="selectedVisibility"
                :value="visibilityLoggedIn"
                @click="toggle"
              >
                {{ $t('pageVisibilitySettings.loggedInVisitors') }}
              </Radio>
            </template>

            <template #default>
              <FormElement
                class="control visibility-form__expanded-form-element"
              >
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
                  v-if="
                    allowAllRolesExceptSelected ||
                    disallowAllRolesExceptSelected
                  "
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
        </div>
      </div>
    </FormGroup>
  </form>
</template>

<script>
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import visibilityForm from '@baserow/modules/builder/mixins/visibilityForm'
import form from '@baserow/modules/core/mixins/form'

import { VISIBILITY_LOGGED_IN } from '@baserow/modules/builder/constants'

export default {
  name: 'PageVisibilityForm',
  mixins: [form, visibilityForm],
  data() {
    return {
      values: {
        visibility: this.defaultValues.visibility,
        roles: this.defaultValues.roles,
        role_type: this.defaultValues.role_type,
      },
      allowedValues: ['visibility'],
    }
  },
  computed: {
    showLoginPageAlert() {
      return this.selectedVisibility === VISIBILITY_LOGGED_IN
    },
    showLogInPageWarning() {
      return !this.loginPageName
    },
    /**
     * Return the login page's name or null if the page doesn't exist.
     */
    loginPageName() {
      try {
        const loginPage = this.$store.getters['page/getById'](
          this.builder,
          this.builder.login_page_id
        )
        return loginPage.name
      } catch (e) {
        if (e instanceof StoreItemLookupError) {
          return null
        }
        throw e
      }
    },
  },
}
</script>
