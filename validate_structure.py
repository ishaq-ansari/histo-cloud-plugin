#!/usr/bin/env python3
"""
Validate tf_keras module structure (no TensorFlow required)
"""
import os
import sys

print("Checking tf_keras module structure...")
print("=" * 60)

# Check if tf_keras directory exists
tf_keras_dir = os.path.join(os.path.dirname(__file__), 'tf_keras')
if not os.path.isdir(tf_keras_dir):
    print("✗ tf_keras directory not found!")
    sys.exit(1)
print(f"✓ tf_keras directory exists: {tf_keras_dir}")

# Check __init__.py
init_file = os.path.join(tf_keras_dir, '__init__.py')
if not os.path.isfile(init_file):
    print("✗ tf_keras/__init__.py not found!")
    sys.exit(1)
print(f"✓ tf_keras/__init__.py exists")

# Check legacy_tf_layers package
legacy_dir = os.path.join(tf_keras_dir, 'legacy_tf_layers')
if not os.path.isdir(legacy_dir):
    print("✗ tf_keras/legacy_tf_layers/ directory not found!")
    sys.exit(1)
print(f"✓ tf_keras/legacy_tf_layers/ directory exists")

# Check legacy_tf_layers/__init__.py
legacy_init = os.path.join(legacy_dir, '__init__.py')
if not os.path.isfile(legacy_init):
    print("✗ tf_keras/legacy_tf_layers/__init__.py not found!")
    sys.exit(1)
print(f"✓ tf_keras/legacy_tf_layers/__init__.py exists")

# Read and check __init__.py content
with open(init_file, 'r') as f:
    init_content = f.read()
    
print("\nChecking __init__.py content...")
if 'tensorflow' in init_content.lower():
    print("✓ __init__.py references tensorflow")
else:
    print("⚠ __init__.py doesn't reference tensorflow")

# Read and check legacy_tf_layers/__init__.py content
with open(legacy_init, 'r') as f:
    legacy_content = f.read()

print("\nChecking legacy_tf_layers/__init__.py content...")
required_modules = ['normalization', 'convolutional', 'core']
all_found = True
for mod in required_modules:
    if mod in legacy_content:
        print(f"✓ {mod} module is referenced")
    else:
        print(f"✗ {mod} module is NOT referenced")
        all_found = False

if not all_found:
    print("\n✗ Some required imports are missing!")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All structural checks passed!")
print("\nThe tf_keras module structure is correct.")
print("It will be included when Docker builds via 'COPY . $htk_path'")
print("and installed via 'pip install .' (setup.py's find_packages()).")
print("\n" + "=" * 60)
print("\nREADY TO BUILD DOCKER IMAGE!")
print("Run: ./build_docker.sh or docker build -t yourimage .")
