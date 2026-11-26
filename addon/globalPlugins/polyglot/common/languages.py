# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

from collections.abc import Collection

import addonHandler
import languageHandler
from logHandler import log

addonHandler.initTranslation()

# Central repository for all language codes and their display names.
# This ensures consistency across all translation engines.

# All display names must be wrapped in _() for localization.

_ALL_LANGUAGES = {
	# --- Special Codes ---
	"auto": _("Auto-detect"),
	"": _("Auto-detect"),  # Used by Microsoft and Yandex
	# --- Chinese Variants ---
	"zh": _("Chinese"),
	"zh-CN": _("Chinese (Simplified)"),
	"zh-CHS": _("Chinese (Simplified)"),
	"zh-Hans": _("Chinese (Simplified)"),
	"zh-TW": _("Chinese (Traditional)"),
	"zh-HK": _("Chinese (Traditional)"),
	"zh-Hant": _("Chinese (Traditional)"),
	"cht": _("Chinese (Traditional)"),
	"yue": _("Cantonese"),
	"wyw": _("Classical Chinese"),
	"ZH": _("Chinese"),  # DeepL
	# --- Major Languages ---
	"en": _("English"),
	"en-US": _("English (American)"),
	"en-GB": _("English (British)"),
	"ja": _("Japanese"),
	"jp": _("Japanese"),  # Baidu
	"ko": _("Korean"),
	"kor": _("Korean"),  # Baidu
	"KO": _("Korean"),  # DeepL
	"fr": _("French"),
	"fra": _("French"),  # Baidu
	"de": _("German"),
	"es": _("Spanish"),
	"es-419": _("Spanish (Latin American)"),
	"spa": _("Spanish"),  # Baidu
	"ru": _("Russian"),
	"pt": _("Portuguese"),
	"pt-BR": _("Portuguese (Brazilian)"),
	"pt-PT": _("Portuguese (European)"),
	"it": _("Italian"),
	"ar": _("Arabic"),
	"ara": _("Arabic"),  # Baidu
	"acu": _("Achuar"),
	"am": _("Amharic"),
	# --- Other European Languages ---
	"nl": _("Dutch"),
	"sv": _("Swedish"),
	"swe": _("Swedish"),  # Baidu
	"pl": _("Polish"),
	"da": _("Danish"),
	"dan": _("Danish"),  # Baidu
	"fi": _("Finnish"),
	"fin": _("Finnish"),  # Baidu
	"no": _("Norwegian"),
	"nb": _("Norwegian (Bokmål)"),
	"nn": _("Norwegian (Nynorsk)"),
	"cs": _("Czech"),
	"sk": _("Slovak"),
	"hu": _("Hungarian"),
	"ro": _("Romanian"),
	"rom": _("Romanian"),  # Baidu
	"bg": _("Bulgarian"),
	"bul": _("Bulgarian"),  # Baidu
	"el": _("Greek"),
	"lt": _("Lithuanian"),
	"lv": _("Latvian"),
	"et": _("Estonian"),
	"est": _("Estonian"),  # Baidu
	"sl": _("Slovenian"),
	"slo": _("Slovenian"),  # Baidu
	"hr": _("Croatian"),
	"sr": _("Serbian"),
	"bs": _("Bosnian"),
	"sq": _("Albanian"),
	"mk": _("Macedonian"),
	"uk": _("Ukrainian"),
	"be": _("Belarusian"),
	"is": _("Icelandic"),
	"ga": _("Irish"),
	"mt": _("Maltese"),
	"cy": _("Welsh"),
	"eu": _("Basque"),
	"ca": _("Catalan"),
	"gl": _("Galician"),
	"lb": _("Luxembourgish"),
	"gd": _("Scots Gaelic"),
	# --- Other Asian & Middle Eastern Languages ---
	"th": _("Thai"),
	"vi": _("Vietnamese"),
	"vie": _("Vietnamese"),  # Baidu
	"id": _("Indonesian"),
	"ms": _("Malay"),
	"tl": _("Filipino"),
	"ceb": _("Cebuano"),
	"my": _("Myanmar (Burmese)"),
	"km": _("Khmer"),
	"lo": _("Lao"),
	"jw": _("Javanese"),
	"su": _("Sundanese"),
	"hi": _("Hindi"),
	"bn": _("Bengali"),
	"pa": _("Punjabi"),
	"gu": _("Gujarati"),
	"mr": _("Marathi"),
	"ta": _("Tamil"),
	"te": _("Telugu"),
	"kn": _("Kannada"),
	"ml": _("Malayalam"),
	"si": _("Sinhala"),
	"ne": _("Nepali"),
	"sd": _("Sindhi"),
	"fa": _("Persian"),
	"he": _("Hebrew"),
	"iw": _("Hebrew"),  # Chrome Translator API
	"tr": _("Turkish"),
	"az": _("Azerbaijani"),
	"hy": _("Armenian"),
	"ka": _("Georgian"),
	"uz": _("Uzbek"),
	"kk": _("Kazakh"),
	"ky": _("Kyrgyz"),
	"tg": _("Tajik"),
	"ur": _("Urdu"),
	"ps": _("Pashto"),
	"ku": _("Kurdish"),
	"mn": _("Mongolian (Cyrillic)"),
	"mo": _("Mongolian (Traditional)"),
	"hmn": _("Hmong"),
	# --- African Languages ---
	"af": _("Afrikaans"),
	"sw": _("Swahili"),
	"so": _("Somali"),
	"ha": _("Hausa"),
	"yo": _("Yoruba"),
	"ig": _("Igbo"),
	"zu": _("Zulu"),
	"xh": _("Xhosa"),
	"st": _("Sesotho"),
	"sn": _("Shona"),
	"mg": _("Malagasy"),
	"ny": _("Chichewa"),
	# --- Oceanic & Constructed Languages ---
	"mi": _("Maori"),
	"sm": _("Samoan"),
	"ht": _("Haitian Creole"),
	"haw": _("Hawaiian"),
	"co": _("Corsican"),
	"fy": _("Frisian"),
	"yi": _("Yiddish"),
	"eo": _("Esperanto"),
	"la": _("Latin"),
}


