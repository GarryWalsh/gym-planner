param(
  [string]$Address = "127.0.0.1",
  [int]$Port = 8501,
  [switch]$Headless
)

$headlessArg = @()
if ($Headless) { $headlessArg = @("--server.headless", "true") }

# Streamlit picks up .env via app code (pydantic-settings)
python -m streamlit run "app\streamlit_app.py" --server.address $Address --server.port $Port @headlessArg
