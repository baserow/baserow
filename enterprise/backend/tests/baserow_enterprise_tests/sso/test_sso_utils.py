from baserow_enterprise.api.sso.utils import get_valid_frontend_url


def test_get_valid_front_url():
    assert get_valid_frontend_url() == "http://localhost:3000/dashboard"
    assert (
        get_valid_frontend_url("http://localhost:3000/dashboard")
        == "http://localhost:3000/dashboard"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/dashboard/after")
        == "http://localhost:3000/dashboard/after"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/other")
        == "http://localhost:3000/other"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/other", allow_any_path=False)
        == "http://localhost:3000/dashboard"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/")
        == "http://localhost:3000/dashboard"
    )

    assert (
        get_valid_frontend_url("http://something.com/")
        == "http://localhost:3000/dashboard"
    )
    assert (
        get_valid_frontend_url("http://something.com/dashboard/test")
        == "http://localhost:3000/dashboard"
    )


def test_get_valid_front_url_with_defaults():
    defaults = ["https://test.com/toto", "http://random.net/"]
    assert (
        get_valid_frontend_url(default_frontend_urls=defaults)
        == "https://test.com/toto"
    )
    assert (
        get_valid_frontend_url("https://test.com/toto", default_frontend_urls=defaults)
        == "https://test.com/toto"
    )
    assert (
        get_valid_frontend_url("http://random.net/", default_frontend_urls=defaults)
        == "http://random.net/"
    )
    assert (
        get_valid_frontend_url(
            "https://test.com/toto/subpath/", default_frontend_urls=defaults
        )
        == "https://test.com/toto/subpath/"
    )
    assert (
        get_valid_frontend_url("https://test.com/titi/", default_frontend_urls=defaults)
        == "https://test.com/titi/"
    )
    assert (
        get_valid_frontend_url(
            "https://test.com/titi/",
            default_frontend_urls=defaults,
        )
        == "https://test.com/titi/"
    )
    assert (
        get_valid_frontend_url(
            "https://test.com/titi/",
            default_frontend_urls=defaults,
            allow_any_path=False,
        )
        == "https://test.com/toto"
    )
    assert (
        get_valid_frontend_url("http://random.net/", default_frontend_urls=defaults)
        == "http://random.net/"
    )
    assert (
        get_valid_frontend_url("http://random.net/path", default_frontend_urls=defaults)
        == "http://random.net/path"
    )
    assert (
        get_valid_frontend_url("http://other.net/path", default_frontend_urls=defaults)
        == "https://test.com/toto"
    )


def test_get_valid_front_url_w_params():
    assert (
        get_valid_frontend_url(query_params={"test": "value"})
        == "http://localhost:3000/dashboard?test=value"
    )
    assert (
        get_valid_frontend_url(
            "http://localhost:3000/dashboard", query_params={"test": "value"}
        )
        == "http://localhost:3000/dashboard?test=value"
    )
