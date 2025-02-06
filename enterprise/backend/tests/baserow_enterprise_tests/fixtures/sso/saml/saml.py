import os

from baserow_enterprise.sso.saml.models import SamlAuthProviderModel


def read_xml_data_from_file(filename):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    return open(os.path.join(dir_path, filename)).read().replace("\n", " ")


def load_test_idp_metadata():
    return read_xml_data_from_file("idp_test_metadata.xml")


def load_valid_idp_metadata_and_response():
    idp_valid_metadata = read_xml_data_from_file("idp_valid_metadata.xml")
    valid_response = read_xml_data_from_file("idp_valid_response.bin")
    return idp_valid_metadata, valid_response


def load_valid_idp_metadata_and_response_for_builder():
    idp_valid_metadata = read_xml_data_from_file("idp_valid_metadata_builder.xml")
    valid_response = read_xml_data_from_file("idp_valid_response_builder.bin")
    return idp_valid_metadata, valid_response


class SamlFixture:
    def get_test_saml_idp_metadata(self):
        return load_test_idp_metadata()

    def get_valid_saml_idp_metadata_and_response(self):
        return load_valid_idp_metadata_and_response()

    def get_valid_saml_idp_metadata_and_response_for_builder(self):
        return load_valid_idp_metadata_and_response_for_builder()

    def create_saml_auth_provider(self, **kwargs):
        if "domain" not in kwargs:
            kwargs["domain"] = self.fake.domain_name()

        if "metadata" not in kwargs:
            kwargs["metadata"] = self.get_test_saml_idp_metadata()

        if "enabled" not in kwargs:
            kwargs["enabled"] = True

        if "is_verified" not in kwargs:
            kwargs["is_verified"] = False

        return SamlAuthProviderModel.objects.create(**kwargs)
