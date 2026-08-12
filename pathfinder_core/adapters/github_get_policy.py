from __future__ import annotations

import re
from urllib.parse import parse_qsl, unquote, urlsplit

from .github_get_transport import API_HOST


MAX_PAGES = 30
_PART = r"[A-Za-z0-9_.%~-]+"
_REF = r"[A-Za-z0-9_.%~/-]+"
_ALLOWED_QUERY_KEYS = frozenset({
    "environment", "includes_parents", "page", "per_page", "ref", "sha",
})
_ALLOWED_PATHS = tuple(re.compile(pattern) for pattern in (
    r"^/versions$",
    r"^/app$",
    r"^/app/installations/[1-9][0-9]*$",
    rf"^/users/{_PART}$",
    rf"^/orgs/{_PART}/memberships/{_PART}$",
    rf"^/orgs/{_PART}/teams/{_PART}/memberships/{_PART}$",
    rf"^/repos/{_PART}/{_PART}$",
    rf"^/repos/{_PART}/{_PART}/git/ref/heads/{_REF}$",
    rf"^/repos/{_PART}/{_PART}/pulls/[1-9][0-9]*$",
    rf"^/repos/{_PART}/{_PART}/pulls/[1-9][0-9]*/(?:files|reviews|requested_reviewers|merge)$",
    rf"^/repos/{_PART}/{_PART}/collaborators/{_PART}/permission$",
    rf"^/repos/{_PART}/{_PART}/branches/{_REF}/protection$",
    rf"^/repos/{_PART}/{_PART}/rules/branches/{_REF}$",
    rf"^/repos/{_PART}/{_PART}/rulesets(?:/[1-9][0-9]*)?$",
    rf"^/repos/{_PART}/{_PART}/commits/{_REF}/(?:check-runs|status)$",
    rf"^/repos/{_PART}/{_PART}/deployments(?:/[1-9][0-9]*/statuses)?$",
))


def validate_evidence_target(target: str) -> str:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith("/"):
        raise ValueError("GitHub GET target must be an API-relative path")
    decoded = unquote(parsed.path)
    if (
        "%2f" in parsed.path.lower()
        or "%5c" in parsed.path.lower()
        or "\\" in decoded
        or any(part in {"", ".", ".."} for part in decoded.split("/")[1:])
    ):
        raise ValueError("GitHub GET target is not normalized")
    if any(ord(character) < 32 for character in target + decoded):
        raise ValueError("GitHub GET target contains a control character")
    if not any(pattern.fullmatch(parsed.path) for pattern in _ALLOWED_PATHS):
        raise ValueError("GitHub GET target is outside the evidence endpoint allowlist")
    query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    keys = [key for key, _value in query]
    if (
        len(keys) != len(set(keys))
        or any(key not in _ALLOWED_QUERY_KEYS for key in keys)
        or any(not value or len(value) > 512 for _key, value in query)
    ):
        raise ValueError("GitHub GET query is outside the evidence parameter allowlist")
    values = dict(query)
    if "includes_parents" in values and values["includes_parents"] != "true":
        raise ValueError("GitHub GET parent-ruleset query must be true")
    for key in ("page", "per_page"):
        ceiling = MAX_PAGES if key == "page" else 100
        if key in values and (
            not values[key].isdigit() or not 1 <= int(values[key]) <= ceiling
        ):
            raise ValueError("GitHub GET pagination parameter is invalid")
    return target


def redirect_evidence_target(location: str) -> str:
    parsed = urlsplit(location)
    if parsed.scheme or parsed.netloc:
        if (
            parsed.scheme != "https"
            or parsed.hostname != API_HOST
            or parsed.port not in {None, 443}
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("GitHub redirect escaped the fixed TLS host")
        location = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    return validate_evidence_target(location)
