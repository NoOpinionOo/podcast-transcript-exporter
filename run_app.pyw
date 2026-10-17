"""Startdatei fuer einen Doppelklick unter Windows."""

import os
import sys
import traceback
from pathlib import Path

# Der optionale Python-Starthelfer installiert Drittmodule nur in diesen lokalen
# Unterordner. Dadurch sind weder Administratorrechte noch eine globale
# Veraenderung der Python-Installation erforderlich.
APP_DIRECTORY = Path(__file__).resolve().parent
LOCAL_PACKAGES = APP_DIRECTORY / "packages"
if LOCAL_PACKAGES.is_dir():
    sys.path.insert(0, str(LOCAL_PACKAGES))

from spotify_transcript_app.gui import main, self_test


def run_self_test() -> int:
    """Fuehrt den Paket-Selbsttest ohne modalen Fehlerdialog aus."""

    result_file = os.environ.get("TRANSCRIPT_APP_SELF_TEST_RESULT")
    try:
        self_test()
    except BaseException:
        if result_file:
            Path(result_file).write_text(
                "FEHLER\n" + traceback.format_exc(),
                encoding="utf-8",
            )
        return 1

    if result_file:
        Path(result_file).write_text("OK\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(run_self_test())
    else:
        main()