GOOGLE_TRANSLATE_CODES = [
	"auto",
	"af",
	"sq",
	"ar",
	"hy",
	"az",
	"eu",
	"be",
	"bn",
	"bs",
	"bg",
	"ca",
	"ceb",
	"ny",
	"zh-CN",
	"zh-TW",
	"co",
	"hr",
	"cs",
	"da",
	"nl",
	"en",
	"eo",
	"et",
	"tl",
	"fi",
	"fr",
	"fy",
	"gl",
	"ka",
	"de",
	"el",
	"gu",
	"ht",
	"ha",
	"haw",
	"he",
	"hi",
	"hmn",
	"hu",
	"is",
	"ig",
	"id",
	"ga",
	"it",
	"ja",
	"jw",
	"kn",
	"kk",
	"km",
	"ko",
	"ku",
	"ky",
	"lo",
	"la",
	"lv",
	"lt",
	"lb",
	"mk",
	"mg",
	"ms",
	"ml",
	"mt",
	"mi",
	"mr",
	"mn",
	"my",
	"ne",
	"no",
	"ps",
	"fa",
	"pl",
	"pt",
	"pa",
	"ro",
	"ru",
	"sm",
	"gd",
	"sr",
	"st",
	"sn",
	"sd",
	"si",
	"sk",
	"sl",
	"so",
	"es",
	"su",
	"sw",
	"sv",
	"tg",
	"ta",
	"te",
	"th",
	"tr",
	"uk",
	"ur",
	"uz",
	"vi",
	"cy",
	"xh",
	"yi",
	"yo",
	"zu",
]


