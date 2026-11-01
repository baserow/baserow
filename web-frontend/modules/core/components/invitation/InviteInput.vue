<template>
  <div class="invite-input">
    <p v-if="batchLimitExceeded" class="invite-input__batch-error" role="alert">
      {{
        $t('inviteInput.batchLimitExceeded', { limit: invitationBatchLimit })
      }}
    </p>
    <div ref="row" class="invite-input__row">
      <div class="invite-input__field" @click="focus">
        <span
          v-for="item in selected"
          :key="item.key"
          v-tooltip:[chipTooltipOptions]="chipError(item)"
          class="invite-input__chip"
          :class="{ 'invite-input__chip--error': chipError(item) !== null }"
          @mousedown.prevent
        >
          <component
            :is="item.avatarComponent"
            v-if="item.avatarComponent"
            :subject="item.subject"
            size="small"
            aria-hidden="true"
          />
          <i v-else class="invite-input__chip-icon" :class="item.icon"></i>
          <span class="invite-input__chip-label">{{ item.name }}</span>
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
          @blur="blur"
          @keydown.enter.prevent="pickEmails(query)"
          @keyup.escape="escape"
          @keydown.delete="removeLastWhenEmpty"
          @paste="paste"
        />
        <a
          v-if="query !== ''"
          class="invite-input__clear"
          @mousedown.prevent
          @click.stop="clearQuery"
        >
          <i class="iconoir-cancel"></i>
        </a>
      </div>
      <WorkspaceRoleSelector
        v-model="roleUid"
        class="invite-input__role"
        :workspace="workspace"
        :roles="roles"
      />
      <Button
        type="primary"
        :disabled="
          validSelected.length === 0 ||
          hasInvalidEmails ||
          batchLimitExceeded ||
          disabled
        "
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
    <Context
      ref="results"
      class="invite-input__results"
      :style="{ width: resultsWidth }"
      @hidden="close"
      @mousedown.prevent
    >
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
        <a
          role="button"
          :title="$t('action.close')"
          class="invite-input__close"
          @click="close"
        >
          <i class="iconoir-cancel"></i>
        </a>
      </div>
      <ul class="invite-input__list">
        <li
          v-for="option in emailOptions"
          :key="option.key"
          class="invite-input__item"
          @click="toggle(option)"
        >
          <Avatar icon="iconoir-mail" color="neutral" rounded size="large" />
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
          <component
            :is="option.avatarComponent"
            v-if="option.avatarComponent"
            :subject="option.subject"
            size="large"
          />
          <Avatar
            v-else
            :initials="option.initials"
            :icon="option.initials ? '' : option.icon"
            :color="option.color"
            rounded
            size="large"
          />
          <div class="invite-input__item-text">
            <div class="invite-input__item-title">{{ option.name }}</div>
            <div v-if="option.subtitle" class="invite-input__item-subtitle">
              {{ option.subtitle }}
            </div>
          </div>
          <span
            v-if="option.disabledReason"
            v-tooltip:[chipTooltipOptions]="option.disabledReason"
            class="invite-input__item-hint"
          >
            {{ option.disabledHint }}
          </span>
          <Checkbox
            v-else
            :checked="isSelected(option)"
            @click.stop
            @update:model-value="toggle(option)"
          ></Checkbox>
        </li>
      </ul>
      <div v-if="nothingToShow" class="invite-input__empty">
        {{ noResultsTextOrDefault }}
      </div>
    </Context>
    <slot></slot>
  </div>
</template>

