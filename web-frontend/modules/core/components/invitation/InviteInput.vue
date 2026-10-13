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
          @mousedown.prevent
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
          :class="{ 'invite-input__item--disabled': option.disabledReason }"
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
            <div
              v-if="option.disabledReason || option.subtitle"
              class="invite-input__item-subtitle"
            >
              {{ option.disabledReason || option.subtitle }}
            </div>
          </div>
          <Checkbox
            v-if="!option.disabledReason"
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
 * or pasted in bulk, and searches a list of `options`, grouped by `tabs`, such
 * as the members, teams and agents of the workspace. Every pick is shown as a
 * chip. Submitting emits `add` with the picked items and the chosen role uid;
 * the parent calls `remove()` or `reset()` once they were added.
 *
 * An option is an object of `{ key, type, id, name, subtitle, search,
 * initials, icon, color }` with an optional `email` for someone who can be
 * found by their address. One that can't be picked, because it already has a
 * role, an invitation or whatever else, carries the reason in
 * `disabledReason`: it is listed with that reason instead of a checkbox, and an
 * address that belongs to it turns into a chip marked as an error that is left
 * out of what is submitted. The same happens to every new address while a role
 * outside `emailRoleUids` is chosen, for a role that can be given to a member
 * but makes no sense as an invitation. The parent decides what is disabled and
 * why, so the input needs to know nothing about members, agents or invitations.
 *
 * `tabs` are `{ value, label }` matching the option types, and an "All" tab is
 * added in front. Without tabs the list only opens once something is typed.
 *
 * A result row toggles on click, and so does its checkbox. The checkbox is a
 * label around a native input, whose click would bubble to the row and toggle
 * it back, so the checkbox keeps its click to itself and toggles through its
 * own change event instead. The list stays open while the chips and the list
 * itself are clicked, because neither takes the focus away from the input.
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
    /**
     * The uids of the roles an email address can be invited with, or null when
     * every role will do. The default role is the last of these.
     */
    emailRoleUids: {
      type: Array,
      required: false,
      default: null,
    },
    placeholder: {
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
      roleUid: this.initialRoleUid(this.roles),
    }
  },
  computed: {
    placeholderText() {
      return this.placeholder ?? this.$t('inviteInput.placeholder')
    },
    noResultsTextOrDefault() {
      return this.noResultsText ?? this.$t('inviteInput.noResults')
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
    roleAllowsEmails() {
      return (
        this.emailRoleUids === null || this.emailRoleUids.includes(this.roleUid)
      )
    },
    normalizedQuery() {
      return this.query.trim().toLowerCase()
    },
    /**
     * The options matching the tab and the search. An address row is about an
     * address rather than a kind of subject, so it shows under every tab. What
     * can't be picked only shows up when it is searched for, to explain why it
     * isn't offered, and stays out of the way otherwise.
     */
    visibleOptions() {
      return this.options.filter(
        (option) =>
          (this.activeTab === TAB_ALL ||
            option.type === 'email' ||
            option.type === this.activeTab) &&
          (!option.disabledReason || this.normalizedQuery !== '') &&
          option.search.toLowerCase().includes(this.normalizedQuery)
      )
    },
    /**
     * The distinct addresses in the field.
     */
    queryEmails() {
      return [
        ...new Set(
          extractEmails(this.query).map((email) => email.toLowerCase())
        ),
      ]
    },
    /**
     * The rows of new addresses: one per typed address that isn't known as an
     * option, followed by the picked addresses that match the search. The
     * picked ones keep a row like a picked member does, so they can be
     * unchecked from the list as well as from their chip.
     */
    emailOptions() {
      const typed = this.queryEmails
        .map((email) => this.newEmailOptionFor(email))
        .filter(Boolean)
      const picked = this.selected.filter(
        (item) =>
          item.type === 'email' &&
          this.chipError(item) === null &&
          !typed.some(({ key }) => key === item.key) &&
          item.email.includes(this.normalizedQuery)
      )
      return [...typed, ...picked]
    },
    /**
     * With a list to browse the results open on focus, otherwise there is
     * nothing to show until something is typed.
     */
    showResults() {
      return (
        this.open &&
        (this.tabs.length > 0 ||
          this.options.some((option) => !option.disabledReason) ||
          this.normalizedQuery !== '')
      )
    },
    nothingToShow() {
      return this.emailOptions.length === 0 && this.visibleOptions.length === 0
    },
    /**
     * The picks that can be submitted: everything but the chips that carry an
     * error.
     */
    validSelected() {
      return this.selected.filter((item) => this.chipError(item) === null)
    },
  },
  watch: {
    roles(roles) {
      if (!roles.some((role) => role.uid === this.roleUid)) {
        this.roleUid = this.initialRoleUid(roles)
      }
    },
  },
  methods: {
    /**
     * The last active role is the one with the least access, the safest
     * default, as long as an address can be invited with it.
     */
    initialRoleUid(roles) {
      const active = roles.filter(
        (role) =>
          !role.isDeactivated &&
          (this.emailRoleUids === null || this.emailRoleUids.includes(role.uid))
      )
      return active.length > 0 ? active[active.length - 1].uid : null
    },
    focus() {
      this.$refs.input.focus()
    },
    optionWithEmail(email) {
      return this.options.find(
        (option) => option.email?.toLowerCase() === email
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
    /**
     * A pick for a new address: a valid address that no option, pickable or
     * not, answers to.
     */
    newEmailOptionFor(email) {
      if (!isValidEmail(email) || this.optionWithEmail(email)) {
        return null
      }
      return this.emailPick(email)
    },
    /**
     * Why a chip can't be submitted, or null when it can. Judged at render time
     * so that a chip picked before the options were fully known is marked as
     * soon as they are.
     */
    chipError(item) {
      if (item.disabledReason) {
        return item.disabledReason
      }
      if (item.type === 'email' && !this.roleAllowsEmails) {
        return this.$t('inviteInput.roleNotForEmails', { role: this.roleName })
      }
      return null
    },
    isSelected(option) {
      return this.selected.some((item) => item.key === option.key)
    },
    toggle(option) {
      if (option.disabledReason) {
        return
      }
      if (this.isSelected(option)) {
        this.remove(option)
      } else {
        this.selected.push(option)
        this.dropFromQuery(option.email)
      }
      this.focus()
    },
    /**
     * Takes the address out of the field once it was picked, whether as a new
     * address or as the option it belongs to, so it isn't left behind as text.
     */
    dropFromQuery(email) {
      const tokens = extractEmails(this.query)
      const matches = (token) => token.toLowerCase() === email?.toLowerCase()
      if (email && tokens.some(matches)) {
        this.query = tokens.filter((token) => !matches(token)).join(' ')
      }
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
     * Picks every address in the text: the option it belongs to, which makes
     * a chip marked as an error when that option can't be picked, or else a
     * new address. Only text that isn't an address stays in the field.
     */
    pickEmails(text) {
      const leftovers = []
      for (const token of extractEmails(text)) {
        const email = token.toLowerCase()
        if (!isValidEmail(email)) {
          leftovers.push(token)
          continue
        }
        const pick = this.optionWithEmail(email) || this.emailPick(email)
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
