"""Telephony adapters - pluggable telephony provider implementations."""

from vozbot.telephony.adapters.base import CallInfo, CallStatus, TelephonyAdapter
from vozbot.telephony.adapters.twilio_adapter import TwilioAdapter

__all__ = ["CallInfo", "CallStatus", "TelephonyAdapter", "TwilioAdapter"]
