# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

from configobj import ConfigObj

configSpec: ConfigObj = ConfigObj(
	[
		# Global settings
		'engine = string(default="google")',
		"copyResult = boolean(default=False)",
		"enableLocalDictionaryForTranslation = boolean(default=True)",
		"enableLocalDictionaryForTextReview = boolean(default=True)",
		"reviewDictionaryLanguage = option('en', 'it', default='en')",
		"enableSmartFilter = boolean(default=True)",
		"",
		# Define an 'engines' subsection for engine-specific configurations.
		"[engines]",
		"   # [[__many__]] is a wildcard section for engine-specific settings.",
		"   [[__many__]]",
		"       # Settings for each engine are dynamically added here.",
		"       # They are defined by the getConfigSpec() method in each engine class.",
	],
	list_values=False,
	encoding="UTF8",
)
