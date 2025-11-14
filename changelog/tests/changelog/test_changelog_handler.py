import json

from src.changelog_entry import BugChangelogEntry
from src.handler import MAXIMUM_FILE_NAME_MESSAGE_LENGTH, ChangelogHandler
from src.domains import BuilderDomain, DatabaseDomain


def test_add_entry(fs):
    file_path = ChangelogHandler().add_entry(
        DatabaseDomain.type, BugChangelogEntry.type, "Introducing a new feature."
    )
    assert fs.isfile(file_path)
    with open(file_path, "r") as entry_file:
        entry = json.load(entry_file)
        assert entry["message"] == "Introducing a new feature."
        assert entry["domain"] == DatabaseDomain.type


def test_get_changelog_entries(fs):
    handler = ChangelogHandler()
    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "msg1")
    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "msg2")

    changelog_entries = handler.get_changelog_entries()

    assert BugChangelogEntry.type in changelog_entries
    assert [
        BugChangelogEntry().generate_entry_dict(DatabaseDomain.type, "msg1", "github"),
        BugChangelogEntry().generate_entry_dict(DatabaseDomain.type, "msg2", "github"),
    ] in changelog_entries.values()


def test_get_changelog_entries_order(fs):
    handler = ChangelogHandler()
    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "msg2")
    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "msg1")

    changelog_entries = handler.get_changelog_entries()

    assert BugChangelogEntry.type in changelog_entries
    assert [
        BugChangelogEntry().generate_entry_dict(DatabaseDomain.type, "msg1", "github"),
        BugChangelogEntry().generate_entry_dict(DatabaseDomain.type, "msg2", "github"),
    ] in changelog_entries.values()


def test_get_release_meta_data(fs):
    handler = ChangelogHandler()
    data = {"releases": [{"name": "1.0"}]}
    fs.create_file(handler.release_meta_data_file_path, contents=json.dumps(data))

    assert handler.get_releases_meta_data() == data


def test_get_release_meta_data_file_missing(fs):
    handler = ChangelogHandler()
    assert handler.get_releases_meta_data() is None


def test_order_release_folders(fs):
    releases_meta_data = {"releases": [{"name": "a"}, {"name": "b"}]}
    fs.create_file(
        ChangelogHandler().release_meta_data_file_path,
        contents=json.dumps(releases_meta_data),
    )

    assert ChangelogHandler().order_release_folders(["b", "a"]) == ["a", "b"]


def test_move_entries_to_release_folder(fs):
    handler = ChangelogHandler()

    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "1")
    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "2")
    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "3")

    assert fs.isdir(f"{handler.entries_file_path}/{handler.UNRELEASED_FOLDER_NAME}")

    release_name = handler.move_entries_to_release_folder()

    assert fs.isdir(f"{handler.entries_file_path}/{handler.UNRELEASED_FOLDER_NAME}")
    assert fs.isdir(f"{handler.entries_file_path}/{release_name}")


def test_move_entries_to_release_folder_release_already_exists(fs):
    handler = ChangelogHandler()

    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "1")
    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "2")
    handler.add_entry(DatabaseDomain.type, BugChangelogEntry.type, "3")

    assert fs.isdir(f"{handler.entries_file_path}/{handler.UNRELEASED_FOLDER_NAME}")

    release_name = "test"

    assert handler.move_entries_to_release_folder(release_name) is release_name

    assert fs.isdir(f"{handler.entries_file_path}/{handler.UNRELEASED_FOLDER_NAME}")
    assert fs.isdir(f"{handler.entries_file_path}/{release_name}")

    assert handler.move_entries_to_release_folder(release_name) is None

    # Make sure no extra dir was created for some reason
    assert len(fs.listdir(handler.entries_file_path)) == 2


def test_generate_entry_file_name():
    assert ChangelogHandler.generate_entry_file_name("test") == "test.json"
    assert ChangelogHandler.generate_entry_file_name("test", 123) == "123_test.json"
    assert ChangelogHandler.generate_entry_file_name(":&(tes*..t") == "test.json"
    assert ChangelogHandler.generate_entry_file_name(" test ") == "test.json"
    assert (
        ChangelogHandler.generate_entry_file_name("test sentence")
        == "test_sentence.json"
    )
    assert ChangelogHandler.generate_entry_file_name("TEST") == "test.json"

    long_str = "".join(["e" for i in range(MAXIMUM_FILE_NAME_MESSAGE_LENGTH * 2)])

    assert (
        ChangelogHandler.generate_entry_file_name(long_str)
        == f"{long_str[:MAXIMUM_FILE_NAME_MESSAGE_LENGTH]}.json"
    )


def test_write_release_meta_data_file_doesnt_exist_yet(fs):
    handler = ChangelogHandler()

    assert not fs.isfile(handler.release_meta_data_file_path)

    handler.write_release_meta_data("release")

    assert fs.isfile(handler.release_meta_data_file_path)


def test_write_release_meta_data_file_does_exist(fs):
    handler = ChangelogHandler()

    fs.create_file(handler.release_meta_data_file_path)

    handler.write_release_meta_data("release")

    fs.isfile(handler.release_meta_data_file_path)


def test_write_release_meta_data_file(fs):
    handler = ChangelogHandler()

    handler.write_release_meta_data("first release")
    handler.write_release_meta_data("second release")

    meta_data = handler.get_releases_meta_data()

    assert "releases" in meta_data
    assert len(meta_data["releases"]) == 2
    assert meta_data["releases"][0]["name"] == "second release"
    assert meta_data["releases"][1]["name"] == "first release"


def test_is_release_name_unique(fs):
    fs.create_dir(f"{ChangelogHandler().entries_file_path}/exists")

    assert ChangelogHandler().is_release_name_unique("exists") is False
    assert ChangelogHandler().is_release_name_unique("not exists") is True
