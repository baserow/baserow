<template>
  <div>
    <p>
      {{ licenseType.getLicenseDescription(license) }}
    </p>
    <div class="license-detail__add">
      <div
        v-show="license.seats - license.seats_taken > 0"
        class="license-detail__add-dropdown"
      >
        <div v-if="addUserLoading" class="loading-overlay"></div>
        <PaginatedDropdown
          ref="add"
          :value="null"
          :fetch-page="fetchUsers"
          :not-selected-text="$t('license.addUser')"
          :add-empty-item="false"
          @input="addUser"
        ></PaginatedDropdown>
      </div>
      {{
        $t('license.seatLeft', {
          count: leftSeats,
        })
      }}
    </div>
    <div
      v-for="(licenseUser, index) in license.users"
      :key="licenseUser.email"
      class="license-detail__user"
    >
      <div class="license-detail__user-number">{{ index + 1 }}</div>
      <div class="license-detail__user-name">
        {{ licenseUser.first_name }}
      </div>
      <div class="license-detail__user-email">{{ licenseUser.email }}</div>
      <div>
        <div v-if="removingUser === licenseUser.id" class="loading"></div>
        <a
          v-else
          class="license-detail__user-delete"
          @click="removeUser(licenseUser)"
        >
          <i class="iconoir-bin"></i>
        </a>
      </div>
    </div>
    <div class="license-detail__actions">
      <div v-if="actionLoading" class="loading"></div>
      <template v-else>
        <a
          v-show="license.seats - license.seats_taken > 0"
          class="margin-right-2"
          @click="fillSeats()"
          >{{ $t('license.fillSeats') }}</a
        >
        <a
          v-show="license.seats - license.seats_taken < license.seats"
          class="color-error"
          @click="removeAllUsers()"
          >{{ $t('license.removeAll') }}</a
        >
      </template>
    </div>
  </div>
</template>
<script>
import LicenseService from '@baserow_premium/services/license'
import { notifyIf } from '@baserow/modules/core/utils/error'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'

export default {
  name: 'ManualLicenseSeatForm',
  components: { PaginatedDropdown },
  props: {
    license: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      user: null,
      addUserLoading: false,
      actionLoading: false,
      checkLoading: false,
      removingUser: -1,
    }
  },
  computed: {
    licenseType() {
      return this.$registry.get('license', this.license.product_code)
    },
    leftSeats() {
      return this.license.seats - this.license.seats_taken
    },
  },
  methods: {
    async addUser(event) {
      this.addUserLoading = true
      try {
        const { data } = await LicenseService(this.$client).addUser(
          this.license.id,
          event
        )
        this.license.users.push(data)
        this.license.seats_taken += 1
      } catch (error) {
        notifyIf(error)
      }

      this.addUserLoading = false
      this.$nextTick(() => {
        this.user = null
        this.$refs.add.reset()
      })
    },
    async removeUser(user) {
      this.removingUser = user.id

      try {
        await LicenseService(this.$client).removeUser(this.license.id, user.id)
        const index = this.license.users.findIndex((u) => u.id === user.id)
        if (index !== undefined) {
          this.license.seats_taken -= 1
          this.license.users.splice(index, 1)
        }
        this.$refs.add.reset()
      } catch (error) {
        notifyIf(error)
      } finally {
        this.removingUser = -1
      }
    },
    async fillSeats() {
      this.actionLoading = true

      try {
        const { data } = await LicenseService(this.$client).fillSeats(
          this.license.id
        )
        this.license.seats_taken += data.length
        this.license.users.push(...data)
        this.$refs.add.reset()
      } catch (error) {
        notifyIf(error)
      }

      this.actionLoading = false
    },
    async removeAllUsers() {
      this.actionLoading = true

      try {
        await LicenseService(this.$client).removeAllUsers(this.license.id)
        this.license.seats_taken = 0
        this.license.users = []
        this.$refs.add.reset()
      } catch (error) {
        notifyIf(error)
      }

      this.actionLoading = false
    },
    fetchUsers(page, search) {
      return LicenseService(this.$client).lookupUsers(
        this.license.id,
        page,
        search
      )
    },
  },
}
</script>
