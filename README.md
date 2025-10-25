# Colorado CareAssist Sales Tracker

A full-stack web application for tracking sales visits, business card scanning, and financial data for Colorado CareAssist.

## Features

- **Dashboard**: Real-time analytics with visits, hours tracked, and closed sales
- **PDF Upload**: Upload MyWay route PDFs to automatically parse visit data
- **Business Card Scanner**: Upload business card images (JPEG, PNG, HEIC) with OCR extraction
- **Mailchimp Integration**: Automatically export scanned contacts to Mailchimp
- **Visits Tracking**: View all sales visits with filtering and search
- **Closed Sales**: Track closed deals with commission and bonus data
- **Financial Data**: Import and manage financial records
- **Google Sheets Sync**: Append visit data to shared Google Sheets

## Tech Stack

- **Backend**: Python FastAPI
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **PDF Parsing**: pdfplumber
- **OCR**: pytesseract (Tesseract OCR)
- **Image Processing**: Pillow with pillow-heif for HEIC support
- **Google Sheets**: gspread with service account authentication
- **Mailchimp**: REST API integration
- **Frontend**: HTML5, CSS3, JavaScript (vanilla), Chart.js
- **Hosting**: Heroku

## Setup Instructions

### 1. Environment Variables

Copy `env.example` to `.env` and fill in:

```bash
# Database
DATABASE_URL=postgresql://...

# Google Sheets
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account",...}
SHEET_ID=your-sheet-id

# App Configuration
APP_SECRET_KEY=your-random-secret-key

# Mailchimp (optional)
MAILCHIMP_API_KEY=your-api-key
MAILCHIMP_SERVER_PREFIX=us1
MAILCHIMP_LIST_ID=your-list-id
```

### 2. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app:app --reload
```

### 3. Deploy to Heroku

```bash
# Create app
heroku create your-app-name

# Add buildpacks
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-apt
heroku buildpacks:add heroku/python

# Set environment variables
heroku config:set DATABASE_URL=postgresql://...
heroku config:set APP_SECRET_KEY=your-secret-key
# ... etc

# Deploy
git push heroku main
```

## Usage

- **Dashboard**: View analytics and summaries
- **Upload**: Upload MyWay PDFs or business card images
- **Visits**: Browse and filter all recorded visits
- **Closed Sales**: Track closed deals and commissions

## License

This project is proprietary to Colorado CareAssist.
