from starlette.requests import Request

from qrfacile_app import auth_routes
from qrfacile_app.ui_shell import banner


def _request(path="/login"):
    return Request({
        "type": "http", "method": "GET", "scheme": "https", "path": path,
        "headers": [(b"host", b"example.test")], "client": ("127.0.0.1", 1),
    })


def test_login_fields_have_explicit_accessible_labels():
    body = auth_routes.login_get(_request()).body.decode("utf-8")
    assert 'label for="login-email"' in body
    assert 'id="login-email" name="email"' in body
    assert 'label for="login-password"' in body
    assert 'id="login-password" name="password"' in body


def test_password_recovery_fields_have_explicit_accessible_labels():
    forgot = auth_routes._forgot_password_body()
    reset = auth_routes._reset_password_body("opaque-token")
    assert 'label for="forgot-email"' in forgot
    assert 'id="forgot-email" name="email"' in forgot
    assert 'label for="reset-password"' in reset
    assert 'label for="reset-password-confirm"' in reset


def test_feedback_is_announced_to_assistive_technology():
    output = banner("Salvato", "Controlla i dati")
    assert "role='status' aria-live='polite'" in output
    assert "role='alert'" in output
    assert 'role="status" aria-live="polite"' in auth_routes._forgot_password_body(msg="Controlla la posta")
    assert 'role="alert"' in auth_routes._reset_password_body("opaque-token", err="Link scaduto")
