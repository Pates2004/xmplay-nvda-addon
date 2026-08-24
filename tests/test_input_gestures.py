from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
GLOBAL_PLUGIN = ROOT / "addon" / "globalPlugins" / "xmplayAccessibility" / "__init__.py"
APP_MODULE = ROOT / "addon" / "appModules" / "xmplay" / "__init__.py"


EXPECTED_GESTURES = {
	"script_showControlCenter": "kb:NVDA+shift+x",
	"script_showPlaylist": "kb:NVDA+shift+p",
	"script_reportTrack": "kb:NVDA+shift+i",
	"script_reportTime": "kb:NVDA+shift+t",
	"script_reportStatus": "kb:NVDA+shift+s",
	"script_reportVolume": "kb:NVDA+shift+v",
	"script_showGeneralInfo": "kb:NVDA+shift+g",
	"script_showMessageInfo": "kb:NVDA+shift+m",
	"script_showSampleInfo": "kb:NVDA+shift+a",
	"script_showAllTrackInfo": "kb:NVDA+shift+d",
	"script_showVisibleWindowText": "kb:NVDA+shift+o",
	"script_playPause": "kb:control+shift+space",
	"script_stop": "kb:control+shift+s",
	"script_previous": "kb:control+shift+leftArrow",
	"script_next": "kb:control+shift+rightArrow",
	"script_seekBackward": "kb:control+shift+pageUp",
	"script_seekForward": "kb:control+shift+pageDown",
	"script_volumeUp": "kb:control+shift+upArrow",
	"script_volumeDown": "kb:control+shift+downArrow",
	"script_mute": "kb:control+shift+m",
	"script_loop": "kb:control+shift+l",
}


def script_decorator(function: ast.FunctionDef) -> ast.Call | None:
	for decorator in function.decorator_list:
		if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
			if decorator.func.id == "script":
				return decorator
	return None


class InputGesturesTest(unittest.TestCase):
	def test_all_commands_are_registered_by_the_global_plugin(self):
		tree = ast.parse(GLOBAL_PLUGIN.read_text(encoding="utf-8"))
		global_plugin = next(
			node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GlobalPlugin"
		)
		actual = {}
		for function in (node for node in global_plugin.body if isinstance(node, ast.FunctionDef)):
			decorator = script_decorator(function)
			if not decorator:
				continue
			keywords = {keyword.arg: keyword.value for keyword in decorator.keywords}
			self.assertIsInstance(keywords.get("description"), ast.Call)
			self.assertIsInstance(keywords.get("category"), ast.Name)
			self.assertEqual(keywords["category"].id, "SCRIPT_CATEGORY")
			self.assertIsInstance(keywords.get("gesture"), ast.Constant)
			actual[function.name] = keywords["gesture"].value
		self.assertEqual(actual, EXPECTED_GESTURES)

	def test_app_module_does_not_keep_duplicate_default_bindings(self):
		tree = ast.parse(APP_MODULE.read_text(encoding="utf-8"))
		decorated = [
			node.name
			for node in ast.walk(tree)
			if isinstance(node, ast.FunctionDef) and script_decorator(node)
		]
		self.assertEqual(decorated, [])


if __name__ == "__main__":
	unittest.main()
