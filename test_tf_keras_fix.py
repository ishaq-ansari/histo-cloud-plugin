#!/usr/bin/env python3
"""Test script to verify tf_keras.legacy_tf_layers module works correctly."""

import sys
import os

# Add current directory to path to test local tf_keras module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing tf_keras compatibility shim...")
print("-" * 60)

# Test 1: Import tf_keras
try:
    import tf_keras
    print("✓ Successfully imported tf_keras")
except Exception as e:
    print(f"✗ Failed to import tf_keras: {e}")
    sys.exit(1)

# Test 2: Import tf_keras.legacy_tf_layers (the critical one)
try:
    import tf_keras.legacy_tf_layers
    print("✓ Successfully imported tf_keras.legacy_tf_layers")
except Exception as e:
    print(f"✗ Failed to import tf_keras.legacy_tf_layers: {e}")
    sys.exit(1)

# Test 3: Check BatchNormalization exists
try:
    from tf_keras.legacy_tf_layers import BatchNormalization
    print(f"✓ Successfully imported BatchNormalization: {BatchNormalization}")
except Exception as e:
    print(f"✗ Failed to import BatchNormalization: {e}")
    sys.exit(1)

# Test 4: Simulate what TensorFlow does internally
try:
    import importlib
    module = importlib.import_module('tf_keras.legacy_tf_layers')
    print(f"✓ Module import via importlib works: {module}")
except Exception as e:
    print(f"✗ Module import via importlib failed: {e}")
    sys.exit(1)

# Test 5: Check if the module has expected attributes
try:
    assert hasattr(module, 'BatchNormalization')
    print("✓ Module has BatchNormalization attribute")
except AssertionError:
    print("✗ Module missing BatchNormalization attribute")
    sys.exit(1)

print("-" * 60)
print("All tests passed! ✓")
print("\nThe tf_keras compatibility shim is working correctly.")
print("You can now rebuild the Docker image with confidence.")
