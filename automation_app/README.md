# Quiz Automation App (Tkinter + Selenium + Gemini)

This project includes:

- A desktop app built with Tkinter to run browser automation.
- Moodle-specific automation flow:
  - Log in with username/password.
  - Open quiz link.
  - Read question text + choices.
  - Ask Gemini model to select an answer.
  - Click Next page until Finish flow appears.
- A utility script to extract clean HTML from MHTML and remove CSS for easier inspection.

## Important

Use this only for systems and quizzes where you are authorized to run automation.

## 1) Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) (Optional) Strip CSS from your saved MHTML files

```powershell
python tools/mhtml_extract_clean_html.py "Log in to the site _ EBook.mhtml" "Chapter 2 (page 100 of 136) _ EBook.mhtml" --out-dir clean_html
```

Output files will be created in `clean_html` with `_clean.html` suffix.

## 3) Run the desktop app

```powershell
python -m automation_app.main
```

## 4) In the app, fill fields and start

- Login URL
- Quiz URL
- Username
- Password
- Gemini API key
- Gemini model (default: `gemini-3.1-flash-lite-preview`)
- Optional: headless mode
- Optional: keep browser open after completion

Then click **Start Automation**.

## Architecture

- `automation_app/core`: domain models and runtime config
- `automation_app/services`: browser/auth/quiz/Gemini/orchestration logic
- `automation_app/ui`: Tkinter UI
- `tools`: helper scripts (MHTML to clean HTML)
