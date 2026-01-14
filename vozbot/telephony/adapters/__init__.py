"""Telephony adapters - pluggable telephony provider implementations."""

from vozbot.telephony.adapters.base import CallInfo, CallStatus, TelephonyAdapter

__all__ = ["CallInfo", "CallStatus", "TelephonyAdapter"]
