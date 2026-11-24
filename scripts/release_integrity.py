"""Build-input provenance and fail-closed release validation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SHADOW_AI_FILES = ('Shadowrocket_Johnshall_AI.conf',
                   'data/ai-shadowrocket-sources.json',
                   'rules/johnshall-apple-news.list', 'rules/openai-auto.list',
                   'data/sources.json', 'data/review-queue.md',
                   'data/review-notifications.json')
V2_FILES = ('v2rayN_Johnshall_AI.json', 'data/v2rayn-sources.json')
RELEASE_FILES = {'shadowrocket_ai': SHADOW_AI_FILES, 'v2rayn': V2_FILES}
COMMON_INPUTS = ('scripts/build.py', 'scripts/v2rayn_core.py',
                 'scripts/ai_services.py', 'scripts/release_integrity.py',
                 'config/manual-openai.rules', 'config/ai-services.rules',
                 'config/ai-review-decisions.json')
CLIENT_INPUTS = {
    'shadowrocket_ai': ('scripts/build_ai_shadowrocket.py', 'scripts/build_v2rayn.py',
                        'scripts/review_queue.py', 'config/user-settings.json',
                        'config/review-decisions.json',
                        'config/reviewed-johnshall-ad-decrease.json',
                        'config/reviewed-voice-expansion.json'),
    'v2rayn': ('scripts/build_v2rayn.py', 'scripts/routing_conflicts.py', 'config/v2rayn/openai-extra.rules',
               'config/v2rayn/verified-processes.txt', 'data/bitbrowser_domains.txt'),
}

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def artifact_manifest(paths, root: Path = ROOT) -> dict:
    return {path: digest(root / path) for path in paths}

def build_inputs_fingerprint(client: str, root: Path = ROOT) -> str:
    paths = COMMON_INPUTS + CLIENT_INPUTS[client]
    inputs = {p: digest(root / p) if (root / p).is_file() else None for p in paths}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

def valid_build_report(report) -> bool:
    return (isinstance(report, dict)
            and report.get('build_success') is True
            and type(report.get('config_changed')) is bool
            and isinstance(report.get('statistics'), dict)
            and bool(report['statistics']))

def validate_release(client: str, status: dict, root: Path = ROOT) -> dict:
    """A successful exit alone cannot authorize staging."""
    path = status.get('reports', {}).get(client)
    if not isinstance(path, str) or not Path(path).is_file():
        raise ValueError('Missing fresh build report')
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    if not valid_build_report(report):
        raise ValueError('Incomplete or unsuccessful build report')
    expected = RELEASE_FILES[client]
    manifest = report.get('artifact_sha256')
    if not isinstance(manifest, dict) or set(manifest) != set(expected):
        raise ValueError('Missing or unexpected artifact manifest paths')
    for name in expected:
        if not isinstance(manifest[name], str) or not re.fullmatch(r'[0-9a-f]{64}', manifest[name]):
            raise ValueError('Invalid artifact digest: ' + name)
        if digest(root / name) != manifest[name]:
            raise ValueError('Artifact digest mismatch: ' + name)
    output, state_path = expected[:2]
    state = json.loads((root / state_path).read_text(encoding='utf-8'))
    if not isinstance(state, dict) or state.get('schema_version') != 2:
        raise ValueError('Invalid generated release state')
    if state.get('output_sha256') != manifest[output]:
        raise ValueError('Output/state digest mismatch')
    if state.get('build_inputs_sha256') != build_inputs_fingerprint(client, root):
        raise ValueError('Generated release does not match current build inputs')
    if not isinstance(state.get('statistics'), dict) or not state['statistics']:
        raise ValueError('Missing generated release statistics')
    for key, value in state['statistics'].items():
        if report['statistics'].get(key) != value:
            raise ValueError('Report/state statistics mismatch: ' + key)
    size_key = 'conf_bytes' if client == 'shadowrocket_ai' else 'json_bytes'
    if report['statistics'].get(size_key) != (root / output).stat().st_size:
        raise ValueError('Report/output byte count mismatch')
    if client == 'shadowrocket_ai':
        for key, name in (('voice_auto_sha256', 'rules/openai-auto.list'),
                          ('legacy_state_sha256', 'data/sources.json')):
            if state.get(key) != manifest[name]:
                raise ValueError('Auxiliary state digest mismatch: ' + name)
    return report
