from bs4 import BeautifulSoup, Tag
from fastapi.testclient import TestClient

from dashski.main import app

client = TestClient(app)


def _attr(tag: Tag, name: str) -> str | None:
    value = tag.get(name)
    assert value is None or isinstance(value, str), (
        f"{name} on {tag} is multi-valued, expected a single value"
    )
    return value


def _hx_elements(soup: BeautifulSoup) -> list[Tag]:
    return [tag for tag in soup.find_all(True) if tag.has_attr("hx-get") or tag.has_attr("hx-post")]


def test_hx_targets_exist_on_initial_page() -> None:
    soup = BeautifulSoup(client.get("/").text, "html.parser")
    ids = {_attr(tag, "id") for tag in soup.find_all(id=True)}

    for tag in _hx_elements(soup):
        target = _attr(tag, "hx-target")
        if target is None or not target.startswith("#"):
            continue
        target_id = target.removeprefix("#")
        assert target_id in ids, f"hx-target={target!r} on {tag} has no matching id on the page"


def test_outer_html_swaps_preserve_their_target_id() -> None:
    soup = BeautifulSoup(client.get("/").text, "html.parser")

    for tag in _hx_elements(soup):
        if _attr(tag, "hx-swap") != "outerHTML":
            continue

        target = _attr(tag, "hx-target")
        assert target and target.startswith("#"), (
            f"{tag} uses hx-swap=outerHTML but has no #id hx-target"
        )
        target_id = target.removeprefix("#")

        method, url = (
            ("get", _attr(tag, "hx-get"))
            if tag.has_attr("hx-get")
            else ("post", _attr(tag, "hx-post"))
        )
        assert url is not None
        response = getattr(client, method)(url)
        assert response.status_code == 200

        # outerHTML replaces the target element itself, so the response must
        # re-declare the same id or the next click has nothing to target.
        root = BeautifulSoup(response.text, "html.parser").find(True)
        assert root is not None and _attr(root, "id") == target_id, (
            f"{url} response must have id={target_id!r} at its root, got {root}"
        )
