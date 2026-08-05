"""
One-shot manual sync (testing only).
For production, run: python AdsManagement/service.py
"""
import os
import sys

GRATIFY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADS_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, GRATIFY_DIR)
sys.path.insert(0, ADS_DIR)

from service import sync_and_apply

if __name__ == "__main__":
    sync_and_apply()
