# Quick Start Guide: CRM Bulk Import System

## 🎯 For Portfolio Viewers

This is a **production-ready system** for automated HubSpot data migration. Below are instructions for both demo and actual usage.

---

## 📦 Installation (5 minutes)

### Step 1: Prerequisites
```bash
# Ensure Python 3.8+ is installed
python --version

# Should output: Python 3.8.x or higher
```

### Step 2: Install Dependencies
```bash
cd crm-bulk-import
pip install -r requirements.txt
```

That's it! The system is ready to use.

---

## 🚀 Usage Options

### Option A: Demo Mode (No API Key Needed)

Perfect for **testing** or **portfolio demonstrations**.

```bash
# Run with sample data
python main.py --demo

# Customize success rate (0.0-1.0)
python main.py --demo --success-rate 0.98

# Enable verbose output for debugging
python main.py --demo --verbose
```

**What happens in demo mode?**
- Validates your CSV data (real validation)
- Simulates API calls (no actual HubSpot connection)
- Generates realistic success/error reports
- Shows exact same flow as production

**Output:**
```
============================================================
📊 IMPORT SUMMARY
============================================================

⏱️  Duration: 3.19 seconds
📦 Total Processed: 292
✅ Successful: 277
❌ Failed: 15
📈 Success Rate: 94.86%

📄 Report saved: output/reports/import_report_20241120_132907.json
📄 Summary saved: output/reports/import_summary_20241120_132907.txt
```

### Option B: Production Mode (Requires HubSpot API Key)

For **actual imports** to your HubSpot account.

#### Step 1: Get Your API Key

1. Log into HubSpot
2. Go to Settings → Integrations → Private Apps
3. Create a new Private App
4. Grant permissions:
   - ✅ CRM: Read & Write (companies, contacts, tickets)
   - ✅ Associations: Read & Write
5. Generate API key

#### Step 2: Set Environment Variable

```bash
# On macOS/Linux
export HUBSPOT_API_KEY="your-api-key-here"

# On Windows (PowerShell)
$env:HUBSPOT_API_KEY="your-api-key-here"
```

#### Step 3: Run Import

```bash
python main.py
```

**Safety Features:**
- ✅ Validates data before any API calls
- ✅ Test connection before import
- ✅ Automatic retry on errors
- ✅ Detailed error logging
- ✅ Rollback not needed (creates new records)

---

## 📊 Understanding the Output

### Console Output

The system provides real-time progress updates:

```
🎯 Running in PRODUCTION MODE

============================================================
STEP 1: LOADING & VALIDATING DATA
============================================================
✓ Loaded 48 rows from companies.csv
✓ Loaded 80 rows from contacts.csv
✓ Loaded 165 rows from tickets.csv

Data Quality Assessment:
  Companies: 67.33% complete (48 rows, 14 columns)
  Contacts: 100.0% complete (80 rows, 11 columns)
  Tickets: 79.34% complete (165 rows, 11 columns)

============================================================
STEP 2: IMPORTING COMPANIES
============================================================
Prepared 48 companies for import
  Processing batch 1/1 (48 records)...
  ✓ Successfully created 48 companies
✓ Stored 48 company mappings for associations

...
```

### Generated Reports

Two types of reports are saved in `output/reports/`:

#### 1. JSON Report (`import_report_TIMESTAMP.json`)
```json
{
  "start_time": "2025-11-20T13:29:07.123456",
  "end_time": "2025-11-20T13:29:10.234567",
  "duration_seconds": 3.19,
  "objects": {
    "companies": {
      "total_processed": 48,
      "successful": 46,
      "failed": 2,
      "success_rate": 95.83
    },
    ...
  },
  "totals": {
    "total_processed": 292,
    "total_successful": 288,
    "overall_success_rate": 98.63
  }
}
```

#### 2. Text Summary (`import_summary_TIMESTAMP.txt`)
```
============================================================
CRM BULK IMPORT SUMMARY
============================================================

Start Time: 2025-11-20T13:29:07
End Time: 2025-11-20T13:29:10
Duration: 3.19 seconds

RESULTS BY OBJECT TYPE:
------------------------------------------------------------

COMPANIES:
  Total Processed: 48
  Successful: 46
  Failed: 2
  Success Rate: 95.83%

...
```

---

## 📁 Data Requirements

### CSV File Structure

Place your CSV files in the `data/` directory:

#### companies.csv
```csv
name,domain,industry,country,phone,numberofemployees,annualrevenue
Acme Corp,acme.com,Software,USA,+11234567890,500,50000000
```

**Required fields:**
- `name` (company name)

**Optional fields:**
- domain, industry, city, state, country, phone, numberofemployees, annualrevenue, lifecyclestage

