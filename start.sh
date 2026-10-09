#!/bin/bash
cd /root/clipgrab
source venv/bin/activate
exec uvicorn main:app --host 0.0.0.0 --port 9002
