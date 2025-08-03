.PHONY: install serve serve-prod build-frontend help

# Install dependencies
install:
	uv sync

# Start the development server
serve:
	uv run uvicorn src.server:get_app --reload --host 0.0.0.0 --port 8000 --factory

# Start the production server
serve-prod:
	uv run python src/server.py

# npm build and move to backend/ui
build-frontend:
	cd ../frontend && npm run build
	cp -r ../frontend/dist src/ui

# Help
help:
	@echo "Available commands:"
	@echo "  serve          - Start development server with auto-reload"
	@echo "  serve-prod     - Start production server"
	@echo "  install        - Install dependencies"
	@echo "  build-frontend - Build the frontend"
	@echo "  help           - Show this help message"
