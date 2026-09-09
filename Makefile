.PHONY: load ratios test report dashboard api clean

load:
	uv run python src/etl/loader.py

ratios:
	uv run python src/analytics/ratios.py

test:
	uv run pytest tests --html=reports/pytest_report.html --self-contained-html

report:
	uv run python src/reports/generate_all.py

dashboard:
	uv run streamlit run src/dashboard/app.py

api:
	uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000

clean:
	uv run python scripts/clean.py
