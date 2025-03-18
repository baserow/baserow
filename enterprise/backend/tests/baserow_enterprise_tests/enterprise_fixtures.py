import faker
from baserow_premium.license.models import License

from baserow.core.cache import local_cache
from baserow.core.models import Settings
from baserow_enterprise.models import Role, RoleAssignment, Team, TeamSubject

VALID_ONE_SEAT_ENTERPRISE_LICENSE = (
    # id: "1", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjUzODczYmVkLWJlNTQtNDEwZS04N2EzLTE2OTM2ODY2YjBiNiIsICJ2YWxpZF9mcm9tIjogIjIwMjItMTAtMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDY5LTA4LTA5VDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJlbnRlcnByaXNlIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIyLTEwLTI2VDE0OjQ4OjU0LjI1OTQyMyIsICJpc3N1ZWRfdG9fZW1haWwiOiAidGVzdEB0ZXN0LmNvbSIsICJpc3N1ZWRfdG9fbmFtZSI6ICJ0ZXN0QHRlc3QuY29tIiwgImluc3RhbmNlX2lkIjogIjEifQ==.B7aPXR0R4Fxr28AL7B5oopa2Yiz_MmEBZGdzSEHHLt4wECpnzjd_SF440KNLEZYA6WL1rhNkZ5znbjYIp6KdCqLdcm1XqNYOIKQvNTOtl9tUAYj_Qvhq1jhqSja-n3HFBjIh9Ve7a6T1PuaPLF1DoxSRGFZFXliMeJRBSzfTsiHiO22xRQ4GwafscYfUIWvIJJHGHtYEd9rk0tG6mfGEaQGB4e6KOsN-zw-bgLDBOKmKTGrVOkZnaGHBVVhUdpBn25r3CFWqHIApzUCo81zAA96fECHPlx_fBHhvIJXLsN5i3LdeJlwysg5SBO15Vt-tsdPmdcsec-fOzik-k3ib0A== "
)


class EnterpriseFixtures:
    faker = faker.Faker()

    def create_enterprise_admin_user_and_token(self, **kwargs):
        user, token = self.create_user_and_token(is_staff=True, **kwargs)
        self.enable_enterprise()
        return user, token

    def enable_enterprise(self):
        Settings.objects.update_or_create(defaults={"instance_id": "1"})
        if not License.objects.filter(cached_untrusted_instance_wide=True).exists():
            license = License.objects.create(
                license=VALID_ONE_SEAT_ENTERPRISE_LICENSE.decode(),
                cached_untrusted_instance_wide=True,
            )
        else:
            license = License.objects.filter(cached_untrusted_instance_wide=True).get()

        local_cache.clear()

        return license

    def delete_all_licenses(self):
        License.objects.all().delete()
        local_cache.clear()

    def create_team(self, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace()
        members = kwargs.pop("members", [])

        team = Team.objects.create(**kwargs)

        for member in members:
            self.create_subject(team=team, subject=member)

        return team

    def create_subject(self, team=None, subject=None, **kwargs):
        if subject is None:
            subject = self.create_user()
        if team is None:
            team = self.create_team()

        subject = TeamSubject.objects.create(team=team, subject=subject, **kwargs)

        return subject

    def create_role_assignment(self, **kwargs):
        user = kwargs.get("user", None)
        role_uid = kwargs.get("role_uid", "builder")
        workspace = kwargs.get("workspace", None)
        scope = kwargs.get("scope", None)

        if "user" not in kwargs:
            user = super().create_user()

        if workspace is None:
            workspace = super().create_workspace(user=user)

        if scope is None:
            scope = workspace

        role = Role.objects.get(uid=role_uid)

        return RoleAssignment.objects.create(
            subject=user, role=role, workspace=workspace, scope=scope
        )
