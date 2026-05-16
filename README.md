# Frame Window Extrema Service

Browser-based tool for uploading a text file with one numeric value per line, selecting a frame, extracting local extrema, analyzing amplitude-difference rows `A[i + 2^k] - A[i]`, and plotting the resulting per-`k` and aggregate charts.

## Features

- Upload `.txt` with one number per line
- Select a fixed frame by size and frame number
- Or override with a manual observation range
- Plateau-aware extrema detection:
  - odd plateau length -> middle point
  - even plateau length -> left-middle point
- Per-`k` analysis for:
  - signed amplitude difference
  - absolute amplitude difference
  - amplitude series itself
- Final aggregate chart by grouped interval durations
- JSON export

## Local Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
PORT=8126 python serve.py
```

Then open `http://127.0.0.1:8126/`.
