#!/usr/bin/env python3
from build import ROOT, validate_output

if __name__ == "__main__":
    manifest = validate_output(ROOT)
    print(f"Static validation passed: {manifest['build_id']}")
    print("Still requires compilation and functional testing in Shadowrocket on iOS.")