def getLanguageDictForCodes(codes: list[str]) -> dict[str, str]:
	"""
	Build a language-name dictionary for the supplied engine codes.
	If a code is not found in the central repository, it logs an error
	and uses the code itself as the display name as a fallback.
	:param codes: A list of language codes supported by the engine.
	:return: A dictionary mapping the supported codes to their display names.
	"""
	langDict: dict[str, str] = {}
	for code in codes:
		if code in _ALL_LANGUAGES:
			langDict[code] = _ALL_LANGUAGES[code]
		else:
			# Log an error for missing definitions and use the code as a fallback display name.
			log.error(
				f"Language code '{code}' not found in central repository. Using the code as its display name.",
			)
			langDict[code] = code
	return langDict


def getLanguageName(code: str) -> str:
	"""Return the translated language name, falling back to the supplied code."""
	return _ALL_LANGUAGES.get(code, code)


def getLanguageFamily(code: str) -> str:
	"""Return the base language subtag used for language-family comparisons."""
	return code.partition("-")[0].casefold()


def normalizeLanguageCode(language: str | None) -> str:
	"""Normalize language-code spelling to lower case with hyphen separators."""
	return (language or "").strip().replace("_", "-").casefold()


_SIMPLIFIED_CHINESE = ("zh-hans", "zh-cn", "zh-chs")
_TRADITIONAL_CHINESE = ("zh-hant", "zh-tw", "zh-hk", "cht")
_LOCALE_ALIASES: dict[str, tuple[str, ...]] = {
	"zh-cn": _SIMPLIFIED_CHINESE,
	"zh-sg": _SIMPLIFIED_CHINESE,
	"zh-hans": _SIMPLIFIED_CHINESE,
	"zh-tw": _TRADITIONAL_CHINESE,
	"zh-hk": _TRADITIONAL_CHINESE,
	"zh-mo": _TRADITIONAL_CHINESE,
	"zh-hant": _TRADITIONAL_CHINESE,
	"es-co": ("es-419",),
}

_BASE_LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
	"ar": ("ara",),
	"bg": ("bul",),
	"da": ("dan",),
	"en": ("en-us", "en-gb"),
	"es": ("spa", "es-419"),
	"et": ("est",),
	"fi": ("fin",),
	"fil": ("tl",),
	"fr": ("fra",),
	"he": ("iw",),
	"iw": ("he",),
	"ja": ("jp",),
	"jv": ("jw",),
	"ko": ("kor",),
	"nb": ("no",),
	"nn": ("no", "nb"),
	"no": ("nb",),
	"pt": ("pt-pt", "pt-br"),
	"ro": ("rom",),
	"sl": ("slo",),
	"sv": ("swe",),
	"vi": ("vie",),
	"zh": _SIMPLIFIED_CHINESE,
}


def resolveTargetLanguage(
	supportedCodes: Collection[str],
	fallback: str,
	nvdaLanguage: str | None = None,
	excludeCodes: Collection[str] = (),
) -> str:
	"""Resolve NVDA's interface language to the best matching engine target code."""
	if nvdaLanguage is None:
		try:
			nvdaLanguage = languageHandler.getLanguage()
		except Exception:
			return fallback
	if not nvdaLanguage:
		return fallback

	excluded = {code.casefold() for code in excludeCodes}
	supportedByLower = {code.casefold(): code for code in supportedCodes if code.casefold() not in excluded}

	normalized = normalizeLanguageCode(nvdaLanguage)
	if not normalized:
		return fallback

	parts = normalized.split("-")
	base = getLanguageFamily(normalized)
	candidates: list[str] = [normalized, *_LOCALE_ALIASES.get(normalized, ())]
	if len(parts) > 2:
		prefix = f"{parts[0]}-{parts[1]}"
		candidates.extend((prefix, *_LOCALE_ALIASES.get(prefix, ())))
	candidates.append(base)
	candidates.extend(_BASE_LANGUAGE_ALIASES.get(base, ()))

	for candidate in candidates:
		matched = supportedByLower.get(candidate)
		if matched is not None:
			return matched
	return fallback
