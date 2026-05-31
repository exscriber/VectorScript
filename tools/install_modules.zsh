#!/bin/zsh

VW_VER=2024
PY_VER=3.9
PY_MODULES=(numpy scipy geopy shapely debugpy)

VW_PYTHON_PATH="$HOME/Library/Application Support/Vectorworks/$VW_VER/Python Externals"
uv pip install $PY_MODULES $NO_BINARY --target $VW_PYTHON_PATH --python $PY_VER
