#!/bin/bash

echo "🚀 Deploying to Render.com..."

# Check if render CLI is installed
if ! command -v render &> /dev/null; then
    echo "❌ Render CLI not found. Please install it first:"
    echo "   brew install render"
    echo "   Or visit: https://render.com/docs/using-render-cli"
    exit 1
fi

# Check if we're logged in
if ! render whoami &> /dev/null; then
    echo "❌ Not logged in to Render. Please run:"
    echo "   render login"
    exit 1
fi

echo "✅ Render CLI ready"

# Create new service
echo "📦 Creating new Render service..."
render new --type web --name contemplation-flow --env python --plan starter

echo "✅ Service created!"
echo ""
echo "🔧 Next steps:"
echo "1. Go to https://dashboard.render.com"
echo "2. Find your 'contemplation-flow' service"
echo "3. Set these environment variables:"
echo "   - ASAM_DB_URL (your Supabase connection string)"
echo "   - ASAM_JWT_SECRET (your JWT secret)"
echo "   - ASAM_OPENAI_TOKEN (your OpenAI API key)"
echo "   - ASAM_SUPABASE_URL (your Supabase URL)"
echo "   - ASAM_SUPABASE_KEY (your Supabase key)"
echo "4. Deploy!"
echo ""
echo "🌐 Your app will be available at: https://contemplation-flow.onrender.com" 