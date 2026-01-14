# VozBot Audio Prompts

This directory contains audio prompt files used by VozBot for call handling.

## Required Audio Files

### Bilingual Greeting
- `greeting_en.mp3` - English greeting
- `greeting_es.mp3` - Spanish greeting
- `greeting_bilingual.mp3` - Combined bilingual greeting

### Language Selection
- `language_select.mp3` - "Press 1 for English, Presione 2 para espanol"

### Hold Music
- `hold_music.mp3` - Background hold music

### Confirmation Messages
- `callback_confirmation_en.mp3` - English callback confirmation
- `callback_confirmation_es.mp3` - Spanish callback confirmation

## Audio Specifications

- Format: MP3 or WAV
- Sample Rate: 8kHz (for telephony) or 16kHz
- Channels: Mono
- Bit Rate: 32kbps minimum

## Usage

Audio files are served via `/static/audio/{filename}` endpoint.

Example: `https://your-domain.com/static/audio/greeting_bilingual.mp3`

## Generating Audio

For development, you can use text-to-speech services:
- AWS Polly
- Google Cloud Text-to-Speech
- Azure Cognitive Services

For production, consider professional voice recordings.