<script>
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'
import { isValidStrictEmail } from '@baserow/modules/core/utils/string'

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
 * avatarComponent, subject }` with an optional `email` for someone who can be
 * found by their address. One that can't be picked, because it already has a
 * role, an invitation or whatever else, carries the reason in
 * `disabledReason` and a short version of it, like "Editor here", in
 * `disabledHint`: it is listed with the hint in place of a checkbox and the
 * reason as its tooltip, so that every row keeps the same height, and an
 * address that belongs to it turns into a chip marked as an error that is left
 * out of what is submitted. The same happens to every new address while a role
 * outside `emailRoleUids` is chosen, for a role that can be given to a member
 * but makes no sense as an invitation. Malformed email addresses are also
 * marked as errors, but block the whole batch until corrected or removed.
 * The parent decides what is disabled and
 * why, so the input needs to know nothing about members, agents or invitations.
 *
 * `tabs` are `{ value, label }` matching the option types, and an "All" tab is
 * added in front. With tabs the list opens on focus and shows every option,
 * including those that can't be picked with their hint, so nobody has to be
 * remembered by name. Without tabs it only opens once something is typed.
 *
 * A result row toggles on click, and so does its checkbox. The checkbox is a
 * label around a native input, whose click would bubble to the row and toggle
 * it back, so the checkbox keeps its click to itself and toggles through its
 * own change event instead. The list stays open while the chips and the list
 * itself are clicked, because neither takes the focus away from the input,
 * except for the native input of a checkbox, which gets the focus when its
 * label is clicked and hands it straight back. The results open in an anchored
 * context below the input, leaving the default slot visible. Closing the context
 * keeps the picks and search so they can be continued on focus.
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
    /**
     * Why new email invitations are unavailable, while existing subjects can
     * still be picked. Null allows new email invitations.
     */
    emailDisabledReason: {
      type: String,
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
      resultsWidth: 'auto',
      open: false,
      activeTab: TAB_ALL,
      selected: [],
      roleUid: this.initialRoleUid(this.roles),
    }
  },
  computed: {
    invitationBatchLimit() {
      const limit = Number(this.$config.public.baserowInvitationBatchLimit)
      return Number.isInteger(limit) && limit > 0 ? limit : 5
    },
    /**
     * Count distinct new addresses, including those still being typed. Known
     * subjects and pending invitations are not new email invitations.
     */
    batchLimitExceeded() {
      const emails = [
        ...this.selected
          .filter((item) => item.type === 'email')
          .map(({ email }) => email),
        ...this.queryEmails,
      ].filter((email) => !this.optionWithEmail(email))
      return (
        new Set(emails.map((email) => email.toLowerCase())).size >
        this.invitationBatchLimit
      )
    },
    placeholderText() {
      return this.placeholder ?? this.$t('inviteInput.placeholder')
    },
    noResultsTextOrDefault() {
      if (this.emailDisabledReason && this.queryEmails.length > 0) {
        return this.emailDisabledReason
      }
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
     * can't be picked is listed with the reason why it isn't offered, but an
     * address that can't be picked only shows up when it is searched for, as
     * it isn't someone to browse for.
     */
    visibleOptions() {
      return this.options.filter(
        (option) =>
          (this.activeTab === TAB_ALL ||
            option.type === 'email' ||
            option.type === this.activeTab) &&
          (option.type !== 'email' ||
            !option.disabledReason ||
            this.normalizedQuery !== '') &&
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
      return this.open && (this.tabs.length > 0 || this.normalizedQuery !== '')
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
    /**
     * A malformed address blocks the whole batch, including an address still
     * in the text field, so successful invitations can't clear it unseen.
     */
    hasInvalidEmails() {
      return (
        this.selected.some(
          (item) => item.type === 'email' && !isValidStrictEmail(item.email)
        ) || this.queryEmails.some((email) => !isValidStrictEmail(email))
      )
    },
  },
  watch: {
    showResults(show) {
      if (show) {
        this.showResultsContext()
      } else {
        this.$refs.results.hide(false)
      }
    },
    // Picking chips can wrap the input onto another line.
    'selected.length'() {
      if (this.showResults) {
        this.$nextTick(() => this.showResultsContext())
      }
    },
    roles(roles) {
      if (!roles.some((role) => role.uid === this.roleUid)) {
        this.roleUid = this.initialRoleUid(roles)
      }
    },
  },
  methods: {
    /**
     * Prefer the default declared by an active invitation role. When none is
     * available, fall back to the last active invitation role.
     */
    initialRoleUid(roles) {
      const active = roles.filter(
        (role) =>
          !role.isDeactivated &&
          (this.emailRoleUids === null || this.emailRoleUids.includes(role.uid))
      )
      return (
        active.find((role) => role.isDefaultForInvitations)?.uid ??
        active[active.length - 1]?.uid ??
        null
      )
    },
    focus() {
      this.$refs.input.focus()
    },
    showResultsContext() {
      const row = this.$refs.row
      this.resultsWidth = `${row.offsetWidth}px`
      this.$refs.results.show(row, 'bottom', 'left', 8)
    },
    /**
     * Escape closes the results when they are open, and only them: the modal
     * around the input closes on the key going up as well, so it must not
     * reach it then.
     */
    escape(event) {
      if (this.showResults) {
        event.stopPropagation()
        this.close()
      }
    },
    /**
     * Closes the results and leaves the input, so that they open again once it
     * is focused. The input is left first, as leaving it keeps the results of a
     * search open.
     */
    close() {
      this.$refs.input.blur()
      this.open = false
    },
    /**
     * Closes the results, unless the focus went to something inside them, like
     * the native input of a checkbox, which would remove the checkbox before
     * its change event toggles the row. Results of a search stay, so that what
     * was typed isn't lost by clicking elsewhere.
     */
    blur(event) {
      if (
        this.$refs.results
          ?.getTeleportedElement()
          ?.contains(event.relatedTarget)
      ) {
        this.focus()
        return
      }
      this.open = this.normalizedQuery !== ''
    },
    clearQuery() {
      this.query = ''
      this.focus()
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
      if (
        this.emailDisabledReason ||
        !isValidStrictEmail(email) ||
        this.optionWithEmail(email)
      ) {
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
      if (item.type === 'email' && !isValidStrictEmail(item.email)) {
        return this.$t('error.invalidEmail')
      }
      if (item.disabledReason) {
        return item.disabledReason
      }
      if (item.type === 'email' && this.emailDisabledReason) {
        return this.emailDisabledReason
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
     * new address. Malformed addresses stay visible as error chips and block
     * submission until removed and corrected.
     */
    pickEmails(text) {
      for (const token of extractEmails(text)) {
        const email = token.toLowerCase()
        const pick = this.optionWithEmail(email) || this.emailPick(email)
        if (!this.isSelected(pick)) {
          this.selected.push(pick)
        }
      }
      this.query = ''
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
      if (
        this.validSelected.length === 0 ||
        this.hasInvalidEmails ||
        this.batchLimitExceeded ||
        this.disabled
      ) {
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
