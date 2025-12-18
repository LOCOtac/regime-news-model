# Regime + News Model (Live API)

## Quick start
```bash
cd regime_news_model_api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Set API key (recommended)
```bash
export FMP_API_KEY="YOUR_KEY"
```

Or put it in `src/secrets_local.py` (not committed to git).

## Run
```bash
python run_pipeline.py --ticker NVDA --start 2015-01-01
```

### Offline mode
Uses cached price pickle if available:
```bash
python run_pipeline.py --ticker NVDA --offline
```

## Output
Prints:
- latest regime and regime probabilities
- 5d/20d forward return quantiles conditioned on current regime
- news score + risk flags + watchouts
