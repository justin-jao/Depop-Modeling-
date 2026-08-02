# Listing Metrics Calculator

Calculates listing volume, estimated revenue, and margin metrics for a search
query using eBay listing data.

## Workflow

1. **Collect listing data (`listing_volume.py` or `listing_volume_sqlite.py`)**
	Pulls listing-level pricing and volume signals.
2. **Apply user cost inputs**
	Prompts for piece cost and computes gross-margin estimates.
3. **Report metrics**
	Prints summary outputs for quick buying/reselling decisions.

## Getting Started

### 1. Create a virtual environment

macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r calculating-metrics/requirements.txt
```

### 3. Run the calculator

```bash
python calculating-metrics/listing_volume.py
```

Or use the SQLite-backed variant:

```bash
python calculating-metrics/listing_volume_sqlite.py
```

## Notes

- Both scripts prompt for interactive query and cost inputs.
- Use the SQLite version when you want persistent local metric snapshots.
