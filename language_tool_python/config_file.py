from typing import Any, Dict

import atexit
import os
import tempfile

ALLOWED_CONFIG_KEYS = { 
    'maxTextLength', 'maxTextHardLength', 'maxCheckTimeMillis', 'maxErrorsPerWordRate',
    'maxSpellingSuggestions', 'maxCheckThreads', 'cacheSize', 'cacheTTLSeconds', 'requestLimit',
    'requestLimitInBytes', 'timeoutRequestLimit', 'requestLimitPeriodInSeconds', 'languageModel',
    'fasttextModel', 'fasttextBinary', 'maxWorkQueueSize', 'rulesFile',
    'blockedReferrers', 'premiumOnly', 'disabledRuleIds', 'pipelineCaching', 'maxPipelinePoolSize',
    'pipelineExpireTimeInSeconds', 'pipelinePrewarming'
}
class LanguageToolConfig:
    config: Dict[str, Any]
    path: str
    def __init__(self, config: Dict[str, Any]):
        assert set(config.keys()) <= ALLOWED_CONFIG_KEYS, f"unexpected keys in config: {set(config.keys()) - ALLOWED_CONFIG_KEYS}"
        assert len(config), "config cannot be empty"
        self.config = config

        if 'disabledRuleIds' in self.config:
            self.config['disabledRuleIds'] = ','.join(self.config['disabledRuleIds'])
        if 'blockedReferrers' in self.config:
            self.config['blockedReferrers'] = ','.join(self.config['blockedReferrers'])
        for key in ["pipelineCaching", "premiumOnly", "pipelinePrewarming"]:
            if key in self.config:
                self.config[key] = str(bool(self.config[key])).lower()

        self.path = self._create_temp_file()
    
    def _create_temp_file(self) -> str:
        tmp_file = tempfile.NamedTemporaryFile(delete=False)

        # WRite key=value entries as lines in temporary file.
        for key, value in self.config.items():
            next_line = f'{key}={value}\n'
            tmp_file.write(next_line.encode())
        tmp_file.close()

        # Remove file when program exits.
        atexit.register(lambda: os.unlink(tmp_file.name))

        return tmp_file.name
