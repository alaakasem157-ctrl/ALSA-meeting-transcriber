# ALSA Meeting Transcriber

A Windows desktop application for **meeting transcription, glossary-based correction, and structured summarization** with support for **Arabic / English mixed speech**.

The application is designed for **local execution** and focuses on a practical delivery workflow:
- upload or record meeting audio,
- generate a transcript,
- apply domain-specific corrections,
- produce a structured meeting summary,
- export the final result as a **DOCX** file.

---

## Project Overview

ALSA Meeting Transcriber was built as a desktop solution for handling spoken meeting content in a controlled local environment. The project combines speech-to-text, post-processing, and document generation in a single user-facing application.

The workflow is intended for academic, administrative, or organizational use cases where the user needs a fast transcription pipeline and a readable final summary instead of raw speech output only.

---

## Core Capabilities

- Upload audio files for transcription
- Record audio directly from a microphone
- Transcribe **Arabic / English mixed-language** audio
- Apply glossary-based correction after transcription
- Generate a structured meeting summary
- Export the final result to **DOCX**
- Run locally on Windows without requiring a browser-based interface
- Package the application as a standalone executable using **PyInstaller**

---

## Repository Information

- **GitHub Repository:** https://github.com/alaakasem157-ctrl/ALSA-meeting-transcriber
- **Demo Video:** https://drive.google.com/file/d/1FPOtC6QMErVuLnuy9g9WrXqvMGbY2AR9/view?usp=drive_link

---

## Technology Stack

| Component | Technology |
|---|---|
| Desktop UI | PySide6 / Qt for Python |
| Speech-to-Text | faster-whisper |
| Inference Backend | ctranslate2 |
| Audio Decoding | ffmpeg |
| Document Export | python-docx |
| Runtime | Python 3 |
| Packaging | PyInstaller |

---

## System Requirements

### Minimum
- **Operating System:** Windows 10 or Windows 11
- **Python:** 3.10 or newer
- **RAM:** 8 GB
- **Storage:** Enough free space for Python packages, model files, output files, and temporary audio processing

### Recommended
- **Python:** 3.10 or 3.11
- **RAM:** 16 GB
- **CPU:** Modern multi-core processor for better transcription speed
- **Storage:** SSD preferred for model loading and faster file operations

### Required External Tool
- **ffmpeg** must be installed and accessible from the system `PATH`

---

## Software and Libraries You Need

This project depends on three categories of software:

1. **Python**
2. **ffmpeg**
3. **Python packages installed through pip**

---

## 1) Install Python

Download Python from the official Python website:

- https://www.python.org/downloads/

During installation on Windows:
- enable **Add Python to PATH**
- use the default installation unless your environment requires a custom location

Verify the installation:

```bash
python --version
```

You should also verify pip:

```bash
pip --version
```

---

## 2) Install ffmpeg

Download ffmpeg from the official project page or an official distribution page:

- https://ffmpeg.org/download.html

### Windows Setup Steps
1. Download the Windows build archive.
2. Extract the archive.
3. Open the extracted folder and locate the `bin` directory.
4. Confirm that `ffmpeg.exe` exists inside that directory.
5. Add the full `bin` path to the Windows **Environment Variables > PATH**.
6. Open a new terminal window.
7. Verify installation:

```bash
ffmpeg -version
```

If the command works, ffmpeg is installed correctly.

---

## 3) Install Project Libraries

All Python dependencies should be installed from **requirements.txt** whenever that file is available and up to date.

Typical libraries used by this application include:

- `PySide6`
- `faster-whisper`
- `ctranslate2`
- `python-docx`
- `numpy`
- audio input libraries such as `sounddevice` if microphone recording is enabled in the codebase
- any helper packages explicitly imported by the project

Preferred command:

```bash
pip install -r requirements.txt
```

---

## Recommended Installation Workflow

### Clone the Repository

```bash
git clone https://github.com/alaakasem157-ctrl/ALSA-meeting-transcriber.git
cd ALSA-meeting-transcriber
```

### Create a Virtual Environment

```bash
python -m venv .venv
```

### Activate the Virtual Environment

**Command Prompt**
```bash
.venv\Scripts\activate
```

**PowerShell**
```bash
.venv\Scripts\Activate.ps1
```

### Upgrade pip

```bash
python -m pip install --upgrade pip setuptools wheel
```

### Install Requirements

```bash
pip install -r requirements.txt
```

---

## Manual Installation of Main Packages

If you need to install the main packages manually instead of using `requirements.txt`, use:

```bash
pip install PySide6
pip install faster-whisper
pip install ctranslate2
pip install python-docx
pip install numpy
```

If your application includes microphone recording, also install the audio input package used by the source code.

Example:

```bash
pip install sounddevice
```

Only install packages that are actually used in your project source files.

---

## How to Run the Application

Run the application from the project root directory.

### If the main entry file is `main.py`

```bash
python main.py
```

### If the project uses another launcher
Replace `main.py` with the actual startup file used by the application.

Examples:

```bash
python app.py
```

