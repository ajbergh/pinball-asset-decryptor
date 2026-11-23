"""Prepared VPX launch ordering and ownership, without starting WSL or VPX."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "spike2_emu" / "vpx"))
import play_spike2 as play  # noqa: E402


class PreparedLaunchTest(unittest.TestCase):
    def test_prepared_run_skips_the_card_and_standalone_helpers(self):
        mod = play.padlaunch
        with patch.object(mod.padpath, "to_wsl", return_value="/rig"), \
                patch.object(mod, "no_linux", return_value=""), \
                patch.object(mod, "card_store") as card_store, \
                patch.object(mod.Launch, "base_rig", return_value=""), \
                patch.object(mod.Launch, "_start_watch") as watch:
            launch = mod.Launch("godzilla_le", None, dist="PAD-Runtime", minutes=0,
                                game_dir="/home/pad games/godzilla_le")
            launch.slot = 2
            launch.board_env = Mock(return_value=[])
            launch.start()

        watch.assert_called_once_with()
        card_store.assert_not_called()
        env = dict(value.split("=", 1) for value in launch.env())
        self.assertEqual(env["PAD_GAME_DIR"], "/home/pad games/godzilla_le")
        self.assertEqual(env["PAD_AUDIO"], "1")
        for name in ("PLAYFIELD", "HIDDEN", "BALL_FEED", "TOPPER", "RECORD"):
            self.assertEqual(env["PAD_" + name], "0")
        self.assertEqual(env["PAD_CARD"], "")

    def test_vpx_starts_after_the_game_and_exit_releases_the_run(self):
        calls = []
        launch = SimpleNamespace(title="godzilla_le", slot=2, start=lambda: calls.append("game"),
                                 stop=lambda: calls.append("stop"))
        exe = Path("VPX Install/VPinballX64.exe")
        table = Path("Tables/Godzilla (PAD).vpx")
        rig = SimpleNamespace(distro="PAD-Runtime", root="/slots/2/root")
        proc = MagicMock()
        proc.__enter__.return_value.wait.side_effect = lambda: calls.append("wait VPX") or 0

        with patch.object(play.padcontroller.Rig, "board_run", return_value=None), \
                patch.object(play, "wait_for_game", side_effect=lambda *_: calls.append("ready") or rig), \
                patch.object(play.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, create=True), \
                patch.object(play.subprocess, "Popen", return_value=proc) as popen:
            self.assertEqual(play.play(launch, exe, table, 30), 0)
        self.assertEqual(calls, ["game", "ready", "wait VPX", "stop"])
        self.assertEqual(popen.call_args.args, ([str(exe), "-play", str(table)],))
        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["PAD_ROOT_WSL"], rig.root)
        self.assertEqual(env["PAD_SLOT"], "2")
        self.assertEqual(env["PAD_VPX_LINK"], "1")
        self.assertEqual(env["PAD_WSL_DISTRO"], rig.distro)

    def test_failed_game_start_never_opens_vpx_and_cleans_up(self):
        launch = Mock(title="godzilla_le")
        launch.start.side_effect = RuntimeError("game died")
        with patch.object(play.padcontroller.Rig, "board_run", return_value=None), \
                patch.object(play.subprocess, "Popen") as popen, \
                self.assertRaisesRegex(RuntimeError, "game died"):
            play.play(launch, Path("VPinballX64.exe"), Path("table.vpx"), 30)
        popen.assert_not_called()
        launch.stop.assert_called_once_with()
