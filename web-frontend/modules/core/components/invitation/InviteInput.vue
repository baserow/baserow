<template>
  <div class="invite-input">
    <div class="invite-input__row">
      <div
        class="invite-input__field"
        :class="{ 'invite-input__field--focused': open }"
        @click="focus"
      >
        <span
          v-for="item in selected"
          :key="item.key"
          v-tooltip:[chipTooltipOptions]="chipError(item)"
          class="invite-input__chip"
          :class="{ 'invite-input__chip--error': chipError(item) !== null }"
        >
          <i class="invite-input__chip-icon" :class="item.icon"></i>
          {{ item.name }}
          <a class="invite-input__chip-remove" @click.stop="remove(item)">
            <i class="iconoir-cancel"></i>
          </a>
        </span>
        <input
          ref="input"
          v-model="query"
          class="invite-input__input"
          :placeholder="selected.length === 0 ? placeholderText : ''"
          :disabled="disabled"
          @focus="open = true"
          @blur="open = false"
          @keydown.enter.prevent="pickEmails(query)"
          @keydown.escape="open = false"
          @keydown.delete="removeLastWhenEmpty"
          @paste="paste"
        />
      </div>
      <WorkspaceRoleSelector
        v-model="roleUid"
        class="invite-input__role"
        :workspace="workspace"
        :roles="roles"
      />
      <Button
        type="primary"
        :disabled="validSelected.length === 0 || disabled"
        @click="submit"
      >
        <slot
          name="submit-label"
          :count="validSelected.length"
          :role="roleName"
        >
          {{
            validSelected.length === 0
              ? $t('inviteInput.invite')
              : $t('inviteInput.inviteAs', {
                  count: validSelected.length,
                  role: roleName,
                })
          }}
        </slot>
      </Button>
    </div>
    <div v-show="showResults" class="invite-input__results" @mousedown.prevent>
      <div v-if="tabs.length > 0" class="invite-input__tabs">
        <a
          v-for="tab in allTabs"
          :key="tab.value"
          class="invite-input__tab"
          :class="{ 'invite-input__tab--active': activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </a>
      </div>
      <ul class="invite-input__list">
        <li
          v-for="email in pendingQueryEmails"
          :key="`pending:${email}`"
          class="invite-input__item invite-input__item--pending"
        >
          <Avatar icon="iconoir-mail" color="neutral" rounded size="medium" />
          <div class="invite-input__item-text">
            <div class="invite-input__item-title">{{ email }}</div>
            <div class="invite-input__item-subtitle">
              {{ pendingTextOrDefault }}
            </div>
          </div>
        </li>
        <li
          v-for="email in memberQueryEmails"
          :key="`member:${email}`"
          class="invite-input__item invite-input__item--pending"
        >
          <Avatar icon="iconoir-user" color="neutral" rounded size="medium" />
          <div class="invite-input__item-text">
            <div class="invite-input__item-title">{{ email }}</div>
            <div class="invite-input__item-subtitle">
              {{ $t('inviteInput.alreadyMember') }}
            </div>
          </div>
        </li>
        <li
          v-for="option in emailOptions"
          :key="option.key"
          class="invite-input__item"
          @click="toggle(option)"
        >
          <Avatar icon="iconoir-mail" color="neutral" rounded size="medium" />
          <div class="invite-input__item-text">
            <div class="invite-input__item-title">
              {{ $t('inviteInput.inviteEmail', { email: option.name }) }}
            </div>
            <div class="invite-input__item-subtitle">
              <slot name="email-description" :role="roleName">
                {{
                  $t('inviteInput.inviteEmailDescription', { role: roleName })
                }}
              </slot>
            </div>
          </div>
          <Checkbox
            :checked="isSelected(option)"
            @click.stop
            @update:model-value="toggle(option)"
          ></Checkbox>
        </li>
        <li
          v-for="option in visibleOptions"
          :key="option.key"
          class="invite-input__item"
          @click="toggle(option)"
        >
          <Avatar
            :initials="option.initials"
            :icon="option.initials ? '' : option.icon"
            :color="option.color"
            rounded
            size="medium"
          />
          <div class="invite-input__item-text">
            <div class="invite-input__item-title">{{ option.name }}</div>
            <div v-if="option.subtitle" class="invite-input__item-subtitle">
              {{ option.subtitle }}
            </div>
          </div>
          <Checkbox
            :checked="isSelected(option)"
            @click.stop
            @update:model-value="toggle(option)"
          ></Checkbox>
        </li>
      </ul>
      <div v-if="nothingToShow" class="invite-input__empty">
        {{ noResultsTextOrDefault }}
      </div>
    </div>
  </div>
