"""
Shim to properly map tf_keras.legacy_tf_layers.normalization to TF1-compatible layers.
"""
import tensorflow as tf

# Use tf.compat.v1.layers which provides TF1-compatible batch normalization
# that properly handles variable scopes
BatchNormalization = tf.compat.v1.layers.BatchNormalization
batch_normalization = tf.compat.v1.layers.batch_normalization

__all__ = ['BatchNormalization', 'batch_normalization']
