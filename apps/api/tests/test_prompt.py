"""Mai Filer system-prompt composition tests."""

from app.agents.mai_filer.prompt import BASE_DOCTRINE, build_system_blocks, get_system_prompt


def test_base_doctrine_mentions_all_ten_roles() -> None:
    for n in range(1, 11):
        assert f"{n}." in BASE_DOCTRINE, f"role #{n} missing from base doctrine"


def test_base_doctrine_cites_v1_scope_and_pit_bands() -> None:
    assert "v1 scope" in BASE_DOCTRINE
    assert "₦800,000" in BASE_DOCTRINE
    assert "₦50,000,000" in BASE_DOCTRINE
    assert "NIN" in BASE_DOCTRINE
    assert "consent" in BASE_DOCTRINE


def test_system_blocks_use_cache_on_base_only() -> None:
    blocks = build_system_blocks("en")
    assert len(blocks) == 2
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocks[1]


def test_language_addendum_varies_by_code() -> None:
    en = build_system_blocks("en")[1]["text"]
    ha = build_system_blocks("ha")[1]["text"]
    yo = build_system_blocks("yo")[1]["text"]
    ig = build_system_blocks("ig")[1]["text"]
    pcm = build_system_blocks("pcm")[1]["text"]
    variants = {en, ha, yo, ig, pcm}
    assert len(variants) == 5, "each language must have a distinct addendum"


def test_flat_prompt_contains_base_and_language() -> None:
    flat = get_system_prompt("pcm")
    assert BASE_DOCTRINE in flat
    assert "Nigerian Pidgin" in flat