</template>

<script>
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'
import { isValidEmail } from '@baserow/modules/core/utils/string'

const TAB_ALL = 'all'
// The reason a chip can't be submitted spans two lines, which the plain
// tooltip would run together.
const CHIP_TOOLTIP_OPTIONS = {
  contentClasses: [
    'tooltip__content--expandable',
    'tooltip__content--expandable-plain-text',
  ],
}

/**
 * Pulls the email-like tokens out of free text, so that a pasted list of
 * addresses in any common separator, with or without display names, is taken
 * apart into its addresses.
 */
export function extractEmails(text) {
  return text.match(/[^\s,;<>()[\]"']+@[^\s,;<>()[\]"']+/g) || []
}

/**
 * The input of the invite modal: one field that takes email addresses, typed
 * or pasted in bulk, and optionally searches a list of pickable `options` such
 * as the members, teams and agents of the workspace, grouped by `tabs`. Every
 * pick is shown as a chip. Submitting emits `add` with the picked items and the
 * chosen role uid; the parent calls `remove()` or `reset()` once they were
 * added. An address in `pendingEmails` already has an invitation and one in
 * `memberEmails` belongs to a member: typed, they are explained instead of
 * offered, and once picked, for example as part of a pasted list, their chip
 * is marked as an error and left out of what is submitted.
 *
 * Options are objects of `{ key, type, id, name, subtitle, search, initials,
 * icon, color }` with an optional `email` for people; `tabs` are `{ value,
 * label }` matching the option types, and an "All" tab is added in front.
 *
 * A result row toggles on click, and so does its checkbox. The checkbox is a
 * label around a native input, whose click would bubble to the row and toggle
 * it back, so the checkbox keeps its click to itself and toggles through its
 * own change event instead.
 */
export default {
  name: 'InviteInput',
  components: { WorkspaceRoleSelector },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    roles: {
      type: Array,
      required: true,
    },
    options: {
      type: Array,
      required: false,
      default: () => [],
    },
    tabs: {
      type: Array,
      required: false,
      default: () => [],
    },
    pendingEmails: {
      type: Array,
      required: false,
      default: () => [],
    },
    memberEmails: {
      type: Array,
      required: false,
      default: () => [],
    },
    placeholder: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * What is said about an address that already has an invitation.
     */
    pendingText: {
      type: String,
      required: false,
      default: null,
    },
    noResultsText: {
      type: String,
      required: false,
      default: null,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['add'],
  data() {
    return {
      chipTooltipOptions: CHIP_TOOLTIP_OPTIONS,
      query: '',
      open: false,
      activeTab: TAB_ALL,
      selected: [],
      roleUid: this.defaultRoleUid(this.roles),
    }
  },
  computed: {
    placeholderText() {
      return this.placeholder ?? this.$t('inviteInput.placeholder')
    },
    noResultsTextOrDefault() {
      return this.noResultsText ?? this.$t('inviteInput.noResults')
    },
    pendingTextOrDefault() {
      return this.pendingText ?? this.$t('inviteInput.alreadyInvited')
    },
    /**
     * The picks that can be submitted: everything but the addresses that
     * turned out to have an invitation or a membership already.
     */
    validSelected() {
      return this.selected.filter((item) => this.chipError(item) === null)
    },
    allTabs() {
      return [
        { value: TAB_ALL, label: this.$t('inviteInput.tabAll') },
        ...this.tabs,
      ]
    },
    roleName() {
      return this.roles.find((role) => role.uid === this.roleUid)?.name || ''
    },
    normalizedQuery() {
      return this.query.trim().toLowerCase()
    },
    visibleOptions() {
      return this.options.filter(
        (option) =>
          (this.activeTab === TAB_ALL || option.type === this.activeTab) &&
          option.search.toLowerCase().includes(this.normalizedQuery)
      )
    },
    /**
     * The distinct email addresses in the query, so that a pasted list that was
     * not fully picked is explained address by address.
     */
    queryEmails() {
      return [
        ...new Set(
          extractEmails(this.query).map((email) => email.toLowerCase())
        ),
      ]
    },
    pendingQueryEmails() {
      return this.queryEmails.filter((email) => this.isPending(email))
    },
    /**
     * The typed addresses of members, unless the member is right there in the
     * list to be picked.
     */
    memberQueryEmails() {
      return this.queryEmails.filter(
        (email) =>
          !this.isPending(email) &&
          this.isMember(email) &&
          !this.visibleOptions.some(
            (option) => option.email?.toLowerCase() === email
          )
      )
    },
    /**
     * One option per typed address that can be invited: a valid address that
     * neither has an invitation nor belongs to a member.
     */
    emailOptions() {
      return this.queryEmails
        .map((email) => this.invitableOptionFor(email))
        .filter(Boolean)
    },
    /**
     * With a list to search the results open on focus, otherwise there is
     * nothing to show until an address is typed.
     */
    showResults() {
      return (
        this.open &&
        (this.tabs.length > 0 ||
          this.options.length > 0 ||
          this.normalizedQuery !== '')
      )
    },
    nothingToShow() {
      return (
        this.pendingQueryEmails.length === 0 &&
        this.memberQueryEmails.length === 0 &&
        this.emailOptions.length === 0 &&
        this.visibleOptions.length === 0
      )
    },
  },
  watch: {
    roles(roles) {
      if (!roles.some((role) => role.uid === this.roleUid)) {
        this.roleUid = this.defaultRoleUid(roles)
      }
    },
  },
  methods: {
    /**
     * The last active role is the one with the least access, the safest default.
     */
    defaultRoleUid(roles) {
      const active = roles.filter((role) => !role.isDeactivated)
      return active.length > 0 ? active[active.length - 1].uid : null
    },
    focus() {
      this.$refs.input.focus()
    },
    isPending(email) {
      return this.pendingEmails.some(
        (pendingEmail) => pendingEmail.toLowerCase() === email
      )
    },
    /**
     * Whether the address belongs to a member, either one given in
     * `memberEmails` or one that is offered as an option and should be picked
     * as such.
     */
    isMember(email) {
      return (
        this.memberEmails.some(
          (memberEmail) => memberEmail.toLowerCase() === email
        ) ||
        this.options.some((option) => option.email?.toLowerCase() === email)
      )
    },
    emailPick(email) {
      return {
        key: `email:${email}`,
        type: 'email',
        email,
        name: email,
        icon: 'iconoir-mail',
      }
    },
    invitableOptionFor(email) {
      if (
        !isValidEmail(email) ||
        this.isPending(email) ||
        this.isMember(email)
      ) {
        return null
      }
      return this.emailPick(email)
    },
    /**
     * Why a chip can't be submitted, or null when it can. Judged at render time
     * so that a chip picked before the pending invitations were known is
     * marked as soon as they are.
     */
    chipError(item) {
      if (item.type !== 'email') {
        return null
      }
      if (this.isPending(item.email)) {
        return this.pendingTextOrDefault
      }
      if (this.isMember(item.email)) {
        return this.$t('inviteInput.alreadyMember')
      }
      return null
    },
    isSelected(option) {
      return this.selected.some((item) => item.key === option.key)
    },
    toggle(option) {
      if (this.isSelected(option)) {
        this.remove(option)
      } else {
        this.selected.push(option)
        if (option.type === 'email') {
          this.query = extractEmails(this.query)
            .filter((email) => email.toLowerCase() !== option.email)
            .join(' ')
        }
      }
      this.focus()
    },
    remove(item) {
      this.selected = this.selected.filter(({ key }) => key !== item.key)
    },
    removeLastWhenEmpty() {
      if (this.query === '' && this.selected.length > 0) {
        this.selected.pop()
      }
    },
    /**
     * Picks every address in the text. A member who is in the list is picked
     * as such, an address that can't be invited becomes a chip marked as an
     * error, and only text that isn't an address stays in the field.
     */
    pickEmails(text) {
      const leftovers = []
      for (const token of extractEmails(text)) {
        const email = token.toLowerCase()
        if (!isValidEmail(email)) {
          leftovers.push(token)
          continue
        }
        const pick =
          this.options.find(
            (option) => option.email?.toLowerCase() === email
          ) || this.emailPick(email)
        if (!this.isSelected(pick)) {
          this.selected.push(pick)
        }
      }
      this.query = leftovers.join(' ')
      this.focus()
    },
    /**
     * Pasted addresses become chips right away. Text without an address is
     * left to the browser to paste as usual.
     */
    paste(event) {
      const text = event.clipboardData?.getData('text') ?? ''
      if (extractEmails(text).length === 0) {
        return
      }
      event.preventDefault()
      this.pickEmails(`${this.query} ${text}`)
      this.open = true
    },
    submit() {
      if (this.validSelected.length === 0 || this.disabled) {
        return
      }
      this.$emit('add', [...this.validSelected], this.roleUid)
    },
    reset() {
      this.selected = []
      this.query = ''
    },
  },
}
</script>
