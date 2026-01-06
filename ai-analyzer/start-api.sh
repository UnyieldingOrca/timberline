#!/bin/bash
set -e

# Use Python startup script for proper logging configuration
exec python start_server.py
