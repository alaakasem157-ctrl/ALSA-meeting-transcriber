# ALSA Meeting Transcriber (PyQt)

Desktop application for **meeting transcription and summarization** with Arabic/English mixed support.

## Links
- Repository: https://github.com/alaakasem157-ctrl/ALSA-meeting-transcriber
- Demo video: (PUT YOUR DEMO LINK HERE)

## Features
- Upload/record audio
- Transcription (Arabic/English mixed)
- Post-processing + glossary correction
- Structured summary (key points / decisions / action items)
- Export results (DOCX)

## Tech Stack
- UI: **PySide6 (Qt)**
- Speech-to-Text (ASR): **faster-whisper** + **ctranslate2**
- Audio processing: **ffmpeg**

## Requirements
- Windows 10/11
- Python 3.x
- **ffmpeg** installed and added to PATH

## Install ffmpeg (Windows)
1. Download ffmpeg build for Windows
2. Extract it (you should have: `ffmpeg/bin/ffmpeg.exe`)
3. Add `ffmpeg/bin` to **PATH**
4. Verify:
```bash
ffmpeg -version