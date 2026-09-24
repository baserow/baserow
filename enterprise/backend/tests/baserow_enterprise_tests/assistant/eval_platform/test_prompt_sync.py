import hashlib

from baserow_enterprise.assistant.evals.prompt_sync import (
    SYNCED_PROMPTS,
    prompt_hashes,
    sync_prompts,
)


def _make_version(text: str):
    from phoenix.client.types.prompts import PromptVersion

    return PromptVersion(
        [{"role": "system", "content": text}],
        model_name="gpt-4o",
        model_provider="OPENAI",
        template_format="NONE",
    )


class _FakePromptsAPI:
    def __init__(self):
        self._existing: dict = {}
        self.create_calls: list[dict] = []

    def seed(self, identifier: str, text: str) -> None:
        self._existing[identifier] = _make_version(text)

    def get(self, *, prompt_identifier):
        if prompt_identifier not in self._existing:
            raise ValueError(f"Prompt not found: {prompt_identifier}")
        return self._existing[prompt_identifier]

    def create(self, *, name, version, **kwargs):
        self.create_calls.append({"name": name, "version": version})
        self._existing[name] = version
        return version


class _FakeClient:
    def __init__(self):
        self.prompts = _FakePromptsAPI()


def _seed_all_current(client, except_identifier: str | None = None) -> None:
    for identifier, text in SYNCED_PROMPTS.items():
        if identifier == except_identifier:
            continue
        client.prompts.seed(identifier, text)


class TestSyncedPrompts:
    def test_covers_five_to_ten_prompts(self):
        assert 5 <= len(SYNCED_PROMPTS) <= 10

    def test_identifiers_are_lowercase_kebab(self):
        for identifier in SYNCED_PROMPTS:
            assert identifier == identifier.lower()
            assert " " not in identifier
            assert "_" not in identifier
            assert identifier[0].isalnum()

    def test_includes_the_main_kuma_system_prompt(self):
        from baserow_enterprise.assistant.prompts import AGENT_SYSTEM_PROMPT

        assert SYNCED_PROMPTS["kuma-system-prompt"] == AGENT_SYSTEM_PROMPT

    def test_all_values_are_nonempty_strings(self):
        for identifier, template in SYNCED_PROMPTS.items():
            assert isinstance(template, str), identifier
            assert template.strip(), identifier

    def test_no_duplicate_templates(self):
        """Every synced entry should be a distinct, load-bearing prompt."""

        templates = list(SYNCED_PROMPTS.values())
        assert len(templates) == len(set(templates))


class TestPromptHashes:
    def test_matches_sha256_hexdigest_prefix(self):
        hashes = prompt_hashes()

        assert set(hashes) == set(SYNCED_PROMPTS)
        for identifier, template in SYNCED_PROMPTS.items():
            expected = hashlib.sha256(template.encode()).hexdigest()[:12]
            assert hashes[identifier] == expected

    def test_hashes_are_twelve_hex_chars(self):
        for value in prompt_hashes().values():
            assert len(value) == 12
            int(value, 16)


class TestSyncPrompts:
    def test_creates_every_prompt_when_none_exist(self):
        client = _FakeClient()

        results = sync_prompts(client)

        assert set(results) == set(SYNCED_PROMPTS)
        assert all(status == "created" for status in results.values())
        created_names = {c["name"] for c in client.prompts.create_calls}
        assert created_names == set(SYNCED_PROMPTS)

    def test_leaves_unchanged_prompt_alone(self):
        client = _FakeClient()
        _seed_all_current(client)

        results = sync_prompts(client)

        assert all(status == "unchanged" for status in results.values())
        assert client.prompts.create_calls == []

    def test_updates_when_stored_template_differs(self):
        identifier = "kuma-system-prompt"
        client = _FakeClient()
        _seed_all_current(client, except_identifier=identifier)
        client.prompts.seed(identifier, "a stale, previously-synced version")

        results = sync_prompts(client)

        assert results[identifier] == "updated"
        assert {k: v for k, v in results.items() if k != identifier} == {
            k: "unchanged" for k in SYNCED_PROMPTS if k != identifier
        }
        create_call = next(
            c for c in client.prompts.create_calls if c["name"] == identifier
        )
        stored_content = create_call["version"]._template["messages"][0]["content"]
        assert stored_content == SYNCED_PROMPTS[identifier]

    def test_created_version_carries_current_template_text(self):
        client = _FakeClient()

        sync_prompts(client)

        for identifier, template in SYNCED_PROMPTS.items():
            call = next(
                c for c in client.prompts.create_calls if c["name"] == identifier
            )
            content = call["version"]._template["messages"][0]["content"]
            assert content == template

    def test_mixed_created_updated_unchanged(self):
        client = _FakeClient()
        identifiers = list(SYNCED_PROMPTS)
        untouched, stale = identifiers[0], identifiers[1]
        # everything except `untouched` and `stale` stays missing -> created
        client.prompts.seed(untouched, SYNCED_PROMPTS[untouched])
        client.prompts.seed(stale, "outdated text")

        results = sync_prompts(client)

        assert results[untouched] == "unchanged"
        assert results[stale] == "updated"
        for identifier in identifiers[2:]:
            assert results[identifier] == "created"
