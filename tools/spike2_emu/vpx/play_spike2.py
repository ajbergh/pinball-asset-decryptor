"""Run a prepared SPIKE 2 title alongside its PAD-patched VPX table."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time

# PAD's embedded Windows Python does not add the script directory to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import padcontroller  # noqa: E402
import padlaunch  # noqa: E402


def read_title(table):
    from vpxfile import biff_records, olefile
    from vpxsetup import script_title

    # Only the embedded script is needed. Skip the table's other streams.
    with olefile.OleFileIO(str(table)) as ole:
        data = ole.openstream("GameStg/GameData").read()
    script = next((body[4:].decode("utf-8", "replace")
                   for tag, body, _ in biff_records(data) if tag == "CODE"), "")
    title = script_title(script)
    if (not re.fullmatch(r"[A-Za-z0-9_-]+", title)
            or not any(marker in script.lower() for marker in ("padspike2.vbs", "pad.controller"))):
        raise ValueError("The table needs an embedded PAD controller script and title.")
    return title


def resolve_vpx(exe):
    if not exe:
        from vpxsetup import find_vpx

        folder = find_vpx()
        exe = Path(folder) / "VPinballX64.exe" if folder else None
    if not exe or not exe.is_file():
        raise ValueError("Pass the path to VPinballX64.exe with -VpxExe.")
    return exe.resolve()


def check_controller():
    import winreg

    try:
        clsid = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, r"PAD.Controller\CLSID")
        server = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32")
    except OSError as exc:
        raise RuntimeError("Register PAD.Controller with the VPX kit before launching.") from exc
    if not server:
        raise RuntimeError("PAD.Controller has no registered COM server.")


def wait_for_game(launch, timeout):
    deadline = time.monotonic() + timeout
    while launch.alive() and time.monotonic() < deadline:
        record = padcontroller.Rig.board_slot(launch.slot)
        if record and record.get("label") == launch.label:
            if record.get("game") != launch.title:
                raise RuntimeError("The rig started a different title from the table's map.")
            rig = padcontroller.Rig(launch.title, record=record)
            if padcontroller.block_in_wsl(rig, timeout=5):
                return rig
        time.sleep(0.5)
    problem = "Stern runtime did not become ready" if launch.alive() else "Stern runtime exited during startup"
    raise RuntimeError(f"{problem}. See {launch.logfile}")


def play(launch, exe, table, timeout):
    # COM can discover the run from the board independently of VPX's environment.
    if padcontroller.Rig.board_run(launch.title):
        raise RuntimeError(f"Close the existing {launch.title} rig before starting this table.")
    try:
        launch.start()
        rig = wait_for_game(launch, timeout)
        env = dict(os.environ, PAD_WSL_DISTRO=rig.distro, PAD_ROOT_WSL=rig.root,
                   PAD_SLOT=str(launch.slot), PAD_VPX_LINK="1")
        with subprocess.Popen([str(exe), "-play", str(table)], cwd=exe.parent,
                              env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) as vpx:
            while True:
                try:
                    return vpx.wait()
                except KeyboardInterrupt:
                    print("Close VPX to stop the Stern runtime and release its slot.", file=sys.stderr)
    finally:
        launch.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", required=True, help="Extracted Stern title directory, in Windows or WSL")
    parser.add_argument("--table", type=Path, required=True, help="PAD-patched .vpx file")
    parser.add_argument("--vpx-exe", type=Path, help="Override the installed VPX player")
    parser.add_argument("--distro", help="Override the prepared WSL distribution")
    parser.add_argument("--startup-timeout", type=int, default=180)
    args = parser.parse_args()
    try:
        if sys.platform != "win32":
            raise RuntimeError("This launcher requires Windows and WSL.")
        if args.startup_timeout < 1:
            raise ValueError("Startup timeout must be positive.")
        table = args.table.resolve(strict=True)
        if not table.is_file() or table.suffix.lower() != ".vpx":
            raise ValueError("Pass a PAD-patched .vpx table.")
        title = read_title(table)
        mapping = padlaunch.table_map(title)
        if not mapping or mapping.get("platform", "spike2") != "spike2":
            raise ValueError(f"No SPIKE 2 map was found for {title}.")
        native_title = padlaunch.game_for(title)
        exe = resolve_vpx(args.vpx_exe)
        check_controller()

        distro = args.distro or padlaunch.distro()
        game_dir = args.game_dir
        if not game_dir.startswith("/"):
            game_dir = padlaunch.padpath.to_wsl(str(Path(game_dir).resolve(strict=True)), distro)
        game_dir = game_dir.rstrip("/")
        if game_dir.rsplit("/", 1)[-1] != native_title:
            raise ValueError(f"The extracted game directory must be named {native_title}.")
        probe = subprocess.run(padlaunch.wsl_head(distro) + ["-e", "test", "-x", game_dir + "/game"],
                               capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        if probe.returncode:
            detail = padlaunch._text(probe.stderr).strip()
            raise RuntimeError(f"WSL could not access an executable at {game_dir}/game. {detail}".strip())
        launch = padlaunch.Launch(title, None, dist=distro, minutes=0, game_dir=game_dir)
        return play(launch, exe, table, args.startup_timeout)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        print(f"SPIKE 2 VPX: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
