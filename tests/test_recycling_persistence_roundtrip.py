from pathlib import Path

from qrfacile_app.services.recycling_persistence import persist_recycling_component


class MemoryCursor:
    def __init__(self):
        self.rows = {}
        self.rowcount = 0
        self.result = None

    def execute(self, sql, params):
        compact = " ".join(sql.split()).upper()
        if compact.startswith("INSERT INTO WINE_RECYCLE_ITEMS"):
            wine_id, component, code, note, product, extra = params
            self.rows[(wine_id, component)] = {
                "product": product, "code": code, "extra_code": extra, "note": note,
            }
            self.rowcount = 1
        elif compact.startswith("DELETE FROM WINE_RECYCLE_ITEMS"):
            self.rowcount = int(self.rows.pop(tuple(params), None) is not None)
        elif compact.startswith("SELECT PRODUCT, CODE"):
            self.result = self.rows.get(tuple(params))
            self.rowcount = int(self.result is not None)
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return dict(self.result) if self.result else None


def test_required_catalog_values_roundtrip_and_reload_exactly():
    cur = MemoryCursor()
    values = {
        "bottle": ("Vetro verde", "GL 71"),
        "closure": ("Sughero", "FOR 51"),
        "capsule": ("Alluminio", "ALU 41"),
        "label": ("Carta", "PAP 22"),
        "box": ("Cartone ondulato", "PAP 20"),
    }
    for component, (material, code) in values.items():
        stored = persist_recycling_component(cur, 7, component, {
            "product": material, "code": code, "extra_code": "", "note": f"Nota {component}",
        })
        assert stored.code == code
        assert cur.rows[(7, component)]["code"] == code
        assert cur.rows[(7, component)]["note"] == f"Nota {component}"


def test_custom_extra_note_replacement_and_empty_delete():
    cur = MemoryCursor()
    persist_recycling_component(cur, 8, "other", {
        "product": "Materiale fornitore", "code": "XYZ 99", "extra_code": "LOT-A", "note": "Verificato",
    })
    replaced = persist_recycling_component(cur, 8, "other", {
        "product": "Materiale fornitore", "code": "XYZ 100", "extra_code": "LOT-B", "note": "Nuova nota",
    })
    assert replaced.code == "XYZ 100"
    assert cur.rows[(8, "other")] == {
        "product": "Materiale fornitore", "code": "XYZ 100", "extra_code": "LOT-B", "note": "Nuova nota",
    }
    persist_recycling_component(cur, 8, "other", {"product": "", "code": "-", "extra_code": "", "note": ""})
    assert (8, "other") not in cur.rows


def test_persistence_is_server_side_and_does_not_require_javascript():
    source = Path("qrfacile_app/recycling_validation_ui.py").read_text(encoding="utf-8")
    assert "await request.form()" in source
    assert "persist_recycling_component" in source
    assert "conn.commit()" in source
