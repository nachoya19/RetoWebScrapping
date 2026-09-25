"""Form extractor — identifies and classifies HTML forms."""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import FormField, FormInfo, FormType

# Tokens CSRF habituales
_CSRF_NAMES = {
    "csrf", "csrftoken", "csrf_token", "_csrf", "_token",
    "authenticity_token", "xsrf", "xsrf_token", "__requestverificationtoken",
    "anticsrf", "anti-csrf-token",
}


def _classify_form(form_info: FormInfo) -> FormType:
    """Heuristic classification of a form."""
    field_types = {f.type for f in form_info.fields}
    field_names = {(f.name or "").lower() for f in form_info.fields}

    # Upload: multipart or file input
    if form_info.enctype and "multipart" in form_info.enctype:
        return FormType.UPLOAD
    if "file" in field_types:
        return FormType.UPLOAD

    # Login: password + text/email
    if "password" in field_types and field_types & {"text", "email"}:
        return FormType.LOGIN

    # Search: search-like field names or HTML5 search input type (any method)
    search_names = {"q", "query", "search", "s", "buscar", "keyword", "keywords"}
    if field_names & search_names or "search" in field_types:
        return FormType.SEARCH

    return FormType.OTHER


def extract_forms(html: str, page_url: str) -> list[FormInfo]:
    """Extract all <form> elements from *html* and return structured data."""
    soup = BeautifulSoup(html, "lxml")
    results: list[FormInfo] = []

    for form_tag in soup.find_all("form"):
        if not isinstance(form_tag, Tag):
            continue

        action_raw = form_tag.get("action", "")
        if isinstance(action_raw, list):
            action_raw = action_raw[0] if action_raw else ""
        action = urljoin(page_url, action_raw) if action_raw else page_url

        method = (form_tag.get("method") or "get")
        if isinstance(method, list):
            method = method[0]
        method = method.lower()

        enctype = form_tag.get("enctype")
        if isinstance(enctype, list):
            enctype = enctype[0]

        fields: list[FormField] = []
        has_csrf = False
        csrf_name: str | None = None

        for tag in form_tag.find_all(["input", "select", "textarea"]):
            if not isinstance(tag, Tag):
                continue

            name = tag.get("name")
            if isinstance(name, list):
                name = name[0]
            ftype = tag.get("type", "text") if tag.name == "input" else tag.name  # type: ignore[arg-type]
            if isinstance(ftype, list):
                ftype = ftype[0]
            ftype = (ftype or "text").lower()

            value = tag.get("value", "")
            if isinstance(value, list):
                value = value[0]

            placeholder = tag.get("placeholder", "")
            if isinstance(placeholder, list):
                placeholder = placeholder[0]

            required = tag.has_attr("required")
            is_hidden = ftype == "hidden"

            fields.append(
                FormField(
                    name=name,
                    type=ftype,
                    value=value or None,
                    placeholder=placeholder or None,
                    required=required,
                    is_hidden=is_hidden,
                )
            )

            # CSRF detection
            if is_hidden and name and name.lower().replace("-", "").replace("_", "") in {
                n.replace("-", "").replace("_", "") for n in _CSRF_NAMES
            }:
                has_csrf = True
                csrf_name = name

        form_info = FormInfo(
            page_url=page_url,
            action=action,
            method=method,
            enctype=enctype,
            fields=fields,
            has_csrf_token=has_csrf,
            csrf_field_name=csrf_name,
        )
        form_info.form_type = _classify_form(form_info)
        results.append(form_info)

    return results
