"""Define Polyglot command-layer gestures and exit behavior."""

from collections.abc import Collection


ENTRY_GESTURE = "kb:NVDA+Alt+Z"
LAYER_GESTURES = {
	"kb:t": "translateSelection",
	"kb:shift+t": "translateReverseSelection",
	"kb:b": "translateClipboard",
	"kb:shift+b": "translateReverseClipboard",
	"kb:l": "translateLastSpoken",
	"kb:shift+l": "translateReverseLastSpoken",
	"kb:s": "cycleSourceLangForward",
	"kb:shift+s": "cycleSourceLangBackward",
	"kb:g": "cycleTargetLangForward",
	"kb:shift+g": "cycleTargetLangBackward",
	"kb:e": "cycleEngineForward",
	"kb:shift+e": "cycleEngineBackward",
	"kb:w": "swapLanguages",
	"kb:a": "announceEngineLanguagesInfo",
	"kb:c": "copyLastResult",
	"kb:v": "toggleAutoTranslate",
	"kb:i": "openInteractiveDialog",
	"kb:o": "openSettings",
	"kb:x": "clearCache",
	"kb:h": "layerHelp",
	"kb:escape": "layerExit",
}


def shouldExitLayer(
	isLayerActive: bool,
	isModifier: bool,
	gestureIdentifiers: Collection[str],
	layerGestureIdentifiers: frozenset[str],
) -> bool:
	"""Return whether an unrelated gesture should close the active command layer."""
	return isLayerActive and not isModifier and layerGestureIdentifiers.isdisjoint(gestureIdentifiers)