#### contacts.csv
```csv
email,firstname,lastname,phone,company,jobtitle,lifecyclestage
john@acme.com,John,Doe,+11234567890,Acme Corp,Manager,customer
```

**Required fields:**
- `email` (must be valid format)

**Optional fields:**
- firstname, lastname, phone, company, jobtitle, lifecyclestage, hs_lead_status

#### tickets.csv
```csv
subject,content,hs_ticket_priority,hs_pipeline_stage,source_type
Bug Report,User john@acme.com reported issue,HIGH,1,EMAIL
```

**Required fields:**
- `subject` (ticket title)

**Optional fields:**
- content, hs_ticket_priority, hs_pipeline_stage, hs_ticket_category, source_type

**Pro Tip**: The system automatically extracts emails and phone numbers from the `content` field to create associations with contacts!

---

## 🔧 Configuration

### Basic Configuration

Edit `config.py` to customize:

```python
# Batch sizes (max 100 per HubSpot)
BATCH_SIZE_COMPANIES = 100
BATCH_SIZE_CONTACTS = 100
BATCH_SIZE_TICKETS = 100

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
EXPONENTIAL_BACKOFF = True

# Rate limiting
RATE_LIMIT_REQUESTS_PER_SECOND = 10  # HubSpot limit
```

### Advanced Configuration

**Custom property mapping:**

```python
# In config.py
CONTACT_PROPERTY_MAPPING = {
    "email": "email",
    "firstname": "firstname",
    "my_custom_field": "custom_field_name"  # Maps to HubSpot custom property
}
```

---

## ❓ Troubleshooting

### Common Issues

#### Issue: "HUBSPOT_API_KEY environment variable not set"

**Solution:**
```bash
# Check if set
echo $HUBSPOT_API_KEY

# If empty, set it
export HUBSPOT_API_KEY="your-key"
```

#### Issue: "API connection failed"

**Possible causes:**
1. Invalid API key → Check HubSpot settings
2. Insufficient permissions → Grant CRM read/write access
3. Network issues → Check internet connection

**Debug:**
```bash
python main.py --demo --verbose  # Test without API
```

#### Issue: "Missing required fields"

**Solution:** Ensure CSV has required columns:
- Companies: `name`
- Contacts: `email`
- Tickets: `subject`

#### Issue: High error rate (>5%)

**Common causes:**
1. Invalid email formats
2. Duplicate records
3. Missing associations

**Solution:** Check generated error report in `output/reports/`

---

## 📈 Success Metrics

### Expected Performance

| Metric | Target | Your Results |
|--------|--------|--------------|
| Success Rate | >95% | Run to see |
| Processing Speed | ~100 rec/sec | Run to see |
| Association Rate | >90% | Run to see |
| Error Recovery | <1% permanent failures | Run to see |

### What Makes a Good Import?

✅ **Great** (95-100% success):
- Well-formatted data
- Valid emails/phones
- Correct associations
- Clean source data

⚠️ **Good** (85-95% success):
- Some validation errors
- Missing optional fields
- Partial associations

❌ **Needs Work** (<85% success):
- Check data quality
- Validate formats
- Review error logs

---

## 🎓 For Technical Reviewers

### Architecture Highlights

1. **Modular Design**
   - Separation of concerns (validation, mapping, import, reporting)
   - Easy to test individual components
   - Extensible for new object types

2. **Production-Ready Features**
   - Comprehensive error handling
   - Retry logic with exponential backoff
   - Rate limiting compliance
   - Detailed logging and reporting

3. **Smart Automation**
   - Automatic email/phone extraction
   - Intelligent column mapping
   - Association creation
   - Data quality scoring

### Code Quality

- ✅ Type hints for clarity
- ✅ Docstrings for all functions
- ✅ Logging for debugging
- ✅ Error categorization
- ✅ Configuration separation
- ✅ Demo mode for testing

### Testing

```bash
# Run demo mode to test without API
python main.py --demo

# Test with verbose output
python main.py --demo --verbose

# Run individual components
cd src
python data_validator.py  # Test validator
python hubspot_client.py  # Test client
```

---

## 📞 Need Help?

For questions or support regarding this system:

**Documentation:**
- See `README.md` for complete documentation
- See `docs/TECHNICAL_ARTICLE.md` for deep dive
- Check `output/reports/` for error details

**Contact:**
- Author: Khadi97 - WBSE
- Specialization: AI-Driven CRM Automation

---

## ⚖️ License & Usage

This is a portfolio project demonstrating professional CRM automation capabilities.

**Allowed:**
- ✅ Use for your own HubSpot imports
- ✅ Study the code for learning
- ✅ Reference in technical discussions

**Attribution:**
Please credit when sharing or adapting this work.

---

*Happy importing! 🚀*