or

```bash
python MeetingTranscriber.py
```

Use the real entry point defined by the project source.

---

## Application Workflow

A typical user workflow is:

1. Launch the application.
2. Choose an input method:
   - upload an audio file, or
   - record from the microphone.
3. Start transcription.
4. Wait for the transcript generation process to complete.
5. Apply glossary-based correction if configured.
6. Generate the structured meeting summary.
7. Review the transcript and summary output.
8. Export the result as a **DOCX** document.

---

## Input and Output

### Supported Input Formats
Depending on the final implementation, the application may support common audio formats such as:

- WAV
- MP3
- M4A
- OGG
- WEBM

### Output Types
- Transcript text
- Structured meeting summary
- Exported **DOCX** file

---

## Model and Runtime Notes

### Speech Model
The project uses **faster-whisper** for transcription.

### Inference Backend
The project uses **ctranslate2** as the inference backend.

### Audio Decoding
The project uses **ffmpeg** for audio decoding and conversion.

### Language Handling
The application is intended to handle **Arabic / English mixed speech**, which is important in real meeting environments where code-switching is common.

### Model Selection
If the project uses a fixed model, document it explicitly here. Typical examples might include:

- `large-v3`
- `faster-distil-whisper-large-v3`
- another model selected in the source code or settings

If your project stores model files in a custom cache directory, document that path here as well.

---

## Offline / Local Execution Notes

This application is designed to run **locally** on the target Windows machine.

That means:
- the desktop UI runs on the user device,
- transcription is performed locally using the installed runtime and model files,
- exported results are saved locally,
- internet access is not required for the core application flow after setup, unless your specific implementation downloads models dynamically on first use.

If your build requires model download on first launch, mention that clearly in the final repository version.

---

## Building an Executable with PyInstaller

If the project includes a specification file such as `MeetingTranscriber.spec`, build the executable from the project root:

```bash
python -m PyInstaller --noconfirm --clean MeetingTranscriber.spec
```

### Typical Output Location
After a successful build, the executable is usually generated inside:

```text
dist/
```

### Clean Rebuild Example
If you want to remove previous build folders first:

```bash
rmdir /S /Q build
rmdir /S /Q dist
python -m PyInstaller --noconfirm --clean MeetingTranscriber.spec
```

Use this from **Command Prompt** on Windows.

---

## Suggested Project Structure

The exact structure depends on the repository, but a typical layout may look like this:

```text
ALSA-meeting-transcriber/
├── assets/
├── dist/
├── build/
├── output/
├── .venv/
├── requirements.txt
├── MeetingTranscriber.spec
├── main.py
└── README.md
```

Adjust this section to match the real repository structure.

---

## Troubleshooting

### Python is not recognized
Cause:
- Python was not added to `PATH`

Fix:
- reinstall Python and enable **Add Python to PATH**, or
- add Python manually to Windows environment variables

Check again:

```bash
python --version
```

---

### pip is not recognized
Cause:
- Python installation is incomplete or PATH is not configured correctly

Fix:

```bash
python -m ensurepip --upgrade
python -m pip --version
```

---

### ffmpeg is not recognized
Cause:
- ffmpeg is not added to `PATH`

Fix:
- add the folder containing `ffmpeg.exe` to `PATH`
- close and reopen the terminal
- verify again:

```bash
ffmpeg -version
```

---

### PowerShell blocks virtual environment activation
Cause:
- execution policy restrictions

Fix:

```bash
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then reactivate:

```bash
.venv\Scripts\Activate.ps1
```

---

### `pip install -r requirements.txt` fails
Try:

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

If a specific package fails, install it separately to inspect the exact error.

---

### The application opens but transcription does not start
Check the following:
- ffmpeg is installed correctly
- required model files are available
- the selected audio file format is supported
- microphone permission is enabled if recording is used
- the environment contains all required Python packages

---

### Building the EXE fails
Check the following:
- `PyInstaller` is installed
- the `.spec` file exists and is valid
- all imported files and assets are included correctly
- the virtual environment is active during the build command

Install PyInstaller if needed:

```bash
pip install pyinstaller
```

---

## Recommended `requirements.txt`

If your repository does not yet contain a complete dependency file, create one based on the actual imports used in the code.

A minimal example might look like this:

```txt
PySide6
faster-whisper
ctranslate2
python-docx
numpy
pyinstaller
```

If microphone recording is implemented, add the actual audio package used by the application.

Example:

```txt
sounddevice
```

Do not keep unused packages in the final `requirements.txt`.

---

## Pre-Submission Checklist

Before submitting the project or sharing it publicly, verify the following:

- `requirements.txt` is complete and accurate
- the exact startup file name is documented
- the exact transcription model name is documented
- the demo video link is added
- the build command works from a clean environment
- ffmpeg setup instructions are correct
- screenshots are added if needed
- output export is tested successfully

---

## License

Add the project license here if required.

Example:

```text
MIT License
```

or replace it with the license used by your repository.

---

## Author

**Alaa Kasem**
