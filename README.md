# RING RING!

A minimal Werkzeug webapp which uses Jinja2 templates. To run it locally:

1. Create a virtual environment (optional but recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate
   ```
2. Install dependencies:
   ```powershell
   pip install werkzeug jinja2
   ```
3. Start the development server:
   ```powershell
   python app.py
   ```
4. Open **http://localhost:5000** in your browser.

The `BASE_URL` in `app.py` is set to `""` for local development. Adjust as
needed for deployment.
