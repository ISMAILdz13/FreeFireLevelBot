"""
Level Bot Configuration
Loads level bot settings from the main config or CLI args.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LevelBotConfig:
    """Configuration for the level bot."""
    uid: str = ""
    password: str = ""
    team_code: str = ""
    max_cycles: int = 1000
    spam_duration: int = 18       # seconds to spam start packets
    spam_delay: float = 0.2       # delay between start packets (seconds)
    wait_after_match: int = 20   # seconds to wait after match starts
    join_delay: float = 2.0       # delay after joining team
    leave_delay: float = 2.0      # delay after leaving team
    cycle_delay: float = 2.0      # delay between cycles
    accounts_file: str = "data/level_accounts.json"  # JSON file with uid:password pairs

    @classmethod
    def from_args(cls, **kwargs):
        """Create config from CLI args, filtering out None values."""
        fields = cls.__dataclass_fields__
        filtered = {k: v for k, v in kwargs.items() if k in fields and v is not None}
        return cls(**filtered)

    def validate(self) -> list:
        """Validate config, return list of error messages (empty = valid)."""
        errors = []
        if not self.uid and not self.accounts_file:
            errors.append("Either --uid or --accounts-file is required")
        if self.uid and not self.password:
            errors.append("--password is required when --uid is provided")
        if not self.team_code:
            errors.append("--team-code is required")
        if not self.team_code.isdigit():
            errors.append(f"Team code must be numeric, got: {self.team_code}")
        if self.spam_duration < 1:
            errors.append("spam-duration must be at least 1 second")
        if self.wait_after_match < 1:
            errors.append("wait-after-match must be at least 1 second")
        return errors
