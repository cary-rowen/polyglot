# -*- coding: utf-8 -*-

import addonHandler
from logHandler import log

addonHandler.initTranslation()

# Central repository for all language codes and their display names.
# This ensures consistency across all translation engines.

# All display names must be wrapped in _() for localization.

ALL_LANGUAGES = {
    # --- Special Codes ---
    'auto': _("Auto-detect"),
    '': _("Auto-detect"),  # Used by Microsoft and Yandex

    # --- Chinese Variants ---
    'zh': _("Chinese"),
    'zh-CN': _("Chinese (Simplified)"),
    'zh-CHS': _("Chinese (Simplified)"),
    'zh-Hans': _("Chinese (Simplified)"),
    'zh-TW': _("Chinese (Traditional)"),
    'zh-Hant': _("Chinese (Traditional)"),
    'zh_HANT': _("Chinese (Traditional)"), # Lingva
    'cht': _("Chinese (Traditional)"),
    'yue': _("Cantonese"),
    'wyw': _("Classical Chinese"),
    'ZH': _("Chinese"), # DeepL

    # --- Major Languages ---
    'en': _("English"),
    'ja': _("Japanese"),
    'jp': _("Japanese"), # Baidu
    'ko': _("Korean"),
    'kor': _("Korean"), # Baidu
    'KO': _("Korean"), # DeepL
    'fr': _("French"),
    'fra': _("French"), # Baidu
    'de': _("German"),
    'es': _("Spanish"),
    'spa': _("Spanish"), # Baidu
    'ru': _("Russian"),
    'pt': _("Portuguese"),
    'it': _("Italian"),
    'ar': _("Arabic"),
    'ara': _("Arabic"), # Baidu

    # --- Other European Languages ---
    'nl': _("Dutch"),
    'sv': _("Swedish"),
    'swe': _("Swedish"), # Baidu
    'pl': _("Polish"),
    'da': _("Danish"),
    'dan': _("Danish"), # Baidu
    'fi': _("Finnish"),
    'fin': _("Finnish"), # Baidu
    'no': _("Norwegian"),
    'nb': _("Norwegian (Bokmål)"),
    'nn': _("Norwegian (Nynorsk)"),
    'cs': _("Czech"),
    'sk': _("Slovak"),
    'hu': _("Hungarian"),
    'ro': _("Romanian"),
    'rom': _("Romanian"), # Baidu
    'bg': _("Bulgarian"),
    'bul': _("Bulgarian"), # Baidu
    'el': _("Greek"),
    'lt': _("Lithuanian"),
    'lv': _("Latvian"),
    'et': _("Estonian"),
    'est': _("Estonian"), # Baidu
    'sl': _("Slovenian"),
    'slo': _("Slovenian"), # Baidu
    'hr': _("Croatian"),
    'sr': _("Serbian"),
    'bs': _("Bosnian"),
    'sq': _("Albanian"),
    'mk': _("Macedonian"),
    'uk': _("Ukrainian"),
    'be': _("Belarusian"),
    'is': _("Icelandic"),
    'ga': _("Irish"),
    'mt': _("Maltese"),
    'cy': _("Welsh"),
    'eu': _("Basque"),
    'ca': _("Catalan"),
    'gl': _("Galician"),
    'lb': _("Luxembourgish"),
    'gd': _("Scots Gaelic"),

    # --- Other Asian & Middle Eastern Languages ---
    'th': _("Thai"),
    'vi': _("Vietnamese"),
    'vie': _("Vietnamese"), # Baidu
    'id': _("Indonesian"),
    'ms': _("Malay"),
    'tl': _("Filipino"),
    'ceb': _("Cebuano"),
    'my': _("Myanmar (Burmese)"),
    'km': _("Khmer"),
    'lo': _("Lao"),
    'jw': _("Javanese"),
    'su': _("Sundanese"),
    'hi': _("Hindi"),
    'bn': _("Bengali"),
    'pa': _("Punjabi"),
    'gu': _("Gujarati"),
    'mr': _("Marathi"),
    'ta': _("Tamil"),
    'te': _("Telugu"),
    'kn': _("Kannada"),
    'ml': _("Malayalam"),
    'si': _("Sinhala"),
    'ne': _("Nepali"),
    'sd': _("Sindhi"),
    'fa': _("Persian"),
    'he': _("Hebrew"),
    'tr': _("Turkish"),
    'az': _("Azerbaijani"),
    'hy': _("Armenian"),
    'ka': _("Georgian"),
    'uz': _("Uzbek"),
    'kk': _("Kazakh"),
    'ky': _("Kyrgyz"),
    'tg': _("Tajik"),
    'ur': _("Urdu"),
    'ps': _("Pashto"),
    'ku': _("Kurdish"),
    'mn': _("Mongolian (Cyrillic)"),
    'mo': _("Mongolian (Traditional)"),
    'hmn': _("Hmong"),
    
    # --- African Languages ---
    'af': _("Afrikaans"),
    'sw': _("Swahili"),
    'so': _("Somali"),
    'ha': _("Hausa"),
    'yo': _("Yoruba"),
    'ig': _("Igbo"),
    'zu': _("Zulu"),
    'xh': _("Xhosa"),
    'st': _("Sesotho"),
    'sn': _("Shona"),
    'mg': _("Malagasy"),
    'ny': _("Chichewa"),

    # --- Oceanic & Constructed Languages ---
    'mi': _("Maori"),
    'sm': _("Samoan"),
    'ht': _("Haitian Creole"),
    'haw': _("Hawaiian"),
    'co': _("Corsican"),
    'fy': _("Frisian"),
    'yi': _("Yiddish"),
    'eo': _("Esperanto"),
    'la': _("Latin"),
}

def get_language_dict_for_codes(codes: list[str]) -> dict:
    """
    Builds a language dictionary for a specific engine.
    If a code is not found in the central repository, it logs an error
    and uses the code itself as the display name as a fallback.
    @param codes: A list of language codes supported by the engine.
    @return: A dictionary mapping the supported codes to their display names.
    """
    lang_dict = {}
    for code in codes:
        if code in ALL_LANGUAGES:
            lang_dict[code] = ALL_LANGUAGES[code]
        else:
            # Log an error for missing definitions and use the code as a fallback display name.
            log.error(f"Language code '{code}' not found in central repository. Using the code as its display name.")
            lang_dict[code] = code
    return lang_dict