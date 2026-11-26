# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for command-layer state transitions."""

import unittest

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from polyglot._commandLayer import LAYER_GESTURES, shouldExitLayer  # noqa: E402


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
			with self.subTest(isActive=isActive, isModifier=isModifier, identifiers=identifiers):
				self.assertEqual(
					shouldExitLayer(isActive, isModifier, identifiers, layerIdentifiers),
					expected,
				)


if __name__ == "__main__":
	unittest.main()
