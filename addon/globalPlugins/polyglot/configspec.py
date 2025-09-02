# -*- coding: utf-8 -*-

from configobj import ConfigObj

config_spec = ConfigObj([
    # Global settings
    'engine = string(default="google")',
    'copyResult = boolean(default=False)',
    '',
    # Define an 'engines' subsection for engine-specific configurations.
    '[engines]',
    '   # [[__many__]] is a wildcard section for engine-specific settings.',
    '   [[__many__]]',
    '       # Settings for each engine are dynamically added here.',
    '       # They are defined by the get_config_spec() method in each engine class.',
], list_values=False, encoding='UTF8')