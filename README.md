# Colorado CareAssist Route Tracker

A full-stack web application for Colorado CareAssist that automatically parses MyWay route PDFs and appends visit data to a shared Google Sheet.

## Features

- **PDF Upload**: Drag-and-drop interface for uploading MyWay route PDFs
- **Automatic Parsing**: Extracts stop numbers, business names, addresses, cities, and notes
- **Smart Business Name Inference**: Uses known healthcare facility databases and heuristics
- **Google Sheets Integration**: Automatically appends parsed data to the shared tracker
- **Responsive Design**: Works on desktop and mobile devices
- **Error Handling**: Comprehensive validation and user feedback

## Tech Stack

- **Backend**: Python FastAPI
- **PDF Parsing**: pdfplumber
- **Google Sheets**: gspread with service account authentication
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)
- **Hosting**: Heroku (auto-deploy from GitHub)

## Setup Instructions

### 1. Google Sheets Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Sheets API
4. Create a Service Account:
   - Go to IAM & Admin → Service Accounts
   - Click "Create Service Account"
   - Name: "careassist-sheets-access"
   - Click "Create and Continue"
   - Skip role assignment, click "Done"
5. Generate Service Account Key:
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" → "Create new key"
   - Choose JSON format
   - Download the JSON file

### 2. Google Sheet Permissions

1. Open the target Google Sheet: https://docs.google.com/spreadsheets/d/1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg/edit
2. Click "Share" button
3. Add the service account email (from the JSON file) with "Editor" permissions
4. The email format is: `your-service-account@your-project.iam.gserviceaccount.com`

### 3. Environment Variables

Set these environment variables in your deployment platform:

```bash
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account",...}  # Full JSON from step 1
SHEET_ID=1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg
APP_SECRET_KEY=your-random-secret-key
```

### 4. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_SERVICE_ACCOUNT_KEY='{"type":"service_account",...}'
export SHEET_ID=1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg
export APP_SECRET_KEY=your-secret-key

# Run the application
uvicorn app:app --reload
```

### 5. Deploy to Heroku

1. **Install Heroku CLI** (if not already installed):
   ```bash
   # macOS
   brew install heroku/brew/heroku
   
   # Or download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Login to Heroku**:
   ```bash
   heroku login
   ```

3. **Create Heroku App**:
   ```bash
   heroku create colorado-careassist-route-tracker
   ```

4. **Set Environment Variables**:
   ```bash
   heroku config:set GOOGLE_SERVICE_ACCOUNT_KEY='{"type":"service_account","project_id":"your-project",...}'
   heroku config:set SHEET_ID=1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg
   heroku config:set APP_SECRET_KEY=your-random-secret-key
   ```

5. **Deploy**:
   ```bash
   git add .
   git commit -m "Initial deployment"
   git push heroku main
   ```

6. **Open App**:
   ```bash
   heroku open
   ```

**Alternative: GitHub Integration**
1. Push code to GitHub repository
2. Go to Heroku Dashboard → Create New App
3. Connect GitHub repository
4. Enable automatic deploys from main branch
5. Add environment variables in Settings → Config Vars
6. Deploy!

## Usage

1. **Upload PDF**: Click "Choose PDF File" or drag-and-drop a MyWay route PDF
2. **Review Results**: The app will parse and display extracted visits in a table
3. **Append to Tracker**: Click "Append to Tracker" to add visits to the Google Sheet
4. **Success**: You'll see a confirmation message when data is successfully added

## File Structure

```
/app
├── app.py                 # FastAPI main application
├── parser.py              # PDF parsing logic
├── google_sheets.py       # Google Sheets integration
├── templates/
│   └── index.html         # Frontend interface
├── requirements.txt       # Python dependencies
├── Procfile              # Heroku deployment config
├── runtime.txt           # Python version specification
└── env.example           # Environment variables template
```

## API Endpoints

- `GET /` - Main upload interface
- `POST /upload` - Upload and parse PDF file
- `POST /append-to-sheet` - Append visits to Google Sheet
- `GET /health` - Health check endpoint

## Data Format

The app extracts visits in this format:

| Stop | Business Name | Location | City | Notes |
|------|---------------|----------|------|-------|
| 1 | UCHealth Memorial Hospital Central | 1400 E Boulder St | Colorado Springs | Met discharge planner |
| 2 | Pikes Peak Hospice | 2550 Tenderfoot Hill St | Colorado Springs | Great visit |

## Known Healthcare Facilities

The parser recognizes these Colorado Springs area facilities:
- UCHealth Memorial Hospital Central
- Pikes Peak Hospice
- The Independence Center
- Penrose Hospital
- Centura Health facilities
- VA Medical Center
- And many more...

## Troubleshooting

### Common Issues

1. **"Google Sheets not initialized"**
   - Check `GOOGLE_SERVICE_ACCOUNT_KEY` environment variable
   - Verify service account has access to the sheet

2. **"No visits found in PDF"**
   - Ensure PDF contains recognizable stop numbers and addresses
   - Check that PDF is not password-protected

3. **"Failed to append visits"**
   - Verify sheet permissions for service account
   - Check that "Visits" tab exists in the sheet

### Support

For technical support, contact the development team or create an issue in the repository.

## License

This project is proprietary to Colorado CareAssist.
