#!/bin/bash

echo "🧪 Flash Sales Testing Suite"
echo "=============================="
echo ""

echo "1️⃣ Running migration..."
python -m db.migrate_flash_sales
echo ""

echo "2️⃣ Seeding test data..."
python -m db.seed_flash_sales
echo ""

echo "3️⃣ Running unit tests..."
pytest tests/flash_sales/ -v --tb=short
echo ""

echo "✅ Tests complete!"
echo ""
echo "🚀 Start the app with:"
echo "   flask --app src.app run"
echo ""
echo "🌐 Then visit:"
echo "   http://127.0.0.1:5000/flash/products"