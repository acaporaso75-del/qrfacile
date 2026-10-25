from pathlib import Path

from qrfacile_app.password_policy import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    new_password_error,
)
from qrfacile_app import auth_routes, studio_register_routes, winery_register_routes


def test_new_password_policy_accepts_passphrases_and_rejects_extremes():
    assert MIN_PASSWORD_LENGTH == 12
    assert MAX_PASSWORD_LENGTH == 128
    assert new_password_error("a" * 11) == "Password minimo 12 caratteri."
    assert new_password_error("correct horse battery staple") == ""
    assert new_password_error("a" * 129) == "Password massimo 128 caratteri."


def test_all_new_password_flows_use_the_central_policy():
    for module in (auth_routes, studio_register_routes, winery_register_routes):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "new_password_error(password)" in source
        assert "len(password) < 8" not in source


def test_password_inputs_publish_the_same_length_bounds():
    reset = auth_routes._reset_password_body("opaque-token")
    studio = studio_register_routes._input("password", "password", "secret", required=True)
    winery = winery_register_routes._input("password", "password", "secret", required=True)
    for markup in (reset, studio, winery):
        assert 'minlength="12"' in markup
        assert 'maxlength="128"' in markup


def test_both_registration_flows_require_password_confirmation():
    for module in (studio_register_routes, winery_register_routes):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert 'password_confirm: str = Form(...)' in source
        assert '_input("password_confirm", "password"' in source
        assert 'password != (password_confirm or "")' in source
