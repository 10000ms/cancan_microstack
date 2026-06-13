#!/bin/bash
# controllersrv 启动脚本

cd /Users/victor.lai/project/my_app_be

export NE_CONFIG=dev
export PYTHONPATH=/Users/victor.lai/project/my_app_be/src:/Users/victor.lai/project/my_app_be/src/libs:/Users/victor.lai/project/my_app_be/cmd

/Users/victor.lai/project/my_app_be/venv/bin/python cmd/controllersrv/run.py
