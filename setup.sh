#!/bin/bash

set -e

echo "=================================="
echo "  cp-gpre setup"
echo "=================================="
echo ""

# 1. Check Ollama
if ! command -v ollama &> /dev/null; then
    echo "❌  Ollama not installed."
    echo "    Get it from: https://ollama.com"
    exit 1
fi
echo "✓  Ollama found: $(ollama --version)"

# 2. Ensure Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "   Starting Ollama in the background..."
    ollama serve &>/dev/null &
    sleep 3
fi
echo "✓  Ollama is running"

# 3. Pull base models (~9 GB total)
echo ""
echo "Pulling base models (this may take a while)..."
ollama pull deepseek-r1:7b
ollama pull qwen2.5-coder:7b
echo "✓  Base models pulled"

# 4. Build custom models with system prompts
echo ""
echo "Building cp-math and cp-code..."
ollama create cp-math -f core/math.Modelfile
ollama create cp-code -f core/code.Modelfile
echo "✓  Custom models built"

# 5. Verify
echo ""
echo "Registered models:"
ollama list | grep -E "cp-math|cp-code" || echo "  (none matched — check Modelfiles)"

echo ""
echo "=================================="
echo "  Setup complete."
echo "=================================="
echo ""
echo "Quick start:"
echo "  python core/localModel.py --only dijkstra          # test one topic"
echo "  python core/localModel.py --category Strings       # test one category"
echo "  python core/localModel.py                          # full run (~4 hrs)"
echo ""
echo "After the run:"
echo "  python core/inspect.py stats"
echo "  python core/inspect.py show dijkstra"
echo "  python core/inspect.py failed"
echo "  python core/retry_failed.py"
