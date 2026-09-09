.PHONY: load ratios test report dashboard api clean

load:
	uv run python -m src.etl.loader

ratios:
	uv run python -m src.analytics.ratios

test:
	uv run pytest tests --html=reports/pytest_report.html --self-contained-html

report:
	uv run python -m src.reports.generate_all

dashboard:
	uv run streamlit run src/dashboard/app.py

api:
	uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000

clean:
	uv run python scripts/clean.py
