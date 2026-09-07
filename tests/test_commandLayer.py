# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for command-layer state transitions."""

import runpy
import unittest
from pathlib import Path
from typing import Any


COMMAND_LAYER = runpy.run_path(
	Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "polyglot" / "_commandLayer.py"
)
LAYER_GESTURES: dict[str, str] = COMMAND_LAYER["LAYER_GESTURES"]
shouldExitLayer: Any = COMMAND_LAYER["shouldExitLayer"]


class CommandLayerTestCase(unittest.TestCase):
	"""Check the command layer's gesture map and exit decision."""

	def test_escapeHasAnExplicitExitCommand(self) -> None:
		"""Escape is handled inside the layer instead of falling through."""
		self.assertEqual(LAYER_GESTURES["kb:escape"], "layerExit")

	def test_onlyAnUnrelatedNonModifierGestureExits(self) -> None:
		"""Mapped keys and modifiers keep the layer active; other keys close it."""
		layerIdentifiers = frozenset(LAYER_GESTURES)
		cases = (
			(False, False, ("kb:q",), False),
			(True, True, ("kb:control",), False),
			(True, False, ("kb:h",), False),
			(True, False, ("kb:q",), True),
		)
		for isActive, isModifier, identifiers, expected in cases:
			with self.subTest(
				isActive=isActive,
				isModifier=isModifier,
				identifiers=identifiers,
			):
				self.assertEqual(
					shouldExitLayer(isActive, isModifier, identifiers, layerIdentifiers),
					expected,
				)


if __name__ == "__main__":
	unittest.main()
