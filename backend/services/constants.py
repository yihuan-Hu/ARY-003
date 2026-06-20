RACE_STATUSES = ('upcoming', 'open', 'judging', 'ended')
CA_PROVIDERS = ('codex', 'claude', 'other')
RISK_LEVELS = ('none', 'low', 'medium', 'high')
ENTRY_STATUSES = (
    'idle', 'running', 'sprinting', 'slowed', 'blocked',
    'pit_stop', 'takeover', 'finished', 'stale',
)
MESSAGE_TYPES = (
    'progress_update', 'milestone', 'strategy_change', 'quality_signal',
    'risk_alert', 'obstacle', 'violation', 'takeover', 'pit_stop',
)
SEVERITIES = ('info', 'warning', 'critical')
